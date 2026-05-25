import json
from pathlib import Path

from causal_emergence_zoo.validation import validate_system
from generators.generate_starter_systems import build_systems

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def test_all_fixtures_validate():
    for path in DATA.glob("*.json"):
        system = json.loads(path.read_text(encoding="utf-8"))
        assert validate_system(system) == []


def test_generated_systems_match_stored_fixtures():
    generated = {system["id"]: system for system in build_systems()}

    assert generated
    for system_id, system in generated.items():
        stored = json.loads((DATA / f"{system_id}.json").read_text(encoding="utf-8"))
        assert stored == system


def test_two_block_fixture_records_positive_delta_cp():
    system = json.loads((DATA / "two_block_noisy_4.json").read_text(encoding="utf-8"))

    best = system["emergent_hierarchy"]["best_partition"]

    assert best["blocks"] == [[0, 1], [2, 3]]
    assert best["deltaCP"] > 0.0


def test_mesoscale_cycle_fixture_records_natural_three_block_peak():
    system = json.loads((DATA / "mesoscale_cycle_6.json").read_text(encoding="utf-8"))

    best = system["emergent_hierarchy"]["best_partition"]

    assert system["state_count"] == 6
    assert len(system["partitions"]) == 203
    assert best["blocks"] == [[0, 1], [2, 3], [4, 5]]
    assert best["deltaCP"] > 0.0


def test_hierarchical_fixture_records_multiple_clean_macro_levels():
    system = json.loads((DATA / "hierarchical_two_cycle_8.json").read_text(encoding="utf-8"))
    levels = {
        item["partition_id"]: item
        for item in system["emergent_hierarchy"]["levels"]
    }

    assert system["state_count"] == 8
    assert len(system["partitions"]) == 4140
    assert levels["01|23|45|67"]["causal_power"] == 1.0
    assert levels["0123|4567"]["causal_power"] == 1.0
    assert system["emergent_hierarchy"]["best_partition"]["blocks"] == [
        [0, 1],
        [2, 3],
        [4, 5],
        [6, 7],
    ]


def test_preferential_attachment_alpha_fixtures_share_graph_but_differ_in_dynamics():
    alpha0 = json.loads((DATA / "preferential_attachment_alpha0_8.json").read_text(encoding="utf-8"))
    alpha2 = json.loads((DATA / "preferential_attachment_alpha2_8.json").read_text(encoding="utf-8"))

    assert alpha0["state_count"] == 8
    assert alpha2["state_count"] == 8
    assert len(alpha0["partitions"]) == 4140
    assert len(alpha2["partitions"]) == 4140
    assert alpha0["provenance"]["seed"] == alpha2["provenance"]["seed"]
    assert alpha0["provenance"]["parameters"]["hub_bias_alpha"] == 0.0
    assert alpha2["provenance"]["parameters"]["hub_bias_alpha"] == 2.0
    assert alpha0["microscale"]["tpm"] != alpha2["microscale"]["tpm"]
    assert alpha0["microscale"]["metrics"]["causal_power"] != alpha2["microscale"]["metrics"]["causal_power"]
