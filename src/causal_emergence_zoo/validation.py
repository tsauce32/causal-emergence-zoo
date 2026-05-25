"""Validation for benchmark fixtures."""

from __future__ import annotations

from typing import Any

from causal_emergence_zoo.coarse_grain import coarse_grain_tpm
from causal_emergence_zoo.metrics import compute_metrics


REQUIRED_TOP_LEVEL_KEYS = {
    "schema_version",
    "id",
    "name",
    "description",
    "conceptual_role",
    "state_count",
    "state_labels",
    "microscale",
    "partitions",
    "emergent_hierarchy",
    "provenance",
}


def _almost_equal(left: float, right: float, tolerance: float) -> bool:
    return abs(left - right) <= tolerance


def _compare_numbers(errors: list[str], label: str, actual: float | None, expected: float, tolerance: float) -> None:
    if actual is None:
        errors.append(f"{label} is missing.")
        return
    if not _almost_equal(actual, expected, tolerance):
        errors.append(f"{label} is {actual}, expected {expected}.")


def _compare_matrix(
    errors: list[str],
    label: str,
    actual: list[list[float]],
    expected: list[list[float]],
    tolerance: float,
) -> None:
    if len(actual) != len(expected):
        errors.append(f"{label} row count is {len(actual)}, expected {len(expected)}.")
        return
    for row_index, (actual_row, expected_row) in enumerate(zip(actual, expected)):
        if len(actual_row) != len(expected_row):
            errors.append(
                f"{label} row {row_index} length is {len(actual_row)}, expected {len(expected_row)}."
            )
            continue
        for col_index, (actual_value, expected_value) in enumerate(zip(actual_row, expected_row)):
            if not _almost_equal(actual_value, expected_value, tolerance):
                errors.append(
                    f"{label}[{row_index}][{col_index}] is {actual_value}, expected {expected_value}."
                )


def _partition_id(blocks: list[list[int]]) -> str:
    return "|".join("".join(str(state) for state in block) for block in blocks)


def validate_system(system: dict, tolerance: float = 1e-8) -> list[str]:
    """Return validation errors for a benchmark system.

    An empty list means the fixture passes the lightweight repository checks.
    """
    errors: list[str] = []
    missing = REQUIRED_TOP_LEVEL_KEYS - set(system)
    if missing:
        errors.append(f"Missing top-level keys: {sorted(missing)}")
        return errors

    state_count = system["state_count"]
    precision = system.get("provenance", {}).get("precision")
    if len(system["state_labels"]) != state_count:
        errors.append("state_labels length must equal state_count.")

    tpm = system["microscale"].get("tpm", [])
    try:
        recomputed = compute_metrics(tpm)
    except ValueError as exc:
        errors.append(str(exc))
        return errors

    stored_metrics = system["microscale"].get("metrics", {})
    for key, value in recomputed.items():
        if key not in stored_metrics:
            errors.append(f"Microscale metric {key} is missing.")
        else:
            _compare_numbers(errors, f"Microscale metric {key}", stored_metrics[key], value, tolerance)

    partitions = system.get("partitions", [])
    partition_ids: set[str] = set()
    partition_by_id: dict[str, dict[str, Any]] = {}

    for item in partitions:
        item_id = item.get("id")
        if not item_id:
            errors.append("A partition is missing id.")
            continue
        if item_id in partition_ids:
            errors.append(f"Partition id {item_id!r} is duplicated.")
        partition_ids.add(item_id)
        partition_by_id[item_id] = item

        partition = item.get("blocks", [])
        covered = sorted(state for block in partition for state in block)
        if covered != list(range(state_count)):
            errors.append(f"Partition {item_id} does not cover all states exactly once.")
            continue

        expected_id = _partition_id(partition)
        if item_id != expected_id:
            errors.append(f"Partition id {item_id!r} does not match canonical id {expected_id!r}.")

        macro_state_count = len(partition)
        if item.get("macro_state_count") != macro_state_count:
            errors.append(
                f"Partition {item_id} macro_state_count is {item.get('macro_state_count')}, "
                f"expected {macro_state_count}."
            )

        expected_macro_tpm = coarse_grain_tpm(tpm, partition, precision=precision)
        if "macro_tpm" not in item:
            errors.append(f"Partition {item_id} is missing macro_tpm.")
        else:
            _compare_matrix(errors, f"Partition {item_id} macro_tpm", item["macro_tpm"], expected_macro_tpm, tolerance)

        try:
            expected_metrics = compute_metrics(expected_macro_tpm)
        except ValueError as exc:
            errors.append(f"Partition {item_id} macro_tpm is invalid: {exc}")
            continue

        stored_partition_metrics = item.get("metrics", {})
        for key, value in expected_metrics.items():
            if key not in stored_partition_metrics:
                errors.append(f"Partition {item_id} metric {key} is missing.")
            else:
                _compare_numbers(
                    errors,
                    f"Partition {item_id} metric {key}",
                    stored_partition_metrics[key],
                    value,
                    tolerance,
                )

        expected_delta_cp = expected_metrics["causal_power"] - recomputed["causal_power"]
        if "deltaCP" not in item:
            errors.append(f"Partition {item_id} is missing deltaCP.")
        else:
            _compare_numbers(errors, f"Partition {item_id} deltaCP", item["deltaCP"], expected_delta_cp, tolerance)

    hierarchy = system.get("emergent_hierarchy", {})
    levels = hierarchy.get("levels", [])
    if levels:
        for previous, current in zip(levels, levels[1:]):
            if (previous["causal_power"], previous["macro_state_count"]) < (
                current["causal_power"],
                current["macro_state_count"],
            ):
                errors.append("Emergent hierarchy levels are not sorted by causal_power and macro_state_count.")
                break

        best = hierarchy.get("best_partition", {})
        top = levels[0]
        if best.get("partition_id") != top.get("partition_id"):
            errors.append("Best partition does not match the top-ranked hierarchy level.")
        top_partition = partition_by_id.get(top.get("partition_id"))
        if top_partition is None:
            errors.append(f"Top hierarchy partition {top.get('partition_id')!r} is not in partitions.")
        else:
            if best.get("blocks") != top_partition.get("blocks"):
                errors.append("Best partition blocks do not match the stored top-ranked partition.")
            _compare_numbers(
                errors,
                "Best partition causal_power",
                best.get("causal_power"),
                top_partition["metrics"]["causal_power"],
                tolerance,
            )
            _compare_numbers(
                errors,
                "Best partition deltaCP",
                best.get("deltaCP"),
                top_partition["deltaCP"],
                tolerance,
            )

        for level in levels:
            partition = partition_by_id.get(level.get("partition_id"))
            if partition is None:
                errors.append(f"Hierarchy level {level.get('partition_id')!r} is not in partitions.")
                continue
            if level.get("macro_state_count") != partition["macro_state_count"]:
                errors.append(f"Hierarchy level {level.get('partition_id')} has wrong macro_state_count.")
            _compare_numbers(
                errors,
                f"Hierarchy level {level.get('partition_id')} causal_power",
                level.get("causal_power"),
                partition["metrics"]["causal_power"],
                tolerance,
            )
            _compare_numbers(
                errors,
                f"Hierarchy level {level.get('partition_id')} deltaCP",
                level.get("deltaCP"),
                partition["deltaCP"],
                tolerance,
            )
    else:
        errors.append("Emergent hierarchy levels are missing.")

    return errors
