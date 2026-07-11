import json
from pathlib import Path

from causal_emergence_zoo.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_cli_list_prints_known_system(capsys):
    assert main(["list"]) == 0

    output = capsys.readouterr().out

    assert "two_block_noisy_4" in output
    assert "mesoscale_cycle_6" in output


def test_cli_summarize_prints_best_partition(capsys):
    assert main(["summarize", "two_block_noisy_4"]) == 0

    output = capsys.readouterr().out

    assert "best partition: 01|23" in output
    assert "best deltaCP" in output


def test_cli_validate_fixture_by_id(capsys):
    assert main(["validate", "identity_3"]) == 0

    output = capsys.readouterr().out

    assert "PASS identity_3" in output


def test_cli_compare_result_json(tmp_path, capsys):
    result = {
        "benchmark_id": "two_block_noisy_4",
        "microscale": {
            "metrics": {
                "causal_power": 0.265502203205,
            }
        },
        "best_partition": {
            "partition_id": "01|23",
            "blocks": [[0, 1], [2, 3]],
            "deltaCP": 0.265502203206,
        },
    }
    path = tmp_path / "result.json"
    path.write_text(json.dumps(result), encoding="utf-8")

    assert main(["compare", "two_block_noisy_4", str(path)]) == 0

    output = capsys.readouterr().out

    assert "PASS" in output


def test_cli_compare_harmonized_exact_result(tmp_path, capsys):
    result = {
        "benchmark_id": "two_block_noisy_4",
        "algorithm_family": "ce1_partition_ei",
        "input_view": {
            "type": "tpm",
            "intervention_convention": "uniform_microstates",
        },
        "comparison_tier": "exact",
        "macro_maps": [
            {
                "id": "best_map",
                "map_type": "partition",
                "blocks": [[0, 1], [2, 3]],
                "macro_state_count": 2,
            }
        ],
        "scores": [
            {
                "namespace": "zoo.ce1",
                "subject": "best_map",
                "values": {
                    "causal_power": 0.531004406411,
                    "deltaCP": 0.265502203206,
                },
            }
        ],
    }
    path = tmp_path / "harmonized.json"
    path.write_text(json.dumps(result), encoding="utf-8")

    assert main(["compare", "two_block_noisy_4", str(path)]) == 0

    output = capsys.readouterr().out

    assert "exact" in output


def test_cli_compare_equivalent_macro_tier(tmp_path, capsys):
    result = {
        "benchmark_id": "two_block_noisy_4",
        "algorithm_family": "svd_coarse_graining",
        "comparison_tier": "equivalent_macro",
        "macro_maps": [
            {
                "id": "projection_as_partition",
                "map_type": "partition",
                "blocks": [[2, 3], [0, 1]],
                "macro_state_count": 2,
            }
        ],
    }
    path = tmp_path / "equivalent.json"
    path.write_text(json.dumps(result), encoding="utf-8")

    assert main(["compare", "two_block_noisy_4", str(path)]) == 0

    output = capsys.readouterr().out

    assert "equivalent_macro" in output


