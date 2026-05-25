# Benchmark Design

`causal-emergence-zoo` treats benchmark systems as reproducible data artifacts. Each fixture should be small enough to inspect or generated from a transparent script.

The project contract is:

```text
Given this TPM,
under these conventions,
with this coarse-graining rule,
these are the expected multiscale outputs.
```

## System Record

Each system stores:

- A row-stochastic microscale TPM
- Metadata describing its conceptual role
- Exhaustive partitions when tractable
- Macro TPMs induced by each stored partition
- Causal primitive values under the zoo convention
- `deltaCP` relative to the microscale
- A sorted emergent hierarchy summary
- Provenance linking back to the generator and seed

## Coarse-Graining Convention

A partition groups microstates into macrostates. For a macro intervention, the benchmark uses a uniform intervention over the microstates in the selected macro block. Target probabilities are summed into target macro blocks.

For source block `A` and target block `B`:

```text
T_macro[A, B] = average over i in A of sum over j in B T_micro[i, j]
```

This convention is intentionally simple and auditable. Other packages can adapt the stored data if they use a different intervention distribution.

## Partition Scope

The starter fixtures enumerate every set partition for systems with up to eight states. Larger benchmark families should either:

- Store selected reference partitions with a clear reason, or
- Store a documented heuristic trace, such as a branching greedy hierarchy.

Current exhaustive partition counts:

- 3 states: 5 partitions
- 4 states: 15 partitions
- 6 states: 203 partitions
- 8 states: 4,140 partitions

## Metric Scope

The initial metric set uses one-step TPM quantities under uniform interventions. This does not exhaust the conceptual space of Causal Emergence 2.0 or Engineering Emergence. Instead, it creates a stable baseline that other implementations can reproduce exactly before adding richer measures.

Future benchmark families should document any additional metrics, including path-based, intervention-distribution-sensitive, or hierarchy-search-specific values.
