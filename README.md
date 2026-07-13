# causal-emergence-zoo

`causal-emergence-zoo` is a benchmark suite and experimental analysis library for causal-emergence research. It complements analysis packages such as PyMergence, `einet`, and related implementations with shared example systems, expected outputs, schemas, reproducible generators, and a careful CE 2.0 exploration workflow.

The benchmark zoo remains its calibration core: finite Markov systems with known
or computed multiscale causal structure that other tools can load, validate,
plot, and test against. It also contains an **experimental CE 2.0 narrative and
continuous-data workflow** for cautious, evidence-linked exploration. It remains
conservative about causal claims: fitted observational dynamics are never
presented as independently identified interventions.

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
src/causal_emergence_zoo/data/
               Packaged benchmark systems and expected outputs
generators/    Reproducible scripts that recreate benchmark systems
schemas/       JSON schemas for benchmark metadata and result files
notebooks/     Explanatory demos and experiments
src/           Lightweight loading, validation, partition, metric, plotting, and CLI utilities
tests/         Regression tests for schemas, metrics, and generated fixtures
docs/          Concept notes and benchmark design docs
```

## First Analysis in Five Minutes

Install the ordinary user package:

```bash
python -m pip install causal-emergence-zoo
```

Then run one command:

```bash
cez demo
```

It writes `cez-social-demo-report.html` and `cez-social-demo-result.json` in
the current directory. Open the HTML file in a browser to inspect the learned
states, CE response chart, macro dynamics, narrative claims, caveats, and
supporting evidence. The bundled country-year example is **synthetic**; it is
for learning the workflow, not evidence about real countries, religion,
poverty, or violence. See the [first-analysis guide](docs/first-analysis.md).
For Parquet files or Pandas/Polars DataFrames later, install the optional
readers with `python -m pip install "causal-emergence-zoo[tabular]"`.

## Developer Quick Start

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
cez greedy mesoscale_cycle_6 --paths 20 --branching-factor 2
cez validate two_block_noisy_4
cez compare two_block_noisy_4 examples/implementation-result.example.json
cez compare two_block_noisy_4 examples/svd-equivalent-macro.example.json
cez compare mesoscale_cycle_6 examples/rank-agreement.example.json
```

Run a branching greedy search from Python:

```python
from causal_emergence_zoo import branching_greedy_search, load_system

system = load_system("mesoscale_cycle_6")
result = branching_greedy_search(system["microscale"]["tpm"], n_paths=20, branching_factor=2)
print(result["best_partition"]["blocks"])
print(result["best_partition"]["deltaCP"])
```

## Guided Exploration

For an unfamiliar grouped numeric CSV, CSV.GZ, or Parquet path, generate a documented plan, full JSON
result, and self-contained report with SVG charts:

```bash
cez explore observations.csv \
  --entity session --time time \
  --report report.html --output result.json
```

The report includes resolution response, state support, macro dynamics,
feature-grounded state descriptions, validation evidence, and selectable
claim-level support/counterevidence. From Python, `explore()` also accepts
Pandas and Polars DataFrames; file paths preserve bounded-memory input semantics.
Install optional readers with `pip install "causal-emergence-zoo[tabular]"`. See the
[guided exploration guide](docs/guided-exploration.md).

## Stable v0.2 API

The original dictionary-returning functions remain available. For new work, use
the typed v0.2 workflow, which gives each stage a versioned, serializable object:

```python
from causal_emergence_zoo import explore_typed

result = explore_typed("country_year.parquet", entity="country_code", time="year")
print(result.summary())
result.export_report("report.html")
```

See the [public API contract](docs/public-api.md) and [changelog](CHANGELOG.md)
for migration and artifact details.

## Experimental CE 2.0 Narrative Workflow

For small discrete trajectory datasets, the package can estimate a first-order
Markov TPM, find dynamically consistent CE 2.0 scales, apportion CP gains along
a nested micro-to-macro path, and return an auditable narrative graph.

```bash
cez narrate examples/two-block-trajectories.example.json
cez narrate examples/two-block-trajectories.example.json --json --output narrative.json
```

```python
from causal_emergence_zoo import analyze_trajectories

result = analyze_trajectories(
    [["A", "A", "B", "B", "A"], ["C", "C", "D", "D", "C"]],
    state_labels=["A", "B", "C", "D"],
)
print(result["narrative_text"])
```

This prototype follows the CE 2.0 path formulation, rather than reinterpreting
the existing best-partition hierarchy as CE 2.0. It performs exhaustive search
through eight states, then automatically uses a bounded, dynamically consistent
beam search for 9–16 states. Beam results explicitly report their budget,
coverage, and non-global-optimality; they are not exact CE 2.0 optima.
Trajectory-derived models remain labelled observational. See [the narrative API guide](docs/narrative-api.md).

## Streaming Continuous CSV Workflow

Large continuous datasets can now be streamed through a bounded-memory bridge:
a reservoir-sampled, frozen k-means encoder converts observations into 2–8
learned microstates for exact CE 2.0, or 9–16 learned microstates for the
explicitly bounded beam search. The package builds a finite TPM in either case;
this is not native continuous-state CE 2.0. Beam results report non-exhaustive
coverage and must not be interpreted as global CE 2.0 optima.

```bash
cez narrate-continuous observations.csv \
  --feature temperature --feature pressure \
  --trajectory-column session --time-column time \
  --microstates 6 --reservoir-size 100000 \
  --json --output continuous-narrative.json
```

The file is read twice but never loaded in full. Rows must be grouped by
trajectory and time ordered; arbitrary interleaved IDs are intentionally not
supported in bounded-memory mode. This is a discretized continuous-data bridge,
not native continuous-state CE 2.0. See [the continuous-data guide](docs/continuous-data.md).

## Passing Information Into The Zoo

There are two main information paths:

1. Add a new benchmark system using `examples/benchmark-input.template.json` and `schemas/benchmark-input.schema.json`.
2. Compare another implementation's output using `examples/implementation-result.example.json` and `schemas/implementation-result.schema.json`.

See [docs/input-format.md](docs/input-format.md) for the full contract.

The implementation-result format now includes an optional harmonization layer for multiple algorithm families, macro-map types, score namespaces, and comparison tiers. This lets CE 2.0, Engineering Emergence, network EI, SVD, dynamical-independence, or learned-latent methods report comparable outputs without pretending to use the same metric.

Benchmark fixtures are package data. A normal wheel install can load them with `load_system()`; an editable checkout is not required.

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
- [CE 2.0 narrative API](docs/narrative-api.md)
- [Hoel CE 2.0 paper reference systems](docs/ce2-paper-reference.md)
- [Streaming continuous data](docs/continuous-data.md)
- [Multiresolution CE2 improvement specification](docs/multiresolution-ce2-spec.md)
- [Five-minute first analysis](docs/first-analysis.md)
- [Guided exploration and HTML reports](docs/guided-exploration.md)
- [Continuous multiscale recovery case study](docs/continuous-recovery-case-study.md)
- [Social-system atlas benchmark](docs/social-system-atlas.md)
- [RAS3 religion-policy empirical pilot](docs/benchmarks/ras3-religion-policy-pilot.md)
- [Benchmark design](docs/benchmark-design.md)
- [Benchmark cards](docs/benchmarks/README.md)
- [Contributing](CONTRIBUTING.md)

## Roadmap

- Expand the Hoel CE 2.0 reference suite when exact paths or supplementary fixtures are published.
- Benchmark approximate CE 2.0 search on larger published and domain-specific systems.
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
