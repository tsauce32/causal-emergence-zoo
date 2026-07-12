import json

from causal_emergence_zoo.continuous import analyze_continuous_csv
from causal_emergence_zoo.explore import explore_csv
from causal_emergence_zoo.narrative import analyze_trajectories
from causal_emergence_zoo.synthetic import generate_two_block_continuous_csv


def _two_block_trajectories():
    labels = ["A", "B", "C", "D"]
    counts = [[9, 9, 1, 1], [9, 9, 1, 1], [1, 1, 9, 9], [1, 1, 9, 9]]
    return labels, [
        [labels[source], labels[target]]
        for source, row in enumerate(counts)
        for target, count in enumerate(row)
        for _ in range(count)
    ]


def test_every_narrative_claim_has_a_linked_evidence_ledger_entry():
    labels, trajectories = _two_block_trajectories()
    result = analyze_trajectories(
        trajectories,
        state_labels=labels,
        bootstrap_replicates=4,
        bootstrap_seed=3,
    )

    ledger = result["evidence_ledger"]
    assert ledger["kind"] == "causal_emergence.evidence_ledger"
    assert ledger["claim_count"] == len(result["narrative_graph"]["claims"])
    assert all(
        claim["evidence_ledger_id"] == f"ledger:{claim['id']}"
        for claim in result["narrative_graph"]["claims"]
    )
    for entry in ledger["claims"]:
        assert entry["supporting_evidence"]
        assert entry["state_support"]["macro_states"]
        assert "transition_support" in entry
        assert entry["uncertainty"]
        assert entry["counterevidence"]
    json.dumps(result, allow_nan=False)


def test_continuous_evidence_ledger_carries_holdout_and_null_checks(tmp_path):
    path = tmp_path / "continuous.csv"
    generate_two_block_continuous_csv(path, transition_count=300, seed=8)
    result = analyze_continuous_csv(
        path,
        feature_columns=["signal"],
        microstate_count=4,
        trajectory_column="trajectory_id",
        time_column="time",
        validation_fraction=0.2,
        smoothing=0.1,
        null_replicates=2,
        null_seed=7,
    )

    uncertainty_kinds = {
        item["kind"] for item in result["evidence_ledger"]["claims"][0]["uncertainty"]
    }
    assert "held_out_path_reproduction" in uncertainty_kinds
    assert "held_out_predictive_score" in uncertainty_kinds
    assert "transition_target_null" in uncertainty_kinds


def test_exploration_report_exposes_local_claim_and_transition_inspection(tmp_path):
    path = tmp_path / "continuous.csv"
    report = tmp_path / "report.html"
    generate_two_block_continuous_csv(path, transition_count=400, seed=10)

    explore_csv(path, resolutions=[4], seeds=[10], report_path=report)
    rendered = report.read_text(encoding="utf-8")

    assert "Narrative claims and evidence" in rendered
    assert "data-claim-id" in rendered
    assert "matrix-cell" in rendered
    assert "cez-report-data" in rendered
    assert "Counterevidence to inspect" in rendered
    assert "addEventListener" in rendered
