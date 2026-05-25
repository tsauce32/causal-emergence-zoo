"""Coarse-graining helpers for finite TPM benchmarks."""

from __future__ import annotations

from causal_emergence_zoo.metrics import Matrix


def coarse_grain_tpm(tpm: Matrix, partition: list[list[int]], precision: int | None = None) -> Matrix:
    """Return the macro TPM induced by a partition.

    Each macro intervention is represented by a uniform intervention over the
    microstates in that macro block, followed by summing target probability mass
    into macro target blocks.
    """
    state_count = len(tpm)
    seen = sorted(state for block in partition for state in block)
    if seen != list(range(state_count)):
        raise ValueError("Partition must cover every state exactly once.")
    macro_tpm: Matrix = []
    for source_block in partition:
        row = []
        for target_block in partition:
            probability = sum(
                tpm[source_state][target_state]
                for source_state in source_block
                for target_state in target_block
            ) / len(source_block)
            row.append(round(probability, precision) if precision is not None else probability)
        macro_tpm.append(row)
    return macro_tpm
