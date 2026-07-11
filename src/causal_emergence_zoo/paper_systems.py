"""Reproducible model systems from Hoel's Causal Emergence 2.0 paper.

The constructors preserve the numerical values behind the rounded figure labels.
They are deliberately separate from empirical estimators: these are reference
systems for regression tests, examples, and comparisons with new algorithms.
"""

from __future__ import annotations

from typing import Any


PAPER_URL = "https://arxiv.org/abs/2503.13395v3"


def figure2_equivalence_class_tpm() -> list[list[float]]:
    """Return the eight-state TPM used for the paper's 0.33 CE example.

    States 0--3 are deterministic self-loops. States 4--7 form one exact
    equivalence class whose effects are uniform over that class.
    """
    tpm = [[0.0] * 8 for _ in range(8)]
    for state in range(4):
        tpm[state][state] = 1.0
    for state in range(4, 8):
        tpm[state][4:] = [0.25] * 4
    return tpm


def figure2_path() -> list[list[list[int]]]:
    """Return a unit-reduction path to Figure 2's five-state endpoint."""
    return [
        [[0], [1], [2], [3], [4], [5], [6], [7]],
        [[0], [1], [2], [3], [4, 5], [6], [7]],
        [[0], [1], [2], [3], [4, 5, 6], [7]],
        [[0], [1], [2], [3], [4, 5, 6, 7]],
    ]


def figure3_top_heavy_tpm() -> list[list[float]]:
    """Return the top-heavy TPM underlying the labels 0.04 and 0.21.

    Values 0.0355 and 0.2145 sum exactly to one across each row and reproduce
    the paper's CP~=0.14, endpoint CP~=0.41, and EC~=1.67 bits.
    """
    within, across = 0.0355, 0.2145
    return (
        [[within] * 4 + [across] * 4 for _ in range(4)]
        + [[across] * 4 + [within] * 4 for _ in range(4)]
    )


def figure3_mesoscale_tpm() -> list[list[float]]:
    """Return the mesoscale TPM underlying the labels 0.00, 0.07, 0.21.

    The plotted labels are rounded. The stochastic values are 1/5 and 1/15.
    States 0 and 4 differ from the other members of their endpoint blocks.
    """
    major, minor = 1.0 / 5.0, 1.0 / 15.0
    return (
        [[major, 0.0, 0.0, 0.0] + [major] * 4]
        + [[0.0, minor, minor, minor] + [major] * 4 for _ in range(3)]
        + [[major] * 4 + [major, 0.0, 0.0, 0.0]]
        + [[major] * 4 + [0.0, minor, minor, minor] for _ in range(3)]
    )


def figure4_block_model_tpm(step: int, *, steps: int = 50) -> list[list[float]]:
    """Return one point on Figure 4's block-model-to-identity manipulation.

    At step zero, every state transitions uniformly within its four-state
    equivalence class. Probability moves linearly from the other three effects
    to the self-loop, reaching the identity TPM at ``step == steps``.
    """
    if not isinstance(step, int) or not isinstance(steps, int):
        raise TypeError("step and steps must be integers.")
    if steps < 1 or not 0 <= step <= steps:
        raise ValueError("Require steps >= 1 and 0 <= step <= steps.")
    progress = step / steps
    other = (1.0 - progress) / 4.0
    self_probability = other + progress
    tpm = [[0.0] * 8 for _ in range(8)]
    for state in range(8):
        block_start = 0 if state < 4 else 4
        for effect in range(block_start, block_start + 4):
            tpm[state][effect] = self_probability if effect == state else other
    return tpm


def ce2_paper_reference_values() -> dict[str, dict[str, Any]]:
    """Published values and their interpretation as regression targets."""
    return {
        "figure2": {
            "micro_cp": 2.0 / 3.0,
            "endpoint_cp": 1.0,
            "causal_emergence": 1.0 / 3.0,
            "endpoint_partition": [[0], [1], [2], [3], [4, 5, 6, 7]],
        },
        "figure3_top_heavy": {
            "micro_cp_rounded": 0.14,
            "endpoint_cp_rounded": 0.41,
            "emergent_complexity_bits_rounded": 1.67,
            "endpoint_partition": [[0, 1, 2, 3], [4, 5, 6, 7]],
        },
        "figure3_mesoscale": {
            "causal_emergence_rounded": 0.13,
            "emergent_complexity_bits_rounded": 2.07,
            "endpoint_partition": [[0, 1, 2, 3], [4, 5, 6, 7]],
            "path_status": "published partition sequence unavailable",
        },
        "figure4": {
            "steps": 50,
            "endpoint_partition": [[0, 1, 2, 3], [4, 5, 6, 7]],
            "initial_ce2": 2.0 / 3.0,
            "final_ce2": 0.0,
        },
    }

