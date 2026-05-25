# hierarchical_two_cycle_8

## Purpose

Eight-state fixture with nested pair-level and component-level structure.

## Expected Behavior

The pair partition `[[0, 1], [2, 3], [4, 5], [6, 7]]` exposes clean macro dynamics. The component partition `[[0, 1, 2, 3], [4, 5, 6, 7]]` is also clean under the current convention.

## Pass Condition

A compatible implementation should enumerate 4,140 partitions and report causal-power plateaus across multiple macro depths.

## Common Failure Mode

Best-partition-only summaries can hide the fact that more than one macro level is informative.
