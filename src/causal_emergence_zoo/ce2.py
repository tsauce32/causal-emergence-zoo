"""A small, explicit implementation of the path-based core of Causal Emergence 2.0.

This module implements the finite-Markov-chain, hard-partition setting used in
Hoel's CE 2.0 paper.  It is intentionally conservative: it exhaustively searches
small systems, rejects dynamically inconsistent coarse grains, and exposes every
path-selection choice in its result.  It is not a substitute for the broader
CE 2.0 research programme (black-boxing, higher-order macrostates, and scalable
heuristics remain future work).
"""

from __future__ import annotations

import math
from typing import Any

from causal_emergence_zoo.coarse_grain import coarse_grain_tpm
from causal_emergence_zoo.metrics import Matrix, compute_metrics, entropy_bits
from causal_emergence_zoo.partitions import enumerate_partitions
from causal_emergence_zoo.search import Partition, canonical_partition, partition_id, score_partition


# Bell-number enumeration grows beyond a practical and auditable budget very
# quickly.  Eight states is deliberately a hard implementation limit, not a
# tuning default that callers can raise into an accidentally intractable run.
MAX_EXACT_STATES = 8


def check_dynamical_consistency(
    tpm: Matrix,
    partition: Partition,
    *,
    horizon: int = 5,
    tolerance: float = 1e-10,
) -> dict[str, Any]:
    """Check a partition against CE 2.0's random-walk consistency criterion.

    For every possible microstate start, this compares the projected distribution
    of a micro random walker with a walker on the induced macro TPM for each step
    through ``horizon``.  The summed KL divergence is zero (up to ``tolerance``)
    precisely when this coarse grain is dynamically consistent under this strict
    finite-horizon test.
    """
    if horizon < 1:
        raise ValueError("horizon must be at least 1.")
    if tolerance < 0 or not math.isfinite(tolerance):
        raise ValueError("tolerance must be a finite non-negative number.")

    # This also checks that the TPM is square and row stochastic.
    compute_metrics(tpm)
    blocks = canonical_partition(partition)
    state_count = len(tpm)
    _assert_partition_covers_state_space(blocks, state_count)
    macro_tpm = coarse_grain_tpm(tpm, blocks)
    macro_index = _macro_index(blocks, state_count)

    total_divergence = 0.0
    per_start: list[dict[str, Any]] = []
    for start_state in range(state_count):
        micro_distribution = [0.0] * state_count
        micro_distribution[start_state] = 1.0
        macro_distribution = [0.0] * len(blocks)
        macro_distribution[macro_index[start_state]] = 1.0
        divergences: list[float] = []

        for _ in range(horizon):
            micro_distribution = _advance_distribution(micro_distribution, tpm)
            macro_distribution = _advance_distribution(macro_distribution, macro_tpm)
            projected_micro = _project_distribution(micro_distribution, blocks)
            divergence = _kl_divergence(projected_micro, macro_distribution)
            divergences.append(divergence)
            total_divergence += divergence

        per_start.append({"state": start_state, "kl_divergences": divergences, "total": sum(divergences)})

    finite_total = total_divergence if math.isfinite(total_divergence) else None
    finite_per_start = [
        {
            "state": item["state"],
            "kl_divergences": [value if math.isfinite(value) else None for value in item["kl_divergences"]],
            "total": item["total"] if math.isfinite(item["total"]) else None,
        }
        for item in per_start
    ]
    return {
        "partition_id": partition_id(blocks),
        "blocks": blocks,
        "horizon": horizon,
        "tolerance": tolerance,
        "total_kl_divergence": finite_total,
        "is_dynamically_consistent": math.isfinite(total_divergence) and total_divergence <= tolerance,
        "per_start_state": finite_per_start,
    }


