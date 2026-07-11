"""Guided, one-call exploration for grouped numeric CSV datasets."""
from __future__ import annotations

import csv
import gzip
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

from causal_emergence_zoo.multiresolution import analyze_continuous_multiresolution_csv
from causal_emergence_zoo.report import render_exploration_report


def profile_csv(path: str | Path, *, entity: str | None = None, time: str | None = None) -> dict[str, Any]:
    """Inspect a CSV without choosing a causal model."""
    source = Path(path)
    opener = gzip.open if source.suffix.lower() == ".gz" else open
    with opener(source, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV must contain a header.")
        columns = list(reader.fieldnames)
        entity = entity or _infer_column(columns, ["trajectory_id", "country_code", "entity", "subject", "session", "id"])
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
        for row in reader:
            row_count += 1
            trajectory = row.get(entity, "__single__") if entity else "__single__"
            trajectories[trajectory] += 1
            for column in columns:
                raw = (row.get(column) or "").strip()
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
                    except ValueError:
                        numeric[column] = False
    numeric_features = [column for column, is_numeric in numeric.items() if is_numeric and missing[column] == 0]
    lengths = sorted(trajectories.values())
    return {
        "schema_version": "0.1.0",
        "kind": "causal_emergence.data_profile",
        "source": {"path": str(source.resolve()), "size_bytes": source.stat().st_size},
        "row_count": row_count,
        "columns": columns,
        "inferred_roles": {"entity": entity, "time": time, "numeric_features": numeric_features},
        "missing_counts": dict(missing),
        "numeric_ranges": {column: [minimum[column], maximum[column]] for column in numeric_features},
        "trajectory_count": len(trajectories),
        "trajectory_length": {"minimum": lengths[0] if lengths else 0, "median": lengths[len(lengths) // 2] if lengths else 0, "maximum": lengths[-1] if lengths else 0},
        "warnings": (["No entity column was inferred; the file will be treated as one trajectory."] if entity is None else []) + (["No numeric time column was inferred; explicit row-order confirmation is required."] if time is None else []) + (["Fewer than two complete numeric feature columns were detected."] if len(numeric_features) < 2 else []),
    }


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


def explore_csv(path: str | Path, *, entity: str | None = None, time: str | None = None, features: Sequence[str] | None = None, resolutions: Sequence[int] | None = None, seeds: Sequence[int] = (0,), report_path: str | Path | None = None) -> dict[str, Any]:
    """Profile, plan, analyze, describe, and optionally render one CSV."""
    profile = profile_csv(path, entity=entity, time=time)
    plan = recommend_analysis_plan(profile, features=features, resolutions=resolutions, seeds=seeds)
    result = analyze_continuous_multiresolution_csv(
        path,
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


def write_exploration_json(exploration: dict[str, Any], path: str | Path) -> None:
    Path(path).write_text(json.dumps(exploration, indent=2, allow_nan=False), encoding="utf-8")


def _infer_column(columns: Sequence[str], candidates: Sequence[str]) -> str | None:
    lowered = {column.lower(): column for column in columns}
    return next((lowered[candidate] for candidate in candidates if candidate in lowered), None)
