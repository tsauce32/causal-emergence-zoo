# Changelog

## 0.2.1

- Made high-level CE 2.0 analysis automatically select exact search through
  eight learned states and a bounded, explicitly non-exhaustive beam search for
  nine through sixteen states. Calls that formerly rejected 9–16 states now
  return a result only with `ce2.is_exhaustive: false`; consumers must preserve
  that distinction in interpretation and downstream displays.
- Added a first-run social-system tutorial and a one-command HTML-report
  workflow for public-beta users.
- Added a secure GitHub Release-to-PyPI Trusted Publishing workflow and release
  checklist.

## 0.2.0

- Added a stable typed public API: `DataProfile`, `AnalysisPlan`, `StateModel`,
  `CausalHierarchy`, `EvidenceLedger`, `NarrativeReport`, and
  `ExplorationResult`.
- Added typed entry points for discrete TPM, trajectory, continuous, and guided
  exploration workflows.
- Added canonical v0.2 JSON envelopes, round-trip loaders, a packaged public
  artifact schema, and explicit extension-field compatibility rules.
- Preserved the existing dictionary-returning functions and result wire shapes
  as compatibility APIs.
- Promoted package metadata from pre-alpha `0.1.0` to alpha `0.2.0`.
