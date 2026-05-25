# Spec Change: Algorithm Harmonization Layer

Status: implemented as a lightweight compatibility layer

Implementation notes:

- `algorithm_family`, `input_view`, `comparison_tier`, `macro_maps`, `scores`,
  and `artifacts` are optional fields in `implementation-result.schema.json`.
- The original minimal CE 1.0 result shape remains valid.
- `cez compare` now checks `comparison_tier` before choosing exact numeric,
  macro-equivalence, rank-agreement, qualitative, or exploratory behavior.
- The initial registry uses closed enums so invalid family/tier names are caught
  early; this can be relaxed later if extension strings become necessary.

## Summary

The zoo currently standardizes finite Markov-system fixtures under one benchmark
convention: uniform interventions, hard state partitions, induced macro TPMs,
effective-information primitives, and `deltaCP` relative to the microscale.

That is enough for CE 1.0-style partition benchmarks, but it does not fully
harmonize newer or adjacent causal-emergence algorithms. This change proposes a
lightweight harmonization layer that lets different implementations report
comparable results without forcing them into one metric or one macro-map type.

## Current Coverage

Already handled:

- Row-stochastic microscale TPMs.
- Hard partitions of microstates into macrostates.
- Uniform-within-block macro interventions.
- Macro TPMs induced by stored partitions.
- Zoo benchmark metrics: entropy primitives, effective information, normalized
  causal power, and `deltaCP`.
- Exhaustive partition lattices for small systems.
- A permissive `implementation-result.schema.json` that can accept extra fields
  from external tools.

Not yet handled as a stable contract:

- Algorithm family identity, such as CE 1.0, CE 2.0, Engineering Emergence,
  network EI, SVD coarse graining, dynamical independence, or learned latent
  macro-dynamics.
- Macro maps other than hard partitions, such as projection matrices, variable
  groupings, hierarchy paths, learned encoders, or stochastic maps.
- Score namespaces other than the zoo's current `causal_power` convention.
- Full hierarchy or multiscale contribution profiles.
- Data-driven inputs such as trajectories with known or learned macro variables.
- Comparison tiers that distinguish exact metric reproducibility from looser
  qualitative agreement.

## Goals

1. Preserve the existing CE 1.0 fixture format as the stable baseline.
2. Let multiple algorithm families submit results against the same benchmark.
3. Make metric and macro-map conventions explicit enough to compare tools.
4. Support hierarchy-level outputs without requiring exhaustive partition data.
5. Keep the core zoo lightweight: fixtures and adapters, not a full analysis
   package.

## Non-Goals

- Do not redefine causal emergence around a single preferred metric.
- Do not require every algorithm to output `deltaCP`.
- Do not require learned or spectral methods to convert their macro maps into
  hard partitions when that would misrepresent the method.
- Do not implement CE 2.0, Engineering Emergence, or SVD search in the zoo core.

## Proposed Concepts

### Algorithm Family

Each external result should declare an `algorithm_family`:

- `ce1_partition_ei`
- `network_ei`
- `ce2_multiscale`
- `engineering_emergence`
- `svd_coarse_graining`
- `dynamical_independence`
- `latent_dynamics`
- `other`

This field identifies the comparison contract, not merely the software package.

### Input View

An `input_view` records what the implementation treated as its primitive object:

- `tpm`: row-stochastic transition matrix.
- `graph`: graph whose transition operator is derived by a documented rule.
- `boolean_network`: local mechanisms or Boolean update rules.
- `trajectory`: observed time series.
- `linear_system`: matrices for a linear stochastic dynamical system.
- `other`: documented externally.

When an input view is not `tpm`, the result should describe how it maps back to a
benchmark TPM or why no exact mapping is claimed.

### Macro Map

A result can report one or more macro maps. Each map declares a `map_type`:

- `partition`: hard grouping of source states.
- `variable_grouping`: grouping of system variables rather than full states.
- `projection_matrix`: linear or spectral projection.
- `stochastic_map`: probabilistic mapping from microstates to macrostates.
- `encoder`: learned representation or latent assignment.
- `hierarchy_path`: ordered sequence of maps across scales.
- `none`: used for algorithms that score emergence without a recovered macro map.

For exact CE 1.0 comparison, `partition` remains the preferred map type.

### Score Namespace

Scores should be namespaced so unrelated quantities are not compared as if they
were identical. Initial namespaces:

