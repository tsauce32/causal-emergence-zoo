"""Small dependency-free validation for benchmark fixtures."""

from __future__ import annotations

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
        if key in stored_metrics and abs(stored_metrics[key] - value) > tolerance:
            errors.append(f"Microscale metric {key} differs from recomputed value.")

    for item in system.get("partitions", []):
        partition = item.get("blocks", [])
        covered = sorted(state for block in partition for state in block)
        if covered != list(range(state_count)):
            errors.append(f"Partition {item.get('id')} does not cover all states exactly once.")
    return errors
