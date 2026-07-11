"""Bounded-memory bridge from continuous CSV observations to small CE 2.0 models.

This module does *not* claim a native continuous-state implementation of Causal
Emergence 2.0.  Instead it learns a frozen, auditable finite-state encoder from a
bounded reservoir sample, streams the full CSV into a small transition-count
matrix, and runs the existing exact finite-state CE 2.0 analysis on that model.

The deliberate contract is two-pass and memory bounded: input rows are never
materialized, while the learned state space is limited to the small cardinality
required by exact partition search.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import math
import random
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Any

from causal_emergence_zoo.ce2 import analyze_ce2_path
from causal_emergence_zoo.estimation import estimate_tpm_from_transition_counts
from causal_emergence_zoo.narrative import narrate_tpm


MAX_EXACT_MICROSTATES = 8
MAX_APPROXIMATE_MICROSTATES = 32


def fit_continuous_state_encoder(
    observations: Iterable[Sequence[float]],
    *,
    feature_names: Sequence[str],
    microstate_count: int,
    reservoir_size: int = 10_000,
    random_seed: int = 0,
    max_iterations: int = 50,
) -> dict[str, Any]:
    """Fit a frozen standardized k-means encoder from a bounded reservoir.

    ``observations`` may be arbitrarily long. Only ``reservoir_size`` vectors
    are retained. Cluster labels are canonicalized by original-unit centroid so
    that subsequent CE partition IDs do not depend on incidental k-means labels.
    """
    names = _validate_feature_names(feature_names)
    _validate_encoder_configuration(microstate_count, reservoir_size, max_iterations)
    rng = random.Random(random_seed)
    reservoir: list[list[float]] = []
    observation_count = 0

    for observation in observations:
        vector = _coerce_vector(observation, len(names), f"observation {observation_count + 1}")
        observation_count += 1
        if len(reservoir) < reservoir_size:
            reservoir.append(vector)
        else:
            replacement_index = rng.randrange(observation_count)
            if replacement_index < reservoir_size:
                reservoir[replacement_index] = vector

    if observation_count == 0:
        raise ValueError("No continuous observations were available to fit an encoder.")
    if observation_count < microstate_count:
        raise ValueError(
            f"microstate_count {microstate_count} exceeds the {observation_count} available observations."
        )
    if len({tuple(vector) for vector in reservoir}) < microstate_count:
        raise ValueError(
            "microstate_count exceeds the number of distinct observations in the reservoir; "
            "reduce microstate_count or increase data diversity."
        )

    means, scales, constant_indices = _zscore_parameters(reservoir)
    standardized = [_standardize(vector, means, scales) for vector in reservoir]
    centroids, iterations = _fit_kmeans(
        standardized,
        microstate_count=microstate_count,
        rng=rng,
        max_iterations=max_iterations,
    )
    original_centroids = [
        [centroid[index] * scales[index] + means[index] for index in range(len(names))]
        for centroid in centroids
    ]
    canonical = sorted(zip(original_centroids, centroids), key=lambda pair: tuple(pair[0]))
    original_centroids = [original for original, _ in canonical]
    centroids = [standardized_centroid for _, standardized_centroid in canonical]

    return {
        "schema_version": "0.1.0",
        "kind": "continuous_state_encoder",
        "algorithm": "reservoir_sample_then_standardized_kmeans",
        "feature_names": names,
        "microstate_count": microstate_count,
        "random_seed": random_seed,
        "max_iterations": max_iterations,
        "iterations": iterations,
        "reservoir_size_requested": reservoir_size,
        "reservoir_size_used": len(reservoir),
        "observations_seen": observation_count,
        "sampling_unit": "observation",
        "feature_means": means,
        "feature_scales": scales,
        "constant_feature_names": [names[index] for index in constant_indices],
        "centroids_standardized": centroids,
        "centroids_original_units": original_centroids,
        "cluster_id_policy": "lexicographic_original_unit_centroids",
        "out_of_reservoir_policy": "assign_nearest_frozen_centroid",
        "resource_contract": {
            "memory_big_o": "O(reservoir_size * feature_count + microstate_count^2)",
            "retains_raw_observations": False,
        },
    }


def encode_continuous_observation(encoder: dict[str, Any], observation: Sequence[float]) -> int:
    """Return the stable nearest-centroid state for one continuous observation."""
    names, means, scales, centroids = _encoder_components(encoder)
    vector = _coerce_vector(observation, len(names), "continuous observation")
    standardized = _standardize(vector, means, scales)
    return _nearest_centroid(standardized, centroids)


def fit_continuous_csv_encoder(
    csv_path: str | Path,
    *,
    feature_columns: Sequence[str],
    microstate_count: int,
    trajectory_column: str | None = None,
    time_column: str | None = None,
    row_order_is_time: bool = False,
    reservoir_size: int = 10_000,
    random_seed: int = 0,
    max_iterations: int = 50,
    validation_fraction: float = 0.0,
    split_seed: int = 0,
) -> dict[str, Any]:
    """Pass 1: stream a grouped CSV and fit a train-only frozen state encoder."""
    _validate_csv_configuration(
        feature_columns=feature_columns,
        trajectory_column=trajectory_column,
        time_column=time_column,
        row_order_is_time=row_order_is_time,
        validation_fraction=validation_fraction,
    )
    path = Path(csv_path)
    signature_before = _source_signature(path)
    row_counts = {"all": 0, "train": 0, "validation": 0}

    def training_observations() -> Iterator[list[float]]:
        for trajectory_id, _, vector in _iter_csv_observations(
            path,
            feature_columns=feature_columns,
            trajectory_column=trajectory_column,
            time_column=time_column,
        ):
            row_counts["all"] += 1
            split = _trajectory_split(
                trajectory_id,
                trajectory_column=trajectory_column,
                validation_fraction=validation_fraction,
                split_seed=split_seed,
            )
            row_counts[split] += 1
            if split == "train":
                yield vector

    encoder = fit_continuous_state_encoder(
        training_observations(),
        feature_names=feature_columns,
        microstate_count=microstate_count,
        reservoir_size=reservoir_size,
        random_seed=random_seed,
        max_iterations=max_iterations,
    )
    signature_after = _source_signature(path)
    if signature_after != signature_before:
        raise ValueError("CSV source changed while fitting the continuous encoder; rerun on a stable file.")

    encoder.update(
        {
            "input_schema": {
                "feature_columns": list(feature_columns),
                "trajectory_column": trajectory_column,
                "time_column": time_column,
                "ordering_assurance": "caller_declared_grouped_by_trajectory",
                "row_order_is_time": row_order_is_time,
            },
            "fit_scope": {
                "split": "train",
                "validation_fraction": validation_fraction,
                "split_seed": split_seed,
                "rows_seen": row_counts,
            },
            "source_signature": signature_before,
        }
    )
    return encoder


def count_continuous_csv_transitions(
    csv_path: str | Path,
    encoder: dict[str, Any],
    *,
    trajectory_column: str | None = None,
    time_column: str | None = None,
    row_order_is_time: bool = False,
    validation_fraction: float = 0.0,
    split_seed: int = 0,
    max_gap: float | None = None,
    smoothing: float = 0.0,
    expected_source_signature: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Pass 2: stream a frozen encoder into train/validation/all TPM counts.

    The input must be grouped by trajectory. Supporting arbitrary interleaved
    trajectory IDs would require retaining state for every active trajectory and
    would violate this module's bounded-memory contract.
    """
    names, _, _, centroids = _encoder_components(encoder)
    _validate_csv_configuration(
        feature_columns=names,
        trajectory_column=trajectory_column,
        time_column=time_column,
        row_order_is_time=row_order_is_time,
        validation_fraction=validation_fraction,
    )
    if max_gap is not None and (
        not isinstance(max_gap, (int, float)) or not math.isfinite(max_gap) or max_gap <= 0
    ):
        raise ValueError("max_gap must be a finite positive number when supplied.")
    if max_gap is not None and time_column is None:
        raise ValueError("max_gap requires a numeric time_column.")

    path = Path(csv_path)
    signature_before = _source_signature(path)
    if expected_source_signature is not None and signature_before != expected_source_signature:
        raise ValueError("CSV source does not match the encoder's pass-1 source signature.")

    state_count = len(centroids)
    labels = [f"microstate_{index}" for index in range(state_count)]
    counts = {scope: [[0 for _ in range(state_count)] for _ in range(state_count)] for scope in _SCOPES}
    observation_counts = {scope: [0 for _ in range(state_count)] for scope in _SCOPES}
    squared_error_sums = {scope: 0.0 for scope in _SCOPES}
    trajectory_counts = {scope: 0 for scope in _SCOPES}
    row_counts = {scope: 0 for scope in _SCOPES}
    gap_breaks = {scope: 0 for scope in _SCOPES}

    previous_trajectory: str | None | object = _UNSET
    previous_state: int | None = None
    previous_time: float | None = None
    previous_scope: str | None = None

    for trajectory_id, timestamp, vector in _iter_csv_observations(
        path,
        feature_columns=names,
        trajectory_column=trajectory_column,
        time_column=time_column,
    ):
        scope = _trajectory_split(
            trajectory_id,
            trajectory_column=trajectory_column,
            validation_fraction=validation_fraction,
            split_seed=split_seed,
        )
        state, squared_error = _encode_with_error(encoder, vector)
        row_counts["all"] += 1
        row_counts[scope] += 1
        observation_counts["all"][state] += 1
        observation_counts[scope][state] += 1
        squared_error_sums["all"] += squared_error
        squared_error_sums[scope] += squared_error

        new_trajectory = previous_trajectory is _UNSET or trajectory_id != previous_trajectory
        gap_break = (
            not new_trajectory
            and max_gap is not None
            and timestamp is not None
            and previous_time is not None
            and timestamp - previous_time > max_gap
        )
        if new_trajectory:
            trajectory_counts["all"] += 1
            trajectory_counts[scope] += 1
        elif gap_break:
            gap_breaks["all"] += 1
            gap_breaks[scope] += 1
        elif previous_state is not None and previous_scope == scope:
            counts["all"][previous_state][state] += 1
            counts[scope][previous_state][state] += 1

        previous_trajectory = trajectory_id
        previous_state = state
        previous_time = timestamp
        previous_scope = scope

    signature_after = _source_signature(path)
    if signature_after != signature_before:
        raise ValueError("CSV source changed while counting transitions; rerun on a stable file.")

    splits = {
        scope: _split_estimate(
            counts[scope],
            labels=labels,
            trajectory_count=trajectory_counts[scope],
            row_count=row_counts[scope],
            smoothing=smoothing,
        )
        for scope in _SCOPES
    }
    for scope in _SCOPES:
        splits[scope].update(
            {
                "state_observation_counts": observation_counts[scope],
                "mean_squared_quantization_error": (
                    squared_error_sums[scope] / row_counts[scope] if row_counts[scope] else None
                ),
                "trajectory_breaks_from_gaps": gap_breaks[scope],
            }
        )

    return {
        "schema_version": "0.1.0",
        "kind": "continuous_csv_transition_estimate",
        "method": "two_pass_streaming_nearest_centroid_markov_estimation",
        "state_labels": labels,
        "microstate_count": state_count,
        "source_signature": {
            "pass_2": signature_before,
            "matches_expected_pass_1": expected_source_signature is None
            or signature_before == expected_source_signature,
        },
        "input_schema": {
            "feature_columns": names,
            "trajectory_column": trajectory_column,
            "time_column": time_column,
            "ordering_assurance": "caller_declared_grouped_by_trajectory",
            "row_order_is_time": row_order_is_time,
        },
        "validation_fraction": validation_fraction,
        "split_seed": split_seed,
        "max_gap": max_gap,
        "smoothing": smoothing,
        "splits": splits,
        "resource_contract": {
            "memory_big_o": "O(microstate_count^2 + feature_count * microstate_count)",
            "retains_raw_observations": False,
        },
    }