- `zoo.ce1`: current zoo metrics, including `causal_power` and `deltaCP`.
- `published.ce1`: paper- or package-specific EI/effectiveness conventions.
- `ce2`: multiscale causal contribution and causal apportioning values.
- `engineering`: hierarchy profile values such as top-heavy, bottom-heavy, or
  scale-free classifications.
- `svd`: spectral emergence or reducibility scores.
- `dynamical_independence`: transfer-entropy or independence-based scores.
- `prediction`: predictive or reconstruction scores used by learned dynamics.

Within a namespace, scores should include their unit or normalization convention
when applicable.

### Comparison Tier

The zoo should support different comparison tiers:

- `exact`: values should match the stored fixture within tolerance.
- `equivalent_macro`: the reported macro map induces the same macro TPM or the
  same partition up to relabeling.
- `rank_agreement`: the implementation ranks the same top partitions or scale
  levels, but metric values differ by convention.
- `qualitative`: the implementation agrees on the fixture role, such as
  no-emergence, top-heavy, mesoscale peak, or multiple-path hierarchy.
- `exploratory`: outputs are stored for inspection without pass/fail claims.

This prevents the zoo from over-penalizing algorithms that are intentionally not
using the current `causal_power` convention.

## Proposed Result Shape

Future implementation results should remain JSON-compatible and may extend the
current schema along these lines:

```json
{
  "benchmark_id": "two_block_noisy_4",
  "implementation": {
    "name": "example-tool",
    "version": "0.1.0",
    "url": "https://example.org"
  },
  "algorithm_family": "ce1_partition_ei",
  "input_view": {
    "type": "tpm",
    "intervention_convention": "uniform_microstates"
  },
  "comparison_tier": "exact",
  "macro_maps": [
    {
      "id": "map_1",
      "map_type": "partition",
      "blocks": [[0, 1], [2, 3]],
      "macro_state_count": 2
    }
  ],
  "scores": [
    {
      "namespace": "zoo.ce1",
      "subject": "map_1",
      "values": {
        "causal_power": 0.531004,
        "deltaCP": 0.104722
      }
    }
  ],
  "artifacts": {
    "macro_tpm": [[0.95, 0.05], [0.05, 0.95]]
  }
}
```

## Benchmark Fixture Extensions

Benchmark systems may optionally add an `algorithm_contracts` section:

```json
{
  "algorithm_contracts": [
    {
      "algorithm_family": "ce1_partition_ei",
      "supported_comparison_tiers": ["exact", "equivalent_macro", "rank_agreement"],
      "reference_outputs": ["microscale", "partitions", "emergent_hierarchy"]
    },
    {
      "algorithm_family": "ce2_multiscale",
      "supported_comparison_tiers": ["qualitative", "exploratory"],
      "reference_outputs": ["emergent_hierarchy"]
    }
  ]
}
```

This section should be optional at first so existing fixtures remain valid.

## Migration Plan

1. Keep existing `benchmark-system.schema.json` and fixtures valid.
2. Add examples of implementation results for at least two families:
   `ce1_partition_ei` and `network_ei`.
3. Extend `implementation-result.schema.json` with optional fields:
   `algorithm_family`, `input_view`, `comparison_tier`, `macro_maps`,
   `scores`, and `artifacts`.
4. Add comparison utilities that first check `comparison_tier` before deciding
   whether to require exact numeric agreement.
5. Add CE 2.0 / Engineering Emergence fixtures as exploratory contracts until
   reference implementations and tolerances are stable.

## Acceptance Criteria

- Existing tests and fixtures continue to pass unchanged.
- A CE 1.0 implementation can still submit the old minimal result shape.
- A network EI implementation can specify its graph-to-TPM convention.
- A CE 2.0 or Engineering Emergence result can report hierarchy-level outputs
  without pretending there is a single best partition.
- A spectral or learned method can report a projection or encoder macro map with
  a documented comparison tier.

## Open Questions

- Should `algorithm_family` be a closed enum in the schema or a documented
  registry with extension strings?
- Should projection matrices and learned encoders be stored inline, by artifact
  path, or both?
- What tolerance policy should apply to `rank_agreement` when scores are tied?
- Should graph-derived TPMs be stored as benchmark systems, benchmark inputs, or
  separate provenance artifacts?
