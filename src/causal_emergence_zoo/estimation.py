"""Estimate discrete first-order Markov models from independent trajectories.

The functions in this module deliberately distinguish observed trajectories from
interventional causal models.  They estimate a transition model that can then be
*treated* as a causal model only when the caller accepts the relevant modeling
assumptions.  Those assumptions are carried into the narrative result.
"""

from __future__ import annotations

import json
import math
from collections.abc import Hashable, Iterable, Sequence
from typing import Any


State = Hashable
Trajectory = Sequence[State]


def materialize_trajectories(trajectories: Iterable[Trajectory]) -> list[list[State]]:
    """Validate and copy independent trajectories without joining their ends."""
    copied: list[list[State]] = []
    for index, trajectory in enumerate(trajectories):
        if isinstance(trajectory, (str, bytes)):
            raise ValueError(f"Trajectory {index} must be a sequence of states, not a string.")
        try:
            states = list(trajectory)
        except TypeError as exc:
            raise ValueError(f"Trajectory {index} is not an iterable sequence of states.") from exc
        for state in states:
            try:
                hash(state)
            except TypeError as exc:
                raise ValueError(f"State {state!r} in trajectory {index} is not hashable.") from exc
        copied.append(states)

    if not copied:
        raise ValueError("At least one trajectory is required.")
    return copied


def estimate_tpm_from_trajectories(
    trajectories: Iterable[Trajectory],
    *,
    state_labels: Sequence[State] | None = None,
    smoothing: float = 0.0,
    precision: int | None = None,
) -> dict[str, Any]:
    """Estimate a row-stochastic TPM from independent discrete trajectories.

    Each inner trajectory is independent: the final state of one trajectory is
    never connected to the first state of the next.  When ``state_labels`` is
    omitted, labels are ordered by first appearance.  Supplying labels makes the
    state space explicit and stable across data subsets.

    ``smoothing`` is additive (Laplace-style) smoothing per target state.  With
    zero smoothing, a state with no observed outgoing transition is rejected
    rather than silently assigned invented dynamics.
    """
    if not isinstance(smoothing, (int, float)) or not math.isfinite(smoothing) or smoothing < 0:
        raise ValueError("smoothing must be a finite non-negative number.")

    copied = materialize_trajectories(trajectories)
    labels = _resolve_state_labels(copied, state_labels)
    label_index = {label: index for index, label in enumerate(labels)}
    state_count = len(labels)
    counts = [[0 for _ in range(state_count)] for _ in range(state_count)]
    transition_count = 0

    for trajectory in copied:
        for source, target in zip(trajectory, trajectory[1:]):
            counts[label_index[source]][label_index[target]] += 1
            transition_count += 1

    if transition_count == 0:
        raise ValueError("At least one within-trajectory transition is required.")

    return estimate_tpm_from_transition_counts(
        counts,
        state_labels=labels,
        trajectory_count=len(copied),
        nonempty_trajectory_count=sum(bool(trajectory) for trajectory in copied),
        smoothing=smoothing,
        precision=precision,
    )


