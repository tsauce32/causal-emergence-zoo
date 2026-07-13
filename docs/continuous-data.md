# Continuous Tabular Data

The continuous-data workflow is an experimental, bounded-memory bridge to the
finite-state CE 2.0 implementation. It is designed for CSV or Parquet paths
that are too large to load into Python at once. Pandas and Polars DataFrames are
also accepted for convenience, but are explicitly recorded as caller-materialized
rather than bounded-memory sources.

It does **not** implement native continuous-state Causal Emergence 2.0. Instead,
it learns a small, frozen discrete state model from continuous observations, then
runs exact or explicitly bounded CE 2.0 search over that reported finite TPM. This distinction is preserved in
the output as `analysis_type: "ce2_multiscale_discretized_continuous"`.

## What Scales

The workflow reads the input twice:

```text
pass 1: stream rows → bounded reservoir sample → frozen standardized k-means encoder
pass 2: stream rows → learned state assignments → K × K transition counts → CE 2.0
```

It never retains the whole CSV or its trajectories. Memory grows with:

```text
reservoir_size × feature_count + microstate_count²
```

not with the number of rows. The default reservoir holds 10,000 observations.
Exact CE 2.0 applies to **2–8 learned microstates** because it enumerates
partitions of the learned TPM. The default `auto` search uses a bounded,
dynamically consistent beam search for **9–16 learned microstates**; its result
is explicitly non-exhaustive and is never presented as a global optimum.

## Required CSV Contract

Input must have a header and one or more finite numeric feature columns. For
multi-trajectory data, rows must already be grouped by trajectory and ordered in
time within each group. The streaming reader deliberately does not support
interleaved trajectory IDs because remembering an active state for every ID would
break its bounded-memory guarantee.

Provide either:

- a strictly increasing numeric `--time-column`, or
- `--row-order-is-time` to explicitly declare that row order is temporal.

For example:

```csv
session,time,temperature,pressure
alpha,0,20.1,1.02
alpha,1,20.3,1.01
beta,0,18.9,0.98
beta,1,19.0,0.99
```

Invalid, missing, non-finite, or out-of-order values fail fast. A supplied
`--max-gap` breaks a trajectory at large time gaps instead of fabricating a
transition across the gap.

## Run It

```bash
cez narrate-continuous observations.csv \
  --feature temperature \
  --feature pressure \
  --trajectory-column session \
  --time-column time \
  --microstates 6 \
  --reservoir-size 100000 \
  --seed 7 \
  --json --output continuous-narrative.json
```

Parquet paths use optional Arrow batch streaming. Install the optional readers
with `pip install "causal-emergence-zoo[tabular]"`.

```python
from causal_emergence_zoo import analyze_continuous_csv

result = analyze_continuous_csv(
    country_year_frame,
    feature_columns=["poverty_rate", "education_index"],
    trajectory_column="country_code",
    time_column="year",
    microstate_count=8,
)
```

For a single ordered time series, omit `--trajectory-column` and explicitly set
`--row-order-is-time` if it has no numeric time column:

```bash
cez narrate-continuous measurements.csv \
  --feature signal \
  --row-order-is-time \
  --microstates 4
```

The included [small example](../examples/two-block-continuous.example.csv) can be
run with:

```bash
cez narrate-continuous examples/two-block-continuous.example.csv \
  --feature signal \
  --trajectory-column trajectory_id \
  --time-column time \
  --microstates 4
```

## Encoder Contract

Pass 1 takes a uniform reservoir sample of training observations, standardizes
each feature using that sample, and fits deterministic fixed-seed k-means. Cluster
identifiers are then canonicalized by sorted original-unit centroids. The result
contains the feature means, scales, centroids, seed, reservoir size, and source
file signature.

All rows in pass 2 are assigned to the nearest frozen centroid. New values do not
silently create new states; they are assigned to the closest existing state. This
keeps the TPM dimensions fixed and auditable.

## Optional Holdout

If the file has many independent trajectories, set a trajectory-level holdout:

```bash
--validation-fraction 0.2 --split-seed 17
```

The encoder and CE 2.0 endpoint are selected on the training trajectories. The
chosen path is then scored unchanged on the validation and all-data TPMs. The
library does not rediscover a better path on validation data.

With one long trajectory, leave the validation fraction at its default `0.0`.
Splitting individual adjacent rows would not provide an independent validation
test for this Markov workflow.

## Interpretation Boundaries

## Approximate Larger State Models

Exact CE2 search is retained for 2–8 learned microstates. For 9–16
microstates, the default `auto` mode selects bounded dynamically-consistent
beam search (or request it explicitly):

```bash
cez narrate-continuous observations.csv \
  --feature temperature --feature pressure \
  --trajectory-column session --time-column time \
  --microstates 16 --search-mode beam --beam-width 20 --branching-factor 4
```

This result is a best sampled hierarchy, not a global partition optimum. State
budgets above 16 are rejected by the current implementation. Use the
multiresolution workflow specified in `multiresolution-ce2-spec.md` before
interpreting a larger learned state budget as a substantive scale.

Use `--max-partition-evaluations` to cap approximate search work. The result
records whether that budget was exhausted, so a partial search is never
misreported as a global optimum.

The final narrative contains the encoder, state support, quantization error,
source signature, and a continuous-discretization caveat on every claim. Treat
the result as a model-derived multiscale pattern conditional on:

- selected features and their units;
- sampling interval and trajectory grouping;
- reservoir sample and random seed;
- k-means' Euclidean geometry and state budget;
- Markov, stationarity, and intervention assumptions; and
- strict or explicitly relaxed dynamic-consistency tolerance.

The pipeline does not infer interventions from observational data. It is useful
for systematically proposing, auditing, and stress-testing multiscale narratives;
external causal knowledge is still needed to treat the transition model as an
interventional one.

## Temporal Change Features

Use `--temporal-difference 1` to append one-step within-trajectory changes, or
`--temporal-volatility-window 5` to append trailing five-observation volatility.
Rows without sufficient prior history are dropped; transformations never cross a
trajectory or declared gap boundary. These features let the learned states
distinguish a stable country from a similarly situated country that is rapidly
changing.

## Validation Outputs

Every continuous result reports negative log likelihood for the frozen selected
micro TPM on selection, validation, and all-data transitions. With
`--null-replicates N`, it also evaluates a transition-target permutation null
that preserves source outgoing counts and the global target distribution while
breaking source-target association. This is a transition-level null, not a full
within-trajectory time shuffle; the result labels that limitation explicitly.

For independent trajectories, opt into the stronger trajectory-respecting
checks below. They replay the frozen encoder, preserve trajectory membership,
and materialize complete encoded trajectories for the requested resampling, so
they are not part of the bounded-memory path.

```bash
cez narrate-continuous observations.parquet \
  --feature temperature --feature pressure \
  --trajectory-column session --time-column time \
  --microstates 6 \
  --trajectory-null-replicates 200 --trajectory-null-seed 17 \
  --grouped-bootstrap-replicates 500 --grouped-bootstrap-seed 19
```

The trajectory null shuffles state order only within each trajectory; the
bootstrap resamples complete trajectories and reports percentile intervals for
endpoint CP and CP gain. Both are stability checks conditional on the frozen
state encoding, not tests of interventionally identified causation.
