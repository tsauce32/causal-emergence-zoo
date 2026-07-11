from causal_emergence_zoo.explore import explore_csv, profile_csv, recommend_analysis_plan
from causal_emergence_zoo.synthetic import generate_two_block_continuous_csv


def test_profile_and_plan_infer_grouped_numeric_csv(tmp_path):
    path = tmp_path / "data.csv"
    generate_two_block_continuous_csv(path, transition_count=100, seed=3)
    profile = profile_csv(path)
    plan = recommend_analysis_plan(profile, resolutions=[4])
    assert profile["inferred_roles"]["entity"] == "trajectory_id"
    assert profile["inferred_roles"]["time"] == "time"
    assert profile["inferred_roles"]["numeric_features"] == ["signal"]
    assert plan["resolutions"] == [4]


def test_explore_writes_self_contained_html_report(tmp_path):
    path = tmp_path / "data.csv"
    report = tmp_path / "report.html"
    generate_two_block_continuous_csv(path, transition_count=500, seed=7)
    result = explore_csv(path, resolutions=[4], seeds=[7], report_path=report)
    rendered = report.read_text(encoding="utf-8")
    assert result["kind"] == "causal_emergence.exploration"
    assert result["state_descriptions"]
    assert "CE by resolution" in rendered
    assert "Selected macro dynamics" in rendered
    assert "<svg" in rendered
