# mesoscale_cycle_6

## Purpose

Mesoscale-positive block-cycle benchmark larger than the starter four-state systems.

## Expected Behavior

The system has three two-state blocks. The natural partition `[[0, 1], [2, 3], [4, 5]]` forms a clean three-state macro cycle and improves causal power.

## Pass Condition

A compatible implementation should enumerate 203 partitions, identify `01|23|45` as the best partition, and report positive `deltaCP`.

## Common Failure Mode

An implementation that searches only binary top-level coarse-grainings may miss the three-block mesoscale peak.
