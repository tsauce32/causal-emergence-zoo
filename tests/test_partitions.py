from causal_emergence_zoo.partitions import enumerate_partitions


def test_partition_counts_match_bell_numbers_for_small_systems():
    assert len(enumerate_partitions(1)) == 1
    assert len(enumerate_partitions(2)) == 2
    assert len(enumerate_partitions(3)) == 5
    assert len(enumerate_partitions(4)) == 15


def test_partitions_are_canonical_and_cover_all_states():
    partitions = enumerate_partitions(3)

    assert [[0, 1, 2]] in partitions
    assert [[0], [1], [2]] in partitions
    for partition in partitions:
        covered = sorted(state for block in partition for state in block)
        assert covered == [0, 1, 2]