def test_cli_compare_non_exact_tiers(tmp_path, capsys):
    qualitative = tmp_path / "qualitative.json"
    qualitative.write_text(
        json.dumps(
            {
                "benchmark_id": "mesoscale_cycle_6",
                "algorithm_family": "engineering_emergence",
                "comparison_tier": "qualitative",
                "classification": "mesoscale peak",
            }
        ),
        encoding="utf-8",
    )
    exploratory = tmp_path / "exploratory.json"
    exploratory.write_text(
        json.dumps(
            {
                "benchmark_id": "hierarchical_two_cycle_8",
                "algorithm_family": "engineering_emergence",
                "comparison_tier": "exploratory",
                "scores": [
                    {
                        "namespace": "engineering",
                        "subject": "hierarchy",
                        "values": {"profile": "multiple-path hierarchy"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["compare", "mesoscale_cycle_6", str(qualitative)]) == 0
    assert main(["compare", "hierarchical_two_cycle_8", str(exploratory)]) == 0

    output = capsys.readouterr().out

    assert "qualitative" in output
    assert "exploratory" in output


def test_cli_greedy_prints_best_sampled_partition(capsys):
    assert main(["greedy", "two_block_noisy_4", "--paths", "4", "--branching-factor", "2"]) == 0

    output = capsys.readouterr().out

    assert "greedy search: two_block_noisy_4" in output
    assert "best sampled partition: 01|23" in output
    assert "paths:" in output


def test_cli_exact_requires_numeric_comparison(tmp_path, capsys):
    result = {
        "benchmark_id": "two_block_noisy_4",
        "algorithm_family": "ce1_partition_ei",
        "comparison_tier": "exact",
        "macro_maps": [
            {
                "id": "best_map",
                "map_type": "partition",
                "blocks": [[0, 1], [2, 3]],
                "macro_state_count": 2,
            }
        ],
    }
    path = tmp_path / "structural_only.json"
    path.write_text(json.dumps(result), encoding="utf-8")

    assert main(["compare", "two_block_noisy_4", str(path)]) == 1

    output = capsys.readouterr().out

    assert "requires at least one numeric" in output


def test_cli_compare_schema_validation_catches_invalid_family(tmp_path, capsys):
    result = {
        "benchmark_id": "two_block_noisy_4",
        "algorithm_family": "not_a_family",
        "comparison_tier": "exploratory",
    }
    path = tmp_path / "invalid_schema.json"
    path.write_text(json.dumps(result), encoding="utf-8")

    assert main(["compare", "two_block_noisy_4", str(path)]) == 1

    output = capsys.readouterr().out

    assert "Schema error at algorithm_family" in output


def test_cli_compare_packaged_examples(capsys):
    examples = [
        ("two_block_noisy_4", "implementation-result.example.json"),
        ("preferential_attachment_alpha0_8", "network-ei-result.example.json"),
        ("hierarchical_two_cycle_8", "engineering-emergence-qualitative.example.json"),
        ("hierarchical_two_cycle_8", "engineering-emergence-result.example.json"),
        ("mesoscale_cycle_6", "ce2-multiscale-exploratory.example.json"),
        ("two_block_noisy_4", "svd-equivalent-macro.example.json"),
        ("mesoscale_cycle_6", "rank-agreement.example.json"),
    ]

    for system_id, filename in examples:
        assert main(["compare", system_id, str(ROOT / "examples" / filename)]) == 0

    output = capsys.readouterr().out

    assert output.count("PASS") == len(examples)


def test_cli_narrate_prints_json_narrative_graph(tmp_path, capsys):
    payload = {
        "state_labels": ["A", "B", "C", "D"],
        "trajectories": [
            ["A", "A", "B", "B", "A", "B", "A"],
            ["C", "C", "D", "D", "C", "D", "C"],
        ],
    }
    path = tmp_path / "trajectories.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert main(["narrate", str(path), "--json"]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["analysis_type"] == "ce2_multiscale"
    assert result["status"] == "emergent"
    assert result["selected_macro_model"]["blocks"] == [[0, 1], [2, 3]]


def test_cli_narrate_human_output_and_file_output_agree(tmp_path, capsys):
    payload = {
        "state_labels": ["A", "B", "C"],
        "trajectories": [["A", "A"], ["B", "B"], ["C", "C"]],
    }
    input_path = tmp_path / "identity.json"
    output_path = tmp_path / "narrative.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    assert main(["narrate", str(input_path), "--output", str(output_path)]) == 0

    output = capsys.readouterr().out
    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert "No dynamically consistent coarser model" in output
    assert result["status"] == "no_emergence"


def test_cli_narrate_continuous_emits_json_analysis(tmp_path, capsys):
    path = tmp_path / "continuous.csv"
    path.write_text(
        "trajectory_id,time,signal\n"
        "left,0,0\nleft,1,0\nleft,2,1\nleft,3,1\nleft,4,0\n"
        "right,0,10\nright,1,10\nright,2,11\nright,3,11\nright,4,10\n",
        encoding="utf-8",
    )

    assert main([
        "narrate-continuous",
        str(path),
        "--feature",
        "signal",
        "--microstates",
        "4",
        "--trajectory-column",
        "trajectory_id",
        "--time-column",
        "time",
        "--json",
    ]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["analysis_type"] == "ce2_multiscale_discretized_continuous"
    assert result["input_model"]["source"]["kind"] == "streaming_continuous_csv"
