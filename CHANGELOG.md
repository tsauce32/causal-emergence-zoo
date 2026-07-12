# Changelog

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