def analyze_continuous_csv(
    csv_path: str | Path,
    *,
    feature_columns: Sequence[str],
    microstate_count: int = MAX_EXACT_MICROSTATES,
    trajectory_column: str | None = None,
    time_column: str | None = None,
    row_order_is_time: bool = False,
    reservoir_size: int = 10_000,
    random_seed: int = 0,
    max_iterations: int = 50,
    validation_fraction: float = 0.0,
    split_seed: int = 0,
    max_gap: float | None = None,
    smoothing: float = 0.0,
    consistency_horizon: int = 5,
    consistency_tolerance: float = 1e-10,
    gain_tolerance: float = 1e-12,
    edge_probability_threshold: float = 0.0,
    top_k: int = 10,
    search_mode: str = "exact",
    beam_width: int = 20,
    branching_factor: int = 4,
    minimum_state_observations: int = 0,
    minimum_outgoing_transitions: int = 0,
    support_policy: str = "retain_exploratory",
) -> dict[str, Any]:
    """Run a two-pass, bounded-memory continuous CSV CE 2.0 analysis.

    CE 2.0 endpoint selection occurs on the training split when one is requested;
    any validation and all-data results score the frozen selected path rather
    than rediscovering a new one. This prevents the same data from both selecting
    and validating a narrative.
    """
    if search_mode not in {"exact", "beam", "auto"}:
        raise ValueError("search_mode must be 'exact', 'beam', or 'auto'.")
    resolved_search_mode = "exact" if search_mode == "auto" and microstate_count <= MAX_EXACT_MICROSTATES else ("beam" if search_mode == "auto" else search_mode)
    maximum = MAX_EXACT_MICROSTATES if resolved_search_mode == "exact" else MAX_APPROXIMATE_MICROSTATES
    if microstate_count > maximum:
        raise ValueError(
            f"microstate_count must be at most {maximum} for {resolved_search_mode} CE 2.0 search."
        )
    if microstate_count < 2:
        raise ValueError("microstate_count must be at least 2 for continuous CE 2.0 analysis.")
    if minimum_state_observations < 0 or minimum_outgoing_transitions < 0:
        raise ValueError("minimum support values must be non-negative.")
    if support_policy not in {"retain_exploratory", "reject_run"}:
        raise ValueError("support_policy must be 'retain_exploratory' or 'reject_run'.")

    encoder = fit_continuous_csv_encoder(
        csv_path,
        feature_columns=feature_columns,
        microstate_count=microstate_count,
        trajectory_column=trajectory_column,
        time_column=time_column,
        row_order_is_time=row_order_is_time,
        reservoir_size=reservoir_size,
        random_seed=random_seed,
        max_iterations=max_iterations,
        validation_fraction=validation_fraction,
        split_seed=split_seed,
    )
    transitions = count_continuous_csv_transitions(
        csv_path,
        encoder,
        trajectory_column=trajectory_column,
        time_column=time_column,
        row_order_is_time=row_order_is_time,
        validation_fraction=validation_fraction,
        split_seed=split_seed,
        max_gap=max_gap,
        smoothing=smoothing,
        expected_source_signature=encoder["source_signature"],
    )
    selection_scope = "train" if validation_fraction > 0.0 else "all"
    selection_estimate = transitions["splits"][selection_scope]
    if selection_estimate["status"] != "ready":
        raise ValueError(
            f"The {selection_scope} split cannot support a TPM: {selection_estimate['error']}"
        )
    support = _state_support_audit(
        selection_estimate,
        minimum_state_observations=minimum_state_observations,
        minimum_outgoing_transitions=minimum_outgoing_transitions,
    )
    if support_policy == "reject_run" and not support["is_adequately_supported"]:
        raise ValueError("Learned microstate support is below the configured threshold.")

    source = {
        "kind": "streaming_continuous_csv",
        "causal_interpretation": "model_derived_from_continuous_observations_via_frozen_discretization",
        "selection_scope": selection_scope,
        "continuous_encoder": encoder,
        "transition_estimation": {
            "method": transitions["method"],
            "source_signature": transitions["source_signature"],
            "max_gap": max_gap,
            "smoothing": smoothing,
        },
    }
    narrative = narrate_tpm(
        selection_estimate["tpm"],
        state_labels=transitions["state_labels"],
        max_exhaustive_states=MAX_EXACT_MICROSTATES,
        consistency_horizon=consistency_horizon,
        consistency_tolerance=consistency_tolerance,
        gain_tolerance=gain_tolerance,
        edge_probability_threshold=edge_probability_threshold,
        top_k=top_k,
        search_mode=resolved_search_mode,
        beam_width=beam_width,
        branching_factor=branching_factor,
        source=source,
    )
    selected_path = [step["blocks"] for step in narrative["ce2"]["path"]]
    validation = _score_frozen_path(
        transitions["splits"]["validation"],
        selected_path,
        consistency_horizon=consistency_horizon,
        consistency_tolerance=consistency_tolerance,
        gain_tolerance=gain_tolerance,
    )
    all_data = _score_frozen_path(
        transitions["splits"]["all"],
        selected_path,
        consistency_horizon=consistency_horizon,
        consistency_tolerance=consistency_tolerance,
        gain_tolerance=gain_tolerance,
    )

    narrative["analysis_type"] = "ce2_multiscale_discretized_continuous"
    narrative["search"] = {"mode": resolved_search_mode, "beam_width": beam_width if resolved_search_mode == "beam" else None, "branching_factor": branching_factor if resolved_search_mode == "beam" else None}
    narrative["state_support"] = {**support, "policy": support_policy}
    narrative["input_model"].update(
        {
            "transition_counts": selection_estimate["transition_counts"],
            "outgoing_counts": selection_estimate["outgoing_counts"],
            "continuous_encoder": encoder,
            "streaming_transition_estimate": {
                "selection_scope": selection_scope,
                "state_observation_counts": selection_estimate["state_observation_counts"],
                "mean_squared_quantization_error": selection_estimate[
                    "mean_squared_quantization_error"
                ],
            },
        }
    )
    narrative["continuous_data"] = {
        "discretizer": encoder,
        "transitions": transitions,
        "selection": {
            "scope": selection_scope,
            "selected_path_partition_ids": [step["partition_id"] for step in narrative["ce2"]["path"]],
        },
        "validation": validation,
        "all_data_fixed_path": all_data,
    }
    narrative["robustness"] = {
        "status": "not_requested",
        "note": "Use a future grouped-trajectory or temporal-block resampling workflow for uncertainty; this streaming path does not materialize raw rows.",
    }
    narrative["assumptions"].extend(
        [
            "Continuous observations are represented by nearest assignments to a frozen standardized k-means encoder.",
            "The CSV is grouped by trajectory and ordered by time within each group; arbitrary interleaved trajectory IDs are unsupported in bounded-memory mode.",
            "Exact CE 2.0 is applied to the learned finite-state TPM, conditional on the reported encoder—not directly to the original continuous state space.",
        ]
    )
    narrative["limitations"].extend(
        [
            "Reservoir sampling and Euclidean k-means can change the learned state model; feature scaling, sampling interval, and microstate count are part of the result's evidence.",
            "A near-zero consistency tolerance is strict CE 2.0. Raising it for noisy empirical data produces an approximate exploratory result, not an exact lumpability claim.",
        ]
    )
    return narrative


