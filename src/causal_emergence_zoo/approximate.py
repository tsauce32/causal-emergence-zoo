"""Bounded CE2 partition search for state spaces beyond exhaustive enumeration."""

from __future__ import annotations

from typing import Any

from causal_emergence_zoo.ce2 import analyze_ce2_path, check_dynamical_consistency
from causal_emergence_zoo.metrics import Matrix, compute_metrics
from causal_emergence_zoo.search import pairwise_merges, score_partition, singleton_partition


def approximate_ce2_path(
    tpm: Matrix,
    *,
    beam_width: int = 20,
    branching_factor: int = 4,
    consistency_horizon: int = 5,
    consistency_tolerance: float = 1e-10,
    max_partition_evaluations: int = 100_000,
) -> dict[str, Any]:
    """Search dynamically consistent pairwise merges with a bounded beam.

    The best sampled CP is selected, with CE2's least-reduction tie break. This
    is explicitly approximate: it makes no global-optimality claim.
    """
    if beam_width < 1 or branching_factor < 1 or max_partition_evaluations < 1:
        raise ValueError("beam_width, branching_factor, and max_partition_evaluations must be positive.")
    micro = singleton_partition(len(tpm))
    micro_cp = compute_metrics(tpm)["causal_power"]
    frontier: list[tuple[list[list[list[int]]], dict[str, Any]]] = [
        ([micro], score_partition(tpm, micro, micro_causal_power=micro_cp))
    ]
    sampled = {frontier[0][1]["partition_id"]: frontier[0]}
    consistency_cache: dict[str, bool] = {frontier[0][1]["partition_id"]: True}
    score_cache: dict[str, dict[str, Any]] = {frontier[0][1]["partition_id"]: frontier[0][1]}
    evaluations = 0
    termination_reason = "search_complete"

    while frontier and any(len(item[1]["blocks"]) > 1 for item in frontier):
        expanded = []
        for path, record in frontier:
            if len(record["blocks"]) == 1:
                continue
            candidates = []
            for blocks in pairwise_merges(record["blocks"]):
                candidate_id = score_partition(tpm, blocks, micro_causal_power=micro_cp)["partition_id"]
                if candidate_id not in consistency_cache:
                    if evaluations >= max_partition_evaluations:
                        termination_reason = "partition_evaluation_budget_exhausted"
                        break
                    consistency = check_dynamical_consistency(tpm, blocks, horizon=consistency_horizon, tolerance=consistency_tolerance)
                    consistency_cache[candidate_id] = consistency["is_dynamically_consistent"]
                    evaluations += 1
                if not consistency_cache[candidate_id]:
                    continue
                candidate = score_cache.get(candidate_id)
                if candidate is None:
                    candidate = score_partition(tpm, blocks, micro_causal_power=micro_cp)
                    score_cache[candidate_id] = candidate
                candidates.append(candidate)
            if termination_reason != "search_complete":
                break
            candidates.sort(key=lambda item: (-round(item["score"], 12), -item["macro_state_count"], item["partition_id"]))
            for candidate in candidates[:branching_factor]:
                entry = (path + [candidate["blocks"]], candidate)
                sampled[candidate["partition_id"]] = entry
                expanded.append(entry)
        expanded.sort(key=lambda item: (-round(item[1]["score"], 12), -item[1]["macro_state_count"], item[1]["partition_id"]))
        frontier = expanded[:beam_width]
        if termination_reason != "search_complete":
            break

    best_path, best = min(
        sampled.values(),
        key=lambda item: (-round(item[1]["score"], 12), -item[1]["macro_state_count"], item[1]["partition_id"]),
    )
    result = analyze_ce2_path(
        tpm,
        best_path,
        consistency_horizon=consistency_horizon,
        consistency_tolerance=consistency_tolerance,
    )
    result.update(
        {
            "algorithm": "dynamically_consistent_ce2_beam_search",
            "is_exhaustive": False,
            "beam_width": beam_width,
            "branching_factor": branching_factor,
            "sampled_partition_count": len(sampled),
            "partition_evaluation_count": evaluations,
            "max_partition_evaluations": max_partition_evaluations,
            "termination_reason": termination_reason,
            "endpoint_optimality": "best_sampled_not_global",
            "path_optimality": "best_sampled_not_global",
        }
    )
    return result
