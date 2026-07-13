# Specification: Multiresolution CE2 for Continuous and Panel Data

Status: proposed

Target milestone: `0.2.0`

## Summary

> **Implementation status (v0.2):** the current supported envelope is 2–8
> exact learned microstates and 9–16 bounded beam-search microstates. The
> 32-state references below are a forward-looking design target, not current
> implementation behavior.

This change extends the continuous-data workflow from a single exact analysis
with 2–8 learned microstates to a validated multiresolution workflow supporting
up to 32 learned microstates.

The workflow will characterize how causal-emergence results vary with the
upstream discretization resolution. Cross-resolution recurrence is evidence of
robustness, but it is **not a necessary condition** for a CE2 result. A result
that occurs only near a particular resolution may indicate a characteristic
scale of the fitted model and must remain reportable as a resolution-specific
finding.

The change also adds temporal change features, bounded approximate CE2 search,
state-support safeguards, trajectory holdout, seed replication, and temporal
null models. Together these features distinguish a stable multiscale narrative,
a meaningful resolution peak, and an isolated modeling artifact.

## Scientific Distinction

Two uses of “scale” must remain separate in code, schemas, and documentation:

1. **Discretization resolution** is the number of learned microstates used to
   represent continuous observations. Comparing 8, 16, and 32 learned states is
   model selection outside CE2 proper.
2. **CE2 causal scale** is a dynamically consistent coarse-grain of one fixed
   microstate TPM. Causal apportioning along that fixed hierarchy is the CE2
   analysis described by Hoel.

The library must never imply that agreement across different learned
discretizations is an axiom or requirement of CE2.

## Goals

1. Support bounded-memory continuous analyses with 2–32 learned microstates.
2. Preserve exhaustive CE2 behavior for 2–8 states.
3. Use explicitly approximate search above the exhaustive limit.
4. Analyze a caller-selected set of resolutions in one reproducible run.
5. Detect plateaus, localized peaks, and recurring macrostructure across
   resolutions without using them as automatic acceptance gates.
6. Represent both system condition and temporal movement.
7. Quantify sensitivity to encoder seed, held-out trajectories, and destroyed
   temporal order.
8. Prevent low-support learned states from generating unqualified narratives.
9. Keep all conclusions evidence-linked and conditional on the fitted model.

## Non-Goals

- This change does not implement native continuous-state CE2.
- It does not turn observational transitions into identified interventions.
- It does not claim global optimality for approximate partition search.
- It does not require every real system to possess a resolution-stable
  hierarchy.
- It does not treat cluster count as a physical or ontological state count.
- It does not silently interpolate missing social indicators.
- It does not automatically choose substantive names for learned regimes.

## Terminology

- **Resolution:** requested learned microstate count, `K`.
- **Resolution run:** one complete encoder, TPM, search, and validation result at
  one `K` and one seed.
- **Resolution profile:** the ordered set of resolution runs.
- **Anchor observations:** a frozen evaluation sample encoded at every
  resolution and used to compare macro assignments across incompatible state
  spaces.
- **Characteristic resolution:** a localized resolution or range with a
  reproducible CE signal stronger than neighboring resolutions.
- **Recurrence:** materially similar macro assignments reappearing at separated
  resolutions.
- **Plateau:** materially similar macrostructure across adjacent resolutions.
- **Isolated spike:** a CE signal found at one resolution that is not stable to
  seed, holdout, or modest preprocessing changes.

## Proposed Public API

The existing single-resolution call remains valid:

```python
analyze_continuous_csv(
    path,
    feature_columns=[...],
    microstate_count=8,
)
```

The following options are added:

```python
# The 24/32-state values below illustrate the forward-looking design target;
# the current implementation accepts resolutions through 16 only.
analyze_continuous_multiresolution_csv(
    path,
    feature_columns=[...],
    resolutions=[4, 8, 12, 16, 24, 32],
    search_mode="auto",
    encoder_seeds=[7, 17, 29],
    validation_fraction=0.2,
    temporal_features={
        "differences": [1],
        "trends": [3, 5],
        "volatility_windows": [5],
    },
    support={
        "minimum_state_observations": 25,
        "minimum_outgoing_transitions": 20,
    },
    null_models=["within_trajectory_time_shuffle"],
)
```

`search_mode` accepts:

- `exact`: require `K <= 8`; fail otherwise.
- `beam`: use dynamically consistent bounded beam search.
- `auto`: exact for `K <= 8`, beam otherwise.

The single-resolution API may later accept `search_mode`, but its default must
preserve current exact behavior and the current eight-state safety limit until
the approximate result schema is stable.

## Temporal Feature Contract

