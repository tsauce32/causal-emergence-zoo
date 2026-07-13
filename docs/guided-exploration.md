# Guided exploration and HTML reports

`cez explore` is the plug-and-play entry point for grouped numeric CSV, CSV.GZ,
or Parquet data. It
profiles the file, proposes a serializable analysis plan, runs bounded
multiresolution CE2, describes learned states from their distinguishing
features, and writes a self-contained HTML report.

If you want to see the complete report before using your own data, run the
bundled synthetic social-system-style example with `cez demo`. It writes an
HTML report in one command and makes no claim about real countries or social
causes; see the [first-analysis guide](first-analysis.md).

```console
cez explore observations.csv \
  --entity country_code \
  --time year \
  --report report.html \
  --output result.json
```

Common entity names such as `trajectory_id`, `country_code`, `subject`, and
`session`, and numeric time names such as `time`, `year`, and `step`, are inferred
when omitted. Complete numeric feature columns are selected by default. Use
repeated `--feature`, `--resolution`, and `--seed` options to override the
recommendation.

The report includes:

- source coverage and trajectory profile;
- the exact recommended analysis plan;
- CE gain by learned-state resolution;
- learned-state support;
- the selected macro-transition heatmap;
- deterministic feature-grounded state descriptions;
- frozen held-out prediction and transition-null status;
- selectable narrative claims with their supporting states, transitions,
  uncertainty checks, caveats, and counterevidence;
- search and interpretation limitations.

“Auto” means a documented recommendation, not an unreported scientific choice.
The complete profile, plan, encoders, TPMs, hierarchies, evidence, and source
signature remain in the JSON artifact.

From Python, the same workflow accepts Pandas or Polars DataFrames as well as
paths. A DataFrame is marked as caller-materialized (rather than bounded-memory)
in the result; CSV and Parquet paths retain the two-pass streaming contract.

```python
from causal_emergence_zoo import explore

result = explore(frame, entity="country_code", time="year")
```

Install optional readers with `pip install "causal-emergence-zoo[tabular]"`.
Missing numeric values are reported rather than silently imputed. SQL remains a
future adapter because its ordering and repeatable-scan contract must be explicit.
