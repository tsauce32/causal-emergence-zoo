"""Trajectory-respecting validation for fitted finite-state CE2 models.

These helpers deliberately operate on *independent, already encoded*
trajectories.  They are useful after a continuous encoder has been frozen, but
they do not alter that encoder, select a new hierarchy, or turn observational
data into interventional evidence.

The functions are opt-in because grouped resampling needs a collection of
complete trajectories.  This is a different resource contract from the
bounded-memory CSV estimator: callers should use it only when the number of
independent groups is manageable or when they have deliberately retained a
group-level representation.
"""

from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from causal_emergence_zoo.estimation import estimate_tpm_from_transition_counts
from causal_emergence_zoo.narrative import narrate_tpm


_OBSERVATIONAL_CAVEAT = (
    "These resampling and alignment checks quantify stability of the fitted "
    "finite-state model under the declared encoding and trajectory grouping. "
    "They do not identify intervention effects or establish real-world causation."
)

_NARRATION_OPTION_KEYS = {
    "max_exhaustive_states",
    "consistency_horizon",
    "consistency_tolerance",
    "gain_tolerance",
    "edge_probability_threshold",
    "top_k",
    "search_mode",
    "beam_width",
    "branching_factor",
    "max_partition_evaluations",
}
_UNSET = object()