def _state_support_audit(
    estimate: dict[str, Any],
    *,
    minimum_state_observations: int,
    minimum_outgoing_transitions: int,
) -> dict[str, Any]:
    observation_counts = estimate["state_observation_counts"]
    outgoing_counts = estimate["outgoing_counts"]
    under_supported = [
        index
        for index, (observations, outgoing) in enumerate(zip(observation_counts, outgoing_counts))
        if observations < minimum_state_observations or outgoing < minimum_outgoing_transitions
    ]
    return {
        "minimum_state_observations": minimum_state_observations,
        "minimum_outgoing_transitions": minimum_outgoing_transitions,
        "observation_counts": observation_counts,
        "outgoing_transition_counts": outgoing_counts,
        "under_supported_state_indices": under_supported,
        "is_adequately_supported": not under_supported,
    }


_SCOPES = ("all", "train", "validation")
_UNSET = object()


def _iter_csv_observations(
    path: Path,
    *,
    feature_columns: Sequence[str],
    trajectory_column: str | None,
    time_column: str | None,
) -> Iterator[tuple[str | None, float | None, list[float]]]:
    with _open_csv(path) as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV must include a header row.")
        required = list(feature_columns)
        if trajectory_column:
            required.append(trajectory_column)
        if time_column:
            required.append(time_column)
        missing = [column for column in required if column not in reader.fieldnames]
        if missing:
            raise ValueError(f"CSV is missing required column(s): {', '.join(missing)}.")

        active_trajectory: str | None | object = _UNSET
        previous_time: float | None = None
        for line_number, row in enumerate(reader, start=2):
            trajectory_id = row[trajectory_column] if trajectory_column else None
            if trajectory_column and not trajectory_id:
                raise ValueError(f"CSV line {line_number} has an empty trajectory identifier.")
            timestamp = None
            if time_column:
                timestamp = _coerce_number(row[time_column], f"CSV line {line_number}, column {time_column!r}")
                if trajectory_id != active_trajectory:
                    active_trajectory = trajectory_id
                    previous_time = None
                if previous_time is not None and timestamp <= previous_time:
                    raise ValueError(
                        f"CSV line {line_number} is not strictly increasing in {time_column!r} within its trajectory."
                    )
                previous_time = timestamp
            vector = [
                _coerce_number(row[column], f"CSV line {line_number}, column {column!r}")
                for column in feature_columns
            ]
            yield trajectory_id, timestamp, vector


