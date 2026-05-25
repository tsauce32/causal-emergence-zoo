"""Command-line interface for causal-emergence-zoo."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from causal_emergence_zoo.io import available_systems, load_system
from causal_emergence_zoo.search import branching_greedy_search
from causal_emergence_zoo.validation import validate_system

COMPARISON_TIERS = {
    "exact",
    "equivalent_macro",
    "rank_agreement",
    "qualitative",
    "exploratory",
}


@dataclass
class ComparisonCounts:
    numeric: int = 0
    structural: int = 0

    @property
    def total(self) -> int:
        return self.numeric + self.structural

    def add(self, other: "ComparisonCounts") -> None:
        self.numeric += other.numeric
        self.structural += other.structural


def _blocks_label(blocks: list[list[int]]) -> str:
    return "[" + ", ".join("[" + ", ".join(str(state) for state in block) + "]" for block in blocks) + "]"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_target(target: str) -> tuple[str, dict[str, Any]]:
    path = Path(target)
    if path.exists():
        return str(path), _read_json(path)
    return target, load_system(target)


def _almost_equal(left: float, right: float, tolerance: float) -> bool:
    return abs(left - right) <= tolerance


def _implementation_result_schema() -> dict[str, Any]:
    schema = files("causal_emergence_zoo").joinpath("schemas/implementation-result.schema.json")
    return json.loads(schema.read_text(encoding="utf-8"))


def _validate_implementation_result(result: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(_implementation_result_schema())
    errors = []
    for error in sorted(validator.iter_errors(result), key=lambda item: list(item.path)):
        path = ".".join(str(part) for part in error.path) or "<root>"
        errors.append(f"Schema error at {path}: {error.message}")
    return errors


def _canonical_blocks(blocks: list[list[int]]) -> tuple[tuple[int, ...], ...]:
    return tuple(sorted(tuple(sorted(block)) for block in blocks))


def _partition_lookup(benchmark: dict[str, Any]) -> dict[tuple[tuple[int, ...], ...], dict[str, Any]]:
    return {
        _canonical_blocks(partition["blocks"]): partition
        for partition in benchmark.get("partitions", [])
    }


def _macro_maps_by_id(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        macro_map["id"]: macro_map
        for macro_map in result.get("macro_maps", [])
        if "id" in macro_map
    }


def _compare_number(
    failures: list[str],
    label: str,
    actual: float,
    expected: float,
    tolerance: float,
) -> ComparisonCounts:
    if not _almost_equal(actual, expected, tolerance):
        failures.append(f"{label}: got {actual}, expected {expected}.")
    return ComparisonCounts(numeric=1)


def _compare_legacy_exact(
    benchmark: dict[str, Any],
    result: dict[str, Any],
    failures: list[str],
    tolerance: float,
) -> ComparisonCounts:
    counts = ComparisonCounts()

    result_micro_metrics = result.get("microscale", {}).get("metrics", {})
    expected_micro_metrics = benchmark["microscale"]["metrics"]
    for key, expected in expected_micro_metrics.items():
        if key in result_micro_metrics:
            counts.add(_compare_number(
                failures,
                f"microscale.metrics.{key}",
                result_micro_metrics[key],
                expected,
                tolerance,
            ))

    result_best = result.get("best_partition", {})
    expected_best = benchmark["emergent_hierarchy"]["best_partition"]
    if "partition_id" in result_best:
        counts.structural += 1
        if result_best["partition_id"] != expected_best["partition_id"]:
            failures.append(
                "best_partition.partition_id: "
                f"got {result_best['partition_id']!r}, expected {expected_best['partition_id']!r}."
            )
    if "blocks" in result_best:
        counts.structural += 1
        if _canonical_blocks(result_best["blocks"]) != _canonical_blocks(expected_best["blocks"]):
            failures.append(
                "best_partition.blocks: "
                f"got {result_best['blocks']!r}, expected {expected_best['blocks']!r}."
            )
    if "deltaCP" in result_best:
        counts.add(_compare_number(
            failures,
            "best_partition.deltaCP",
            result_best["deltaCP"],
            expected_best["deltaCP"],
            tolerance,
        ))
    if "causal_power" in result_best:
        counts.add(_compare_number(
            failures,
            "best_partition.causal_power",
            result_best["causal_power"],
            expected_best["causal_power"],
            tolerance,
        ))

    return counts


def _compare_harmonized_exact(
    benchmark: dict[str, Any],
    result: dict[str, Any],
    failures: list[str],
    tolerance: float,
) -> ComparisonCounts:
    counts = ComparisonCounts()
    lookup = _partition_lookup(benchmark)
    maps_by_id = _macro_maps_by_id(result)

    for macro_map in result.get("macro_maps", []):
        if macro_map.get("map_type") != "partition" or "blocks" not in macro_map:
            continue
        counts.structural += 1
        if _canonical_blocks(macro_map["blocks"]) not in lookup:
            failures.append(f"macro_maps.{macro_map.get('id', '<unnamed>')} is not a valid partition.")

    for score_index, score in enumerate(result.get("scores", [])):
        if score.get("namespace") != "zoo.ce1":
            continue
        subject = score.get("subject")
        values = score.get("values", {})
        if subject in ("microscale", "micro", None):
            expected_values = benchmark["microscale"]["metrics"]
            expected_delta_cp = 0.0
        elif subject in maps_by_id:
            macro_map = maps_by_id[subject]
            if macro_map.get("map_type") != "partition" or "blocks" not in macro_map:
                failures.append(f"scores[{score_index}] subject {subject!r} is not a partition map.")
                continue
            partition = lookup.get(_canonical_blocks(macro_map["blocks"]))
            if partition is None:
                failures.append(f"scores[{score_index}] subject {subject!r} has no matching fixture partition.")
                continue
            expected_values = partition["metrics"]
            expected_delta_cp = partition["deltaCP"]
        else:
            failures.append(f"scores[{score_index}] subject {subject!r} does not reference a known macro map.")
            continue

        for key, actual in values.items():
            if key == "deltaCP":
                counts.add(_compare_number(
                    failures,
                    f"scores[{score_index}].values.deltaCP",
                    actual,
                    expected_delta_cp,
                    tolerance,
                ))
            elif key in expected_values:
                counts.add(_compare_number(
                    failures,
                    f"scores[{score_index}].values.{key}",
                    actual,
                    expected_values[key],
                    tolerance,
                ))
    return counts


def _compare_equivalent_macro(
    benchmark: dict[str, Any],
    result: dict[str, Any],
    failures: list[str],
) -> ComparisonCounts:
    expected = _canonical_blocks(benchmark["emergent_hierarchy"]["best_partition"]["blocks"])
    candidate_blocks = []
    if result.get("best_partition", {}).get("blocks"):
        candidate_blocks.append(result["best_partition"]["blocks"])
    candidate_blocks.extend(
        macro_map["blocks"]
        for macro_map in result.get("macro_maps", [])
        if macro_map.get("map_type") == "partition" and "blocks" in macro_map
    )

    for blocks in candidate_blocks:
        if _canonical_blocks(blocks) == expected:
            return ComparisonCounts(structural=1)

    failures.append("No reported partition macro map matches the expected best partition up to relabeling.")
    return ComparisonCounts(structural=1)


def _compare_rank_agreement(
    benchmark: dict[str, Any],
    result: dict[str, Any],
    failures: list[str],
) -> ComparisonCounts:
    expected_top = benchmark["emergent_hierarchy"]["levels"][0]["partition_id"]
    reported = result.get("ranked_partitions") or result.get("rankings", {}).get("partitions")
    if not reported:
        failures.append("rank_agreement requires ranked_partitions or rankings.partitions.")
        return ComparisonCounts(structural=1)
    first = reported[0]
    reported_top = first.get("partition_id") if isinstance(first, dict) else first
    if reported_top != expected_top:
        failures.append(f"Top ranked partition is {reported_top!r}, expected {expected_top!r}.")
    return ComparisonCounts(structural=1)


def _compare_qualitative(
    benchmark: dict[str, Any],
    result: dict[str, Any],
    failures: list[str],
) -> ComparisonCounts:
    expected_role = benchmark["conceptual_role"]
    reported_role = result.get("qualitative_role") or result.get("classification")
    if not reported_role:
        failures.append("qualitative comparison requires qualitative_role or classification.")
        return ComparisonCounts(structural=1)
    expected_terms = {term.strip().lower() for term in expected_role.replace("/", ",").split(",")}
    reported = str(reported_role).lower()
    if not any(term and term in reported for term in expected_terms):
        failures.append(f"Qualitative role {reported_role!r} does not match fixture role {expected_role!r}.")
    return ComparisonCounts(structural=1)


def list_systems(_: argparse.Namespace) -> int:
    print("system_id\tstates\tpartitions\trole")
    for system_id in available_systems():
        system = load_system(system_id)
        print(
            f"{system_id}\t{system['state_count']}\t"
            f"{len(system.get('partitions', []))}\t{system['conceptual_role']}"
        )
    return 0


def summarize_system(args: argparse.Namespace) -> int:
    system = load_system(args.system_id)
    micro = system["microscale"]["metrics"]
    best = system["emergent_hierarchy"]["best_partition"]
    print(f"{system['id']}: {system['name']}")
    print(f"role: {system['conceptual_role']}")
    print(f"states: {system['state_count']}")
    print(f"stored partitions: {len(system.get('partitions', []))}")
    print(f"microscale causal_power: {micro['causal_power']}")
    print(f"best partition: {best['partition_id']} {_blocks_label(best['blocks'])}")
    print(f"best deltaCP: {best['deltaCP']}")
    if args.notes:
        for note in system.get("notes", []):
            print(f"- {note}")
    return 0


def validate_targets(args: argparse.Namespace) -> int:
    status = 0
    for target in args.targets:
        label, system = _load_target(target)
        errors = validate_system(system, tolerance=args.tolerance)
        if errors:
            status = 1
            print(f"FAIL {label}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"PASS {label}")
    return status


def compare_result(args: argparse.Namespace) -> int:
    benchmark = load_system(args.system_id)
    result = _read_json(Path(args.result_json))
    failures: list[str] = []
    counts = ComparisonCounts()
    tier = result.get("comparison_tier", "exact")

    failures.extend(_validate_implementation_result(result))

    if result.get("benchmark_id") not in (None, benchmark["id"]):
        failures.append(
            f"benchmark_id is {result.get('benchmark_id')!r}, expected {benchmark['id']!r}."
        )

    if tier not in COMPARISON_TIERS:
        failures.append(f"comparison_tier is {tier!r}; expected one of {sorted(COMPARISON_TIERS)}.")
    elif tier == "exact":
        counts.add(_compare_legacy_exact(benchmark, result, failures, args.tolerance))
        counts.add(_compare_harmonized_exact(benchmark, result, failures, args.tolerance))
        if counts.numeric == 0:
            failures.append("Exact comparison requires at least one numeric value comparison.")
    elif tier == "equivalent_macro":
        counts.add(_compare_equivalent_macro(benchmark, result, failures))
    elif tier == "rank_agreement":
        counts.add(_compare_rank_agreement(benchmark, result, failures))
    elif tier == "qualitative":
        counts.add(_compare_qualitative(benchmark, result, failures))
    elif tier == "exploratory":
        counts.structural += 1

    if counts.total == 0:
        failures.append("No comparable fields found. See schemas/implementation-result.schema.json.")

    if failures:
        print(f"FAIL {args.result_json} against {benchmark['id']}")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(
        f"PASS {args.result_json} against {benchmark['id']} "
        f"({tier}, {counts.numeric} numeric, {counts.structural} structural checks)"
    )
    return 0


def greedy_search(args: argparse.Namespace) -> int:
    system = load_system(args.system_id)
    result = branching_greedy_search(
        system["microscale"]["tpm"],
        n_paths=args.paths,
        branching_factor=args.branching_factor,
        score_key=args.score_key,
        precision=args.precision,
    )

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    best = result["best_partition"]
    print(f"greedy search: {system['id']}")
    print(f"score key: {result['score_key']}")
    print(f"paths kept: {result['n_paths']}")
    print(f"branching factor: {result['branching_factor']}")
    print(f"sampled partitions: {result['sampled_partition_count']}")
    print(f"microscale causal_power: {result['microscale']['metrics']['causal_power']}")
    print(f"best sampled partition: {best['partition_id']} {_blocks_label(best['blocks'])}")
    print(f"best sampled causal_power: {best['metrics']['causal_power']}")
    print(f"best sampled deltaCP: {best['deltaCP']}")
    print("paths:")
    for index, path in enumerate(result["paths"], start=1):
        labels = " -> ".join(step["partition_id"] for step in path)
        print(f"  {index}. {labels}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cez",
        description="Inspect, validate, and compare causal-emergence-zoo benchmarks.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List available benchmark systems.")
    list_parser.set_defaults(func=list_systems)

    summarize_parser = subparsers.add_parser("summarize", help="Print a benchmark summary.")
    summarize_parser.add_argument("system_id")
    summarize_parser.add_argument("--notes", action="store_true", help="Include benchmark notes.")
    summarize_parser.set_defaults(func=summarize_system)

    validate_parser = subparsers.add_parser("validate", help="Validate benchmark fixtures by id or JSON path.")
    validate_parser.add_argument("targets", nargs="+")
    validate_parser.add_argument("--tolerance", type=float, default=1e-8)
    validate_parser.set_defaults(func=validate_targets)

    compare_parser = subparsers.add_parser("compare", help="Compare an implementation result JSON to a benchmark.")
    compare_parser.add_argument("system_id")
    compare_parser.add_argument("result_json")
    compare_parser.add_argument("--tolerance", type=float, default=1e-8)
    compare_parser.set_defaults(func=compare_result)

    greedy_parser = subparsers.add_parser("greedy", help="Run branching greedy partition search on a benchmark.")
    greedy_parser.add_argument("system_id")
    greedy_parser.add_argument("--paths", type=int, default=20, help="Maximum active paths to keep.")
    greedy_parser.add_argument("--branching-factor", type=int, default=2, help="Pairwise merges to keep per path.")
    greedy_parser.add_argument("--score-key", default="causal_power", help="Metric key to maximize.")
    greedy_parser.add_argument("--precision", type=int, default=None, help="Optional rounding precision.")
    greedy_parser.add_argument("--json", action="store_true", help="Print the full JSON search result.")
    greedy_parser.set_defaults(func=greedy_search)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
