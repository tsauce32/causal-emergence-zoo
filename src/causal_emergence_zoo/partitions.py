"""Enumeration of set partitions for small finite state spaces."""

from __future__ import annotations


def enumerate_partitions(state_count: int) -> list[list[list[int]]]:
    """Enumerate canonical set partitions of states ``0..state_count-1``.

    The output order is deterministic and suitable for serialized fixtures. This
    grows by Bell numbers, so callers should only use it for small systems.
    """
    if state_count < 1:
        raise ValueError("state_count must be positive.")

    partitions: list[list[list[int]]] = []

    def extend(next_state: int, blocks: list[list[int]]) -> None:
        if next_state == state_count:
            partitions.append([block[:] for block in blocks])
            return
        for index in range(len(blocks)):
            blocks[index].append(next_state)
            extend(next_state + 1, blocks)
            blocks[index].pop()
        blocks.append([next_state])
        extend(next_state + 1, blocks)
        blocks.pop()

    extend(0, [])
    return partitions
