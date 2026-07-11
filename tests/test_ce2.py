import json

from causal_emergence_zoo import load_system
from causal_emergence_zoo.ce2 import (
    analyze_ce2_path,
    check_dynamical_consistency,
    discover_ce2_path,
)


def test_ce2_discovers_two_block_endpoint_and_telescoping_path():
    tpm = load_system("two_block_noisy_4")["microscale"]["tpm"]

    result = discover_ce2_path(tpm)

    assert result["endpoint"]["blocks"] == [[0, 1], [2, 3]]
    assert result["causal_apportioning"]["endpoint_cp_gain"] > 0.0
    increments = [step["delta_cp_from_previous_scale"] for step in result["path"][1:]]
    assert sum(increments) == result["causal_apportioning"]["endpoint_cp_gain"]
    assert result["emergent_complexity"]["status"] == "defined"


def test_ce2_consistency_accepts_block_partition_and_rejects_invalid_summary():
    tpm = load_system("two_block_noisy_4")["microscale"]["tpm"]

    valid = check_dynamical_consistency(tpm, [[0, 1], [2, 3]])
    invalid = check_dynamical_consistency(tpm, [[0, 1, 2], [3]])

    assert valid["is_dynamically_consistent"]
    assert not invalid["is_dynamically_consistent"]
    assert invalid["total_kl_divergence"] is not None
    json.dumps(invalid, allow_nan=False)


def test_supplied_ce2_path_requires_nested_consistent_scales():
    tpm = load_system("two_block_noisy_4")["microscale"]["tpm"]

    valid = analyze_ce2_path(
        tpm,
        [[[0], [1], [2], [3]], [[0, 1], [2], [3]], [[0, 1], [2, 3]]],
    )
    invalid = analyze_ce2_path(
        tpm,
        [[[0], [1], [2], [3]], [[0, 1], [2, 3]], [[0, 1], [2], [3]]],
    )

    assert valid["validity"]["is_valid"]
    assert valid["endpoint"]["partition_id"] == "01|23"
    assert not invalid["validity"]["is_valid"]
    assert any("strict coarsening" in error for error in invalid["validity"]["errors"])


def test_ce2_identity_has_no_positive_macro_contribution_or_entropy():
    result = discover_ce2_path(load_system("identity_3")["microscale"]["tpm"])

    assert result["endpoint"]["partition_id"] == "0|1|2"
    assert not result["causal_apportioning"]["has_positive_macro_contribution"]
    assert result["emergent_complexity"]["status"] == "undefined_without_positive_macro_contributions"
    assert result["emergent_complexity"]["bits"] is None
