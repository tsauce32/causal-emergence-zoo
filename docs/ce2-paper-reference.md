# Hoel CE 2.0 reference systems

The library includes executable model systems from Erik Hoel's *Causal
Emergence 2.0: Quantifying emergent complexity* (arXiv:2503.13395v3). They are
regression fixtures for the finite-state CE 2.0 implementation, not new empirical
claims.

| Paper example | Reproduced target |
| --- | --- |
| Equivalence-class example (paper Figure 2) | micro CP = 2/3, endpoint CP = 1, CE = 1/3 |
| Top-heavy example (paper Figure 3A-C) | micro CP ~= 0.14, endpoint CP ~= 0.41, EC ~= 1.67 bits |
| Mesoscale example (paper Figure 3D-F) | endpoint CE ~= 0.13 |
| Block redistribution (paper Figure 4) | 51 TPMs; CE 2.0 falls monotonically from 2/3 to 0 |

The paper's heatmaps print rounded probabilities. The top-heavy stochastic TPM
uses 0.0355 and 0.2145 behind its displayed 0.04 and 0.21 labels. The mesoscale
TPM uses 1/15 and 1/5 behind its displayed 0.07 and 0.21 labels.

The paper reports 2.07 bits of emergent complexity for the mesoscale example but
does not publish the exact ordered partition path used to produce it. Because CE
2.0's apportioning is path-dependent, the library records 2.07 as a provenance
target but does not pretend to reproduce it from an invented path. The TPM and
its reported endpoint CE are tested exactly to the precision published.

Use the constructors in `causal_emergence_zoo.paper_systems` when benchmarking a
new search or approximation algorithm. Tests live in
`tests/test_ce2_paper_systems.py`.