Temporal features are computed within trajectory boundaries only. They must
never cross countries, subjects, sessions, missing-data gaps, or a caller's
`max_gap` boundary.

Supported transformations:

- lagged difference: `x[t] - x[t-lag]`;
- least-squares trend over a trailing window;
- trailing standard deviation or robust dispersion;
- optional acceleration: change in the first difference.

Every derived feature records:

- source feature;
- transformation;
- lag or window;
- leading-row policy;
- gap policy;
- original units.

The default leading-row policy is `drop_until_defined`. No zero-filling is
allowed unless explicitly requested and recorded.

Streaming memory remains bounded by the longest requested window per active
trajectory. The existing grouped-trajectory input contract remains in force.

## State Estimation and Support

Each resolution uses the current frozen standardized k-means encoder unless a
future encoder is explicitly selected. Cluster identifiers remain canonicalized
by lexicographic original-unit centroid order.

A learned state is under-supported when either:

- its training observation count is below `minimum_state_observations`; or
- its outgoing training-transition count is below
  `minimum_outgoing_transitions`.

Under-supported runs are not silently repaired. The configured policy is one of:

- `reject_run` (default for confirmatory analysis);
- `reduce_resolution_and_refit` (allowed only when recorded as an adaptive
  choice);
- `retain_exploratory` (result cannot support a substantive narrative).

TPM smoothing is explicit and reported. It must not be used to make a partition
appear dynamically consistent. Raw counts and smoothed probabilities are both
retained.

## Search Above Eight States

Approximate search uses the existing dynamically consistent beam-search core,
extended with:

- configurable beam width and branching factor;
- cached partition scores and consistency checks;
- early rejection of merges involving inadequate transition support;
- deterministic ranking and tie-breaking;
- time and sampled-partition budgets;
- explicit termination reason;
- best-sampled endpoint and path;
- no global-optimality claim.

The result must include:

```json
{
  "search": {
    "mode": "beam",
    "is_exhaustive": false,
    "endpoint_optimality": "best_sampled_not_global",
    "beam_width": 20,
    "branching_factor": 4,
    "sampled_partition_count": 812,
    "termination_reason": "search_complete"
  }
}
```

Approximate consistency tolerances remain scientific parameters, not search
conveniences. Strict and relaxed results must never be pooled without labels.

## Cross-Resolution Comparison

Partition identifiers cannot be compared directly across resolutions because
their microstates differ. Comparison therefore uses anchor observations:

1. Freeze a bounded sample of training and validation observations.
2. Encode each anchor observation at every resolution.
3. Map its learned microstate to the selected macrostate for that run.
4. Compare the resulting anchor-level macro assignments.

The initial comparison metrics are:

- adjusted mutual information;
- variation of information;
- pairwise co-assignment agreement;
- macrostate-count difference;
- endpoint CP and CE difference.

Macrostate labels are aligned only for display. Scientific comparison uses
label-invariant metrics.

## Resolution-Profile Classification

Classification describes evidence; it does not accept or reject CE2 results.

### Plateau

Adjacent successful resolutions have materially similar anchor assignments and
positive CE. Report as broad discretization robustness.

### Characteristic Resolution Peak

One resolution or a short adjacent range has reproducible positive CE while
neighboring resolutions are weaker or absent. Report the peak as a conditional,
resolution-specific finding when seed and holdout evidence support it.

### Recurrence

Similar macro assignments reappear at separated resolutions. Report the
observed recurrence and candidate modular interpretation. Do not call it
periodic unless at least three occurrences support an explicit spacing model.

### Isolated Unstable Spike

A positive result fails seed, holdout, support, or null checks. Retain it as an
exploratory finding and suppress strong narrative language.

### No Detected Emergence

No analyzed resolution yields a positive supported macro contribution. This is
conditional on the analyzed resolutions, features, estimators, and search
budgets.

### Indeterminate

Coverage, state support, search completion, or validation is insufficient.

Thresholds for “materially similar” and “reproducible” are configuration values
stored in the result. They must not be hidden constants.

## Validation Layers

Each resolution run can carry four distinct evidence layers.

### Encoder-Seed Replication

Repeat state learning with multiple declared seeds. Compare endpoint CP, CE,
macro assignments, state support, and hierarchy profile.

### Trajectory Holdout

Fit the encoder and select the hierarchy on training trajectories. Freeze both
before scoring validation trajectories. For country panels, countries—not
country-years—are the split unit.

### Temporal Null Models

At minimum support within-trajectory time shuffling. This preserves the
observation distribution while destroying ordered dynamics. Additional nulls
may include transition rewiring that preserves state occupancy or degree.

The main report includes the empirical statistic, null distribution, replicate
count, seed, and empirical tail probability. A null comparison evaluates
temporal dependence; it does not establish intervention causality.

