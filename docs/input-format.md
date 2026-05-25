# Passing Information Into The Zoo

There are two common ways to pass information into `causal-emergence-zoo`.

## 1. Add A New Benchmark

Use this path when you want to contribute a new causal system to the zoo.

Start with a human-authored benchmark input specification:

```text
examples/benchmark-input.template.json
schemas/benchmark-input.schema.json
```

The minimum information is:

- `id`: stable machine-readable name
- `name`: human-readable name
- `description`: what the system is
- `conceptual_role`: why the system belongs in the zoo
- `state_labels`: labels for each state
- `tpm`: row-stochastic microscale transition matrix
- `expected_behavior`: qualitative behavior a compatible implementation should find
- `provenance`: generator, seed, paper, or empirical source

The generated benchmark fixture in `data/` then adds:

- computed metrics
- partition results
- coarse-grained TPMs
- `deltaCP`
- hierarchy summaries

## 2. Compare Another Implementation

Use this path when another causal-emergence tool wants to test itself against the zoo.

That tool can write a result JSON shaped like:

```text
examples/implementation-result.example.json
schemas/implementation-result.schema.json
```

Then compare it with:

```bash
cez compare two_block_noisy_4 examples/implementation-result.example.json
```

The comparison format is intentionally partial. A tool can start by reporting only microscale metrics, then later add best partitions, `deltaCP`, or full partition results.

## CLI Commands

List available benchmarks:

```bash
cez list
```

Summarize a benchmark:

```bash
cez summarize two_block_noisy_4 --notes
```

Validate stored fixtures:

```bash
cez validate two_block_noisy_4
cez validate data/two_block_noisy_4.json
```

Compare an implementation result:

```bash
cez compare two_block_noisy_4 examples/implementation-result.example.json
```