def analyze_ce2_path(
    tpm: Matrix,
    path: list[Partition],
    *,
    consistency_horizon: int = 5,
    consistency_tolerance: float = 1e-10,
    gain_tolerance: float = 1e-12,
) -> dict[str, Any]:
    """Validate and apportion a caller-supplied CE 2.0 micro→macro path.

    This is useful when an external algorithm supplies an interpretable hierarchy.
    It validates nesting and dynamic consistency but deliberately makes no claim
    that the endpoint or path is globally optimal.
    """
    if not path:
        raise ValueError("A CE 2.0 path must contain at least the microscale partition.")
    micro_metrics = compute_metrics(tpm)
    state_count = len(tpm)
    expected_micro = [[state] for state in range(state_count)]
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    previous: Partition | None = None

    for index, supplied_blocks in enumerate(path):
        try:
            blocks = canonical_partition(supplied_blocks)
            _assert_partition_covers_state_space(blocks, state_count)
        except (TypeError, ValueError) as exc:
            errors.append(f"path[{index}] is invalid: {exc}")
            continue
        if index == 0 and blocks != expected_micro:
            errors.append("path[0] must be the singleton microscale partition.")
        if previous is not None:
            if blocks == previous or not _is_refinement(previous, blocks):
                errors.append(f"path[{index}] must be a strict coarsening of path[{index - 1}].")
        previous = blocks
        record = score_partition(tpm, blocks, micro_causal_power=micro_metrics["causal_power"])
        consistency = check_dynamical_consistency(
            tpm,
            blocks,
            horizon=consistency_horizon,
            tolerance=consistency_tolerance,
        )
        record["cp"] = record["metrics"]["causal_power"]
        record["dynamical_consistency"] = {
            "total_kl_divergence": consistency["total_kl_divergence"],
            "is_dynamically_consistent": consistency["is_dynamically_consistent"],
        }
        if not consistency["is_dynamically_consistent"]:
            errors.append(f"path[{index}] is not dynamically consistent.")
        records.append(record)

    if errors:
        return {
            "framework": "hoel_ce2_partition_path",
            "is_exhaustive": False,
            "validity": {
                "is_valid": False,
                "errors": errors,
                "consistency_horizon": consistency_horizon,
                "consistency_tolerance": consistency_tolerance,
            },
            "path": [_compact_record(record) for record in records],
        }

    apportioned_path = _apportion_path(records)
    return {
        "framework": "hoel_ce2_partition_path",
        "is_exhaustive": False,
        "cp_definition": "determinism + specificity - 1",
        "cp_metric_key": "causal_power",
        "validity": {
            "is_valid": True,
            "errors": [],
            "consistency_horizon": consistency_horizon,
            "consistency_tolerance": consistency_tolerance,
        },
        "microscale": _compact_record(records[0]),
        "endpoint": _compact_record(records[-1]),
        "path": apportioned_path,
        "causal_apportioning": _summarize_apportioning(apportioned_path, gain_tolerance),
        "emergent_complexity": _emergent_complexity(apportioned_path, gain_tolerance),
        "endpoint_optimality": "not_assessed_for_supplied_path",
        "path_optimality": "not_assessed_for_supplied_path",
    }


