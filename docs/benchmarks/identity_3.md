# identity_3

## Purpose

Sanity check for a deterministic, non-degenerate microscale.

## Expected Behavior

The microscale has maximal causal power under the zoo convention. Coarse partitions should not improve on it.

## Pass Condition

A compatible implementation should report microscale `causal_power = 1.0` and no positive best-partition `deltaCP`.

## Common Failure Mode

If a tool reports emergence here, it may be normalizing coarse scales incorrectly or using a different `deltaCP` baseline.
