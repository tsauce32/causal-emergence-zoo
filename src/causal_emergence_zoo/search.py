"""Greedy search helpers for causal-emergence partition lattices."""

from __future__ import annotations

from typing import Any

from causal_emergence_zoo.coarse_grain import coarse_grain_tpm
from causal_emergence_zoo.metrics import Matrix, compute_metrics


Partition = list[list[int]]
SearchRecord = dict[str, Any]


def partition_id(partition: Partition) -> str:
    """Return the zoo's compact display id for a partition."""
    return "|".join("".join(str(state) for state in block) for block in canonical_partition(partition))


def singleton_partition(state_count: int) -> Partition:
    """Return the microscale partition for ``state_count`` states."""
    if state_count < 1:
        raise ValueError("state_count must be positive.")
    return [[state] for state in range(state_count)]


def canonical_partition(partition: Partition) -> Partition:
    """Return a deterministic copy of a partition."""
    if not partition:
        raise ValueError("Partition must contain at least one block.")
    canonical = [sorted(block) for block in partition]
    if any(not block for block in canonical):
        raise ValueError("Partition blocks must be non-empty.")
    states = [state for block in canonical for state in block]
    if len(states) != len(set(states)):
        raise ValueError("Partition states must be unique.")
    return sorted(canonical, key=lambda block: (block[0], len(block), block))


def merge_blocks(partition: Partition, left_index: int, right_index: int) -> Partition:
    """Return a new partition with two blocks merged."""
    canonical = canonical_partition(partition)
    if left_index == right_index:
        raise ValueError("Cannot merge a block with itself.")
    if left_index < 0 or right_index < 0:
        raise IndexError("Block indices must be non-negative.")
    if left_index >= len(canonical) or right_index >= len(canonical):
        raise IndexError("Block index out of range.")

    left, right = sorted((left_index, right_index))
    merged = sorted(canonical[left] + canonical[right])
    blocks = [
        block
        for index, block in enumerate(canonical)
        if index not in (left, right)
    ]
    blocks.append(merged)
    return canonical_partition(blocks)


def pairwise_merges(partition: Partition) -> list[Partition]:
    """Return every one-step coarsening reachable by one pairwise block merge."""
    canonical = canonical_partition(partition)
    return [
        merge_blocks(canonical, left, right)
        for left in range(len(canonical))
        for right in range(left + 1, len(canonical))
    ]


def score_partition(
    tpm: Matrix,
    partition: Partition,
    *,
    score_key: str = "causal_power",
    precision: int | None = None,
    micro_causal_power: float | None = None,
) -> SearchRecord:
    """Score a partition using a metric from the induced macro TPM."""
    blocks = canonical_partition(partition)
    macro_tpm = coarse_grain_tpm(tpm, blocks, precision=precision)
    metrics = compute_metrics(macro_tpm, precision=precision)
    if score_key not in metrics:
        raise ValueError(f"Unknown score key {score_key!r}. Available metrics: {sorted(metrics)}")
    if micro_causal_power is None:
        micro_causal_power = compute_metrics(tpm, precision=precision)["causal_power"]
    delta_cp = metrics["causal_power"] - micro_causal_power
    if precision is not None:
        delta_cp = round(delta_cp, precision)
    if delta_cp == 0.0:
        delta_cp = 0.0

    return {
        "partition_id": partition_id(blocks),
        "blocks": blocks,
        "macro_state_count": len(blocks),
        "macro_tpm": macro_tpm,
        "metrics": metrics,
        "score_key": score_key,
        "score": metrics[score_key],
        "deltaCP": delta_cp,
    }


def greedy_completion(
    tpm: Matrix,
    start_partition: Partition | None = None,
    *,
    score_key: str = "causal_power",
    precision: int | None = None,
) -> list[SearchRecord]:
    """Follow the best-scoring one-step merge until the one-block macroscale.

    This is the deterministic inner loop of the branching greedy heuristic:
    from the current partition, score every pairwise block merge and move to
    the candidate with the highest selected score.
    """
    state_count = len(tpm)
    partition = canonical_partition(start_partition or singleton_partition(state_count))
    micro_causal_power = compute_metrics(tpm, precision=precision)["causal_power"]
    path = [
        score_partition(
            tpm,
            partition,
            score_key=score_key,
            precision=precision,
            micro_causal_power=micro_causal_power,
        )
    ]

    while len(partition) > 1:
        candidates = _rank_candidates(
            tpm,
            pairwise_merges(partition),
            score_key=score_key,
            precision=precision,
            micro_causal_power=micro_causal_power,
        )
        partition = candidates[0]["blocks"]
        path.append(candidates[0])
    return path


