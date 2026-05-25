# Adding Benchmarks

Use this checklist for new systems.

1. Add or update a generator in `generators/`.
2. Include all parameters and a random seed if the system is synthetic.
3. Generate the fixture into `data/`.
4. Explain the system's conceptual role in plain language.
5. Store exhaustive partitions if the state count is small enough.
6. Store selected partitions or heuristic traces for larger systems.
7. Add tests for any expected qualitative behavior.
8. Run `pytest`.

Good benchmark fixtures should be boring to reproduce and interesting to interpret.
