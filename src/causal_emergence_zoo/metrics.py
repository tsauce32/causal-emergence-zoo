"""Benchmark metric conventions for finite Markov-chain TPMs."""

from __future__ import annotations

import math

Matrix = list[list[float]]


def entropy_bits(probabilities: list[float]) -> float:
    """Return Shannon entropy in bits, ignoring zero-mass entries."""
    return -sum(p * math.log2(p) for p in probabilities if p > 0.0)


def _assert_square_stochastic(tpm: Matrix, tolerance: float = 1e-9) -> None:
    if not tpm:
        raise ValueError("TPM must contain at least one row.")
    width = len(tpm[0])
    if width != len(tpm):
        raise ValueError("TPM must be square.")
    for row_index, row in enumerate(tpm):
        if len(row) != width:
            raise ValueError("TPM rows must all have the same length.")
        if any(value < -tolerance for value in row):
            raise ValueError(f"TPM row {row_index} contains a negative probability.")
        if abs(sum(row) - 1.0) > tolerance:
            raise ValueError(f"TPM row {row_index} sums to {sum(row):.12f}, not 1.")


def _clean_number(value: float, precision: int | None = None) -> float:
    if precision is not None:
        value = round(value, precision)
    if value == 0.0:
        return 0.0
    return value


def compute_metrics(tpm: Matrix, precision: int | None = None) -> dict[str, float]:
    """Compute the zoo's causal primitive values for a square row-stochastic TPM.

    The convention assumes a uniform distribution over interventions. For one-state
    macro systems the normalized values are defined as zero because log2(1) = 0.
    """
    _assert_square_stochastic(tpm)
    state_count = len(tpm)
    max_entropy = math.log2(state_count) if state_count > 1 else 0.0

    row_entropies = [entropy_bits(row) for row in tpm]
    row_entropy = sum(row_entropies) / state_count
    average_effect = [
        sum(tpm[row][col] for row in range(state_count)) / state_count
        for col in range(state_count)
    ]
    average_effect_entropy = entropy_bits(average_effect)
    effective_information = average_effect_entropy - row_entropy

    if max_entropy == 0.0:
        determinism = 0.0
        specificity = 0.0
        degeneracy = 0.0
        causal_power = 0.0
    else:
        determinism = 1.0 - row_entropy / max_entropy
        specificity = average_effect_entropy / max_entropy
        degeneracy = 1.0 - specificity
        causal_power = effective_information / max_entropy

    metrics = {
        "row_entropy_bits": row_entropy,
        "path_entropy_bits": max_entropy + row_entropy,
        "average_effect_entropy_bits": average_effect_entropy,
        "determinism": determinism,
        "specificity": specificity,
        "degeneracy": degeneracy,
        "effective_information_bits": effective_information,
        "causal_power": causal_power,
    }
    return {key: _clean_number(value, precision) for key, value in metrics.items()}
