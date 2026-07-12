import json

import pytest

from causal_emergence_zoo.continuous import (
    analyze_continuous_csv,
    count_continuous_csv_transitions,
    encode_continuous_observation,
    fit_continuous_csv_encoder,
    fit_continuous_state_encoder,
)


def _write_two_block_csv(path):
    labels = {"A": 0.0, "B": 1.0, "C": 10.0, "D": 11.0}
    counts = [
        [9, 9, 1, 1],
        [9, 9, 1, 1],
        [1, 1, 9, 9],
        [1, 1, 9, 9],
    ]
    names = ["A", "B", "C", "D"]
    rows = ["trajectory_id,time,signal"]
    trajectory_index = 0
    for source, row in enumerate(counts):
        for target, count in enumerate(row):
            for _ in range(count):
                rows.append(f"t{trajectory_index},0,{labels[names[source]]}")
                rows.append(f"t{trajectory_index},1,{labels[names[target]]}")
                trajectory_index += 1
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_continuous_encoder_is_bounded_and_deterministic():
    observations = [[float(index % 4), float(index)] for index in range(100)]

    first = fit_continuous_state_encoder(
        observations,
        feature_names=["state_like", "trend"],
        microstate_count=4,
        reservoir_size=7,
        random_seed=11,
    )
    second = fit_continuous_state_encoder(
        observations,
        feature_names=["state_like", "trend"],
        microstate_count=4,
        reservoir_size=7,
        random_seed=11,
    )

    assert first == second
    assert first["observations_seen"] == 100
    assert first["reservoir_size_used"] == 7
    assert encode_continuous_observation(first, [0.0, 0.0]) in range(4)
    json.dumps(first, allow_nan=False)


def test_continuous_csv_pipeline_recovers_two_block_model_without_loading_rows(tmp_path):
    path = tmp_path / "continuous.csv"
    _write_two_block_csv(path)

    result = analyze_continuous_csv(
        path,
        feature_columns=["signal"],
        microstate_count=4,
        trajectory_column="trajectory_id",
        time_column="time",
        reservoir_size=1_000,
        random_seed=7,
    )

    all_split = result["continuous_data"]["transitions"]["splits"]["all"]
    assert result["analysis_type"] == "ce2_multiscale_discretized_continuous"
    assert result["status"] == "emergent"
    assert result["ce2"]["endpoint"]["blocks"] == [[0, 1], [2, 3]]
    assert all_split["transition_counts"] == [
        [9, 9, 1, 1],
        [9, 9, 1, 1],
        [1, 1, 9, 9],
        [1, 1, 9, 9],
    ]
    assert all_split["tpm"] == [
        [0.45, 0.45, 0.05, 0.05],
        [0.45, 0.45, 0.05, 0.05],
        [0.05, 0.05, 0.45, 0.45],
        [0.05, 0.05, 0.45, 0.45],
    ]
    assert result["input_model"]["source"]["kind"] == "streaming_continuous_csv"
    assert all(
        "c:continuous_discretization" in claim["caveat_ids"]
        for claim in result["narrative_graph"]["claims"]
    )
    json.dumps(result, allow_nan=False)


def test_continuous_counting_does_not_connect_trajectory_boundaries(tmp_path):
    path = tmp_path / "boundaries.csv"
    path.write_text(
        "trajectory_id,time,signal\n"
        "left,0,0\nleft,1,1\nleft,2,0\n"
        "right,0,10\nright,1,11\nright,2,10\n",
        encoding="utf-8",
    )
    encoder = fit_continuous_csv_encoder(
        path,
        feature_columns=["signal"],
        microstate_count=4,
        trajectory_column="trajectory_id",
        time_column="time",
        reservoir_size=20,
        random_seed=1,
    )
    result = count_continuous_csv_transitions(
        path,
        encoder,
        trajectory_column="trajectory_id",
        time_column="time",
        smoothing=0.5,
        expected_source_signature=encoder["source_signature"],
    )

    counts = result["splits"]["all"]["transition_counts"]
    assert counts[1][2] == 0
    assert sum(sum(row) for row in counts) == 4


