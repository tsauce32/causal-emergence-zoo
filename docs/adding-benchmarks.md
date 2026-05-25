# Adding Benchmarks

Use this checklist for new systems.

Start with `examples/benchmark-input.template.json` and read `docs/input-format.md` for the expected information contract.

1. Add or update a generator in `generators/`.
2. Include all parameters and a random seed if the system is synthetic.
3. Generate the fixture into `data/`.
4. Add a benchmark card in `docs/benchmarks/`.
5. Explain the system's conceptual role in plain language.
6. Store exhaustive partitions if the state count is small enough.
7. Store selected partitions or heuristic traces for larger systems.
8. Add tests for any expected qualitative behavior.
9. Run `python -m pytest`.

Good benchmark fixtures should be boring to reproduce and interesting to interpret.
