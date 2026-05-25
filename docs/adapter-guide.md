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

## Match The Convention First

Before interpreting mismatches, check:

- TPM orientation
- intervention distribution
- macro TPM construction
- causal power normalization
- `deltaCP` definition

These are documented in `docs/conventions.md`.
