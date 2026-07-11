import json

import pytest

from causal_emergence_zoo.approximate import approximate_ce2_path
from causal_emergence_zoo.continuous import analyze_continuous_csv
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
