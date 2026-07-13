import json

import pytest

from causal_emergence_zoo.approximate import approximate_ce2_path
from causal_emergence_zoo.continuous import analyze_continuous_csv
from causal_emergence_zoo.multiresolution import analyze_continuous_multiresolution_csv
from causal_emergence_zoo.narrative import narrate_tpm
from causal_emergence_zoo.paper_systems import figure2_equivalence_class_tpm, figure3_top_heavy_tpm
from causal_emergence_zoo.synthetic import generate_two_block_continuous_csv


def test_narrative_exposes_renderer_independent_hierarchy():
    result = narrate_tpm(figure2_equivalence_class_tpm())
    hierarchy = result["causal_hierarchy"]

    assert hierarchy["kind"] == "causal_emergence.causal_hierarchy"
    assert hierarchy["endpoint"]["partition_id"] == result["ce2"]["endpoint"]["partition_id"]
    assert hierarchy["evidence"]["search_is_exhaustive"]
    json.dumps(hierarchy, allow_nan=False)


@pytest.mark.parametrize("tpm", [figure2_equivalence_class_tpm(), figure3_top_heavy_tpm()])
def test_approximate_search_matches_exact_paper_endpoint(tpm):
    exact = narrate_tpm(tpm)["ce2"]
    approximate = approximate_ce2_path(tpm, beam_width=20, branching_factor=6)

    assert approximate["validity"]["is_valid"]
    assert approximate["endpoint"]["partition_id"] == exact["endpoint"]["partition_id"]
    assert approximate["endpoint"]["cp"] == pytest.approx(exact["endpoint"]["cp"])
    assert approximate["endpoint_optimality"] == "best_sampled_not_global"


def test_approximate_search_operates_beyond_exact_eight_state_limit():
    size = 10
    block_size = 5
    tpm = []
    for state in range(size):
        start = 0 if state < block_size else block_size
        tpm.append([1.0 / block_size if start <= target < start + block_size else 0.0 for target in range(size)])

    result = approximate_ce2_path(tpm, beam_width=8, branching_factor=3)

    assert result["validity"]["is_valid"]
    assert result["endpoint"]["blocks"] == [list(range(5)), list(range(5, 10))]
    assert result["endpoint"]["cp"] == pytest.approx(1.0)


def test_auto_search_supports_sixteen_states_with_explicit_bounded_metadata():
    size = 16
    block_size = 8
    tpm = [
        [
            1.0 / block_size
            if ((source < block_size and target < block_size) or (source >= block_size and target >= block_size))
            else 0.0
            for target in range(size)
        ]
        for source in range(size)
    ]

    result = narrate_tpm(tpm, beam_width=1, branching_factor=1)
    ce2 = result["ce2"]

    assert not ce2["is_exhaustive"]
    assert ce2["algorithm"] == "dynamically_consistent_ce2_bounded_beam_search"
    assert ce2["endpoint"]["blocks"] == [list(range(8)), list(range(8, 16))]
    assert ce2["endpoint"]["partition_id"] == "0,1,2,3,4,5,6,7|8,9,10,11,12,13,14,15"
    assert ce2["search_contract"]["supported_state_count_maximum"] == 16
    assert ce2["search_coverage"]["full_partition_lattice_count"] == 10_480_142_147
    assert ce2["endpoint_optimality"] == "best_sampled_not_global"
    assert "not a global CE 2.0 optimum" in result["summary"]["headline"]
    assert "c:bounded_search" in {
        caveat["id"] for caveat in result["narrative_graph"]["caveats"]
    }


def test_auto_preserves_exact_discovery_for_existing_small_systems():
    tpm = figure2_equivalence_class_tpm()
    automatic = narrate_tpm(tpm)["ce2"]
    exact = narrate_tpm(tpm, search_mode="exact")["ce2"]

    assert automatic == exact


def test_exact_and_bounded_search_limits_are_explicit():
    identity_nine = [[1.0 if source == target else 0.0 for target in range(9)] for source in range(9)]
    identity_seventeen = [
        [1.0 if source == target else 0.0 for target in range(17)] for source in range(17)
    ]

    with pytest.raises(ValueError, match="limited to 8 states"):
        narrate_tpm(identity_nine, search_mode="exact")
    with pytest.raises(ValueError, match="at most 16 states"):
        narrate_tpm(identity_seventeen)
    with pytest.raises(ValueError, match="at most 16 states"):
        approximate_ce2_path(identity_seventeen)


def test_bounded_search_is_deterministic_with_a_fixed_budget():
    size = 10
    tpm = [
        [0.2 if source // 5 == target // 5 else 0.0 for target in range(size)]
        for source in range(size)
    ]

    first = approximate_ce2_path(tpm, beam_width=3, branching_factor=2, max_partition_evaluations=100)
    second = approximate_ce2_path(tpm, beam_width=3, branching_factor=2, max_partition_evaluations=100)

    assert first == second


def test_approximate_search_records_partition_budget_exhaustion():
    result = approximate_ce2_path(figure2_equivalence_class_tpm(), max_partition_evaluations=1)
    assert result["termination_reason"] == "partition_evaluation_budget_exhausted"
    assert result["partition_evaluation_count"] == 1


def test_large_continuous_recovery_benchmark(tmp_path):
    path = tmp_path / "large-two-block.csv"
    generated = generate_two_block_continuous_csv(path, transition_count=10_000, seed=17)
    result = analyze_continuous_csv(
        path,
        feature_columns=["signal"],
        microstate_count=4,
        trajectory_column="trajectory_id",
        time_column="time",
        reservoir_size=2_000,
        random_seed=17,
        consistency_tolerance=0.03,
    )

    endpoint_blocks = sorted(sorted(block) for block in result["ce2"]["endpoint"]["blocks"])
    assert generated["row_count"] == 20_000
    assert result["continuous_data"]["transitions"]["splits"]["all"]["transition_count"] == 10_000
    assert sorted(map(len, endpoint_blocks)) == [2, 2]
    assert result["status"] == "emergent"


def test_multiresolution_profile_reports_peak_without_using_it_as_gate(tmp_path):
    path = tmp_path / "two-block.csv"
    generate_two_block_continuous_csv(path, transition_count=500, seed=9)

    profile = analyze_continuous_multiresolution_csv(
        path,
        feature_columns=["signal"],
        resolutions=[3, 4],
        encoder_seeds=[9],
        trajectory_column="trajectory_id",
        time_column="time",
        reservoir_size=1_000,
    )

    assert profile["kind"] == "causal_emergence.multiresolution_profile"
    assert not profile["profile"]["classification_is_acceptance_gate"]
    assert len(profile["resolution_runs"]) == 2
