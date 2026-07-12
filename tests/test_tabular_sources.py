import json

import pytest

from causal_emergence_zoo.continuous import (
    analyze_continuous_csv,
    count_continuous_csv_transitions,
    fit_continuous_csv_encoder,
)
from causal_emergence_zoo.multiresolution import analyze_continuous_multiresolution_csv
from causal_emergence_zoo.tabular import adapt_continuous_source, describe_continuous_source


def _frame_data():
    return {
        "trajectory_id": ["left", "left", "left", "right", "right", "right"],
        "time": [0, 1, 2, 0, 1, 2],
        "signal": [0.0, 1.0, 0.0, 10.0, 11.0, 10.0],
    }


def test_pandas_dataframe_runs_through_the_existing_continuous_pipeline():
    pandas = pytest.importorskip("pandas")
    frame = pandas.DataFrame(_frame_data())

    encoder = fit_continuous_csv_encoder(
        frame,
        feature_columns=["signal"],
        microstate_count=2,
        trajectory_column="trajectory_id",
        time_column="time",
        reservoir_size=20,
        random_seed=3,
    )
    transitions = count_continuous_csv_transitions(
        frame,
        encoder,
        trajectory_column="trajectory_id",
        time_column="time",
        smoothing=0.1,
        expected_source_signature=encoder["source_signature"],
    )
    analysis = analyze_continuous_csv(
        frame,
        feature_columns=["signal"],
        microstate_count=2,
        trajectory_column="trajectory_id",
        time_column="time",
        reservoir_size=20,
        random_seed=3,
        smoothing=0.1,
    )

    descriptor = encoder["input_schema"]["source_adapter"]
    assert descriptor["adapter"] == "pandas_dataframe"
    assert not descriptor["bounded_memory"]
    assert transitions["splits"]["all"]["transition_count"] == 4
    assert analysis["continuous_data"]["transitions"]["input_schema"]["source_adapter"] == descriptor
    json.dumps(analysis, allow_nan=False)


def test_dataframe_source_flows_through_multiresolution_without_a_csv_path():
    pandas = pytest.importorskip("pandas")
    frame = pandas.DataFrame(_frame_data())

    result = analyze_continuous_multiresolution_csv(
        frame,
        feature_columns=["signal"],
        resolutions=[2],
        encoder_seeds=[2],
        trajectory_column="trajectory_id",
        time_column="time",
        reservoir_size=20,
        smoothing=0.1,
    )

    run = result["resolution_runs"][0]["result"]
    assert run["continuous_data"]["discretizer"]["input_schema"]["source_adapter"]["adapter"] == "pandas_dataframe"


def test_csv_adapter_retains_bounded_memory_semantics(tmp_path):
    path = tmp_path / "observations.csv"
    path.write_text("time,signal\n0,0\n1,1\n", encoding="utf-8")

    source = adapt_continuous_source(path)

    assert source.descriptor()["adapter"] == "csv_path"
    assert source.descriptor()["bounded_memory"]
    assert describe_continuous_source(path)["memory_semantics"] == "streaming_two_pass"
    assert list(source.iter_rows(["time", "signal"])) == [
        {"time": "0", "signal": "0"},
        {"time": "1", "signal": "1"},
    ]


def test_polars_dataframe_adapter_when_polars_is_available():
    polars = pytest.importorskip("polars")
    frame = polars.DataFrame(_frame_data())

    source = adapt_continuous_source(frame)

    assert source.descriptor()["adapter"] == "polars_dataframe"
    assert list(source.iter_rows(["trajectory_id", "time"]))[0] == {
        "trajectory_id": "left",
        "time": 0,
    }


def test_parquet_path_streams_with_arrow_when_available(tmp_path):
    pyarrow = pytest.importorskip("pyarrow")
    parquet = pytest.importorskip("pyarrow.parquet")
    table = pyarrow.table(_frame_data())
    path = tmp_path / "observations.parquet"
    parquet.write_table(table, path)

    source = adapt_continuous_source(path)
    encoder = fit_continuous_csv_encoder(
        source,
        feature_columns=["signal"],
        microstate_count=2,
        trajectory_column="trajectory_id",
        time_column="time",
        reservoir_size=20,
        random_seed=3,
    )
    transitions = count_continuous_csv_transitions(
        source,
        encoder,
        trajectory_column="trajectory_id",
        time_column="time",
        smoothing=0.1,
        expected_source_signature=encoder["source_signature"],
    )
    analysis = analyze_continuous_csv(
        path,
        feature_columns=["signal"],
        microstate_count=2,
        trajectory_column="trajectory_id",
        time_column="time",
        reservoir_size=20,
        random_seed=3,
        smoothing=0.1,
    )

    assert source.descriptor()["adapter"] == "parquet_path"
    assert source.descriptor()["bounded_memory"]
    assert transitions["splits"]["all"]["transition_count"] == 4
    assert (
        analysis["continuous_data"]["discretizer"]["input_schema"]["source_adapter"]
        ["adapter"]
        == "parquet_path"
    )
