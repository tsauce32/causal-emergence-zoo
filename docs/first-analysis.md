# First analysis in five minutes

The fastest way to see the full workflow is the bundled social-system-style
demo. It needs no download and writes both a portable HTML report and a full
JSON artifact.

```console
python -m pip install causal-emergence-zoo
cez demo
```

The second command writes these files in the current directory:

- `cez-social-demo-report.html` - a self-contained report with interactive
  charts, state descriptions, narrative claims, evidence, and limitations.
- `cez-social-demo-result.json` - the profile, analysis plan, learned encoder,
  transition models, hierarchy, and evidence ledger needed to reproduce the
  report.

Open the HTML report in any modern browser. Start with the CE-by-resolution
chart, then select a run and a narrative claim to inspect its measured support,
counterevidence, and caveats.

## What the demo is

The dataset contains deterministic, fictional country codes observed across
successive fictional years. Its four numeric features are styled after poverty,
social capacity, religious restriction, and organized violence. The generator
deliberately creates recurring configurations so that the report has something
useful to inspect on a first run.

It is not a public-country dataset, it does not represent any country or
population, and its output cannot support a claim about the causes of poverty,
religion, violence, or political capacity. The report preserves this caveat in
its limitations section.

The demo uses two modest learned-state resolutions (4 and 6) and a fixed seed
so it completes quickly and is reproducible. Those choices are teaching
parameters, not a state-count recommendation for your data.

## Move to your own data

For a grouped, time-ordered numeric CSV, CSV.GZ, or Parquet file, replace the
demo command with:

```console
cez explore observations.csv \
  --entity country_code --time year \
  --report report.html --output result.json
```

The file must be ordered by entity and then time. `cez explore` profiles the
data before choosing a documented plan; it does not silently impute missing
numeric values or turn an observational association into an intervention claim.
Read the [guided exploration guide](guided-exploration.md) for column rules,
state-resolution choices, and report interpretation.

For Parquet sources or Pandas/Polars DataFrames, install optional readers with:

```console
python -m pip install "causal-emergence-zoo[tabular]"
```
