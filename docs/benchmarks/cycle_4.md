# cycle_4

## Purpose

Small deterministic cycle for partition-lattice and coarse-graining tests.

## Expected Behavior

The microscale is deterministic and non-degenerate, so it already has maximal causal power under the one-step zoo convention.

## Pass Condition

A compatible implementation should report microscale `causal_power = 1.0` and no positive best-partition `deltaCP`.

## Common Failure Mode

Path-based or multi-step analyses may find interesting structure, but that is outside the current one-step fixture convention.
