# Guided exploration and HTML reports

`cez explore` is the plug-and-play entry point for grouped numeric CSV data. It
profiles the file, proposes a serializable analysis plan, runs bounded
multiresolution CE2, describes learned states from their distinguishing
features, and writes a self-contained HTML report.

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
- search and interpretation limitations.

“Auto” means a documented recommendation, not an unreported scientific choice.
The complete profile, plan, encoders, TPMs, hierarchies, evidence, and source
signature remain in the JSON artifact.

Current scope is grouped numeric CSV or CSV.GZ input. Missing numeric values are
reported rather than silently imputed. DataFrame, Parquet, and SQL adapters are
planned as additive input layers over the same profile-plan-analysis contract.