def branching_greedy_search(
    tpm: Matrix,
    start_partition: Partition | None = None,
    *,
    n_paths: int = 20,
    branching_factor: int = 2,
    score_key: str = "causal_power",
    precision: int | None = None,
) -> dict[str, Any]:
    """Sample high-scoring paths through the partition lattice.

    The search starts from the microscale partition by default. At each level,
    each active path branches to its best ``branching_factor`` pairwise merges,
    and the global frontier is capped to ``n_paths``. This gives a small,
    deterministic analogue of the branching greedy procedure discussed in
    Engineering Emergence while keeping the zoo's current TPM convention.
    """
    if n_paths < 1:
        raise ValueError("n_paths must be positive.")
    if branching_factor < 1:
        raise ValueError("branching_factor must be positive.")

    state_count = len(tpm)
    start = canonical_partition(start_partition or singleton_partition(state_count))
    micro_metrics = compute_metrics(tpm, precision=precision)
    micro_causal_power = micro_metrics["causal_power"]
    start_record = score_partition(
        tpm,
        start,
        score_key=score_key,
        precision=precision,
        micro_causal_power=micro_causal_power,
    )
    paths = [[start_record]]
    seen: dict[str, SearchRecord] = {start_record["partition_id"]: start_record}

    while any(path[-1]["macro_state_count"] > 1 for path in paths):
        expanded: list[list[SearchRecord]] = []
        for path in paths:
            current = path[-1]
            if current["macro_state_count"] == 1:
                expanded.append(path)
                continue
            candidates = _rank_candidates(
                tpm,
                pairwise_merges(current["blocks"]),
                score_key=score_key,
                precision=precision,
                micro_causal_power=micro_causal_power,
            )
            for candidate in candidates[:branching_factor]:
                seen[candidate["partition_id"]] = candidate
                expanded.append(path + [candidate])
        paths = _rank_paths(expanded)[:n_paths]

    sampled = sorted(
        seen.values(),
        key=lambda record: (
            record["score"],
            record["deltaCP"],
            record["macro_state_count"],
            _reverse_lex_key(record["partition_id"]),
        ),
        reverse=True,
    )
    best = sampled[0]
    return {
        "algorithm": "branching_greedy_partition_search",
        "score_key": score_key,
        "n_paths": n_paths,
        "branching_factor": branching_factor,
        "microscale": {
            "partition_id": start_record["partition_id"],
            "blocks": start_record["blocks"],
            "metrics": micro_metrics,
        },
        "best_partition": best,
        "sampled_partition_count": len(sampled),
        "sampled_partitions": sampled,
        "paths": paths,
    }


def _rank_candidates(
    tpm: Matrix,
    candidates: list[Partition],
    *,
    score_key: str,
    precision: int | None,
    micro_causal_power: float,
) -> list[SearchRecord]:
    scored = [
        score_partition(
            tpm,
            candidate,
            score_key=score_key,
            precision=precision,
            micro_causal_power=micro_causal_power,
        )
        for candidate in candidates
    ]
    return sorted(
        scored,
        key=lambda record: (
            record["score"],
            record["deltaCP"],
            record["macro_state_count"],
            _reverse_lex_key(record["partition_id"]),
        ),
        reverse=True,
    )


def _rank_paths(paths: list[list[SearchRecord]]) -> list[list[SearchRecord]]:
    return sorted(
        paths,
        key=lambda path: (
            path[-1]["score"],
            path[-1]["deltaCP"],
            sum(record["score"] for record in path),
            _reverse_lex_key(">".join(record["partition_id"] for record in path)),
        ),
        reverse=True,
    )


def _reverse_lex_key(value: str) -> tuple[int, ...]:
    """Invert characters so ascending ids win under reverse sorting."""
    return tuple(-ord(char) for char in value)
