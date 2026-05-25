# Conventions

This document defines the benchmark conventions used by the stored fixtures. These conventions are part of the data contract.

Other papers or software packages may use different choices. That is fine. The point of the zoo is to make those choices explicit.

## TPM Orientation

All transition probability matrices are row-stochastic.

```text
T[i, j] = P(next state = j | do(current state = i))
```

Each row is a source/intervention state. Each column is a target/effect state.

## Intervention Distribution

The benchmark metrics assume a uniform intervention distribution over the states at the scale being evaluated.

For an `n`-state TPM, each intervention has probability `1 / n`.

## Coarse-Graining

A partition groups microstates into macrostates.

Example:

```json
[[0, 1], [2, 3]]
```

For source macro block `A` and target macro block `B`, the zoo constructs the macro TPM as:

```text
T_macro[A, B] = average over i in A of sum over j in B T_micro[i, j]
```

This corresponds to a uniform intervention over the microstates inside the selected macrostate, followed by summing target probability mass into target macrostates.

## Metrics

For a TPM with `n` states:

- `row_entropy_bits`: average row entropy, `H(effect | intervention)`
- `path_entropy_bits`: `log2(n) + row_entropy_bits`
- `average_effect_entropy_bits`: entropy of the average effect distribution
- `determinism`: `1 - row_entropy_bits / log2(n)`
- `specificity`: `average_effect_entropy_bits / log2(n)`
- `degeneracy`: `1 - specificity`
- `effective_information_bits`: `average_effect_entropy_bits - row_entropy_bits`
- `causal_power`: `effective_information_bits / log2(n)`

For a one-state TPM, normalized quantities are defined as `0.0`.

## deltaCP

For each stored partition:

```text
deltaCP = partition causal_power - microscale causal_power
```

This is the current fixture-level convention. Engineering Emergence also discusses non-redundant apportioning across paths in the lattice. That richer hierarchy convention is a planned compatibility target.

## Partition Enumeration

For small systems, the zoo enumerates every set partition. Current exhaustive fixtures include:

- 3 states: 5 partitions
- 4 states: 15 partitions
- 6 states: 203 partitions
- 8 states: 4,140 partitions

Larger systems should store either selected reference partitions or a documented heuristic trace.