def discover_ce2_path(
    tpm: Matrix,
    *,
    max_exhaustive_states: int = 8,
    consistency_horizon: int = 5,
    consistency_tolerance: float = 1e-10,
    gain_tolerance: float = 1e-12,
    top_k: int = 10,
) -> dict[str, Any]:
    """Exhaustively discover a dynamically consistent CE 2.0 path for a small TPM.

    The endpoint is the consistent partition with maximum CP, breaking ties in
    favour of the highest-dimensional scale (the least dimension reduction), as
    specified by Hoel.  Among valid nested paths to that endpoint, the longest is
    chosen; remaining ties are deterministic and are surfaced in the selection
    rule.  CP here is ``determinism + specificity - 1``—the existing zoo
    ``causal_power`` metric.
    """
    micro_metrics = compute_metrics(tpm)
    state_count = len(tpm)
    if not isinstance(max_exhaustive_states, int) or isinstance(max_exhaustive_states, bool):
        raise ValueError("max_exhaustive_states must be an integer between 1 and 8.")
    if not 1 <= max_exhaustive_states <= MAX_EXACT_STATES:
        raise ValueError(
            "max_exhaustive_states must be between 1 and "
            f"{MAX_EXACT_STATES}; exhaustive CE 2.0 enumeration is not supported above that limit."
        )
    if state_count > max_exhaustive_states:
        raise ValueError(
            f"CE 2.0 exhaustive discovery is limited to {max_exhaustive_states} states; "
            f"received {state_count}. Use search_mode='auto' or search_mode='beam' for the "
            "bounded, non-exhaustive search supported through 16 states."
        )
    if top_k < 1:
        raise ValueError("top_k must be positive.")

    records: list[dict[str, Any]] = []
    for blocks in enumerate_partitions(state_count):
        record = score_partition(tpm, blocks, micro_causal_power=micro_metrics["causal_power"])
        consistency = check_dynamical_consistency(
            tpm,
            blocks,
            horizon=consistency_horizon,
            tolerance=consistency_tolerance,
        )
        record["cp"] = record["metrics"]["causal_power"]
        record["dynamical_consistency"] = {
            "total_kl_divergence": consistency["total_kl_divergence"],
            "is_dynamically_consistent": consistency["is_dynamically_consistent"],
        }
        records.append(record)

    valid_records = [
        record
        for record in records
        if record["dynamical_consistency"]["is_dynamically_consistent"]
    ]
    if not valid_records:
        # The singleton partition is always expected to be valid, so this is a
        # defensive error instead of a silently misleading result.
        raise ValueError("No dynamically consistent scales were found.")

    ranked_valid = _rank_records(valid_records)
    endpoint = ranked_valid[0]
    micro = next(record for record in valid_records if record["macro_state_count"] == state_count)
    path = _longest_nested_path(valid_records, endpoint)
    apportioned_path = _apportion_path(path)
    apportioning = _summarize_apportioning(apportioned_path, gain_tolerance)

    return {
        "framework": "hoel_ce2_partition_path",
        "is_exhaustive": True,
        "state_count": state_count,
        "cp_definition": "determinism + specificity - 1",
        "cp_metric_key": "causal_power",
        "selection_rule": (
            "Endpoint maximizes CP among dynamically consistent partitions; ties prefer the "
            "highest-dimensional scale. Path maximizes valid nested scale count, then uses "
            "cumulative CP and lexicographic partition ids for deterministic tie-breaking."
        ),
        "dynamical_consistency": {
            "method": "projected_micro_vs_macro_random_walk_kl",
            "horizon": consistency_horizon,
            "tolerance": consistency_tolerance,
            "valid_partition_count": len(valid_records),
            "discarded_partition_count": len(records) - len(valid_records),
        },
        "microscale": _compact_record(micro),
        "endpoint": _compact_record(endpoint),
        "candidate_endpoint_count": len(ranked_valid),
        "top_consistent_scales": [_compact_record(record) for record in ranked_valid[:top_k]],
        "path": apportioned_path,
        "causal_apportioning": apportioning,
        "emergent_complexity": _emergent_complexity(apportioned_path, gain_tolerance),
    }


def _compact_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "partition_id": record["partition_id"],
        "blocks": record["blocks"],
        "macro_state_count": record["macro_state_count"],
        "cp": record["cp"],
        "delta_cp_from_microscale": record["deltaCP"],
        "metrics": record["metrics"],
        "macro_tpm": record["macro_tpm"],
        "dynamical_consistency": record["dynamical_consistency"],
    }


def _rank_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        records,
        key=lambda record: (
            -round(record["cp"], 12),
            -record["macro_state_count"],
            record["partition_id"],
        ),
    )


