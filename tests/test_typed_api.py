import json

import pytest

import causal_emergence_zoo as cez
from causal_emergence_zoo.synthetic import generate_two_block_continuous_csv


def test_typed_narrative_report_round_trips_and_preserves_legacy_payload():
    system = cez.load_system("two_block_noisy_4")

    report = cez.narrate_tpm_typed(
        system["microscale"]["tpm"], state_labels=system["state_labels"]
    )
    canonical = report.to_dict()
    restored = cez.narrative_report_from_dict(json.loads(json.dumps(canonical)))

    assert isinstance(report, cez.NarrativeReport)
    assert canonical["schema_version"] == cez.API_SCHEMA_VERSION == "0.2.0"
    assert canonical["kind"] == "causal_emergence.narrative_report"
    cez.validate_public_artifact(canonical)
    assert report.summary() == restored.summary()
    assert report.show_hierarchy().endpoint["partition_id"] == "01|23"
    assert restored.to_dict() == canonical
    assert report.to_legacy_dict()["kind"] == "causal_emergence.narrative_graph"
    assert report.state_model.state_count == 4


def test_typed_exploration_returns_composable_artifacts_and_exports(tmp_path):
    path = tmp_path / "observations.csv"
    report_path = tmp_path / "report.html"
    json_path = tmp_path / "result.json"
    generate_two_block_continuous_csv(path, transition_count=160, seed=13)

    profile = cez.profile_typed(path)
    plan = cez.recommend_analysis_plan_typed(profile, resolutions=[4], seeds=[13])
    result = cez.explore_typed(path, plan=plan)
    canonical = result.to_dict()

    assert isinstance(profile, cez.DataProfile)
    assert isinstance(plan, cez.AnalysisPlan)
    assert isinstance(result, cez.ExplorationResult)
    assert isinstance(result.best_report, cez.NarrativeReport)
    assert result.summary() == result.best_report.summary()
    assert result.show_hierarchy() == result.best_report.hierarchy
    assert canonical["kind"] == "causal_emergence.exploration_result"
    assert canonical["profile"]["schema_version"] == "0.2.0"
    assert canonical["plan"]["schema_version"] == "0.2.0"
    cez.validate_public_artifact(canonical)
    restored = cez.exploration_result_from_dict(canonical)
    assert restored.to_dict() == canonical

    result.write_json(json_path)
    result.export_report(report_path)
    assert json.loads(json_path.read_text(encoding="utf-8"))["kind"] == canonical["kind"]
    assert "Narrative claims and evidence" in report_path.read_text(encoding="utf-8")
    restored.export_report(report_path)
    assert "Narrative claims and evidence" in report_path.read_text(encoding="utf-8")


def test_typed_plan_preserves_forward_extensions_and_rejects_conflicting_overrides(tmp_path):
    path = tmp_path / "observations.csv"
    generate_two_block_continuous_csv(path, transition_count=100, seed=17)
    profile = cez.profile_typed(path)
    plan = cez.recommend_analysis_plan_typed(profile, resolutions=[4], seeds=[17])
    document = plan.to_dict()
    document["future_encoder_option"] = {"name": "example"}

    restored = cez.analysis_plan_from_dict(document)
    assert restored.to_dict()["future_encoder_option"] == {"name": "example"}
    with pytest.raises(ValueError, match="declared plan"):
        cez.explore_typed(path, plan=restored, resolutions=[2])
