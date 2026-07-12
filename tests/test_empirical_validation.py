import json
import random

import pytest

from causal_emergence_zoo.continuous import analyze_continuous_csv
from causal_emergence_zoo.empirical_validation import (
    _permute_within_trajectory,
    assess_multiresolution_stability,
    compare_macro_assignments,
    grouped_bootstrap_confidence_intervals,
    trajectory_temporal_permutation_null,
    validate_continuous_analysis_trajectories,
    validate_grouped_trajectories,
)


def _grouped_four_state_trajectories():
    """Independent groups with every encoded state represented repeatedly."""
    return [
        [0, 1, 0, 1, 0, 1],
        [1, 0, 1, 0, 1, 0],
        [2, 3, 2, 3, 2, 3],
        [3, 2, 3, 2, 3, 2],
        [0, 0, 1, 1, 0, 1],
        [2, 2, 3, 3, 2, 3],
    ]


def test_temporal_permutation_preserves_each_trajectory_membership_and_is_seeded():
    trajectories = [[0, 0, 1, 0], [2, 2, 3, 2]]
    rng = random.Random(17)
    shuffled = [_permute_within_trajectory(trajectory, rng) for trajectory in trajectories]

    assert [sorted(trajectory) for trajectory in shuffled] == [
        sorted(trajectory) for trajectory in trajectories
    ]
    assert set(shuffled[0]).isdisjoint(set(shuffled[1]))

    first = trajectory_temporal_permutation_null(
        _grouped_four_state_trajectories(),
        state_count=4,
        smoothing=0.1,
        replicates=4,
        seed=19,
    )
    second = trajectory_temporal_permutation_null(
        _grouped_four_state_trajectories(),
        state_count=4,
        smoothing=0.1,
        replicates=4,
        seed=19,
    )

    assert first == second
    assert first["status"] == "completed"
    assert first["successful_replicates"] == 4
    assert "within-trajectory state occupancy" in first["preserves"]
    assert 0.0 < first["empirical_upper_tail_probability"] <= 1.0
    json.dumps(first, allow_nan=False)


def test_grouped_bootstrap_returns_seeded_percentile_intervals_and_rejects_single_group():
    kwargs = {
        "state_count": 4,
        "smoothing": 0.1,
        "replicates": 6,
        "seed": 23,
        "confidence_level": 0.8,
    }
    first = grouped_bootstrap_confidence_intervals(_grouped_four_state_trajectories(), **kwargs)
    second = grouped_bootstrap_confidence_intervals(_grouped_four_state_trajectories(), **kwargs)

    assert first == second
    assert first["status"] == "completed"
    assert first["resampling_unit"] == "complete_independent_trajectory"
    assert len(first["endpoint_cp_gain"]["replicate_values"]) == 6
    assert first["endpoint_cp_gain"]["lower"] <= first["endpoint_cp_gain"]["upper"]
    assert first["endpoint_cp"]["lower"] <= first["endpoint_cp"]["upper"]

    unavailable = grouped_bootstrap_confidence_intervals(
        [[0, 1, 0, 1]],
        state_count=2,
        smoothing=0.1,
        replicates=3,
    )
    assert unavailable["status"] == "unavailable"
    assert "At least two independent trajectories" in unavailable["reason"]


def test_combined_validation_keeps_the_observational_caveat():
    result = validate_grouped_trajectories(
        _grouped_four_state_trajectories(),
        state_count=4,
        smoothing=0.1,
        temporal_null_replicates=3,
        bootstrap_replicates=3,
        temporal_null_seed=5,
        bootstrap_seed=7,
    )

    assert result["kind"] == "causal_emergence.trajectory_validation"
    assert result["temporal_permutation_null"]["status"] == "completed"
    assert result["grouped_bootstrap"]["status"] == "completed"
    assert "do not identify intervention effects" in result["observational_caveat"]
    json.dumps(result, allow_nan=False)


def test_assignment_alignment_is_invariant_to_macrostate_label_permutations():
    left = [0, 0, 1, 1, 2, 2]
    right = [9, 9, 7, 7, 3, 3]

    comparison = compare_macro_assignments(left, right)

    assert comparison["status"] == "completed"
    assert comparison["pairwise_coassignment_agreement"] == 1.0
    assert comparison["adjusted_rand_index"] == pytest.approx(1.0)
    assert comparison["variation_of_information_bits"] == pytest.approx(0.0)
    assert comparison["dominant_overlap_alignment"]["anchor_overlap_accuracy"] == 1.0


def test_multiresolution_stability_checks_same_resolution_seeds_without_becoming_a_gate():
    result = assess_multiresolution_stability(
        [
            {
                "run_id": "K4:seed0",
                "resolution": 4,
                "seed": 0,
                "macro_assignments": [0, 0, 1, 1, 2, 2],
            },
            {
                "run_id": "K4:seed1",
                "resolution": 4,
                "seed": 1,
                "macro_assignments": [8, 8, 4, 4, 1, 1],
            },
            {
                "run_id": "K6:seed0",
                "resolution": 6,
                "seed": 0,
                "macro_assignments": [0, 0, 0, 1, 1, 1],
            },
        ],
        agreement_threshold=0.9,
    )

    four_state = next(item for item in result["per_resolution_seed_stability"] if item["resolution"] == 4)
    assert result["status"] == "completed"
    assert not result["classification_is_acceptance_gate"]
    assert four_state["stability_status"] == "stable"
    assert four_state["mean_adjusted_rand_index"] == pytest.approx(1.0)
    assert any(not item["same_resolution"] for item in result["pairwise"])


def test_assignment_alignment_rejects_mismatched_anchor_order():
    with pytest.raises(ValueError, match="equal length"):
        compare_macro_assignments([0, 1], [0])


def test_continuous_validation_replays_the_frozen_encoder_without_refitting(tmp_path):
    path = tmp_path / "grouped.csv"
    path.write_text(
        "trajectory_id,time,signal\n"
        "a,0,0\na,1,1\na,2,0\na,3,1\n"
        "b,0,1\nb,1,0\nb,2,1\nb,3,0\n"
        "c,0,0\nc,1,1\nc,2,0\nc,3,1\n",
        encoding="utf-8",
    )
    analysis = analyze_continuous_csv(
        path,
        feature_columns=["signal"],
        microstate_count=2,
        trajectory_column="trajectory_id",
        time_column="time",
        smoothing=0.1,
        random_seed=3,
    )

    validation = validate_continuous_analysis_trajectories(
        path,
        analysis,
        temporal_null_replicates=2,
        temporal_null_seed=13,
        bootstrap_replicates=2,
        bootstrap_seed=17,
    )

    assert validation["continuous_replay"]["frozen_encoder_reused"]
    assert validation["continuous_replay"]["matches_reported_selection_gain"]
    assert validation["temporal_permutation_null"]["status"] == "completed"
    assert validation["grouped_bootstrap"]["status"] == "completed"
