import pytest

from causal_emergence_zoo.estimation import estimate_tpm_from_trajectories


def test_estimation_counts_only_within_independent_trajectories():
    result = estimate_tpm_from_trajectories(
        [["a", "b", "a"], ["c", "d", "c"]],
        state_labels=["a", "b", "c", "d"],
    )

    assert result["transition_counts"] == [
        [0, 1, 0, 0],
        [1, 0, 0, 0],
        [0, 0, 0, 1],
        [0, 0, 1, 0],
    ]
    assert result["tpm"][1][2] == 0.0
    assert result["transition_count"] == 4


def test_estimation_rejects_terminal_only_rows_without_smoothing():
    with pytest.raises(ValueError, match="no outgoing transitions"):
        estimate_tpm_from_trajectories(
            [["a", "b"]],
            state_labels=["a", "b"],
        )


def test_estimation_uses_additive_smoothing_for_terminal_only_rows():
    result = estimate_tpm_from_trajectories(
        [["a", "b"]],
        state_labels=["a", "b"],
        smoothing=0.5,
    )

    assert result["tpm"] == [[0.25, 0.75], [0.5, 0.5]]


def test_estimation_rejects_invalid_smoothing_and_unknown_state_labels():
    with pytest.raises(ValueError, match="finite non-negative"):
        estimate_tpm_from_trajectories([["a", "a"]], smoothing=-0.1)
    with pytest.raises(ValueError, match="absent from state_labels"):
        estimate_tpm_from_trajectories([["a", "b"]], state_labels=["a"])
