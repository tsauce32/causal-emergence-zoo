# Concepts

This project is a benchmark zoo for causal emergence research. It focuses on example systems and expected outputs, not on replacing full analysis libraries.

The practical question it answers is: if a causal-emergence implementation analyzes this TPM under the zoo convention, what should it return?

## Causal Emergence

Causal emergence studies cases where a macro description of a system can have stronger or cleaner causal structure than the micro description. In finite Markov systems, this often means grouping microstates into macrostates and comparing causal quantities across scales.

## Transition Probability Matrices

The initial zoo uses row-stochastic transition probability matrices. Row `i` is the probability distribution over next states after intervening on source state `i`.

## Coarse Graining

A coarse graining is represented as a partition of microstates. For example:

```json
[[0, 1], [2, 3]]
```

This means states `0` and `1` form one macrostate, while states `2` and `3` form another.

## Benchmark Roles

Fixtures are labeled by conceptual role so tests can ask targeted questions:

- `no emergence`: the microscale should be at least as strong as coarser scales
- `fully degenerate`: deterministic rows collapse to the same effect
- `top-heavy emergence`: a coarse scale has higher normalized causal power
- `mesoscale peak`: an intermediate scale beats both bottom and top scales
- `pinpoint emergence`: a special coarse graining or path structure is expected to matter
- `multiple-path hierarchy`: more than one hierarchy-search path is informative
- `network TPM`: the TPM is induced by graph structure rather than hand-authored equivalence classes

These labels are guides for benchmark design. The serialized metrics are the regression-testable source of truth.
