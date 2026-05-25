# Adapter Guide

This guide is for maintainers of causal-emergence tools that want to test against `causal-emergence-zoo`.

## Minimal Workflow

Load a benchmark:

```python
from causal_emergence_zoo import load_system

benchmark = load_system("two_block_noisy_4")
tpm = benchmark["microscale"]["tpm"]
```

Run your implementation on `tpm`, then write a result JSON shaped like:

```json
{
  "benchmark_id": "two_block_noisy_4",
  "implementation": {
    "name": "my-causal-emergence-tool",
    "version": "0.1.0"
  },
  "algorithm_family": "ce1_partition_ei",
  "input_view": {
    "type": "tpm",
    "intervention_convention": "uniform_microstates"
  },
  "comparison_tier": "exact",
  "macro_maps": [
    {
      "id": "best_map",
      "map_type": "partition",
      "blocks": [[0, 1], [2, 3]],
      "macro_state_count": 2
    }
  ],
  "scores": [
    {
      "namespace": "zoo.ce1",
      "subject": "best_map",
      "values": {
        "causal_power": 0.531004406411,
        "deltaCP": 0.265502203206
      }
    }
  ],
  "microscale": {
    "metrics": {
      "causal_power": 0.265502203205
    }
  },
  "best_partition": {
    "partition_id": "01|23",
    "blocks": [[0, 1], [2, 3]],
    "deltaCP": 0.265502203206
  }
}
```

Compare it:

```bash
cez compare two_block_noisy_4 my-result.json
```

## Partial Results Are Allowed

You do not need to report every field at first. Start with the fields your implementation supports:

- microscale metrics
- named coarse-grained TPMs
- best partition
- `deltaCP`
- full partition results

The comparison schema is intentionally permissive so adapters can grow over time.

## Algorithm Families

Set `algorithm_family` to the comparison contract your result is trying to satisfy:

- `ce1_partition_ei`
- `network_ei`
- `ce2_multiscale`
- `engineering_emergence`
- `svd_coarse_graining`
- `dynamical_independence`
- `latent_dynamics`
- `other`

This is not the software package name. Put the package name under `implementation.name`.

## Comparison Tiers

Use `comparison_tier` to tell the zoo how strict the comparison should be:

- `exact`: numeric values should match stored fixture values within tolerance
- `equivalent_macro`: the macro map should match the expected macro partition up to relabeling
- `rank_agreement`: top-ranked partitions or levels should agree, but values may differ
- `qualitative`: the role/classification should agree, such as top-heavy or mesoscale peak
- `exploratory`: store outputs for inspection without pass/fail claims

This lets CE 2.0, Engineering Emergence, spectral, and learned-latent methods report meaningful results without pretending they use the zoo's CE 1.0 metric convention.

## Match The Convention First

Before interpreting mismatches, check:

- TPM orientation
- intervention distribution
- macro TPM construction
- causal power normalization
- `deltaCP` definition

These are documented in `docs/conventions.md`.
