# preferential_attachment_alpha0_8

## Purpose

Network-induced TPM baseline on a seeded preferential-attachment graph.

## Expected Behavior

The graph is generated once with a fixed seed. With `alpha = 0`, neighbor transitions are unbiased apart from the self-loop weight.

## Pass Condition

A compatible implementation should preserve the provenance parameters and reproduce the stored microscale and partition metrics.

## Common Failure Mode

If graph generation or node ordering changes, the TPM will not match the stored fixture.
