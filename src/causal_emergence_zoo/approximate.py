"""Bounded, auditable CE2 partition search beyond exhaustive enumeration.

The exact CE2 implementation deliberately stops at eight states.  This module
extends *search*, not the CE2 definition: it still uses hard partitions, the
same induced macro TPM, and the same finite-horizon dynamical-consistency test.
For 9--16 states it evaluates a deterministic, budgeted subset of pairwise
coarsenings.  Its output must therefore never be read as a global optimum.
"""

from __future__ import annotations

from math import comb
from typing import Any

from causal_emergence_zoo.ce2 import analyze_ce2_path, check_dynamical_consistency
from causal_emergence_zoo.metrics import Matrix, compute_metrics
from causal_emergence_zoo.search import (
    pairwise_merges,
    partition_id,
    score_partition,
    singleton_partition,
)


# This is a deliberately supported envelope, not a claim that a beam search is
# generally adequate for every 16-state system.  The output records all budgets
# and pruning choices so callers can replicate or challenge a result.
MAX_APPROXIMATE_STATES = 16


def approximate_ce2_path(
    tpm: Matrix,
    *,
    beam_width: int = 20,
    branching_factor: int = 4,
    consistency_horizon: int = 5,
    consistency_tolerance: float = 1e-10,
    gain_tolerance: float = 1e-12,
    top_k: int = 10,
    max_partition_evaluations: int = 100_000,
) -> dict[str, Any]:
    """Run a deterministic, dynamically consistent bounded beam search.

    Starting at the singleton microscale, the search considers one pairwise
    block merge at a time.  A candidate is scored only after it passes the same
    CE2 finite-horizon consistency check used by exhaustive discovery.  At each
    scale it retains at most ``branching_factor`` candidates per active path and
    at most ``beam_width`` paths globally.  ``max_partition_evaluations`` caps
    unique candidate consistency checks.

    The endpoint is the highest-CP dynamically consistent partition *evaluated
    by this bounded procedure*.  It is not a global CE2 optimum and neither is
    the returned path.  The supported state-space limit is 16; callers should
    reduce or otherwise model larger systems before using this finite-state
    implementation.
    """
    _validate_search_options(
        beam_width=beam_width,
        branching_factor=branching_factor,
        max_partition_evaluations=max_partition_evaluations,
        top_k=top_k,
    )
    state_count = len(tpm)
    if state_count > MAX_APPROXIMATE_STATES:
        raise ValueError(
            "Bounded CE 2.0 beam search supports at most "
            f"{MAX_APPROXIMATE_STATES} states; received {state_count}."
        )

    # compute_metrics both establishes the shared microscale CP convention and
    # validates the supplied TPM before any search work begins.
    micro_causal_power = compute_metrics(tpm)["causal_power"]
    micro_blocks = singleton_partition(state_count)
    micro_record = score_partition(tpm, micro_blocks, micro_causal_power=micro_causal_power)
    micro_record["cp"] = micro_record["metrics"]["causal_power"]
    micro_record["dynamical_consistency"] = {
        "total_kl_divergence": 0.0,
        "is_dynamically_consistent": True,
    }
    micro_id = micro_record["partition_id"]

    # ``consistent_records`` contains every dynamically consistent candidate
    # actually evaluated. ``paths`` stores an explicitly valid, nested route
    # to each one; the path can only arise from a retained valid parent.
    consistent_records: dict[str, dict[str, Any]] = {micro_id: micro_record}
    paths: dict[str, tuple[str, ...]] = {micro_id: (micro_id,)}
    consistency_cache: dict[str, bool] = {micro_id: True}
    invalid_partition_ids: set[str] = set()
    frontier = [micro_id]
    branch_selected_ids: set[str] = {micro_id}
    frontier_retained_ids: set[str] = {micro_id}
    partition_evaluations = 0
    termination_reason = "search_complete"

    while frontier and any(
        consistent_records[partition_key]["macro_state_count"] > 1
        for partition_key in frontier
    ):
        expanded_paths: dict[str, tuple[str, ...]] = {}
        budget_exhausted = False

        for parent_id in frontier:
            parent = consistent_records[parent_id]
            if parent["macro_state_count"] == 1:
                continue

            candidates: list[str] = []
            parent_path = paths[parent_id]
            for blocks in pairwise_merges(parent["blocks"]):
                candidate_id = partition_id(blocks)
                if candidate_id not in consistency_cache:
                    if partition_evaluations >= max_partition_evaluations:
                        termination_reason = "partition_evaluation_budget_exhausted"
                        budget_exhausted = True
                        break

                    consistency = check_dynamical_consistency(
                        tpm,
                        blocks,
                        horizon=consistency_horizon,
                        tolerance=consistency_tolerance,
                    )
                    partition_evaluations += 1
                    is_consistent = consistency["is_dynamically_consistent"]
                    consistency_cache[candidate_id] = is_consistent
                    if is_consistent:
                        record = score_partition(
                            tpm,
                            blocks,
                            micro_causal_power=micro_causal_power,
                        )
                        record["cp"] = record["metrics"]["causal_power"]
                        record["dynamical_consistency"] = {
                            "total_kl_divergence": consistency["total_kl_divergence"],
                            "is_dynamically_consistent": True,
                        }
                        consistent_records[candidate_id] = record
                    else:
                        invalid_partition_ids.add(candidate_id)

                if not consistency_cache[candidate_id]:
                    continue

                candidate_path = parent_path + (candidate_id,)
                existing_path = paths.get(candidate_id)
                if existing_path is None or _path_rank(candidate_path, consistent_records) < _path_rank(
                    existing_path, consistent_records
                ):
                    paths[candidate_id] = candidate_path
                candidates.append(candidate_id)

            if budget_exhausted:
                break

            for candidate_id in sorted(set(candidates), key=lambda item: _record_rank(consistent_records[item]))[
                :branching_factor
            ]:
                candidate_path = paths[candidate_id]
                existing_path = expanded_paths.get(candidate_id)
                if existing_path is None or _path_rank(candidate_path, consistent_records) < _path_rank(
                    existing_path, consistent_records
                ):
                    expanded_paths[candidate_id] = candidate_path
                branch_selected_ids.add(candidate_id)

        if budget_exhausted:
            break

        frontier = [
            candidate_id
            for candidate_id, _ in sorted(
                expanded_paths.items(),
                key=lambda item: _record_rank(consistent_records[item[0]]),
            )[:beam_width]
        ]
        frontier_retained_ids.update(frontier)

    ranked_consistent = sorted(consistent_records.values(), key=_record_rank)
    endpoint = ranked_consistent[0]
    endpoint_path = paths[endpoint["partition_id"]]
    result = analyze_ce2_path(
        tpm,
        [consistent_records[partition_key]["blocks"] for partition_key in endpoint_path],
        consistency_horizon=consistency_horizon,
        consistency_tolerance=consistency_tolerance,
        gain_tolerance=gain_tolerance,
    )
    # A defensive assertion makes a failed invariant explicit rather than
    # returning an approximate result whose path lacks CE2 validity.
    if not result["validity"]["is_valid"]:
        raise RuntimeError("Bounded CE2 search produced an invalid nested path.")

    full_lattice_size = _bell_number(state_count)
    evaluated_partition_count = len(consistency_cache)
    result.update(
        {
            "algorithm": "dynamically_consistent_ce2_bounded_beam_search",
            "state_count": state_count,
            "is_exhaustive": False,
            "selection_rule": (
                "Endpoint maximizes CP among dynamically consistent partitions evaluated by the "
                "bounded beam; ties prefer the highest-dimensional scale, then partition id. "
                "The reported path is the highest cumulative-CP valid route retained for that endpoint."
            ),
            "dynamical_consistency": {
                "method": "projected_micro_vs_macro_random_walk_kl",
                "horizon": consistency_horizon,
                "tolerance": consistency_tolerance,
                "valid_partition_count": len(consistent_records),
                "discarded_partition_count": len(invalid_partition_ids),
            },
            "candidate_endpoint_count": len(ranked_consistent),
            "top_consistent_scales": [_compact_record(record) for record in ranked_consistent[:top_k]],
            # Retained for compatibility with the earlier beam prototype. It
            # means a candidate selected by a local branch, not exhaustive
            # coverage of the partition lattice.
            "sampled_partition_count": len(branch_selected_ids),
            "partition_evaluation_count": partition_evaluations,
            "max_partition_evaluations": max_partition_evaluations,
            "termination_reason": termination_reason,
            "endpoint_optimality": "best_sampled_not_global",
            "path_optimality": "best_sampled_not_global",
            "search_contract": {
                "search_family": "deterministic_bounded_pairwise_merge_beam",
                "supported_state_count_maximum": MAX_APPROXIMATE_STATES,
                "partition_move": "merge_exactly_two_current_blocks",
                "candidate_admission": "finite_horizon_dynamically_consistent_only",
                "candidate_ranking": "causal_power_desc_then_macro_state_count_desc_then_partition_id",
                "path_tie_break": "path_length_desc_then_cumulative_cp_desc_then_partition_ids",
                "beam_width": beam_width,
                "branching_factor": branching_factor,
                "max_partition_evaluations": max_partition_evaluations,
                "endpoint_selection_scope": "all_dynamically_consistent_partitions_evaluated_from_retained_paths",
            },
            "search_coverage": {
                "full_partition_lattice_count": full_lattice_size,
                "evaluated_partition_count": evaluated_partition_count,
                "evaluated_consistent_partition_count": len(consistent_records),
                "evaluated_inconsistent_partition_count": len(invalid_partition_ids),
                "branch_selected_partition_count": len(branch_selected_ids),
                "frontier_retained_partition_count": len(frontier_retained_ids),
                "partition_evaluation_fraction_of_full_lattice": evaluated_partition_count / full_lattice_size,
                "note": (
                    "This fraction is descriptive only: beam pruning is score-directed, not a random or "
                    "representative sample of the full partition lattice."
                ),
            },
            "limitations": [
                "The endpoint is best among evaluated candidates, not a global CE2 optimum.",
                "Beam and branching pruning can exclude a lower-scoring intermediate scale that leads to a better deeper macro scale.",
                "Only hard partitions reachable through pairwise block merges are searched.",
                "Dynamical consistency is finite-horizon under the declared tolerance, not a proof for every future time step.",
            ],
        }
    )
    return result


def _validate_search_options(
    *,
    beam_width: int,
    branching_factor: int,
    max_partition_evaluations: int,
    top_k: int,
) -> None:
    for name, value in {
        "beam_width": beam_width,
        "branching_factor": branching_factor,
        "max_partition_evaluations": max_partition_evaluations,
        "top_k": top_k,
    }.items():
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ValueError(f"{name} must be a positive integer.")


def _record_rank(record: dict[str, Any]) -> tuple[float, int, str]:
    return (
        -round(record["cp"], 12),
        -record["macro_state_count"],
        record["partition_id"],
    )


def _path_rank(
    path: tuple[str, ...], records: dict[str, dict[str, Any]]
) -> tuple[int, float, tuple[str, ...]]:
    return (
        -len(path),
        -round(sum(records[partition_key]["cp"] for partition_key in path), 12),
        path,
    )


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


def _bell_number(state_count: int) -> int:
    """Return the Bell number for a small non-negative ``state_count``."""
    bell = [0] * (state_count + 1)
    bell[0] = 1
    for size in range(state_count):
        bell[size + 1] = sum(comb(size, index) * bell[index] for index in range(size + 1))
    return bell[state_count]
