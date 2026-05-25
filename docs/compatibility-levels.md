# Compatibility Levels

Not every causal-emergence implementation needs to match every stored output immediately. The zoo can be used in levels.

## Level 1: Microscale Metrics

An implementation loads a benchmark TPM and reproduces microscale metrics such as determinism, degeneracy, effective information, and causal power.

## Level 2: Specified Coarse-Grainings

An implementation reproduces macro TPMs and metrics for named partitions.

## Level 3: Exhaustive Small-System Search

An implementation matches all stored partition results for small exhaustive systems.

## Level 4: Best Partition And deltaCP

An implementation identifies the expected best partition and `deltaCP` behavior under the zoo convention.

## Level 5: Hierarchy And Heuristic Traces

An implementation matches richer emergent hierarchy outputs, including path-based apportioning or branching greedy traces where available.

Level 5 is future-facing. The current fixtures are strongest for Levels 1-4.

## Harmonized Tiers

These compatibility levels describe how much of the zoo a tool supports. The implementation result schema also includes comparison tiers, which describe how strict an individual comparison is:

- `exact`
- `equivalent_macro`
- `rank_agreement`
- `qualitative`
- `exploratory`

For example, a CE 1.0 implementation may aim for Level 4 with `exact` comparisons, while an Engineering Emergence implementation may initially submit Level 5-style hierarchy outputs with `exploratory` or `qualitative` comparisons.
