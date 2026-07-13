from causal_emergence_zoo.io import load_system
from causal_emergence_zoo.search import (
    branching_greedy_search,
    greedy_completion,
    pairwise_merges,
    partition_id,
    singleton_partition,
)


def test_pairwise_merges_return_one_step_coarsenings():
    merges = pairwise_merges(singleton_partition(4))

    assert len(merges) == 6
    assert [[0, 1], [2], [3]] in merges
    assert [[0], [1], [2, 3]] in merges


def test_partition_ids_remain_compact_for_existing_fixtures_and_unambiguous_above_nine():
    assert partition_id([[0, 1], [2, 3]]) == "01|23"
    assert partition_id([[1, 2, 13]]) == "1,2,13"
    assert partition_id([[12, 13]]) == "12,13"
    assert partition_id([[1, 2, 13]]) != partition_id([[12, 13]])


def test_greedy_completion_recovers_two_block_macro_scale():
    system = load_system("two_block_noisy_4")
    path = greedy_completion(system["microscale"]["tpm"])

    assert [step["partition_id"] for step in path] == [
        "0|1|2|3",
        "01|2|3",
        "01|23",
        "0123",
    ]
    assert path[2]["blocks"] == [[0, 1], [2, 3]]
    assert path[2]["deltaCP"] > 0.0


def test_branching_greedy_search_finds_mesoscale_cycle_peak():
    system = load_system("mesoscale_cycle_6")
    result = branching_greedy_search(
        system["microscale"]["tpm"],
        n_paths=20,
        branching_factor=2,
    )

    assert result["best_partition"]["blocks"] == [[0, 1], [2, 3], [4, 5]]
    assert result["best_partition"]["metrics"]["causal_power"] == 1.0
    assert result["sampled_partition_count"] < len(system["partitions"])


def test_branching_greedy_search_uses_fixture_tie_break_for_hierarchical_system():
    system = load_system("hierarchical_two_cycle_8")
    result = branching_greedy_search(
        system["microscale"]["tpm"],
        n_paths=20,
        branching_factor=2,
    )

    assert result["best_partition"]["blocks"] == [
        [0, 1],
        [2, 3],
        [4, 5],
        [6, 7],
    ]
