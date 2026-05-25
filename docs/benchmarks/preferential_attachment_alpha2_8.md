# preferential_attachment_alpha2_8

## Purpose

Network-induced TPM on the same seeded graph as `preferential_attachment_alpha0_8`, but with strong hub-biased transitions.

## Expected Behavior

The graph topology is held fixed while the transition rule changes. This lets implementations test sensitivity to the hub-bias parameter.

## Pass Condition

A compatible implementation should use the same seed and graph provenance, but report different TPM values and causal metrics from the alpha-0 fixture.

## Common Failure Mode

If provenance is not tracked, two systems with the same graph but different dynamics can be mistaken for unrelated examples.
