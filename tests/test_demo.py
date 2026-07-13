import json

from causal_emergence_zoo.cli import main
from causal_emergence_zoo.demo import (
    SOCIAL_SYSTEM_DEMO_FEATURE_COLUMNS,
    social_system_demo_metadata,
    social_system_demo_source,
)


def test_bundled_social_system_demo_source_is_repeatable_and_explicitly_synthetic():
    source = social_system_demo_source()
    columns = source.column_names()
    first = list(source.iter_rows(columns))
    second = list(source.iter_rows(columns))
    metadata = social_system_demo_metadata()

    assert first == second
    assert len(first) == metadata["row_count"]
    assert columns == ["country_code", "year", *SOCIAL_SYSTEM_DEMO_FEATURE_COLUMNS]
    assert first[0]["country_code"].startswith("SYN_")
    assert metadata["synthetic"] is True
    assert "not evidence about real countries" in metadata["caveat"]


def test_cli_demo_writes_an_inspectable_html_report_and_json_artifact(tmp_path, capsys):
    report = tmp_path / "social-demo.html"
    output = tmp_path / "social-demo.json"

    assert main(["demo", "--report", str(report), "--output", str(output)]) == 0

    console = capsys.readouterr().out
    payload = json.loads(output.read_text(encoding="utf-8"))
    rendered = report.read_text(encoding="utf-8")

    assert "fictional countries" in console
    assert payload["demo"]["synthetic"] is True
    assert payload["artifacts"]["html_report"] == str(report.resolve())
    assert any(run["endpoint_cp_gain"] > 0.0 for run in payload["analysis"]["resolution_runs"])
    assert "CE by resolution" in rendered
    assert "synthetic and deliberately constructed" in rendered
