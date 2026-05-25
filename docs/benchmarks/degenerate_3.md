# degenerate_3

## Purpose

Baseline for deterministic but fully degenerate dynamics.

## Expected Behavior

Every state maps to the same next state. Rows are deterministic, but effects are completely overlapping, so causal power is zero.

## Pass Condition

A compatible implementation should report `determinism = 1.0` and `causal_power = 0.0`.

## Common Failure Mode

If a tool treats determinism alone as causal strength, it may over-score this system.
