import json

from causal_emergence_zoo.cli import main


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
