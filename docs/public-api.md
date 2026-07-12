# Public API and artifact contract (v0.2)

Version 0.2 introduces a stable Python-facing layer for the CE2 exploration
workflow. The original JSON-compatible functions remain available, so existing
notebooks, scripts, and stored results do not need to change.

## Canonical typed workflow

```python
from causal_emergence_zoo import (
    explore_typed,
    profile_typed,
    recommend_analysis_plan_typed,
)

profile = profile_typed("country_year.parquet", entity="country_code", time="year")
plan = recommend_analysis_plan_typed(profile, resolutions=[4, 8], seeds=[0, 1])
result = explore_typed("country_year.parquet", plan=plan)

print(result.summary())
hierarchy = result.show_hierarchy()
result.write_json("analysis-v0.2.json")
result.export_report("analysis.html")
```

The typed boundaries are:

- `DataProfile`: observed columns, roles, coverage, and source semantics.
- `AnalysisPlan`: declared feature, time, resolution, and validation choices.
- `StateModel`: the finite TPM and, where applicable, learned encoder.
- `CausalHierarchy`: CE2 scales, selected endpoint, and model evidence.
- `EvidenceLedger`: claim-level support, uncertainty, caveats, and counterevidence.
- `NarrativeReport`: one CE2 analysis and its scientific artifacts.
- `ExplorationResult`: a profile, plan, multiresolution analysis, and reports.

Each object is versioned, JSON serializable, and supports `to_dict()` and
`from_dict()`. The canonical envelope uses `schema_version: "0.2.0"` and can be
validated with `validate_public_artifact()` or the packaged
`public-api.schema.json` schema.

## Typed analysis entry points

Use these when a single model rather than a guided multiresolution exploration
is appropriate:

```python
from causal_emergence_zoo import (
    analyze_continuous_typed,
    analyze_trajectories_typed,
    narrate_tpm_typed,
)
```

They return `NarrativeReport`. The matching legacy functions
`analyze_continuous_csv`, `analyze_trajectories`, and `narrate_tpm` still return
their existing dictionaries.

## Compatibility policy

The v0.2 objects are an additive API. Existing dict-returning functions, their
wire `kind` values, and existing result fields remain supported. A typed object
created from a legacy result exposes `to_legacy_dict()` for code that must pass
the exact original-shaped mapping to an older renderer or integration.

Canonical v0.2 artifacts permit additive extension fields. Consumers should
switch on `kind` and `schema_version`, require the documented fields they use,
and ignore unknown additions. Breaking changes will require a later schema major
version rather than silently changing an existing artifact shape.

## Loading artifacts

```python
import json
from causal_emergence_zoo import exploration_result_from_dict

with open("analysis-v0.2.json", encoding="utf-8") as handle:
    result = exploration_result_from_dict(json.load(handle))
```

The `*_from_dict` helpers also make migrations explicit:
`data_profile_from_dict`, `analysis_plan_from_dict`, `state_model_from_dict`,
`causal_hierarchy_from_dict`, `evidence_ledger_from_dict`, and
`narrative_report_from_dict`.
