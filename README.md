# causal-emergence-zoo

`causal-emergence-zoo` is a small benchmark and data library for causal emergence research. It is meant to complement analysis packages such as PyMergence, `einet`, and related causal-emergence implementations by providing shared example systems, expected outputs, schemas, and reproducible generators.

The project is intentionally not a full causal-emergence analysis package. Its job is to be a reliable zoo of specimens: finite Markov systems with known or computed multiscale causal structure that other tools can load, validate, plot, and test against.

## Problem This Solves

Causal-emergence implementations can disagree because of bugs, different normalization choices, different intervention distributions, different coarse-graining rules, or different hierarchy-search methods.

Without shared benchmark systems, it is hard to tell whether a disagreement is scientifically meaningful or just a convention mismatch.

`causal-emergence-zoo` provides a calibration contract:

```text
Given this TPM,
under these conventions,
with this coarse-graining rule,
these are the expected multiscale outputs.
```

The goal is to make causal-emergence results easier to compare, debug, and reproduce.

## What Is Included

- Microscale transition probability matrices (TPMs)
- Metadata and conceptual roles for each system
- Tractable partition lattices for small systems
- Coarse-grained TPMs for each stored partition
- Primitive causal values using documented benchmark conventions
- `deltaCP` values relative to the microscale
- Emergent hierarchy summaries
- Reproducible generators and fixed seeds for synthetic systems
- Validation tests that generated fixtures match stored data

## Benchmark Systems

The initial fixtures mix tiny sanity checks with larger exhaustive partition lattices:

- `identity_3`: deterministic identity dynamics, a no-emergence sanity check
- `degenerate_3`: fully degenerate many-to-one dynamics
- `two_block_noisy_4`: a noisy two-equivalence-class system with positive coarse-grained `deltaCP`
- `cycle_4`: a deterministic four-state cycle useful as a pinpoint/coarse-graining testbed
- `mesoscale_cycle_6`: a three-block cycle with 203 stored partitions and a natural mesoscale peak
- `hierarchical_two_cycle_8`: nested pair/component cycles with 4,140 stored partitions and multiple clean macro levels
- `preferential_attachment_alpha0_8`: an unbiased random walk on a seeded preferential-attachment graph
- `preferential_attachment_alpha2_8`: the same graph with hub-biased transitions

## Metric Convention

For a TPM with `n` microstates and uniform interventions:

- `row_entropy_bits`: average entropy of each row, `H(effect | intervention)`
- `path_entropy_bits`: entropy of the intervention-effect path distribution, `log2(n) + row_entropy_bits`
- `specificity`: normalized entropy of the average effect distribution
- `degeneracy`: `1 - specificity`
- `determinism`: `1 - row_entropy_bits / log2(n)`
- `effective_information_bits`: `H(average effect) - row_entropy_bits`
- `causal_power`: normalized effective information, `effective_information_bits / log2(n)`
- `deltaCP`: coarse-scale `causal_power - microscale causal_power`

These are benchmark conventions, not a claim that every causal-emergence paper or package uses identical names. One purpose of the zoo is to make those mappings explicit.

## Repository Layout

```text
data/          Serialized benchmark systems and expected outputs
generators/    Reproducible scripts that recreate benchmark systems
schemas/       JSON schemas for benchmark metadata and result files
notebooks/     Explanatory demos and experiments
src/           Lightweight loading, validation, partition, metric, and plotting utilities
tests/         Regression tests for schemas, metrics, and generated fixtures
docs/          Concept notes and benchmark design docs
```

## Quick Start

```bash
python -m pip install -e ".[dev]"
python generators/generate_starter_systems.py
python -m pytest
```

Load a benchmark:

```python
from causal_emergence_zoo import load_system

system = load_system("two_block_noisy_4")
print(system["microscale"]["metrics"]["causal_power"])
print(system["emergent_hierarchy"]["best_partition"]["deltaCP"])
```

Use the CLI:

```bash
cez list
cez summarize two_block_noisy_4 --notes
cez validate two_block_noisy_4
cez compare two_block_noisy_4 examples/implementation-result.example.json
```

## Passing Information Into The Zoo

There are two main information paths:

1. Add a new benchmark system using `examples/benchmark-input.template.json` and `schemas/benchmark-input.schema.json`.
2. Compare another implementation's output using `examples/implementation-result.example.json` and `schemas/implementation-result.schema.json`.

See [docs/input-format.md](docs/input-format.md) for the full contract.

The implementation-result format now includes an optional harmonization layer for multiple algorithm families, macro-map types, score namespaces, and comparison tiers. This lets CE 2.0, Engineering Emergence, network EI, SVD, dynamical-independence, or learned-latent methods report comparable outputs without pretending to use the same metric.

## Design Goals

1. Provide shared, inspectable fixtures for causal emergence implementations.
2. Keep generators reproducible and small enough to audit.
3. Store expected outputs alongside systems so regressions are obvious.
4. Include exhaustive partition data when tractable and documented heuristics when not.
5. Keep package utilities lightweight; serious analysis belongs in dedicated tools.

## Documentation

- [Problem statement](docs/problem-statement.md)
- [Conventions](docs/conventions.md)
- [Input and comparison formats](docs/input-format.md)
- [Adapter guide](docs/adapter-guide.md)
- [Compatibility levels](docs/compatibility-levels.md)
- [Algorithm harmonization spec](docs/algorithm-harmonization-spec-change.md)
- [Benchmark design](docs/benchmark-design.md)
- [Benchmark cards](docs/benchmarks/README.md)
- [Contributing](CONTRIBUTING.md)

## Roadmap

- Add Hoel CE 2.0-style examples that match published figures more closely.
- Add Engineering Emergence examples with branching greedy hierarchy traces for systems too large to exhaust.
- Add reference plots for each benchmark family.
- Add adapters/examples for comparing outputs from PyMergence and `einet`.

## Maintainer

Started by Thomas Hampton, `ThomasRHampton@gmail.com`.

## Contributing

Contributions should include:

- A generator or enough provenance to reproduce the benchmark
- A metadata entry explaining the conceptual role
- Expected metrics and coarse-grained outputs
- Tests that regenerated data match the stored fixture
- Notes about conventions when they differ from published terminology