### Predictive Check

Score the frozen micro and macro TPMs on held-out transitions using log loss or
Brier score. Predictive improvement is supporting evidence, not a CE2
requirement, and remains namespaced separately from CP.

## Proposed Result Shape

```json
{
  "kind": "causal_emergence.multiresolution_profile",
  "schema_version": "0.1.0",
  "resolutions_requested": [4, 8, 12, 16, 24, 32],
  "resolution_runs": [],
  "comparison": {
    "anchor_sample": {},
    "adjacent_similarity": [],
    "separated_recurrence": []
  },
  "profile": {
    "classification": "characteristic_resolution_peak",
    "characteristic_resolutions": [8],
    "classification_is_acceptance_gate": false,
    "evidence_ids": []
  },
  "validation": {
    "seed_replication": {},
    "trajectory_holdout": {},
    "temporal_nulls": {},
    "prediction": {}
  },
  "claims": [],
  "limitations": []
}
```

Each `resolution_run` embeds or references a normal `CausalHierarchy`, encoder,
transition estimate, search record, support audit, and any resolution-specific
claims.

## Narrative Policy

Narratives distinguish three claim levels:

1. **Model finding:** “At 8 learned states, the fitted model has a positive CE2
   gain.” This requires a valid resolution run only.
2. **Resolution-specific interpretation:** “The signal is concentrated near 8
   states and replicates across seeds.” This requires seed evidence and adequate
   support, but not a plateau.
3. **Robust multiresolution interpretation:** “A similar macrostructure recurs
   across 12–32 states and generalizes to held-out trajectories.” This requires
   the stated comparison and holdout evidence.

The renderer must never rewrite level 1 as level 3. An isolated result remains
visible; it is qualified rather than discarded.

For observational social data, every causal-sounding claim retains the existing
model-derived caveat. The library may describe transitions among fitted regimes
but may not state that religion, poverty, democracy, or conflict causes another
variable without an external causal-identification design.

## Backward Compatibility

- Existing `analyze_continuous_csv` calls and outputs remain valid.
- Exact CE2 results for `K <= 8` must be numerically unchanged.
- Existing narrative consumers may ignore the new multiresolution object.
- The multiresolution API is additive during the `0.2.x` series.
- Schema changes use optional fields until at least two empirical benchmarks are
  reproduced end to end.

## Implementation Sequence

1. Add bounded temporal feature generation and tests for trajectory/gap
   boundaries.
2. Generalize continuous transition estimation to `K <= 32` independently of
   exact search.
3. Integrate `search_mode=auto|exact|beam` and approximate-search metadata.
4. Add state-support auditing and policies.
5. Implement one-resolution seed replication and trajectory holdout.
6. Implement multiresolution orchestration and anchor-observation comparison.
7. Add temporal null models and predictive checks.
8. Add profile classification and evidence-tiered narrative rendering.
9. Re-run synthetic, Hoel-reference, continuous-recovery, and RAS3 benchmarks.

## Acceptance Criteria

### Correctness

- All existing tests remain green.
- Exact results for every current `K <= 8` fixture are unchanged.
- Temporal features never cross trajectory or declared gap boundaries.
- Anchor comparison is invariant to state and macrostate label permutations.
- Beam results explicitly report non-exhaustive optimality.
- A resolution-specific positive result is retained even when no plateau exists.

### Scientific Guardrails

- Under-supported states cannot produce an unqualified narrative.
- Train-selected encoders and paths are frozen on validation data.
- Null models preserve their declared marginal properties.
- Strict and relaxed consistency results are labeled separately.
- Missing values are never silently imputed.
- Observational narratives retain model-derived causal caveats.

### Performance

- Streaming memory remains independent of input row count.
- A 32-state TPM requires `O(32^2)` count storage plus configured reservoir,
  temporal windows, beam, and anchor samples.
- Every approximate run accepts explicit time and partition budgets.
- Partial results are serializable when a budget is reached.

### Benchmark Outcomes

- The synthetic two-block continuous benchmark recovers its known macrostructure
  across at least one declared resolution range.
- Hoel finite-state reference values remain exact.
- The RAS3 pilot is classified as a resolution-specific or unstable signal,
  rather than broad multiresolution robustness, unless new evidence changes that
  result.

## Open Decisions

The implementation PR must resolve and document:

- default beam width and branching factor for 9–32 states;
- default support thresholds as absolute counts versus data-dependent rules;
- anchor-sample size and train/validation composition;
- similarity metrics and default reporting thresholds;
- whether adaptive resolution reduction is available in the first release;
- number of null and seed replicates used by quick and confirmatory profiles;
- whether temporal features are materialized into a derived CSV artifact or
  computed only during streaming.
