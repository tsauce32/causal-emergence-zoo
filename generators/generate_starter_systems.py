"""Generate the starter benchmark systems in package data.

Run from the repository root:

    python generators/generate_starter_systems.py
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PACKAGE_DATA = SRC / "causal_emergence_zoo" / "data"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from causal_emergence_zoo.coarse_grain import coarse_grain_tpm
from causal_emergence_zoo.metrics import compute_metrics
from causal_emergence_zoo.partitions import enumerate_partitions

PRECISION = 12


def _partition_id(blocks: list[list[int]]) -> str:
    return "|".join("".join(str(state) for state in block) for block in blocks)


def _round_tpm(tpm: list[list[float]]) -> list[list[float]]:
    return [[round(value, PRECISION) for value in row] for row in tpm]


def _clean(value: float) -> float:
    value = round(value, PRECISION)
    if value == 0.0:
        return 0.0
    return value


def _build_system(
    *,
    system_id: str,
    name: str,
    description: str,
    conceptual_role: str,
    tpm: list[list[float]],
    notes: list[str],
    seed: int | None = None,
    generator_parameters: dict | None = None,
) -> dict:
    state_count = len(tpm)
    micro_metrics = compute_metrics(tpm, precision=PRECISION)
    partition_entries = []
    for blocks in enumerate_partitions(state_count):
        macro_tpm = coarse_grain_tpm(tpm, blocks, precision=PRECISION)
        metrics = compute_metrics(macro_tpm, precision=PRECISION)
        delta_cp = _clean(metrics["causal_power"] - micro_metrics["causal_power"])
        partition_entries.append(
            {
                "id": _partition_id(blocks),
                "blocks": blocks,
                "macro_state_count": len(blocks),
                "macro_tpm": macro_tpm,
                "metrics": metrics,
                "deltaCP": delta_cp,
            }
        )

    best = max(
        partition_entries,
        key=lambda item: (item["metrics"]["causal_power"], item["macro_state_count"]),
    )
    hierarchy = sorted(
        (
            {
                "partition_id": item["id"],
                "macro_state_count": item["macro_state_count"],
                "causal_power": item["metrics"]["causal_power"],
                "deltaCP": item["deltaCP"],
            }
            for item in partition_entries
        ),
        key=lambda item: (item["causal_power"], item["macro_state_count"]),
        reverse=True,
    )

    return {
        "schema_version": "0.1.0",
        "id": system_id,
        "name": name,
        "description": description,
        "conceptual_role": conceptual_role,
        "state_count": state_count,
        "state_labels": [f"s{i}" for i in range(state_count)],
        "microscale": {
            "partition_id": "|".join(str(i) for i in range(state_count)),
            "tpm": _round_tpm(tpm),
            "metrics": micro_metrics,
        },
        "partitions": partition_entries,
        "emergent_hierarchy": {
            "selection_rule": "Partitions sorted by causal_power, then macro_state_count.",
            "best_partition": {
                "partition_id": best["id"],
                "blocks": best["blocks"],
                "causal_power": best["metrics"]["causal_power"],
                "deltaCP": best["deltaCP"],
            },
            "levels": hierarchy,
        },
        "provenance": {
            "generator": "generators/generate_starter_systems.py",
            "seed": seed,
            "precision": PRECISION,
            "parameters": generator_parameters or {},
        },
        "notes": notes,
        "references": [
            {
                "label": "Hoel, Albantakis, Tononi (2013), Quantifying causal emergence",
                "url": "https://doi.org/10.3390/e15051894",
            },
            {
                "label": "Hoel (2017), When the map is better than the territory",
                "url": "https://doi.org/10.3390/e19050188",
            },
        ],
    }


def _block_cycle_tpm(block_count: int, block_size: int) -> list[list[float]]:
    state_count = block_count * block_size
    tpm = [[0.0 for _ in range(state_count)] for _ in range(state_count)]
    for source_block in range(block_count):
        target_block = (source_block + 1) % block_count
        target_states = range(target_block * block_size, (target_block + 1) * block_size)
        for source_state in range(source_block * block_size, (source_block + 1) * block_size):
            for target_state in target_states:
                tpm[source_state][target_state] = 1.0 / block_size
    return tpm


def _hierarchical_two_cycle_tpm() -> list[list[float]]:
    return [
        [0.0, 0.0, 0.5, 0.5, 0.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 0.5, 0.5, 0.0, 0.0, 0.0, 0.0],
        [0.5, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        [0.5, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5, 0.5],
        [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5, 0.5],
        [0.0, 0.0, 0.0, 0.0, 0.5, 0.5, 0.0, 0.0],
        [0.0, 0.0, 0.0, 0.0, 0.5, 0.5, 0.0, 0.0],
    ]


def _preferential_attachment_graph(
    state_count: int,
    edges_per_new_node: int,
    seed: int,
    attractiveness: float = 1.0,
) -> list[set[int]]:
    rng = random.Random(seed)
    initial_nodes = edges_per_new_node + 1
    graph = [set() for _ in range(state_count)]
    for source in range(initial_nodes):
        for target in range(source + 1, initial_nodes):
            graph[source].add(target)
            graph[target].add(source)

    for new_node in range(initial_nodes, state_count):
        targets: set[int] = set()
        while len(targets) < edges_per_new_node:
            candidates = list(range(new_node))
            weights = [len(graph[candidate]) + attractiveness for candidate in candidates]
            total = sum(weights)
            draw = rng.random() * total
            cumulative = 0.0
            for candidate, weight in zip(candidates, weights):
                cumulative += weight
                if draw <= cumulative:
                    targets.add(candidate)
                    break
        for target in targets:
            graph[new_node].add(target)
            graph[target].add(new_node)
    return graph


def _network_walk_tpm(
    graph: list[set[int]],
    hub_bias_alpha: float,
    self_loop_weight: float = 0.1,
) -> list[list[float]]:
    degrees = [len(neighbors) for neighbors in graph]
    state_count = len(graph)
    tpm = [[0.0 for _ in range(state_count)] for _ in range(state_count)]
    for source, neighbors in enumerate(graph):
        tpm[source][source] = self_loop_weight
        weights = {
            target: (degrees[target] + 1) ** hub_bias_alpha
            for target in sorted(neighbors)
        }
        total = sum(weights.values())
        for target, weight in weights.items():
            tpm[source][target] = (1.0 - self_loop_weight) * weight / total
    return tpm


def build_systems() -> list[dict]:
    pa_seed = 1729
    pa_graph = _preferential_attachment_graph(
        state_count=8,
        edges_per_new_node=2,
        seed=pa_seed,
    )

    return [
        _build_system(
            system_id="identity_3",
            name="Three-state identity system",
            description="A deterministic identity TPM used as a no-emergence sanity check.",
            conceptual_role="no emergence / deterministic baseline",
            tpm=[
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
            ],
            notes=[
                "Microscale causal_power is maximal under the zoo convention.",
                "Coarse partitions do not improve over the microscale.",
            ],
        ),
        _build_system(
            system_id="degenerate_3",
            name="Three-state fully degenerate system",
            description="Every intervention maps to the same next state.",
            conceptual_role="fully degenerate / zero causal power baseline",
            tpm=[
                [1.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
            ],
            notes=[
                "Rows are deterministic but effects are maximally overlapping.",
                "The average effect distribution has zero entropy, so causal_power is zero.",
            ],
        ),
        _build_system(
            system_id="two_block_noisy_4",
            name="Four-state noisy two-block system",
            description="Two noisy equivalence classes where the natural two-block macro scale has higher normalized causal power than the microscale.",
            conceptual_role="top-heavy emergence / equivalence-class coarse graining",
            tpm=[
                [0.45, 0.45, 0.05, 0.05],
                [0.45, 0.45, 0.05, 0.05],
                [0.05, 0.05, 0.45, 0.45],
                [0.05, 0.05, 0.45, 0.45],
            ],
            notes=[
                "The partition [[0, 1], [2, 3]] removes within-block indeterminism.",
                "This is a compact fixture for testing positive deltaCP.",
            ],
        ),
        _build_system(
            system_id="cycle_4",
            name="Four-state deterministic cycle",
            description="A deterministic directed cycle over four states.",
            conceptual_role="pinpoint/coarse-graining testbed",
            tpm=[
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
                [1.0, 0.0, 0.0, 0.0],
            ],
            notes=[
                "Included as a small deterministic cycle for partition-lattice and pinpoint-style tests.",
                "The stored primitive metrics use one-step TPM conventions only.",
            ],
        ),
        _build_system(
            system_id="mesoscale_cycle_6",
            name="Six-state three-block mesoscale cycle",
            description="A six-state system with three two-state equivalence classes whose natural three-block macro scale forms a deterministic cycle.",
            conceptual_role="mesoscale peak / block-cycle emergence",
            tpm=_block_cycle_tpm(block_count=3, block_size=2),
            notes=[
                "The exhaustive partition lattice has 203 partitions.",
                "The partition [[0, 1], [2, 3], [4, 5]] removes within-block target uncertainty.",
                "This fixture is a compact mesoscale-positive example larger than the starter four-state systems.",
            ],
            generator_parameters={
                "family": "block_cycle",
                "block_count": 3,
                "block_size": 2,
            },
        ),
        _build_system(
            system_id="hierarchical_two_cycle_8",
            name="Eight-state hierarchical two-cycle system",
            description="An eight-state system with pair-level two-cycles nested inside two larger four-state components.",
            conceptual_role="multiple-path hierarchy / macro-level plateau",
            tpm=_hierarchical_two_cycle_tpm(),
            notes=[
                "The exhaustive partition lattice has 4,140 partitions.",
                "The pair partition [[0, 1], [2, 3], [4, 5], [6, 7]] and the component partition [[0, 1, 2, 3], [4, 5, 6, 7]] both expose clean macro dynamics.",
                "This fixture is useful for testing hierarchy rankings and ties across macro depths.",
            ],
            generator_parameters={
                "family": "hierarchical_two_cycle",
                "pair_blocks": [[0, 1], [2, 3], [4, 5], [6, 7]],
                "component_blocks": [[0, 1, 2, 3], [4, 5, 6, 7]],
            },
        ),
        _build_system(
            system_id="preferential_attachment_alpha0_8",
            name="Eight-state preferential-attachment walk, alpha 0",
            description="A random-walk TPM on a seeded preferential-attachment graph with unbiased neighbor transitions.",
            conceptual_role="network TPM / preferential attachment baseline",
            tpm=_network_walk_tpm(pa_graph, hub_bias_alpha=0.0),
            seed=pa_seed,
            notes=[
                "The exhaustive partition lattice has 4,140 partitions.",
                "The graph is generated once with a fixed seed; alpha controls transition bias toward high-degree neighbors.",
                "Alpha 0 is the unbiased-neighbor baseline for comparison with the hub-biased fixture.",
            ],
            generator_parameters={
                "family": "preferential_attachment_walk",
                "state_count": 8,
                "edges_per_new_node": 2,
                "attractiveness": 1.0,
                "hub_bias_alpha": 0.0,
                "self_loop_weight": 0.1,
            },
        ),
        _build_system(
            system_id="preferential_attachment_alpha2_8",
            name="Eight-state preferential-attachment walk, alpha 2",
            description="A random-walk TPM on the same seeded preferential-attachment graph with strong hub-biased neighbor transitions.",
            conceptual_role="network TPM / preferential attachment hub bias",
            tpm=_network_walk_tpm(pa_graph, hub_bias_alpha=2.0),
            seed=pa_seed,
            notes=[
                "The exhaustive partition lattice has 4,140 partitions.",
                "This fixture shares its graph with preferential_attachment_alpha0_8 but changes the transition rule.",
                "It is useful for testing whether implementations preserve provenance and detect alpha-sensitive causal structure.",
            ],
            generator_parameters={
                "family": "preferential_attachment_walk",
                "state_count": 8,
                "edges_per_new_node": 2,
                "attractiveness": 1.0,
                "hub_bias_alpha": 2.0,
                "self_loop_weight": 0.1,
            },
        ),
    ]


def main() -> None:
    data_dir = PACKAGE_DATA
    data_dir.mkdir(exist_ok=True)
    for system in build_systems():
        output_path = data_dir / f"{system['id']}.json"
        output_path.write_text(json.dumps(system, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {output_path}")


if __name__ == "__main__":
    main()