def test_continuous_csv_requires_explicit_time_contract_and_stable_source(tmp_path):
    path = tmp_path / "time.csv"
    path.write_text(
        "trajectory_id,time,signal\n"
        "a,0,0\na,1,1\nb,0,10\nb,1,11\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="time_column or explicitly"):
        fit_continuous_csv_encoder(
            path,
            feature_columns=["signal"],
            microstate_count=2,
            trajectory_column="trajectory_id",
        )

    encoder = fit_continuous_csv_encoder(
        path,
        feature_columns=["signal"],
        microstate_count=2,
        trajectory_column="trajectory_id",
        time_column="time",
    )
    with pytest.raises(ValueError, match="does not match"):
        count_continuous_csv_transitions(
            path,
            encoder,
            trajectory_column="trajectory_id",
            time_column="time",
            expected_source_signature={"size_bytes": 0, "modified_time_ns": 0},
        )


def test_continuous_analysis_rejects_more_than_exact_state_budget(tmp_path):
    path = tmp_path / "small.csv"
    path.write_text("time,signal\n0,0\n1,1\n2,0\n", encoding="utf-8")

    with pytest.raises(ValueError, match="at most 8"):
        analyze_continuous_csv(
            path,
            feature_columns=["signal"],
            microstate_count=9,
            time_column="time",
        )


def test_continuous_state_support_can_reject_under_supported_encoder_states(tmp_path):
    path = tmp_path / "support.csv"
    _write_two_block_csv(path)

    with pytest.raises(ValueError, match="support"):
        analyze_continuous_csv(
            path,
            feature_columns=["signal"],
            microstate_count=4,
            trajectory_column="trajectory_id",
            time_column="time",
            minimum_state_observations=10_000,
            support_policy="reject_run",
        )


def test_streaming_csv_retains_only_configured_reservoir_not_all_rows(tmp_path):
    path = tmp_path / "many-rows.csv"
    rows = ["time,signal"]
    rows.extend(f"{index},{float(index % 2)}" for index in range(10_000))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    encoder = fit_continuous_csv_encoder(
        path,
        feature_columns=["signal"],
        microstate_count=2,
        time_column="time",
        reservoir_size=13,
        random_seed=5,
    )
    transitions = count_continuous_csv_transitions(
        path,
        encoder,
        time_column="time",
        expected_source_signature=encoder["source_signature"],
    )

    assert encoder["observations_seen"] == 10_000
    assert encoder["reservoir_size_used"] == 13
    assert transitions["splits"]["all"]["row_count"] == 10_000
    assert transitions["splits"]["all"]["transition_count"] == 9_999


def test_continuous_csv_uses_same_temporal_features_in_both_passes(tmp_path):
    path = tmp_path / "temporal.csv"
    path.write_text("trajectory_id,time,signal\na,0,0\na,1,1\na,2,3\na,3,6\na,4,10\n", encoding="utf-8")

    result = analyze_continuous_csv(
        path,
        feature_columns=["signal"],
        microstate_count=2,
        trajectory_column="trajectory_id",
        time_column="time",
        temporal_differences=[1],
        smoothing=0.1,
    )

    encoder = result["continuous_data"]["discretizer"]
    assert encoder["input_schema"]["derived_feature_columns"] == ["signal", "delta_lag_1:signal"]
    assert result["continuous_data"]["transitions"]["splits"]["all"]["row_count"] == 4


def test_continuous_result_reports_frozen_tpm_predictive_scores(tmp_path):
    path = tmp_path / "predictive.csv"
    _write_two_block_csv(path)
    result = analyze_continuous_csv(
        path,
        feature_columns=["signal"],
        microstate_count=4,
        trajectory_column="trajectory_id",
        time_column="time",
        validation_fraction=0.2,
        split_seed=7,
        smoothing=0.1,
    )
    scores = result["continuous_data"]["predictive_validation"]
    assert scores["selection_micro_tpm"]["status"] == "defined"
    assert scores["validation_micro_tpm"]["status"] == "defined"


def test_continuous_result_can_run_transition_target_null(tmp_path):
    path = tmp_path / "null.csv"
    _write_two_block_csv(path)
    result = analyze_continuous_csv(
        path,
        feature_columns=["signal"],
        microstate_count=4,
        trajectory_column="trajectory_id",
        time_column="time",
        smoothing=0.1,
        null_replicates=2,
        null_seed=11,
    )
    null = result["continuous_data"]["transition_null_validation"]
    assert null["status"] == "completed"
    assert len(null["null_endpoint_cp_gains"]) == 2
