"""Guided, one-call exploration for grouped numeric tabular datasets."""
from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

from causal_emergence_zoo.multiresolution import analyze_continuous_multiresolution_csv
from causal_emergence_zoo.report import render_exploration_report
from causal_emergence_zoo.tabular import TabularSource, adapt_continuous_source


def profile_source(source: Any, *, entity: str | None = None, time: str | None = None) -> dict[str, Any]:
    """Inspect a CSV/Parquet path or DataFrame without choosing a causal model."""
    adapted = adapt_continuous_source(source)
    columns = adapted.column_names()
    entity = entity or _infer_column(
        columns, ["trajectory_id", "country_code", "entity", "subject", "session", "id"]
    )
    time = time or _infer_column(columns, ["time", "year", "timestamp", "step", "cycle"])
    if entity is not None and entity not in columns:
        raise ValueError(f"Entity column {entity!r} is not present.")
    if time is not None and time not in columns:
        raise ValueError(f"Time column {time!r} is not present.")
    missing = Counter({column: 0 for column in columns})
    numeric = {column: True for column in columns if column not in {entity, time}}
    minimum: dict[str, float] = {}
    maximum: dict[str, float] = {}
    trajectories = Counter()
    row_count = 0
    for row in adapted.iter_rows(columns):
        row_count += 1
        trajectory = _value_text(row.get(entity)) if entity else "__single__"
        trajectories[trajectory or "__missing_entity__"] += 1
        for column in columns:
            raw = _value_text(row.get(column))
            if not raw:
                missing[column] += 1
                if column in numeric:
                    numeric[column] = False
                continue
            if column in numeric:
                try:
                    value = float(raw)
                    if not math.isfinite(value):
                        raise ValueError
                    minimum[column] = min(minimum.get(column, value), value)
                    maximum[column] = max(maximum.get(column, value), value)
                except (TypeError, ValueError):
                    numeric[column] = False
    numeric_features = [column for column, is_numeric in numeric.items() if is_numeric and missing[column] == 0]
    lengths = sorted(trajectories.values())
    descriptor = adapted.descriptor()
    signature = adapted.source_signature()
    warnings = (
        (["No entity column was inferred; the file will be treated as one trajectory."] if entity is None else [])
        + (["No numeric time column was inferred; explicit row-order confirmation is required."] if time is None else [])
        + (["Fewer than two complete numeric feature columns were detected."] if len(numeric_features) < 2 else [])
    )
    if not descriptor["bounded_memory"]:
        warnings.append(
            "The input is a caller-materialized DataFrame; use a CSV or Parquet path for a bounded-memory two-pass run."
        )
    return {
        "schema_version": "0.1.0",
        "kind": "causal_emergence.data_profile",
        "source": {
            "path": _source_label(adapted),
            "size_bytes": signature.get("size_bytes"),
            "adapter": descriptor,
        },
        "row_count": row_count,
        "columns": columns,
        "inferred_roles": {"entity": entity, "time": time, "numeric_features": numeric_features},
        "missing_counts": dict(missing),
        "numeric_ranges": {column: [minimum[column], maximum[column]] for column in numeric_features},
        "trajectory_count": len(trajectories),
        "trajectory_length": {"minimum": lengths[0] if lengths else 0, "median": lengths[len(lengths) // 2] if lengths else 0, "maximum": lengths[-1] if lengths else 0},
        "warnings": warnings,
    }


def profile_csv(source: Any, *, entity: str | None = None, time: str | None = None) -> dict[str, Any]:
    """Backward-compatible name for :func:`profile_source`."""
    return profile_source(source, entity=entity, time=time)


def profile_typed(source: Any, *, entity: str | None = None, time: str | None = None):
    """Return the v0.2 :class:`DataProfile` while preserving ``profile_source``."""
    from causal_emergence_zoo.api import DataProfile

    return DataProfile.from_dict(profile_source(source, entity=entity, time=time))


def recommend_analysis_plan(profile: dict[str, Any], *, features: Sequence[str] | None = None, resolutions: Sequence[int] | None = None, seeds: Sequence[int] = (0,)) -> dict[str, Any]:
    """Produce a serializable recommendation; no analysis is run here."""
    selected = list(features or profile["inferred_roles"]["numeric_features"])
    if not selected:
        raise ValueError("No complete numeric features are available; specify or clean feature columns.")
    rows = profile["row_count"]
    suggested = list(resolutions or ([4, 8, 12, 16] if rows >= 5_000 else [4, 8]))
    median_length = profile["trajectory_length"]["median"]
    return {
        "schema_version": "0.1.0",
        "kind": "causal_emergence.analysis_plan",
        "entity_column": profile["inferred_roles"]["entity"],
        "time_column": profile["inferred_roles"]["time"],
        "feature_columns": selected,
        "resolutions": suggested,
        "encoder_seeds": list(seeds),
        "search_mode": "auto",
        "temporal_features": {"differences": [1] if median_length >= 5 else [], "volatility_windows": [5] if median_length >= 10 else []},
        "validation_fraction": 0.2 if profile["trajectory_count"] >= 10 else 0.0,
        "support": {"minimum_state_observations": max(5, rows // 500), "minimum_outgoing_transitions": max(3, rows // 1000), "policy": "retain_exploratory"},
        "null_replicates": 0,
        "notes": ["This is a documented recommendation, not an automatic causal claim.", "Enable null replicates for confirmatory rather than quick exploration."],
    }


def recommend_analysis_plan_typed(
    profile: Any,
    *,
    features: Sequence[str] | None = None,
    resolutions: Sequence[int] | None = None,
    seeds: Sequence[int] = (0,),
):
    """Return a v0.2 :class:`AnalysisPlan` from a profile or legacy mapping."""
    from causal_emergence_zoo.api import AnalysisPlan

    return AnalysisPlan.recommend(profile, features=features, resolutions=resolutions, seeds=seeds)


def explore(
    source: Any,
    *,
    entity: str | None = None,
    time: str | None = None,
    features: Sequence[str] | None = None,
    resolutions: Sequence[int] | None = None,
    seeds: Sequence[int] = (0,),
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    """Profile, plan, analyze, describe, and optionally render a tabular source."""
    adapted = adapt_continuous_source(source)
    profile = profile_source(adapted, entity=entity, time=time)
    plan = recommend_analysis_plan(profile, features=features, resolutions=resolutions, seeds=seeds)
    return _execute_exploration(adapted, profile=profile, plan=plan, report_path=report_path)


def explore_typed(
    source: Any,
    *,
    plan: Any | None = None,
    entity: str | None = None,
    time: str | None = None,
    features: Sequence[str] | None = None,
    resolutions: Sequence[int] | None = None,
    seeds: Sequence[int] = (0,),
    report_path: str | Path | None = None,
):
    """Run the canonical v0.2 typed exploration workflow.

    Existing :func:`explore` remains the compatibility function and returns a
    dictionary.  This entry point returns an ``ExplorationResult`` with explicit
    ``DataProfile``, ``AnalysisPlan``, and per-run ``NarrativeReport`` objects.
    When a plan is supplied, it is run as declared; feature/time overrides are
    rejected to avoid silently altering a serialized analysis plan.
    """
    from causal_emergence_zoo.api import AnalysisPlan, DataProfile, ExplorationResult

    adapted = adapt_continuous_source(source)
    profile = DataProfile.from_dict(profile_source(adapted, entity=entity, time=time))
    if plan is None:
        typed_plan = AnalysisPlan.recommend(
            profile, features=features, resolutions=resolutions, seeds=seeds
        )
    else:
        if any(value is not None for value in (entity, time, features, resolutions)) or seeds != (0,):
            raise ValueError(
                "Pass either a declared plan or entity/time/feature/resolution/seed overrides, not both."
            )
        typed_plan = plan if isinstance(plan, AnalysisPlan) else AnalysisPlan.from_dict(plan)
    legacy = _execute_exploration(
        adapted,
        profile=profile.to_dict(),
        plan=typed_plan.to_dict(),
        report_path=report_path,
    )
    return ExplorationResult.from_legacy_dict(legacy)


def _execute_exploration(
    adapted: TabularSource,
    *,
    profile: dict[str, Any],
    plan: dict[str, Any],
    report_path: str | Path | None,
) -> dict[str, Any]:
    """Shared execution path for legacy and typed exploration APIs."""
    result = analyze_continuous_multiresolution_csv(
        adapted,
        feature_columns=plan["feature_columns"],
        resolutions=plan["resolutions"],
        encoder_seeds=plan["encoder_seeds"],
        trajectory_column=plan["entity_column"],
        time_column=plan["time_column"],
        row_order_is_time=plan["time_column"] is None,
        validation_fraction=plan["validation_fraction"],
        temporal_differences=plan["temporal_features"]["differences"],
        temporal_volatility_windows=plan["temporal_features"]["volatility_windows"],
        minimum_state_observations=plan["support"]["minimum_state_observations"],
        minimum_outgoing_transitions=plan["support"]["minimum_outgoing_transitions"],
        support_policy=plan["support"]["policy"],
    )
    exploration = {"schema_version": "0.1.0", "kind": "causal_emergence.exploration", "profile": profile, "plan": plan, "analysis": result}
    exploration["state_descriptions"] = describe_states(exploration)
    if report_path is not None:
        destination = Path(report_path)
        destination.write_text(render_exploration_report(exploration), encoding="utf-8")
        exploration["artifacts"] = {"html_report": str(destination.resolve())}
    return exploration


def explore_csv(
    source: Any,
    *,
    entity: str | None = None,
    time: str | None = None,
    features: Sequence[str] | None = None,
    resolutions: Sequence[int] | None = None,
    seeds: Sequence[int] = (0,),
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    """Backward-compatible name for :func:`explore`."""
    return explore(
        source,
        entity=entity,
        time=time,
        features=features,
        resolutions=resolutions,
        seeds=seeds,
        report_path=report_path,
    )


def describe_states(exploration: dict[str, Any]) -> list[dict[str, Any]]:
    """Create deterministic, feature-grounded state descriptions for the best run."""
    runs = exploration["analysis"]["resolution_runs"]
    best = max(runs, key=lambda run: (run["endpoint_cp_gain"], -run["resolution"], -run["seed"]))
    encoder = best["result"]["continuous_data"]["discretizer"]
    names = encoder["feature_names"]
    means = encoder["feature_means"]
    scales = encoder["feature_scales"]
    descriptions = []
    for index, centroid in enumerate(encoder["centroids_original_units"]):
        standardized = [(value - means[position]) / scales[position] for position, value in enumerate(centroid)]
        strongest = sorted(range(len(names)), key=lambda position: abs(standardized[position]), reverse=True)[:2]
        phrases = []
        for position in strongest:
            if abs(standardized[position]) >= 0.5:
                phrases.append(f"{'high' if standardized[position] > 0 else 'low'} {names[position]}")
        descriptions.append({"state_id": index, "label": "; ".join(phrases) if phrases else "near-average feature profile", "centroid": dict(zip(names, centroid))})
    return [{"resolution": best["resolution"], "seed": best["seed"], "states": descriptions}]


def write_exploration_json(exploration: Any, path: str | Path) -> None:
    """Write a legacy mapping or a v0.2 ``ExplorationResult`` as JSON."""
    if hasattr(exploration, "to_json"):
        Path(path).write_text(exploration.to_json(indent=2) + "\n", encoding="utf-8")
        return
    Path(path).write_text(json.dumps(exploration, indent=2, allow_nan=False), encoding="utf-8")


def _infer_column(columns: Sequence[str], candidates: Sequence[str]) -> str | None:
    lowered = {column.lower(): column for column in columns}
    return next((lowered[candidate] for candidate in candidates if candidate in lowered), None)


def _value_text(value: Any) -> str:
    """Normalize scalar values from CSV and optional DataFrame backends."""
    if value is None:
        return ""
    text = value.strip() if isinstance(value, str) else str(value).strip()
    return "" if text.lower() in {"", "nan", "<na>", "nat", "none", "null"} else text


def _source_label(source: TabularSource) -> str:
    path = getattr(source, "path", None)
    if path is not None:
        return str(Path(path).resolve())
    adapter = source.descriptor()["adapter"].replace("_", " ")
    return f"<{adapter}>"
