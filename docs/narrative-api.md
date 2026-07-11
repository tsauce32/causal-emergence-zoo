# CE 2.0 Narrative API

This repository now includes an experimental, dependency-free vertical slice for
turning small discrete trajectories into an evidence-linked multiscale narrative.
It follows the finite-Markov-chain, hard-partition setting of Erik Hoel's
[Causal Emergence 2.0](https://arxiv.org/html/2503.13395): a relevant
description is a dynamically consistent scale on a nested micro-to-macro path,
not simply the single partition with the best score.

## Scope

The v0 workflow supports:

- Independent trajectories of discrete states
- Empirical first-order, time-homogeneous Markov TPM estimation
- Exhaustive CE 2.0 search for up to eight states
- Strict finite-horizon dynamical-consistency checks
- Endpoint selection by CP, then a longest valid nested path
- Consecutive CP apportioning and emergent-complexity entropy
- JSON-serializable narrative graphs plus deterministic prose
- Optional trajectory-resampling bootstrap stability

It supports a separate streaming bridge from continuous CSV observations to a
frozen learned finite-state model. It does not yet support native continuous-state
CE 2.0, learned latent dynamics beyond the declared k-means encoder,
black-boxing, higher-order macrostates, unbounded consistency checks, or scalable
CE 2.0 heuristics. Do not label a larger-state heuristic as an exact CE 2.0
result.

## Quick Start

```python
from causal_emergence_zoo import analyze_trajectories

result = analyze_trajectories(
    [
        ["A", "A", "B", "B", "A", "B", "A"],
        ["C", "C", "D", "D", "C", "D", "C"],
    ],
    state_labels=["A", "B", "C", "D"],
)

print(result["narrative_text"])
print(result["narrative_graph"]["claims"])
```

Or use the CLI:

```bash
cez narrate examples/two-block-trajectories.example.json
cez narrate examples/two-block-trajectories.example.json --json --output narrative.json
```

The input is a JSON object with independent `trajectories`, an optional explicit
`state_labels` ordering, and optionally `smoothing`. The end of one trajectory
is never treated as a transition into the next trajectory.

Bootstrap stability is opt-in. Use it only when the dataset contains enough
independent trajectories for resampling not to eliminate an observed source
state; its output reports failed replicates rather than silently imputing rows.

## CE 2.0 Implementation Contract

For each candidate partition, the implementation:

1. Induces a macro TPM using the zoo's uniform-within-block intervention rule.
2. Checks dynamic consistency by comparing projected micro random walks to macro
   random walks from every microstate through a configurable horizon (default 5),
   using total KL divergence.
3. Discards inconsistent coarse grains.
4. Defines CP as `determinism + specificity - 1`, numerically equal to this
   project's existing `causal_power` metric.
5. Selects the dynamically consistent endpoint with highest CP; ties favour the
   highest-dimensional scale, as described in CE 2.0.
6. Selects a longest nested valid path to that endpoint and computes each scale's
   CP increment relative to the previous scale—not relative to the microscale.
7. Computes emergent complexity as the entropy of non-negative path increments.
   If a supplied path contains material negative increments, entropy is reported
   as undefined instead of silently rewriting the path's evidence.

The `ce2` field stores the full path, increments, endpoint, consistency policy,
and emergent-complexity result. The `narrative_graph` stores nodes, model
transition edges, claims, evidence IDs, and caveats. Prose is only a rendering
of this graph.

## Causal Interpretation

`estimate_tpm_from_trajectories()` estimates conditional dynamics from observed
data. It does not turn observational transitions into experimental interventions.
The narrative API therefore describes trajectory input as
`model_derived_not_interventionally_identified` and attaches that caveat to every
claim. Use `narrate_tpm()` when the TPM comes from a separately justified causal
or intervention model, and declare its provenance in `source`.

## Public API

```python
from causal_emergence_zoo import (
    analyze_ce2_path,
    analyze_continuous_csv,
    analyze_trajectories,
    check_dynamical_consistency,
    discover_ce2_path,
    estimate_tpm_from_trajectories,
    fit_continuous_csv_encoder,
    narrate_tpm,
)
```

- `estimate_tpm_from_trajectories(...)`: validates independent discrete
  trajectories and returns an empirical TPM and count diagnostics.
- `check_dynamical_consistency(...)`: exposes the strict finite-horizon random
  walk comparison for a proposed macro partition.
- `discover_ce2_path(...)`: exhaustively discovers a valid small-system CE 2.0
  endpoint and path.
- `analyze_ce2_path(...)`: validates and apportions a user-supplied nested path;
  it intentionally does not claim global optimality.
- `narrate_tpm(...)`: produces a narrative graph from a supplied TPM.
- `analyze_trajectories(...)`: the end-to-end estimation and narrative wrapper.

For large continuous CSV input, use `analyze_continuous_csv(...)` or
`cez narrate-continuous`. See [the streaming continuous-data guide](continuous-data.md).

## Reading Results Responsibly

`status: "emergent"` means a dynamically consistent coarser endpoint has a
positive CP gain in the stated model and selected path. It does not mean the
library discovered an independent physical cause, a semantic explanation, or a
validated intervention. The structured evidence and caveats are part of the
result contract, not optional boilerplate.
