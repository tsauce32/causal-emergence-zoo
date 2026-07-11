# Continuous multiscale recovery case study

This case study tests the full claim chain on data whose generating process is
known. Four latent microstates emit noisy continuous observations. States 0--1
and 2--3 are two dynamical equivalence classes, so the ground-truth macro
partition contains two blocks.

Run:

```console
python examples/continuous_multiscale_case_study.py \
  --output-directory case-study-output \
  --transitions 100000 \
  --noise 0.08
```

The generator streams 200,000 CSV rows to a gzip file. The analyzer then makes
two bounded-memory passes: reservoir fitting followed by transition counting.
It does not retain all observations in memory. The output separates:

1. the known generating TPM and partition;
2. the inferred `CausalHierarchy` (states, scales, CP contributions, evidence);
3. the rendered evidence-linked narrative;
4. fixed-path all-data validation information.

`report.json` is the compact case-study artifact and `analysis.json` retains the
complete auditable output. Vary `--transitions`, `--noise`, and `--seed` to test
sample efficiency and robustness. Recovery is expected to weaken when emission
clusters overlap strongly or when there are too few transitions; failure under
those conditions is evidence about the estimator, not proof that the generating
system lacks macrostructure.

The current continuous bridge learns a finite discretization before applying CE
2.0. It is therefore scalable in row count but is not a native continuous-state
causal-emergence measure.

