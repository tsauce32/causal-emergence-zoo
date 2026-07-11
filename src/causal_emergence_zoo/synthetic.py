"""Synthetic continuous observations with known multiscale ground truth."""

from __future__ import annotations

import csv
import gzip
import random
from pathlib import Path
from typing import Any


def generate_two_block_continuous_csv(
    path: str | Path,
    *,
    transition_count: int = 100_000,
    noise_standard_deviation: float = 0.08,
    cross_block_probability: float = 0.1,
    seed: int = 0,
) -> dict[str, Any]:
    """Stream independent two-point trajectories from a known four-state TPM."""
    if transition_count < 1:
        raise ValueError("transition_count must be positive.")
    if not 0.0 <= cross_block_probability <= 1.0:
        raise ValueError("cross_block_probability must be between zero and one.")
    if noise_standard_deviation < 0.0:
        raise ValueError("noise_standard_deviation must be non-negative.")
    output = Path(path)
    rng = random.Random(seed)
    centers = [0.0, 1.0, 10.0, 11.0]
    within = (1.0 - cross_block_probability) / 2.0
    across = cross_block_probability / 2.0
    tpm = [
        [within, within, across, across],
        [within, within, across, across],
        [across, across, within, within],
        [across, across, within, within],
    ]
    opener = gzip.open if output.suffix.lower() == ".gz" else open
    with opener(output, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["trajectory_id", "time", "signal"])
        for index in range(transition_count):
            source = rng.randrange(4)
            draw = rng.random()
            cumulative = 0.0
            target = 3
            for candidate, probability in enumerate(tpm[source]):
                cumulative += probability
                if draw <= cumulative:
                    target = candidate
                    break
            writer.writerow([index, 0, centers[source] + rng.gauss(0.0, noise_standard_deviation)])
            writer.writerow([index, 1, centers[target] + rng.gauss(0.0, noise_standard_deviation)])
    return {
        "path": str(output),
        "transition_count": transition_count,
        "row_count": transition_count * 2,
        "seed": seed,
        "ground_truth_tpm": tpm,
        "ground_truth_partition": [[0, 1], [2, 3]],
        "noise_standard_deviation": noise_standard_deviation,
    }
