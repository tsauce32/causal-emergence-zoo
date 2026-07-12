"""Release-facing compatibility checks for public, JSON artifact APIs.

These tests deliberately assert discriminators and required typed fields rather
than full result dictionaries, so additive evidence fields remain possible
without breaking consumers of the v0.2 artifact surface.
"""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
import tomllib

import causal_emergence_zoo as cez


ROOT = Path(__file__).resolve().parents[1]


def _assert_json_safe(value: object) -> None:
    json.dumps(value, allow_nan=False)


def test_public_exports_include_legacy_and_v02_entry_points():
    required = {
        # Original benchmark and CE1-compatible surface.
        "available_systems",
        "load_system",
        "validate_system",
        "compute_metrics",
        "coarse_grain_tpm",
        "enumerate_partitions",
        "greedy_completion",
        "branching_greedy_search",
        "estimate_tpm_from_trajectories",
        "estimate_tpm_from_transition_counts",
        "narrate_tpm",
        "analyze_trajectories",
        # v0.2 typed artifacts and plug-and-play entry points.
        "build_causal_hierarchy",
        "build_evidence_ledger",
        "attach_evidence_ledger",
        "explore",
        "explore_csv",
        "profile_source",
        "profile_csv",
        "TabularSource",
        "adapt_continuous_source",
        "analyze_continuous_csv",
        "analyze_continuous_multiresolution_csv",
        "validate_grouped_trajectories",
        "validate_continuous_analysis_trajectories",
        "assess_multiresolution_stability",
        "API_SCHEMA_VERSION",
        "DataProfile",
        "AnalysisPlan",
        "StateModel",
        "CausalHierarchy",
        "EvidenceLedger",
        "NarrativeReport",
        "ExplorationResult",
        "profile_typed",
        "recommend_analysis_plan_typed",
        "narrate_tpm_typed",
        "analyze_trajectories_typed",
        "analyze_continuous_typed",
        "explore_typed",
        "validate_public_artifact",
    }

    assert len(cez.__all__) == len(set(cez.__all__))
    assert required <= set(cez.__all__)
    assert all(hasattr(cez, name) for name in cez.__all__)

    # A long-standing benchmark call remains usable through the package root.
    system = cez.load_system("two_block_noisy_4")
    assert cez.compute_metrics(system["microscale"]["tpm"])["causal_power"] > 0.0
    assert cez.validate_system(system) == []


def test_runtime_version_matches_release_metadata():
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert cez.__version__ == "0.2.0"
    assert metadata["project"]["version"] == cez.__version__


def test_narrative_hierarchy_and_ledger_keep_typed_linked_contracts():
    system = cez.load_system("two_block_noisy_4")
    result = cez.narrate_tpm(
        system["microscale"]["tpm"],
        state_labels=system["state_labels"],
    )

    assert result["schema_version"] == "0.2.0"
    assert result["kind"] == "causal_emergence.narrative_graph"
    assert result["analysis_type"] == "ce2_multiscale"
    assert result["status"] in {"emergent", "no_emergence"}
    assert {
        "summary",
        "input_model",
        "ce2",
        "causal_hierarchy",
        "narrative_graph",
        "evidence_ledger",
        "assumptions",
        "limitations",
    } <= set(result)

    hierarchy = result["causal_hierarchy"]
    assert hierarchy["schema_version"] == "0.1.0"
    assert hierarchy["kind"] == "causal_emergence.causal_hierarchy"
    assert hierarchy["endpoint"]["partition_id"] == result["ce2"]["endpoint"]["partition_id"]
    assert isinstance(hierarchy["scales"], list) and hierarchy["scales"]
    assert isinstance(hierarchy["evidence"]["search_is_exhaustive"], bool)

    graph = result["narrative_graph"]
    evidence_ids = {item["id"] for item in graph["evidence"]}
    caveat_ids = {item["id"] for item in graph["caveats"]}
    ledger = result["evidence_ledger"]
    assert ledger["schema_version"] == "0.1.0"
    assert ledger["kind"] == "causal_emergence.evidence_ledger"
    assert ledger["claim_count"] == len(graph["claims"]) == len(ledger["claims"])
    ledger_by_claim = {item["claim_id"]: item for item in ledger["claims"]}
    for claim in graph["claims"]:
        assert claim["id"] in ledger_by_claim
        assert claim["evidence_ledger_id"] == f"ledger:{claim['id']}"
        assert set(claim["evidence_ids"]) <= evidence_ids
        assert set(claim["caveat_ids"]) <= caveat_ids
        entry = ledger_by_claim[claim["id"]]
        assert entry["claim_id"] == claim["id"]
        assert isinstance(entry["supporting_evidence"], list)
        assert isinstance(entry["uncertainty"], list)
        assert isinstance(entry["counterevidence"], list)

    _assert_json_safe(result)