def _longest_nested_path(
    valid_records: list[dict[str, Any]],
    endpoint: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return the longest valid nested path from microscale to ``endpoint``."""
    endpoint_blocks = endpoint["blocks"]
    eligible = [
        record
        for record in valid_records
        if _is_refinement(record["blocks"], endpoint_blocks)
    ]
    ordered = sorted(
        eligible,
        key=lambda record: (-record["macro_state_count"], record["partition_id"]),
    )
    paths: dict[str, list[dict[str, Any]]] = {}

    for record in ordered:
        finer_paths = [
            path
            for previous_id, path in paths.items()
            if _is_refinement(path[-1]["blocks"], record["blocks"])
            and path[-1]["partition_id"] != record["partition_id"]
        ]
        if not finer_paths:
            paths[record["partition_id"]] = [record]
            continue
        best_previous = min(
            finer_paths,
            key=lambda path: (
                -len(path),
                -sum(item["cp"] for item in path),
                tuple(item["partition_id"] for item in path),
            ),
        )
        paths[record["partition_id"]] = best_previous + [record]

    endpoint_path = paths.get(endpoint["partition_id"])
    if endpoint_path is None:
        raise ValueError("Could not construct a valid CE 2.0 path to the selected endpoint.")
    return endpoint_path


def _apportion_path(path: list[dict[str, Any]]) -> list[dict[str, Any]]:
    apportioned: list[dict[str, Any]] = []
    previous_cp: float | None = None
    for index, record in enumerate(path):
        cp = record["cp"]
        delta = 0.0 if previous_cp is None else cp - previous_cp
        apportioned.append(
            {
                "step": index,
                "partition_id": record["partition_id"],
                "blocks": record["blocks"],
                "macro_state_count": record["macro_state_count"],
                "cp": cp,
                "delta_cp_from_previous_scale": delta,
                "positive_causal_contribution": max(delta, 0.0),
                "dynamical_consistency": record["dynamical_consistency"],
            }
        )
        previous_cp = cp
    return apportioned


def _summarize_apportioning(path: list[dict[str, Any]], gain_tolerance: float) -> dict[str, Any]:
    if not path:
        raise ValueError("CE 2.0 path must contain a microscale.")
    deltas = [step["delta_cp_from_previous_scale"] for step in path[1:]]
    positives = [max(delta, 0.0) for delta in deltas]
    return {
        "net_causal_emergence": path[-1]["cp"] - path[0]["cp"],
        "endpoint_cp_gain": path[-1]["cp"] - path[0]["cp"],
        "positive_increment_total": sum(positives),
        "negative_increment_total": sum(min(delta, 0.0) for delta in deltas),
        "positive_contribution_count": sum(value > gain_tolerance for value in positives),
        "has_positive_macro_contribution": any(value > gain_tolerance for value in positives),
    }


def _emergent_complexity(path: list[dict[str, Any]], gain_tolerance: float) -> dict[str, Any]:
    signed_contributions = [step["delta_cp_from_previous_scale"] for step in path[1:]]
    contributions = [step["positive_causal_contribution"] for step in path[1:]]
    total = sum(contributions)
    step_count = len(contributions)
    if any(value < -gain_tolerance for value in signed_contributions):
        return {
            "bits": None,
            "normalized": None,
            "positive_contribution_count": sum(value > gain_tolerance for value in contributions),
            "path_step_count": step_count,
            "status": "undefined_signed_increments",
        }
    if total <= gain_tolerance or step_count == 0:
        return {
            "bits": None,
            "normalized": None,
            "positive_contribution_count": 0,
            "path_step_count": step_count,
            "status": "undefined_without_positive_macro_contributions",
        }

    distribution = [value / total for value in contributions]
    bits = entropy_bits(distribution)
    normalized = bits / math.log2(step_count) if step_count > 1 else 0.0
    return {
        "bits": bits,
        "normalized": normalized,
        "positive_contribution_count": sum(value > gain_tolerance for value in contributions),
        "path_step_count": step_count,
        "status": "defined",
    }


def _assert_partition_covers_state_space(partition: Partition, state_count: int) -> None:
    seen = sorted(state for block in partition for state in block)
    if seen != list(range(state_count)):
        raise ValueError("Partition must cover every TPM state exactly once.")


def _macro_index(partition: Partition, state_count: int) -> list[int]:
    index = [-1] * state_count
    for macro_state, block in enumerate(partition):
        for state in block:
            index[state] = macro_state
    if any(value < 0 for value in index):
        raise ValueError("Partition must cover every TPM state exactly once.")
    return index


def _advance_distribution(distribution: list[float], tpm: Matrix) -> list[float]:
    return [
        sum(distribution[source] * tpm[source][target] for source in range(len(distribution)))
        for target in range(len(tpm))
    ]


def _project_distribution(distribution: list[float], partition: Partition) -> list[float]:
    return [sum(distribution[state] for state in block) for block in partition]


def _kl_divergence(left: list[float], right: list[float]) -> float:
    total = 0.0
    for probability, reference in zip(left, right):
        if probability <= 0.0:
            continue
        if reference <= 0.0:
            return math.inf
        total += probability * math.log2(probability / reference)
    # Numerical round-off can create a tiny negative value even though KL is
    # mathematically non-negative.
    return max(total, 0.0)


def _is_refinement(finer: Partition, coarser: Partition) -> bool:
    coarser_index = {
        state: block_index
        for block_index, block in enumerate(coarser)
        for state in block
    }
    return all(len({coarser_index[state] for state in block}) == 1 for block in finer)