def estimate_tpm_from_transition_counts(
    transition_counts: Sequence[Sequence[int]],
    *,
    state_labels: Sequence[State],
    trajectory_count: int,
    nonempty_trajectory_count: int | None = None,
    smoothing: float = 0.0,
    precision: int | None = None,
    method: str = "empirical_first_order_markov",
) -> dict[str, Any]:
    """Build a TPM estimate from pre-aggregated within-trajectory transition counts.

    This is the bounded-memory counterpart to
    :func:`estimate_tpm_from_trajectories`.  Callers that ingest a very large
    dataset can keep only the state-by-state count matrix in memory and supply
    their aggregate counts here.
    """
    if not isinstance(smoothing, (int, float)) or not math.isfinite(smoothing) or smoothing < 0:
        raise ValueError("smoothing must be a finite non-negative number.")
    if not isinstance(trajectory_count, int) or trajectory_count < 0:
        raise ValueError("trajectory_count must be a non-negative integer.")
    if nonempty_trajectory_count is not None and (
        not isinstance(nonempty_trajectory_count, int) or nonempty_trajectory_count < 0
    ):
        raise ValueError("nonempty_trajectory_count must be a non-negative integer.")
    if not method:
        raise ValueError("method must be a non-empty string.")

    labels = _validate_state_labels(state_labels)
    state_count = len(labels)
    counts = _validate_transition_counts(transition_counts, state_count)
    transition_count = sum(sum(row) for row in counts)
    if transition_count == 0:
        raise ValueError("At least one within-trajectory transition is required.")

    outgoing_counts = [sum(row) for row in counts]
    missing_sources = [labels[index] for index, count in enumerate(outgoing_counts) if count == 0]
    if missing_sources and smoothing == 0:
        rendered = ", ".join(repr(label) for label in missing_sources)
        raise ValueError(
            "Cannot estimate a row-stochastic TPM: no outgoing transitions were observed "
            f"for {rendered}. Supply positive smoothing or remove terminal-only states."
        )

    tpm: list[list[float]] = []
    for row, total in zip(counts, outgoing_counts):
        denominator = total + smoothing * state_count
        probabilities = [(count + smoothing) / denominator for count in row]
        if precision is not None:
            probabilities = [round(value, precision) for value in probabilities]
        tpm.append(probabilities)

    return {
        "method": method,
        "state_labels": list(labels),
        "tpm": tpm,
        "transition_counts": counts,
        "outgoing_counts": outgoing_counts,
        "trajectory_count": trajectory_count,
        "nonempty_trajectory_count": (
            trajectory_count if nonempty_trajectory_count is None else nonempty_trajectory_count
        ),
        "transition_count": transition_count,
        "smoothing": smoothing,
        "assumptions": [
            "Each supplied sequence is an independent first-order discrete trajectory.",
            "Observed transition frequencies estimate conditional dynamics.",
            "Observed trajectories alone do not establish intervention effects or real-world causation.",
        ],
    }


def _resolve_state_labels(
    trajectories: list[list[State]],
    state_labels: Sequence[State] | None,
) -> list[State]:
    if state_labels is None:
        labels: list[State] = []
        seen: set[State] = set()
        for trajectory in trajectories:
            for state in trajectory:
                if state not in seen:
                    seen.add(state)
                    labels.append(state)
        if not labels:
            raise ValueError("At least one state is required.")
        _assert_json_serializable_labels(labels)
        return labels

    labels = list(state_labels)
    labels = _validate_state_labels(labels)
    known = set(labels)
    unknown = [
        state
        for trajectory in trajectories
        for state in trajectory
        if state not in known
    ]
    if unknown:
        raise ValueError(f"Trajectory contains state {unknown[0]!r} absent from state_labels.")
    return labels


def _validate_state_labels(state_labels: Sequence[State]) -> list[State]:
    labels = list(state_labels)
    if not labels:
        raise ValueError("state_labels must contain at least one state.")
    try:
        if len(set(labels)) != len(labels):
            raise ValueError("state_labels must be unique.")
    except TypeError as exc:
        raise ValueError("state_labels must be hashable.") from exc

    _assert_json_serializable_labels(labels)
    return labels


def _validate_transition_counts(
    transition_counts: Sequence[Sequence[int]],
    state_count: int,
) -> list[list[int]]:
    counts = [list(row) for row in transition_counts]
    if len(counts) != state_count:
        raise ValueError("transition_counts must have one row per state label.")
    for row_index, row in enumerate(counts):
        if len(row) != state_count:
            raise ValueError("transition_counts must be square over state_labels.")
        for value in row:
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(
                    f"transition_counts row {row_index} must contain non-negative integer counts."
                )
    return counts


def _assert_json_serializable_labels(labels: list[State]) -> None:
    try:
        json.dumps(labels, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("state labels must be JSON serializable finite values.") from exc