def validate_grouped_trajectories(
    trajectories: Iterable[Sequence[int]],
    *,
    state_count: int,
    state_labels: Sequence[str] | None = None,
    smoothing: float = 0.0,
    temporal_null_replicates: int = 0,
    temporal_null_seed: int = 0,
    bootstrap_replicates: int = 0,
    bootstrap_seed: int = 0,
    confidence_level: float = 0.95,
    narration_options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run temporal-null and grouped-bootstrap checks on complete trajectories.

    Each inner sequence is one resampling unit.  The temporal null shuffles
    observations *within* each sequence; the bootstrap samples complete
    sequences with replacement.  The observed and resampled CE2 statistics are
    conditional on the supplied discrete state encoding.
    """
    copied = _copy_trajectories(trajectories, state_count)
    labels = _resolve_labels(state_count, state_labels)
    options = _resolve_narration_options(narration_options)
    observed = _evaluate_trajectories(
        copied,
        state_count=state_count,
        state_labels=labels,
        smoothing=smoothing,
        narration_options=options,
        source_kind="trajectory_validation_observed_model",
    )

    return {
        "schema_version": "0.1.0",
        "kind": "causal_emergence.trajectory_validation",
        "resampling_unit": "complete_independent_trajectory",
        "trajectory_count": len(copied),
        "observed_model": observed,
        "temporal_permutation_null": trajectory_temporal_permutation_null(
            copied,
            state_count=state_count,
            state_labels=labels,
            smoothing=smoothing,
            replicates=temporal_null_replicates,
            seed=temporal_null_seed,
            observed_endpoint_cp_gain=observed["endpoint_cp_gain"],
            narration_options=options,
        ),
        "grouped_bootstrap": grouped_bootstrap_confidence_intervals(
            copied,
            state_count=state_count,
            state_labels=labels,
            smoothing=smoothing,
            replicates=bootstrap_replicates,
            seed=bootstrap_seed,
            confidence_level=confidence_level,
            observed_endpoint_cp_gain=observed["endpoint_cp_gain"],
            observed_endpoint_cp=observed["endpoint_cp"],
            narration_options=options,
        ),
        "observational_caveat": _OBSERVATIONAL_CAVEAT,
        "resource_caveat": (
            "Grouped bootstrap materializes complete encoded trajectories. It is optional "
            "and is not part of the bounded-memory streaming transition estimator."
        ),
    }


def validate_continuous_analysis_trajectories(
    source: Any,
    analysis: Mapping[str, Any],
    *,
    temporal_null_replicates: int = 0,
    temporal_null_seed: int = 0,
    bootstrap_replicates: int = 0,
    bootstrap_seed: int = 0,
    confidence_level: float = 0.95,
    narration_options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Replay a frozen continuous analysis as grouped encoded trajectories.

    This is an opt-in bridge for the current continuous-result shape.  It
    reuses the reported encoder and trajectory split, never refits the encoder,
    and verifies that the source still matches the encoder's recorded
    pass-one signature.  Complete encoded trajectories are then passed to the
    generic grouped validation routines above.
    """
    try:
        continuous = analysis["continuous_data"]
        encoder = continuous["discretizer"]
        transitions = continuous["transitions"]
    except (KeyError, TypeError) as exc:
        raise ValueError("analysis must be a continuous CE2 result with continuous_data metadata.") from exc

    schema = encoder.get("input_schema", {})
    feature_columns = schema.get("feature_columns")
    trajectory_column = schema.get("trajectory_column")
    time_column = schema.get("time_column")
    if not isinstance(feature_columns, list) or not feature_columns:
        raise ValueError("Continuous analysis is missing encoder input feature_columns.")
    selection_scope = continuous.get("selection", {}).get("scope", "all")
    if selection_scope not in {"all", "train", "validation"}:
        raise ValueError("Continuous analysis has an unknown selection scope.")

    # These imports stay local so the generic encoded-trajectory routines remain
    # independent of CSV, Parquet, and DataFrame adapter implementation details.
    from causal_emergence_zoo.continuous import (
        _iter_source_observations,
        _trajectory_split,
        encode_continuous_observation,
    )
    from causal_emergence_zoo.tabular import adapt_continuous_source
    from causal_emergence_zoo.temporal import derive_temporal_features

    adapted = adapt_continuous_source(source)
    expected_signature = encoder.get("source_signature")
    if expected_signature is not None and adapted.source_signature() != expected_signature:
        raise ValueError(
            "Continuous source does not match the frozen encoder's pass-one source signature."
        )

    temporal = schema.get("temporal_features", {})
    validation_fraction = transitions.get("validation_fraction", 0.0)
    split_seed = transitions.get("split_seed", 0)
    max_gap = transitions.get("max_gap")
    raw = _iter_source_observations(
        adapted,
        feature_columns=feature_columns,
        trajectory_column=trajectory_column,
        time_column=time_column,
    )
    derived = derive_temporal_features(
        raw,
        feature_names=feature_columns,
        differences=temporal.get("differences", ()),
        volatility_windows=temporal.get("volatility_windows", ()),
        max_gap=max_gap,
    )
    groups = _collect_encoded_groups(
        derived,
        encoder=encoder,
        encode=encode_continuous_observation,
        trajectory_column=trajectory_column,
        validation_fraction=validation_fraction,
        split_seed=split_seed,
        selection_scope=selection_scope,
        max_gap=max_gap,
        split_fn=_trajectory_split,
    )
    state_labels = transitions.get("state_labels")
    state_count = len(encoder.get("centroids_standardized", []))
    options = _continuous_narration_options(analysis, narration_options)
    validation = validate_grouped_trajectories(
        groups,
        state_count=state_count,
        state_labels=state_labels,
        smoothing=transitions.get("smoothing", 0.0),
        temporal_null_replicates=temporal_null_replicates,
        temporal_null_seed=temporal_null_seed,
        bootstrap_replicates=bootstrap_replicates,
        bootstrap_seed=bootstrap_seed,
        confidence_level=confidence_level,
        narration_options=options,
    )
    reported_gain = analysis.get("ce2", {}).get("causal_apportioning", {}).get("endpoint_cp_gain")
    recomputed_gain = validation["observed_model"]["endpoint_cp_gain"]
    validation["continuous_replay"] = {
        "selection_scope": selection_scope,
        "frozen_encoder_reused": True,
        "source_adapter": adapted.descriptor(),
        "reported_selection_endpoint_cp_gain": reported_gain,
        "recomputed_endpoint_cp_gain": recomputed_gain,
        "matches_reported_selection_gain": (
            isinstance(reported_gain, (int, float))
            and math.isclose(reported_gain, recomputed_gain, abs_tol=1e-12)
        ),
    }
    return validation


def trajectory_temporal_permutation_null(
    trajectories: Iterable[Sequence[int]],
    *,
    state_count: int,
    state_labels: Sequence[str] | None = None,
    smoothing: float = 0.0,
    replicates: int = 0,
    seed: int = 0,
    observed_endpoint_cp_gain: float | None = None,
    narration_options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare CE2 gain with within-trajectory temporal-permutation nulls.

    The null preserves every trajectory's length and state occupancy while
    destroying its temporal order.  In particular, observations are never
    exchanged between trajectories, unlike a global time shuffle.
    """
    _validate_replicates(replicates, "replicates")
    copied = _copy_trajectories(trajectories, state_count)
    labels = _resolve_labels(state_count, state_labels)
    options = _resolve_narration_options(narration_options)
    if replicates == 0:
        return {
            "status": "not_requested",
            "replicates": 0,
            "method": "within_trajectory_time_permutation",
            "observational_caveat": _OBSERVATIONAL_CAVEAT,
        }

    observed_gain = observed_endpoint_cp_gain
    if observed_gain is None:
        observed_gain = _evaluate_trajectories(
            copied,
            state_count=state_count,
            state_labels=labels,
            smoothing=smoothing,
            narration_options=options,
            source_kind="trajectory_validation_observed_model",
        )["endpoint_cp_gain"]
    _validate_finite_number(observed_gain, "observed_endpoint_cp_gain")

    rng = random.Random(seed)
    gains: list[float] = []
    failures = 0
    for _ in range(replicates):
        shuffled = [_permute_within_trajectory(trajectory, rng) for trajectory in copied]
        try:
            record = _evaluate_trajectories(
                shuffled,
                state_count=state_count,
                state_labels=labels,
                smoothing=smoothing,
                narration_options=options,
                source_kind="within_trajectory_time_permutation_null",
            )
        except ValueError:
            failures += 1
            continue
        gains.append(record["endpoint_cp_gain"])

    if not gains:
        return {
            "status": "unavailable",
            "method": "within_trajectory_time_permutation",
            "replicates": replicates,
            "successful_replicates": 0,
            "failed_replicates": failures,
            "seed": seed,
            "reason": "No permuted replicate produced a valid finite-state TPM and CE2 analysis.",
            "observational_caveat": _OBSERVATIONAL_CAVEAT,
        }

    exceedances = sum(gain >= observed_gain for gain in gains)
    return {
        "status": "completed",
        "method": "within_trajectory_time_permutation",
        "replicates": replicates,
        "successful_replicates": len(gains),
        "failed_replicates": failures,
        "seed": seed,
        "observed_endpoint_cp_gain": observed_gain,
        "null_endpoint_cp_gains": gains,
        "mean_null_endpoint_cp_gain": sum(gains) / len(gains),
        "empirical_upper_tail_probability": (exceedances + 1) / (len(gains) + 1),
        "preserves": [
            "complete trajectory membership",
            "trajectory lengths",
            "within-trajectory state occupancy",
        ],
        "destroys": ["within-trajectory temporal order", "lagged state dependence"],
        "observational_caveat": _OBSERVATIONAL_CAVEAT,
    }


def grouped_bootstrap_confidence_intervals(
    trajectories: Iterable[Sequence[int]],
    *,
    state_count: int,
    state_labels: Sequence[str] | None = None,
    smoothing: float = 0.0,
    replicates: int = 0,
    seed: int = 0,
    confidence_level: float = 0.95,
    observed_endpoint_cp_gain: float | None = None,
    observed_endpoint_cp: float | None = None,
    narration_options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Estimate percentile intervals by resampling whole trajectories.

    This intentionally does not resample individual rows or transitions.  A
    replicate has the same number of trajectory groups as the observed input,
    sampled with replacement, so within-group serial dependence remains intact.
    """
    _validate_replicates(replicates, "replicates")
    _validate_confidence_level(confidence_level)
    copied = _copy_trajectories(trajectories, state_count)
    labels = _resolve_labels(state_count, state_labels)
    options = _resolve_narration_options(narration_options)
    if replicates == 0:
        return {
            "status": "not_requested",
            "replicates": 0,
            "method": "grouped_trajectory_bootstrap",
            "observational_caveat": _OBSERVATIONAL_CAVEAT,
        }
    if len(copied) < 2:
        return {
            "status": "unavailable",
            "method": "grouped_trajectory_bootstrap",
            "replicates": replicates,
            "reason": "At least two independent trajectories are required for grouped bootstrap resampling.",
            "observational_caveat": _OBSERVATIONAL_CAVEAT,
        }

    if observed_endpoint_cp_gain is None or observed_endpoint_cp is None:
        observed = _evaluate_trajectories(
            copied,
            state_count=state_count,
            state_labels=labels,
            smoothing=smoothing,
            narration_options=options,
            source_kind="trajectory_validation_observed_model",
        )
        if observed_endpoint_cp_gain is None:
            observed_endpoint_cp_gain = observed["endpoint_cp_gain"]
        if observed_endpoint_cp is None:
            observed_endpoint_cp = observed["endpoint_cp"]
    _validate_finite_number(observed_endpoint_cp_gain, "observed_endpoint_cp_gain")
    _validate_finite_number(observed_endpoint_cp, "observed_endpoint_cp")

    rng = random.Random(seed)
    gains: list[float] = []
    endpoint_cps: list[float] = []
    endpoint_ids: Counter[str] = Counter()
    positive_count = 0
    failures = 0
    for _ in range(replicates):
        sampled = [copied[rng.randrange(len(copied))] for _ in copied]
        try:
            record = _evaluate_trajectories(
                sampled,
                state_count=state_count,
                state_labels=labels,
                smoothing=smoothing,
                narration_options=options,
                source_kind="grouped_trajectory_bootstrap",
            )
        except ValueError:
            failures += 1
            continue
        gains.append(record["endpoint_cp_gain"])
        endpoint_cps.append(record["endpoint_cp"])
        endpoint_ids[record["endpoint_partition_id"]] += 1
        if record["has_positive_macro_emergence"]:
            positive_count += 1

    if not gains:
        return {
            "status": "unavailable",
            "method": "grouped_trajectory_bootstrap",
            "replicates": replicates,
            "successful_replicates": 0,
            "failed_replicates": failures,
            "seed": seed,
            "reason": "No bootstrap replicate produced a valid finite-state TPM and CE2 analysis.",
            "observational_caveat": _OBSERVATIONAL_CAVEAT,
        }

    return {
        "status": "completed",
        "method": "grouped_trajectory_bootstrap",
        "resampling_unit": "complete_independent_trajectory",
        "observed_trajectory_count": len(copied),
        "replicates": replicates,
        "successful_replicates": len(gains),
        "failed_replicates": failures,
        "seed": seed,
        "confidence_interval_method": "percentile",
        "confidence_level": confidence_level,
        "endpoint_cp_gain": _interval_summary(gains, observed_endpoint_cp_gain, confidence_level),
        "endpoint_cp": _interval_summary(endpoint_cps, observed_endpoint_cp, confidence_level),
        "positive_macro_emergence_frequency": positive_count / len(gains),
        "endpoint_partition_frequencies": [
            {
                "partition_id": partition_id,
                "count": count,
                "frequency": count / len(gains),
            }
            for partition_id, count in sorted(endpoint_ids.items(), key=lambda item: (-item[1], item[0]))
        ],
        "observational_caveat": _OBSERVATIONAL_CAVEAT,
    }


def compare_macro_assignments(
    left_assignments: Sequence[Any],
    right_assignments: Sequence[Any],
) -> dict[str, Any]:
    """Compare two macro assignments without relying on label identity.

    Pairwise coassignment agreement, adjusted Rand index, and variation of
    information are label-invariant.  The returned dominant-overlap mapping is
    only a deterministic display aid, not the scientific comparison metric.
    """
    left = list(left_assignments)
    right = list(right_assignments)
    if len(left) != len(right):
        raise ValueError("Macro-assignment vectors must have equal length.")
    if len(left) < 2:
        return {
            "status": "unavailable",
            "reason": "At least two shared anchor observations are required for assignment comparison.",
            "anchor_observation_count": len(left),
            "observational_caveat": _OBSERVATIONAL_CAVEAT,
        }

    left_labels = _ordered_unique(left)
    right_labels = _ordered_unique(right)
    contingency: dict[Any, Counter[Any]] = {label: Counter() for label in left_labels}
    for left_label, right_label in zip(left, right):
        contingency[left_label][right_label] += 1

    pairwise = _pairwise_coassignment_agreement(left, right)
    ari = _adjusted_rand_index(left, right, contingency, left_labels, right_labels)
    vi = _variation_of_information_bits(contingency, left_labels, right_labels, len(left))
    mapping = _dominant_overlap_mapping(contingency, left_labels, right_labels, len(left))
    return {
        "status": "completed",
        "anchor_observation_count": len(left),
        "left_macrostate_count": len(left_labels),
        "right_macrostate_count": len(right_labels),
        "pairwise_coassignment_agreement": pairwise,
        "adjusted_rand_index": ari,
        "variation_of_information_bits": vi,
        "dominant_overlap_alignment": mapping,
        "metric_caveat": (
            "The first three metrics are invariant to macrostate-label permutations. "
            "The dominant-overlap mapping is descriptive only and may be many-to-one."
        ),
        "observational_caveat": _OBSERVATIONAL_CAVEAT,
    }


def assess_multiresolution_stability(
    run_assignments: Sequence[Mapping[str, Any]],
    *,
    agreement_threshold: float = 0.8,
) -> dict[str, Any]:
    """Summarize seed stability and cross-resolution alignment on shared anchors.

    Each item requires ``run_id``, ``resolution``, ``seed``, and
    ``macro_assignments``.  The result deliberately reports stability rather
    than treating it as a CE2 acceptance gate.
    """
    if not isinstance(agreement_threshold, (int, float)) or not math.isfinite(agreement_threshold):
        raise ValueError("agreement_threshold must be a finite number.")
    if not 0.0 <= agreement_threshold <= 1.0:
        raise ValueError("agreement_threshold must be in the interval [0, 1].")
    normalized = []
    for index, item in enumerate(run_assignments):
        if not isinstance(item, Mapping):
            raise ValueError(f"run_assignments[{index}] must be a mapping.")
        missing = {"run_id", "resolution", "seed", "macro_assignments"} - set(item)
        if missing:
            raise ValueError(f"run_assignments[{index}] is missing {sorted(missing)}.")
        assignments = list(item["macro_assignments"])
        normalized.append(
            {
                "run_id": str(item["run_id"]),
                "resolution": item["resolution"],
                "seed": item["seed"],
                "macro_assignments": assignments,
            }
        )
    if not normalized:
        return {
            "status": "unavailable",
            "reason": "No resolution-run assignments were supplied.",
            "observational_caveat": _OBSERVATIONAL_CAVEAT,
        }

    anchor_count = len(normalized[0]["macro_assignments"])
    if any(len(item["macro_assignments"]) != anchor_count for item in normalized):
        raise ValueError("Every resolution run must use the same ordered anchor observations.")
    if anchor_count < 2:
        return {
            "status": "unavailable",
            "reason": "At least two shared anchor observations are required for stability assessment.",
            "anchor_observation_count": anchor_count,
            "observational_caveat": _OBSERVATIONAL_CAVEAT,
        }

    pairs = []
    by_resolution: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for left_index, left in enumerate(normalized):
        by_resolution[left["resolution"]].append(left)
        for right in normalized[left_index + 1 :]:
            comparison = compare_macro_assignments(
                left["macro_assignments"], right["macro_assignments"]
            )
            comparison.update(
                {
                    "left_run_id": left["run_id"],
                    "right_run_id": right["run_id"],
                    "left_resolution": left["resolution"],
                    "right_resolution": right["resolution"],
                    "left_seed": left["seed"],
                    "right_seed": right["seed"],
                    "same_resolution": left["resolution"] == right["resolution"],
                }
            )
            pairs.append(comparison)

    per_resolution = []
    for resolution, runs in sorted(by_resolution.items(), key=lambda item: item[0]):
        same_resolution_pairs = [
            pair
            for pair in pairs
            if pair["same_resolution"] and pair["left_resolution"] == resolution
        ]
        if same_resolution_pairs:
            mean_agreement = sum(
                pair["pairwise_coassignment_agreement"] for pair in same_resolution_pairs
            ) / len(same_resolution_pairs)
            mean_ari = sum(pair["adjusted_rand_index"] for pair in same_resolution_pairs) / len(
                same_resolution_pairs
            )
            status = "stable" if mean_agreement >= agreement_threshold else "unstable"
        else:
            mean_agreement = None
            mean_ari = None
            status = "not_assessed_single_seed"
        per_resolution.append(
            {
                "resolution": resolution,
                "seed_count": len(runs),
                "pair_count": len(same_resolution_pairs),
                "mean_pairwise_coassignment_agreement": mean_agreement,
                "mean_adjusted_rand_index": mean_ari,
                "stability_status": status,
            }
        )

    return {
        "status": "completed",
        "anchor_observation_count": anchor_count,
        "agreement_threshold": agreement_threshold,
        "pairwise": pairs,
        "per_resolution_seed_stability": per_resolution,
        "classification_is_acceptance_gate": False,
        "observational_caveat": _OBSERVATIONAL_CAVEAT,
    }


def _copy_trajectories(trajectories: Iterable[Sequence[int]], state_count: int) -> list[list[int]]:
    _validate_state_count(state_count)
    copied: list[list[int]] = []
    for trajectory_index, trajectory in enumerate(trajectories):
        if isinstance(trajectory, (str, bytes)):
            raise ValueError(f"Trajectory {trajectory_index} must be a sequence of state indices, not a string.")
        try:
            states = list(trajectory)
        except TypeError as exc:
            raise ValueError(f"Trajectory {trajectory_index} is not an iterable sequence.") from exc
        for state in states:
            if not isinstance(state, int) or isinstance(state, bool) or not 0 <= state < state_count:
                raise ValueError(
                    f"Trajectory {trajectory_index} contains state {state!r}; expected an integer in [0, {state_count})."
                )
        copied.append(states)
    if not copied:
        raise ValueError("At least one independent trajectory is required.")
    return copied


def _collect_encoded_groups(
    observations: Iterable[tuple[str | None, float | None, Sequence[float]]],
    *,
    encoder: Mapping[str, Any],
    encode: Any,
    trajectory_column: str | None,
    validation_fraction: float,
    split_seed: int,
    selection_scope: str,
    max_gap: float | None,
    split_fn: Any,
) -> list[list[int]]:
    """Collect complete selected trajectory segments from a frozen encoder."""
    groups: list[list[int]] = []
    current_trajectory: str | None | object = _UNSET
    current_states: list[int] = []
    previous_time: float | None = None
    for trajectory_id, timestamp, vector in observations:
        scope = split_fn(
            trajectory_id,
            trajectory_column=trajectory_column,
            validation_fraction=validation_fraction,
            split_seed=split_seed,
        )
        # The streaming estimator always records an ``all`` split in addition
        # to train/validation.  It labels individual rows as ``train`` when no
        # holdout is requested, so the all-data replay must retain every row.
        if selection_scope != "all" and scope != selection_scope:
            continue
        new_trajectory = current_trajectory is _UNSET or trajectory_id != current_trajectory
        gap_break = (
            not new_trajectory
            and max_gap is not None
            and timestamp is not None
            and previous_time is not None
            and timestamp - previous_time > max_gap
        )
        if (new_trajectory or gap_break) and current_states:
            groups.append(current_states)
            current_states = []
        if new_trajectory or gap_break:
            current_trajectory = trajectory_id
        current_states.append(encode(dict(encoder), vector))
        previous_time = timestamp
    if current_states:
        groups.append(current_states)
    if not groups:
        raise ValueError("No encoded trajectories were available in the selected continuous-analysis scope.")
    return groups


def _continuous_narration_options(
    analysis: Mapping[str, Any],
    overrides: Mapping[str, Any] | None,
) -> dict[str, Any]:
    ce2 = analysis.get("ce2", {})
    consistency = ce2.get("dynamical_consistency", {}) if isinstance(ce2, Mapping) else {}
    search = analysis.get("search", {})
    options: dict[str, Any] = {
        "consistency_horizon": consistency.get("horizon", 5),
        "consistency_tolerance": consistency.get("tolerance", 1e-10),
    }
    if isinstance(search, Mapping) and search.get("mode") in {"exact", "beam"}:
        options["search_mode"] = search["mode"]
        for key in ("beam_width", "branching_factor", "max_partition_evaluations"):
            if search.get(key) is not None:
                options[key] = search[key]
    options.update(dict(overrides or {}))
    return _resolve_narration_options(options)


def _resolve_labels(state_count: int, state_labels: Sequence[str] | None) -> list[str]:
    labels = list(state_labels) if state_labels is not None else [f"state_{index}" for index in range(state_count)]
    if len(labels) != state_count:
        raise ValueError("state_labels must contain exactly one label per state.")
    if len(set(labels)) != len(labels):
        raise ValueError("state_labels must be unique.")
    return labels


def _validate_state_count(state_count: int) -> None:
    if not isinstance(state_count, int) or isinstance(state_count, bool) or state_count < 1:
        raise ValueError("state_count must be a positive integer.")


def _validate_replicates(replicates: int, label: str) -> None:
    if not isinstance(replicates, int) or isinstance(replicates, bool) or replicates < 0:
        raise ValueError(f"{label} must be a non-negative integer.")


def _validate_confidence_level(confidence_level: float) -> None:
    if not isinstance(confidence_level, (int, float)) or not math.isfinite(confidence_level):
        raise ValueError("confidence_level must be a finite number in the interval (0, 1).")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be in the interval (0, 1).")


def _validate_finite_number(value: float, label: str) -> None:
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number.")


def _resolve_narration_options(options: Mapping[str, Any] | None) -> dict[str, Any]:
    resolved = dict(options or {})
    unknown = set(resolved) - _NARRATION_OPTION_KEYS
    if unknown:
        raise ValueError(f"Unknown narration option(s): {sorted(unknown)}.")
    return resolved


def _permute_within_trajectory(trajectory: Sequence[int], rng: random.Random) -> list[int]:
    shuffled = list(trajectory)
    rng.shuffle(shuffled)
    return shuffled


def _evaluate_trajectories(
    trajectories: Sequence[Sequence[int]],
    *,
    state_count: int,
    state_labels: Sequence[str],
    smoothing: float,
    narration_options: Mapping[str, Any],
    source_kind: str,
) -> dict[str, Any]:
    counts = _transition_counts(trajectories, state_count)
    estimate = estimate_tpm_from_transition_counts(
        counts,
        state_labels=state_labels,
        trajectory_count=len(trajectories),
        nonempty_trajectory_count=sum(bool(trajectory) for trajectory in trajectories),
        smoothing=smoothing,
        method=source_kind,
    )
    graph = narrate_tpm(
        estimate["tpm"],
        state_labels=state_labels,
        source={
            "kind": source_kind,
            "causal_interpretation": "observational_resampling_validation",
        },
        **dict(narration_options),
    )
    endpoint = graph["ce2"]["endpoint"]
    gain = graph["ce2"]["causal_apportioning"]["endpoint_cp_gain"]
    return {
        "transition_count": estimate["transition_count"],
        "endpoint_partition_id": endpoint["partition_id"],
        "endpoint_cp": endpoint["cp"],
        "endpoint_cp_gain": gain,
        "has_positive_macro_emergence": (
            endpoint["macro_state_count"] < state_count
            and graph["ce2"]["causal_apportioning"]["has_positive_macro_contribution"]
            and gain > narration_options.get("gain_tolerance", 1e-12)
        ),
    }


def _transition_counts(trajectories: Sequence[Sequence[int]], state_count: int) -> list[list[int]]:
    counts = [[0 for _ in range(state_count)] for _ in range(state_count)]
    for trajectory in trajectories:
        for source, target in zip(trajectory, trajectory[1:]):
            counts[source][target] += 1
    return counts


def _interval_summary(values: Sequence[float], observed: float, confidence_level: float) -> dict[str, Any]:
    ordered = sorted(values)
    alpha = (1.0 - confidence_level) / 2.0
    return {
        "observed": observed,
        "replicate_values": list(values),
        "lower": _quantile(ordered, alpha),
        "upper": _quantile(ordered, 1.0 - alpha),
    }


def _quantile(values: Sequence[float], probability: float) -> float | None:
    if not values:
        return None
    position = (len(values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    fraction = position - lower
    return values[lower] * (1.0 - fraction) + values[upper] * fraction


def _ordered_unique(values: Sequence[Any]) -> list[Any]:
    output = []
    for value in values:
        if value not in output:
            output.append(value)
    return output


def _pairwise_coassignment_agreement(left: Sequence[Any], right: Sequence[Any]) -> float:
    total = 0
    matches = 0
    for first in range(len(left)):
        for second in range(first + 1, len(left)):
            total += 1
            matches += (left[first] == left[second]) == (right[first] == right[second])
    return matches / total if total else 0.0


def _combination2(value: int) -> int:
    return value * (value - 1) // 2


def _adjusted_rand_index(
    left: Sequence[Any],
    right: Sequence[Any],
    contingency: Mapping[Any, Counter[Any]],
    left_labels: Sequence[Any],
    right_labels: Sequence[Any],
) -> float:
    total_pairs = _combination2(len(left))
    same_pairs = _pairwise_coassignment_agreement(left, right)
    if total_pairs == 0:
        return 0.0
    index = sum(_combination2(count) for row in contingency.values() for count in row.values())
    left_sum = sum(_combination2(sum(contingency[label].values())) for label in left_labels)
    right_sum = sum(
        _combination2(sum(contingency[left_label][right_label] for left_label in left_labels))
        for right_label in right_labels
    )
    expected = left_sum * right_sum / total_pairs
    maximum = (left_sum + right_sum) / 2.0
    denominator = maximum - expected
    if abs(denominator) <= 1e-15:
        return 1.0 if same_pairs == 1.0 else 0.0
    return (index - expected) / denominator


def _variation_of_information_bits(
    contingency: Mapping[Any, Counter[Any]],
    left_labels: Sequence[Any],
    right_labels: Sequence[Any],
    total: int,
) -> float:
    left_totals = {label: sum(contingency[label].values()) for label in left_labels}
    right_totals = {
        label: sum(contingency[left_label][label] for left_label in left_labels)
        for label in right_labels
    }
    entropy_left = _entropy_bits(left_totals.values(), total)
    entropy_right = _entropy_bits(right_totals.values(), total)
    mutual_information = 0.0
    for left_label in left_labels:
        for right_label, count in contingency[left_label].items():
            if count:
                probability = count / total
                mutual_information += probability * math.log2(
                    count * total / (left_totals[left_label] * right_totals[right_label])
                )
    return max(0.0, entropy_left + entropy_right - 2.0 * mutual_information)


def _entropy_bits(counts: Iterable[int], total: int) -> float:
    return -sum(
        (count / total) * math.log2(count / total)
        for count in counts
        if count > 0
    )


def _dominant_overlap_mapping(
    contingency: Mapping[Any, Counter[Any]],
    left_labels: Sequence[Any],
    right_labels: Sequence[Any],
    total: int,
) -> dict[str, Any]:
    pairs = []
    matched = 0
    for right_label in right_labels:
        candidates = [
            (contingency[left_label][right_label], left_index, left_label)
            for left_index, left_label in enumerate(left_labels)
        ]
        count, _, left_label = max(candidates, key=lambda item: (item[0], -item[1]))
        pairs.append(
            {
                "right_macrostate": right_label,
                "left_macrostate": left_label,
                "anchor_overlap_count": count,
            }
        )
        matched += count
    return {
        "method": "right_to_left_dominant_overlap_not_bijective",
        "mapping": pairs,
        "anchor_overlap_accuracy": matched / total,
    }
