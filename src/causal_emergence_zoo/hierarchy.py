"""Scientific intermediate representation between CE2 inference and narration."""

from __future__ import annotations

from typing import Any


def build_causal_hierarchy(model: dict[str, Any], ce2: dict[str, Any]) -> dict[str, Any]:
    """Build a renderer-independent, evidence-carrying hierarchy result."""
    endpoint = ce2["endpoint"]
    labels = model["state_labels"]
    return {
        "schema_version": "0.1.0",
        "kind": "causal_emergence.causal_hierarchy",
        "method": ce2["framework"],
        "source": model["source"],
        "microstates": [
            {"index": index, "label": label} for index, label in enumerate(labels)
        ],
        "scales": [
            {
                "step": step["step"],
                "partition_id": step["partition_id"],
                "blocks": step["blocks"],
                "state_count": step["macro_state_count"],
                "cp": step["cp"],
                "delta_cp": step["delta_cp_from_previous_scale"],
                "positive_contribution": step["positive_causal_contribution"],
                "dynamical_consistency": step["dynamical_consistency"],
            }
            for step in ce2["path"]
        ],
        "endpoint": {
            "partition_id": endpoint["partition_id"],
            "blocks": endpoint["blocks"],
            "macro_tpm": endpoint["macro_tpm"],
            "cp": endpoint["cp"],
            "cp_gain": ce2["causal_apportioning"]["endpoint_cp_gain"],
        },
        "emergent_complexity": ce2["emergent_complexity"],
        "uncertainty": model.get("uncertainty", {"status": "not_estimated"}),
        "evidence": {
            "microscale_tpm": model["tpm"],
            "microscale_metrics": model["microscale_metrics"],
            "search_is_exhaustive": ce2["is_exhaustive"],
            "endpoint_optimality": ce2.get("endpoint_optimality", "exact_over_valid_search_space"),
        },
    }

