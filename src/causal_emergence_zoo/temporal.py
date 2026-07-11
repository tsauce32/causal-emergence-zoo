"""Trajectory-safe temporal feature transformations.

The transformer is intentionally streaming: it retains only the longest declared
window for the current grouped trajectory and never bridges trajectory changes.
"""
from __future__ import annotations

import math
from collections import deque
from collections.abc import Iterable, Iterator, Sequence
from typing import Any


def derive_temporal_features(
    observations: Iterable[tuple[str | None, float | None, Sequence[float]]],
    *,
    feature_names: Sequence[str],
    differences: Sequence[int] = (),
    volatility_windows: Sequence[int] = (),
) -> Iterator[tuple[str | None, float | None, list[float]]]:
    """Append lagged differences and trailing volatility within trajectories.

    Rows lacking enough prior observations are dropped. Inputs must already be
    grouped by trajectory and ordered in time.
    """
    lags = _positive_unique(differences, "differences")
    windows = _positive_unique(volatility_windows, "volatility_windows")
    maximum = max([1, *[lag + 1 for lag in lags], *windows])
    current: str | None | object = object()
    history: deque[list[float]] = deque(maxlen=maximum)
    for trajectory, timestamp, values in observations:
        if trajectory != current:
            current = trajectory
            history.clear()
        vector = [float(value) for value in values]
        sufficient = len(history) >= max([0, *lags, *[window - 1 for window in windows]])
        history.append(vector)
        if not sufficient:
            continue
        output = vector[:]
        prior = list(history)
        for lag in lags:
            reference = prior[-lag - 1]
            output.extend(value - earlier for value, earlier in zip(vector, reference))
        for window in windows:
            selected = prior[-window:]
            for index in range(len(vector)):
                mean = sum(row[index] for row in selected) / window
                output.append(math.sqrt(sum((row[index] - mean) ** 2 for row in selected) / window))
        yield trajectory, timestamp, output


def temporal_feature_names(feature_names: Sequence[str], *, differences: Sequence[int] = (), volatility_windows: Sequence[int] = ()) -> list[str]:
    """Return deterministic names matching :func:`derive_temporal_features`."""
    names = list(feature_names)
    for lag in _positive_unique(differences, "differences"):
        names.extend(f"delta_lag_{lag}:{name}" for name in feature_names)
    for window in _positive_unique(volatility_windows, "volatility_windows"):
        names.extend(f"volatility_window_{window}:{name}" for name in feature_names)
    return names


def _positive_unique(values: Sequence[int], name: str) -> list[int]:
    output = sorted(set(values))
    if any(not isinstance(value, int) or value < 1 for value in output):
        raise ValueError(f"{name} must contain positive integers.")
    return output