def test_resampling_artifact_keeps_status_discriminators_and_observational_caveat():
    result = cez.validate_grouped_trajectories(
        [[0, 1, 0, 1], [1, 0, 1, 0], [0, 0, 1, 1]],
        state_count=2,
        state_labels=["low", "high"],
        smoothing=0.1,
        temporal_null_replicates=2,
        temporal_null_seed=3,
        bootstrap_replicates=2,
        bootstrap_seed=5,
    )

    assert result["schema_version"] == "0.1.0"
    assert result["kind"] == "causal_emergence.trajectory_validation"
    assert result["resampling_unit"] == "complete_independent_trajectory"
    assert result["observed_model"]["endpoint_partition_id"]
    assert result["temporal_permutation_null"]["status"] == "completed"
    assert result["grouped_bootstrap"]["status"] == "completed"
    assert "do not identify intervention effects" in result["observational_caveat"]
    _assert_json_safe(result)


def test_exploration_profile_plan_and_analysis_artifacts_remain_typed(tmp_path):
    path = tmp_path / "observations.csv"
    rows = ["trajectory_id,time,signal"]
    for trajectory in range(12):
        for time, value in enumerate((0.0, 1.0, 0.0, 1.0, 0.0, 1.0)):
            rows.append(f"t{trajectory},{time},{value + (10.0 if trajectory % 2 else 0.0)}")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    profile = cez.profile_csv(path)
    plan = cez.recommend_analysis_plan(profile, resolutions=[2], seeds=[7])
    exploration = cez.explore_csv(path, resolutions=[2], seeds=[7])

    assert (profile["schema_version"], profile["kind"]) == (
        "0.1.0",
        "causal_emergence.data_profile",
    )
    assert (plan["schema_version"], plan["kind"]) == (
        "0.1.0",
        "causal_emergence.analysis_plan",
    )
    assert (exploration["schema_version"], exploration["kind"]) == (
        "0.1.0",
        "causal_emergence.exploration",
    )
    assert exploration["profile"]["kind"] == profile["kind"]
    assert exploration["plan"]["kind"] == plan["kind"]
    assert exploration["analysis"]["kind"] == "causal_emergence.multiresolution_profile"
    assert exploration["analysis"]["comparison"]["stability_alignment"]["classification_is_acceptance_gate"] is False
    assert isinstance(exploration["state_descriptions"], list)
    _assert_json_safe(exploration)


def test_packaged_contract_schemas_match_repository_copies():
    for filename in (
        "benchmark-input.schema.json",
        "benchmark-system.schema.json",
        "implementation-result.schema.json",
        "public-api.schema.json",
    ):
        repository_schema = json.loads((ROOT / "schemas" / filename).read_text(encoding="utf-8"))
        packaged_schema = json.loads(
            files("causal_emergence_zoo")
            .joinpath("schemas", filename)
            .read_text(encoding="utf-8")
        )
        assert packaged_schema == repository_schema