def _open_csv(path: Path):
    if not path.is_file():
        raise FileNotFoundError(f"CSV file not found: {path}")
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return path.open("r", encoding="utf-8", newline="")


def _source_signature(path: Path) -> dict[str, int]:
    if not path.is_file():
        raise FileNotFoundError(f"CSV file not found: {path}")
    stat = path.stat()
    return {"size_bytes": stat.st_size, "modified_time_ns": stat.st_mtime_ns}


def _trajectory_split(
    trajectory_id: str | None,
    *,
    trajectory_column: str | None,
    validation_fraction: float,
    split_seed: int,
) -> str:
    if validation_fraction == 0.0 or trajectory_column is None:
        return "train"
    digest = hashlib.sha256(f"{split_seed}:{trajectory_id}".encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big") / 2**64
    return "validation" if value < validation_fraction else "train"


def _split_estimate(
    counts: list[list[int]],
    *,
    labels: list[str],
    trajectory_count: int,
    row_count: int,
    smoothing: float,
) -> dict[str, Any]:
    transition_count = sum(sum(row) for row in counts)
    if transition_count == 0:
        return {
            "status": "unavailable",
            "error": "No within-trajectory transitions were available for this split.",
            "transition_counts": counts,
            "trajectory_count": trajectory_count,
            "row_count": row_count,
            "transition_count": 0,
        }
    try:
        estimate = estimate_tpm_from_transition_counts(
            counts,
            state_labels=labels,
            trajectory_count=trajectory_count,
            nonempty_trajectory_count=trajectory_count,
            smoothing=smoothing,
            method="streaming_empirical_first_order_markov",
        )
    except ValueError as exc:
        return {
            "status": "unavailable",
            "error": str(exc),
            "transition_counts": counts,
            "trajectory_count": trajectory_count,
            "row_count": row_count,
            "transition_count": transition_count,
        }
    estimate["status"] = "ready"
    estimate["row_count"] = row_count
    return estimate


def _score_frozen_path(
    split_estimate: dict[str, Any],
    path: list[list[list[int]]],
    *,
    consistency_horizon: int,
    consistency_tolerance: float,
    gain_tolerance: float,
) -> dict[str, Any]:
    if split_estimate["status"] != "ready":
        return {
            "status": "unavailable",
            "reason": split_estimate["error"],
        }
    analysis = analyze_ce2_path(
        split_estimate["tpm"],
        path,
        consistency_horizon=consistency_horizon,
        consistency_tolerance=consistency_tolerance,
        gain_tolerance=gain_tolerance,
    )
    return {
        "status": "completed" if analysis["validity"]["is_valid"] else "path_not_reproduced",
        "analysis": analysis,
    }


def _validate_feature_names(feature_names: Sequence[str]) -> list[str]:
    names = list(feature_names)
    if not names:
        raise ValueError("At least one continuous feature column is required.")
    if any(not isinstance(name, str) or not name.strip() for name in names):
        raise ValueError("feature names must be non-empty strings.")
    if len(set(names)) != len(names):
        raise ValueError("feature names must be unique.")
    return names


def _validate_encoder_configuration(
    microstate_count: int,
    reservoir_size: int,
    max_iterations: int,
) -> None:
    if not isinstance(microstate_count, int) or isinstance(microstate_count, bool) or microstate_count < 1:
        raise ValueError("microstate_count must be a positive integer.")
    if not isinstance(reservoir_size, int) or isinstance(reservoir_size, bool) or reservoir_size < 1:
        raise ValueError("reservoir_size must be a positive integer.")
    if not isinstance(max_iterations, int) or isinstance(max_iterations, bool) or max_iterations < 1:
        raise ValueError("max_iterations must be a positive integer.")


def _validate_csv_configuration(
    *,
    feature_columns: Sequence[str],
    trajectory_column: str | None,
    time_column: str | None,
    row_order_is_time: bool,
    validation_fraction: float,
) -> None:
    _validate_feature_names(feature_columns)
    if not isinstance(row_order_is_time, bool):
        raise ValueError("row_order_is_time must be a boolean.")
    if trajectory_column is not None and (not isinstance(trajectory_column, str) or not trajectory_column):
        raise ValueError("trajectory_column must be a non-empty string when supplied.")
    if time_column is not None and (not isinstance(time_column, str) or not time_column):
        raise ValueError("time_column must be a non-empty string when supplied.")
    if time_column is None and not row_order_is_time:
        raise ValueError("Provide time_column or explicitly set row_order_is_time=True.")
    if not isinstance(validation_fraction, (int, float)) or not 0.0 <= validation_fraction < 1.0:
        raise ValueError("validation_fraction must be in the interval [0, 1).")


def _coerce_number(value: object, context: str) -> float:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError(f"{context} is missing.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context} is not numeric.") from exc
    if not math.isfinite(number):
        raise ValueError(f"{context} must be finite.")
    return number


def _coerce_vector(values: Sequence[float], dimension: int, context: str) -> list[float]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{context} must be a numeric feature vector, not a string.")
    try:
        vector = list(values)
    except TypeError as exc:
        raise ValueError(f"{context} is not a feature vector.") from exc
    if len(vector) != dimension:
        raise ValueError(f"{context} has {len(vector)} features; expected {dimension}.")
    return [_coerce_number(value, context) for value in vector]


def _zscore_parameters(vectors: list[list[float]]) -> tuple[list[float], list[float], list[int]]:
    dimension = len(vectors[0])
    means = [sum(vector[index] for vector in vectors) / len(vectors) for index in range(dimension)]
    variances = [
        sum((vector[index] - means[index]) ** 2 for vector in vectors) / len(vectors)
        for index in range(dimension)
    ]
    scales = [math.sqrt(variance) for variance in variances]
    constant_indices = [index for index, scale in enumerate(scales) if scale <= 1e-15]
    scales = [scale if scale > 1e-15 else 1.0 for scale in scales]
    return means, scales, constant_indices


def _standardize(vector: list[float], means: list[float], scales: list[float]) -> list[float]:
    return [(value - means[index]) / scales[index] for index, value in enumerate(vector)]


def _fit_kmeans(
    points: list[list[float]],
    *,
    microstate_count: int,
    rng: random.Random,
    max_iterations: int,
) -> tuple[list[list[float]], int]:
    centroids = _kmeans_plus_plus(points, microstate_count, rng)
    dimension = len(points[0])
    for iteration in range(1, max_iterations + 1):
        assignments = [_nearest_centroid(point, centroids) for point in points]
        counts = [0] * microstate_count
        sums = [[0.0] * dimension for _ in range(microstate_count)]
        for point, assignment in zip(points, assignments):
            counts[assignment] += 1
            for index, value in enumerate(point):
                sums[assignment][index] += value

        new_centroids = [centroid[:] for centroid in centroids]
        nonempty = [index for index, count in enumerate(counts) if count]
        for cluster in nonempty:
            new_centroids[cluster] = [value / counts[cluster] for value in sums[cluster]]
        for cluster, count in enumerate(counts):
            if count == 0:
                replacement = _farthest_point(points, [new_centroids[index] for index in nonempty])
                new_centroids[cluster] = replacement[:]
                nonempty.append(cluster)

        shift = max(
            _squared_distance(old, new)
            for old, new in zip(centroids, new_centroids)
        )
        centroids = new_centroids
        if shift <= 1e-18:
            return centroids, iteration
    return centroids, max_iterations


def _kmeans_plus_plus(points: list[list[float]], count: int, rng: random.Random) -> list[list[float]]:
    first_index = rng.randrange(len(points))
    centroids = [points[first_index][:]]
    selected = {first_index}
    while len(centroids) < count:
        distances = [min(_squared_distance(point, centroid) for centroid in centroids) for point in points]
        total = sum(distances)
        if total <= 0.0:
            next_index = next(index for index in range(len(points)) if index not in selected)
        else:
            threshold = rng.random() * total
            cumulative = 0.0
            next_index = len(points) - 1
            for index, distance in enumerate(distances):
                cumulative += distance
                if cumulative >= threshold and index not in selected:
                    next_index = index
                    break
            if next_index in selected:
                next_index = max(
                    (index for index in range(len(points)) if index not in selected),
                    key=lambda index: distances[index],
                )
        selected.add(next_index)
        centroids.append(points[next_index][:])
    return centroids


def _nearest_centroid(point: list[float], centroids: list[list[float]]) -> int:
    return min(range(len(centroids)), key=lambda index: (_squared_distance(point, centroids[index]), index))


def _farthest_point(points: list[list[float]], centroids: list[list[float]]) -> list[float]:
    if not centroids:
        return points[0]
    return max(
        points,
        key=lambda point: min(_squared_distance(point, centroid) for centroid in centroids),
    )


def _squared_distance(left: list[float], right: list[float]) -> float:
    return sum((a - b) ** 2 for a, b in zip(left, right))


def _encoder_components(
    encoder: dict[str, Any],
) -> tuple[list[str], list[float], list[float], list[list[float]]]:
    if encoder.get("kind") != "continuous_state_encoder":
        raise ValueError("encoder must be a continuous_state_encoder result.")
    names = _validate_feature_names(encoder.get("feature_names", []))
    means = _coerce_vector(encoder.get("feature_means", []), len(names), "encoder feature_means")
    scales = _coerce_vector(encoder.get("feature_scales", []), len(names), "encoder feature_scales")
    if any(scale <= 0.0 for scale in scales):
        raise ValueError("encoder feature_scales must be positive.")
    raw_centroids = encoder.get("centroids_standardized", [])
    if not isinstance(raw_centroids, list) or not raw_centroids:
        raise ValueError("encoder must contain at least one standardized centroid.")
    centroids = [
        _coerce_vector(centroid, len(names), f"encoder centroid {index}")
        for index, centroid in enumerate(raw_centroids)
    ]
    return names, means, scales, centroids


def _encode_with_error(encoder: dict[str, Any], vector: list[float]) -> tuple[int, float]:
    names, means, scales, centroids = _encoder_components(encoder)
    standardized = _standardize(_coerce_vector(vector, len(names), "continuous observation"), means, scales)
    state = _nearest_centroid(standardized, centroids)
    return state, _squared_distance(standardized, centroids[state])
