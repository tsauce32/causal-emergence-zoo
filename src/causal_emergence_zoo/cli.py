"""Command-line interface for causal-emergence-zoo."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from causal_emergence_zoo.io import available_systems, load_system
from causal_emergence_zoo.validation import validate_system


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
    checked = 0

    if result.get("benchmark_id") not in (None, benchmark["id"]):
        failures.append(
            f"benchmark_id is {result.get('benchmark_id')!r}, expected {benchmark['id']!r}."
        )

    result_micro_metrics = result.get("microscale", {}).get("metrics", {})
    expected_micro_metrics = benchmark["microscale"]["metrics"]
    for key, expected in expected_micro_metrics.items():
        if key in result_micro_metrics:
            checked += 1
            actual = result_micro_metrics[key]
            if not _almost_equal(actual, expected, args.tolerance):
                failures.append(f"microscale.metrics.{key}: got {actual}, expected {expected}.")

    result_best = result.get("best_partition", {})
    expected_best = benchmark["emergent_hierarchy"]["best_partition"]
    if "partition_id" in result_best:
        checked += 1
        if result_best["partition_id"] != expected_best["partition_id"]:
            failures.append(
                "best_partition.partition_id: "
                f"got {result_best['partition_id']!r}, expected {expected_best['partition_id']!r}."
            )
    if "blocks" in result_best:
        checked += 1
        if result_best["blocks"] != expected_best["blocks"]:
            failures.append(
                "best_partition.blocks: "
                f"got {result_best['blocks']!r}, expected {expected_best['blocks']!r}."
            )
    if "deltaCP" in result_best:
        checked += 1
        actual = result_best["deltaCP"]
        expected = expected_best["deltaCP"]
        if not _almost_equal(actual, expected, args.tolerance):
            failures.append(f"best_partition.deltaCP: got {actual}, expected {expected}.")

    if checked == 0:
        failures.append("No comparable fields found. See schemas/implementation-result.schema.json.")

    if failures:
        print(f"FAIL {args.result_json} against {benchmark['id']}")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"PASS {args.result_json} against {benchmark['id']} ({checked} checks)")
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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
