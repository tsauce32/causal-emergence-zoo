# Contributing

Thanks for considering a contribution to `causal-emergence-zoo`.

The project is a benchmark and calibration suite, not a full causal-emergence implementation. Contributions should make it easier for researchers and tool authors to compare results under explicit conventions.

## Maintainer

Thomas Hampton, `ThomasRHampton@gmail.com`

## Good Benchmark Contributions

A good benchmark contribution includes:

- A row-stochastic microscale TPM
- A short explanation of the system's conceptual role
- A reproducible generator or clear provenance
- Expected qualitative behavior
- Stored expected outputs generated under the zoo convention
- Tests that protect the expected behavior

Start from:

```text
examples/benchmark-input.template.json
schemas/benchmark-input.schema.json
```

## Adding A Fixture

1. Add or update a generator in `generators/`.
2. Generate the benchmark JSON into `src/causal_emergence_zoo/data/`.
3. Add a benchmark card in `docs/benchmarks/`.
4. Add or update tests in `tests/`.
5. Run:

```bash
python -m pytest
```

## Conventions

Before adding a benchmark, read:

```text
docs/conventions.md
```

If your benchmark intentionally uses a different convention, document that difference clearly.
