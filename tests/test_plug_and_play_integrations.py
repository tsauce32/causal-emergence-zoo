import pytest

from causal_emergence_zoo.continuous import analyze_continuous_csv
from causal_emergence_zoo.explore import explore, profile_source
from causal_emergence_zoo.multiresolution import analyze_continuous_multiresolution_csv
from causal_emergence_zoo.synthetic import generate_two_block_continuous_csv


def test_continuous_runner_exposes_opt_in_trajectory_validation_to_the_ledger(tmp_path):
    path = tmp_path / "trajectories.csv"
    generate_two_block_continuous_csv(path, transition_count=300, seed=31)

    result = analyze_continuous_csv(
        path,
        feature_columns=["signal"],
        microstate_count=4,
        trajectory_column="trajectory_id",
        time_column="time",
        smoothing=0.1,
        trajectory_null_replicates=2,
        trajectory_null_seed=5,
        grouped_bootstrap_replicates=3,
        grouped_bootstrap_seed=7,
    )

    continuous = result["continuous_data"]
    assert continuous["trajectory_time_permutation_validation"]["status"] == "completed"
    assert continuous["grouped_bootstrap_validation"]["status"] == "completed"
    assert result["empirical_validation"]["trajectory_resampling"]["continuous_replay"][
        "frozen_encoder_reused"
    ]
    assert result["robustness"]["endpoint_cp_gain_interval"]
    uncertainty = result["evidence_ledger"]["claims"][0]["uncertainty"]
    assert {item["kind"] for item in uncertainty} >= {
        "trajectory_time_permutation_null",
        "grouped_trajectory_bootstrap",
    }


def test_multiresolution_result_reports_label_invariant_seed_stability(tmp_path):
    path = tmp_path / "trajectories.csv"
    generate_two_block_continuous_csv(path, transition_count=300, seed=41)

    result = analyze_continuous_multiresolution_csv(
        path,
        feature_columns=["signal"],
        resolutions=[4],
        encoder_seeds=[2, 3],
        trajectory_column="trajectory_id",
        time_column="time",
        smoothing=0.1,
    )

    stability = result["comparison"]["stability_alignment"]
    assert stability["status"] == "completed"
    assert not stability["classification_is_acceptance_gate"]
    assert stability["per_resolution_seed_stability"][0]["pair_count"] == 1


def test_generic_explore_accepts_a_pandas_dataframe_when_available(tmp_path):
    pandas = pytest.importorskip("pandas")
    path = tmp_path / "trajectories.csv"
    generate_two_block_continuous_csv(path, transition_count=150, seed=51)
    frame = pandas.read_csv(path)

    profile = profile_source(frame)
    result = explore(frame, resolutions=[4], seeds=[3])

    assert profile["source"]["adapter"]["adapter"] == "pandas_dataframe"
    assert not profile["source"]["adapter"]["bounded_memory"]
    assert result["profile"]["source"]["adapter"]["adapter"] == "pandas_dataframe"
