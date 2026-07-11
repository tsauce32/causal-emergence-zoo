"""Resolution sweeps for continuous CE2 models.

Resolution profiles characterize discretization sensitivity; they do not impose
cross-resolution agreement as a CE2 validity condition.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from causal_emergence_zoo.continuous import analyze_continuous_csv


def analyze_continuous_multiresolution_csv(
    csv_path: str | Path,
    *,
    feature_columns: Sequence[str],
    resolutions: Sequence[int] = (4, 8, 12, 16, 24, 32),
    encoder_seeds: Sequence[int] = (0,),
    **kwargs: Any,
) -> dict[str, Any]:
    """Run declared resolutions and summarize conditional CE2 evidence."""
    values = list(resolutions)
    if not values or len(set(values)) != len(values) or any(value < 2 or value > 32 for value in values):
        raise ValueError("resolutions must be unique integers in [2, 32].")
    if not encoder_seeds:
        raise ValueError("encoder_seeds must not be empty.")
    runs = []
    for resolution in values:
        for seed in encoder_seeds:
            result = analyze_continuous_csv(csv_path, feature_columns=feature_columns, microstate_count=resolution, random_seed=seed, search_mode="auto", **kwargs)
            runs.append({"resolution": resolution, "seed": seed, "status": result["status"], "endpoint_partition_id": result["ce2"]["endpoint"]["partition_id"], "endpoint_macro_state_count": result["ce2"]["endpoint"]["macro_state_count"], "endpoint_cp_gain": result["ce2"]["causal_apportioning"]["endpoint_cp_gain"], "search": result.get("search"), "result": result})
    per_resolution = []
    for resolution in values:
        selected = [run for run in runs if run["resolution"] == resolution]
        gains = [run["endpoint_cp_gain"] for run in selected]
        positive = [run for run in selected if run["status"] == "emergent"]
        per_resolution.append({"resolution": resolution, "seed_count": len(selected), "positive_seed_count": len(positive), "positive_seed_frequency": len(positive) / len(selected), "mean_endpoint_cp_gain": sum(gains) / len(gains), "run_ids": [f"K{resolution}:seed{run['seed']}" for run in selected]})
    classification = _classify(per_resolution)
    return {"schema_version": "0.1.0", "kind": "causal_emergence.multiresolution_profile", "resolutions_requested": values, "encoder_seeds": list(encoder_seeds), "resolution_runs": runs, "per_resolution": per_resolution, "profile": {"classification": classification, "classification_is_acceptance_gate": False, "interpretation": _interpretation(classification)}, "limitations": ["Cross-resolution comparison currently summarizes recurrence of CE signals and seed frequency; anchor-observation macro-assignment similarity is planned next.", "Beam-search results above eight states are best-sampled, not globally optimal."]}


def _classify(rows: list[dict[str, Any]]) -> str:
    positive = [index for index, row in enumerate(rows) if row["positive_seed_frequency"] > 0]
    if not positive:
        return "no_detected_emergence"
    if len(positive) == 1:
        return "characteristic_resolution_peak" if rows[positive[0]]["positive_seed_frequency"] == 1 else "isolated_unstable_spike"
    if any(right == left + 1 for left, right in zip(positive, positive[1:])):
        return "plateau_or_resolution_range"
    return "separated_recurrence"


def _interpretation(classification: str) -> str:
    return {"no_detected_emergence": "No analyzed resolution produced a positive fitted macro contribution.", "characteristic_resolution_peak": "Positive CE is concentrated at one declared resolution and replicated across the declared seeds.", "isolated_unstable_spike": "Positive CE appears at one resolution but does not replicate across declared seeds.", "plateau_or_resolution_range": "Positive CE occurs over adjacent declared resolutions; inspect run-level macro assignments before calling it robust recurrence.", "separated_recurrence": "Positive CE reappears at separated resolutions; inspect run-level macro assignments before interpreting modular recurrence."}[classification]
