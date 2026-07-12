"""Black-box v0.2 public-API regression contracts.

The current public API uses JSON-safe dictionaries.  These tests deliberately
exercise that wire format rather than private implementation details so typed
v0.2 wrappers can be introduced without breaking existing callers.
"""

import json

from causal_emergence_zoo import (
    build_causal_hierarchy,
    build_evidence_ledger,
    build_narrative_graph,
    compute_metrics,
    discover_ce2_path,
    explore,
    load_system,
    profile_source,
    recommend_analysis_plan,
)
from causal_emergence_zoo.synthetic import generate_two_block_continuous_csv


def _round_trip(value):
    return json.loads(json.dumps(value, allow_nan=False))


def test_canonical_public_workflow_emits_named_json_artifacts(tmp_path):
    """Profile -> plan -> explore exposes the v0.2 artifact boundaries."""
    path = tmp_path / "observations.csv"
    generate_two_block_continuous_csv(path, transition_count=80, seed=23)

    profile = profile_source(path)
    plan = recommend_analysis_plan(
        profile,
        features=["signal"],
        resolutions=[4],
        seeds=[23],
    )
    exploration = explore(
        path,
        features=plan["feature_columns"],
        resolutions=plan["resolutions"],
        seeds=plan["encoder_seeds"],
    )
    report = exploration["analysis"]["resolution_runs"][0]["result"]

    # Canonical v0.2 concepts retain their existing JSON envelopes until typed
    # wrappers replace these dicts at the Python boundary.
    artifacts = {
        "analysis_plan": plan,
        "state_model": report["input_model"],
        "causal_hierarchy": report["causal_hierarchy"],
        "evidence_ledger": report["evidence_ledger"],
        "narrative_report": report,
        "exploration_result": exploration,
    }
    assert plan["kind"] == "causal_emergence.analysis_plan"
    assert artifacts["state_model"]["kind"] == "provided_transition_model"
    assert artifacts["causal_hierarchy"]["kind"] == "causal_emergence.causal_hierarchy"
    assert artifacts["evidence_ledger"]["kind"] == "causal_emergence.evidence_ledger"
    assert artifacts["narrative_report"]["kind"] == "causal_emergence.narrative_graph"
    assert artifacts["exploration_result"]["kind"] == "causal_emergence.exploration"
    assert artifacts["evidence_ledger"]["claim_count"] == len(
        artifacts["narrative_report"]["narrative_graph"]["claims"]
    )

    assert _round_trip(artifacts) == artifacts


def test_legacy_plain_dict_model_and_ce2_inputs_remain_publicly_compatible():
    """Existing dict callers can still build hierarchy, report, and ledger."""
    system = load_system("two_block_noisy_4")
    tpm = system["microscale"]["tpm"]
    labels = system["state_labels"]
    legacy_model = {
        "kind": "provided_transition_model",
        "state_labels": labels,
        "state_count": len(labels),
        "tpm": tpm,
        "microscale_metrics": compute_metrics(tpm),
        "source": {
            "kind": "provided_tpm",
            "causal_interpretation": "caller_must_declare_interventional_semantics",
        },
    }
    legacy_ce2 = discover_ce2_path(tpm)

    hierarchy = build_causal_hierarchy(legacy_model, legacy_ce2)
    report = build_narrative_graph(legacy_model, legacy_ce2)
    ledger = build_evidence_ledger(report)

    assert hierarchy == report["causal_hierarchy"]
    assert hierarchy["endpoint"]["partition_id"] == legacy_ce2["endpoint"]["partition_id"]
    assert ledger["claim_count"] == len(report["narrative_graph"]["claims"])
    assert _round_trip({"model": legacy_model, "ce2": legacy_ce2, "report": report})[
        "report"
    ]["causal_hierarchy"] == hierarchy


def test_legacy_analysis_plan_dict_stays_valid_input_to_the_canonical_workflow(tmp_path):
    """A hand-authored v0.1 profile still yields a serializable plan and run."""
    path = tmp_path / "observations.csv"
    generate_two_block_continuous_csv(path, transition_count=60, seed=29)
    legacy_profile = {
        "row_count": 120,
        "inferred_roles": {
            "entity": "trajectory_id",
            "time": "time",
            "numeric_features": ["signal"],
        },
        "trajectory_count": 60,
        "trajectory_length": {"minimum": 2, "median": 2, "maximum": 2},
    }

    plan = recommend_analysis_plan(legacy_profile, resolutions=[4], seeds=[29])
    exploration = explore(
        path,
        entity=plan["entity_column"],
        time=plan["time_column"],
        features=plan["feature_columns"],
        resolutions=plan["resolutions"],
        seeds=plan["encoder_seeds"],
    )

    assert plan["feature_columns"] == ["signal"]
    assert exploration["plan"]["kind"] == "causal_emergence.analysis_plan"
    assert _round_trip(plan) == plan
