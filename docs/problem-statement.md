# Problem Statement

`causal-emergence-zoo` exists because causal-emergence implementations need shared calibration cases.

The field has papers, formulas, examples, and software, but two implementations can still disagree for several reasons:

- One implementation may have a bug.
- They may normalize causal power differently.
- They may use different intervention distributions.
- They may construct macro TPMs differently.
- They may search different parts of the partition lattice.
- They may use the same words for slightly different quantities.

Without shared benchmark systems and expected outputs, these disagreements are hard to diagnose. A disagreement might be scientifically meaningful, or it might be a convention mismatch.

The zoo tries to make that distinction easier.

It also avoids a second problem: forcing every adjacent method into the same output shape. Some algorithms return hard partitions, while others return hierarchy paths, projection matrices, learned encoders, network scores, or qualitative hierarchy profiles. The harmonization layer lets those methods declare what they are reporting and how strict the comparison should be.

## The Contract

For each benchmark, the zoo says:

```text
Given this TPM,
under these conventions,
with this coarse-graining rule,
these are the expected multiscale outputs.
```

The project is therefore a calibration and communication layer. It is not meant to replace causal-emergence libraries. It gives those libraries a common set of systems to test against.

## Who It Helps

Researchers can use the zoo to make examples reproducible.

Library authors can use the zoo to check whether their implementation matches a known convention.

Students can use the zoo to see concrete cases of no emergence, degeneracy, top-heavy emergence, mesoscale peaks, hierarchical structure, and network-induced dynamics.

## Maintainer

This project was started by Thomas Hampton, `ThomasRHampton@gmail.com`.
