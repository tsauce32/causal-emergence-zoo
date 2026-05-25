# two_block_noisy_4

## Purpose

Small positive-emergence example with two natural equivalence classes.

## Expected Behavior

The microscale is noisy within two blocks. Grouping states as `[[0, 1], [2, 3]]` removes within-block target uncertainty and improves normalized causal power.

## Pass Condition

A compatible implementation should identify `01|23` as the best partition and report positive `deltaCP`.

## Common Failure Mode

If the macro TPM is constructed with a different intervention distribution, the numeric `deltaCP` may differ.
