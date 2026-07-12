"""Claim-level evidence ledgers for CE 2.0 narrative results.

The narrative graph already contains claim, evidence, and caveat nodes.  This
module makes those links practical for people and report renderers: every
claim receives a compact ledger entry with its measured state/transition
support, uncertainty checks, and material counterevidence.  A ledger is an
audit aid, not an automatic confidence score or a causal-identification test.
"""

from __future__ import annotations

from typing import Any


def attach_evidence_ledger(result: dict[str, Any]) -> dict[str, Any]:
    """Attach a deterministic, claim-level evidence ledger in place.

    The function is intentionally safe to call again after an analysis adds
    held-out validation, null-model, or resampling results.  This lets the
    continuous pipeline enrich the initial finite-TPM narrative rather than
    maintaining a second, divergent narrative format.
    """
    ledger = build_evidence_ledger(result)
    result["evidence_ledger"] = ledger
    claim_index = {entry["claim_id"]: entry["id"] for entry in ledger["claims"]}
    for claim in result.get("narrative_graph", {}).get("claims", []):
        claim["evidence_ledger_id"] = claim_index.get(claim.get("id"))
    return result


def build_evidence_ledger(result: dict[str, Any]) -> dict[str, Any]:
    """Build an evidence ledger without changing the CE 2.0 calculation.

    Missing empirical support is represented as ``not_available`` rather than
    inferred from a transition probability.  In particular, a supplied TPM can
    support a model claim while still lacking observation counts or uncertainty
    estimates.
    """
    graph = result.get("narrative_graph")
    if not isinstance(graph, dict):
        raise ValueError("A narrative_graph is required to build an evidence ledger.")

    evidence_by_id = {
        item["id"]: item
        for item in graph.get("evidence", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    caveats_by_id = {
        item["id"]: item
        for item in graph.get("caveats", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    endpoint = result.get("ce2", {}).get("endpoint", {})
    model = result.get("input_model", {})
    nodes = graph.get("nodes", [])
    uncertainty = _uncertainty_items(result)
    counterevidence = _counterevidence_items(result, endpoint, model)

    entries = []
    for claim in graph.get("claims", []):
        if not isinstance(claim, dict):
            continue
        claim_evidence = []
        for evidence_id in claim.get("evidence_ids", []):
            source = evidence_by_id.get(evidence_id)
            if source is None:
                claim_evidence.append(
                    {
                        "id": evidence_id,
                        "kind": "missing_evidence_reference",
                        "status": "missing",
                    }
                )
            else:
                claim_evidence.append(dict(source))
        claim_caveats = []
        for caveat_id in claim.get("caveat_ids", []):
            source = caveats_by_id.get(caveat_id)
            if source is None:
                claim_caveats.append(
                    {"id": caveat_id, "kind": "missing_caveat_reference", "status": "missing"}
                )
            else:
                claim_caveats.append(dict(source))

        entries.append(
            {
                "id": f"ledger:{claim.get('id', len(entries))}",
                "claim_id": claim.get("id"),
                "claim_type": claim.get("type"),
                "status": claim.get("status"),
                "statement": claim.get("statement"),
                "supporting_evidence": claim_evidence,
                "state_support": _state_support(endpoint, nodes, model),
                "transition_support": _transition_support(
                    endpoint,
                    model,
                    claim_evidence,
                ),
                "uncertainty": uncertainty,
                "counterevidence": counterevidence,
                "caveats": claim_caveats,
                "interpretation": (
                    "This ledger reports evidence conditional on the fitted model. "
                    "It does not convert observational fit into interventionally identified causation."
                ),
            }
        )

    return {
        "schema_version": "0.1.0",
        "kind": "causal_emergence.evidence_ledger",
        "claim_count": len(entries),
        "source_kind": model.get("source", {}).get("kind"),
        "claims": entries,
        "summary": {
            "observed_transition_counts_available": bool(_transition_counts(model)),
            "uncertainty_items": len(uncertainty),
            "counterevidence_items": len(counterevidence),
            "note": (
                "Counterevidence records alternatives, failed checks, and missing evidence to inspect; "
                "it is not combined into a single confidence score."
            ),
        },
    }


def _state_support(
    endpoint: dict[str, Any], nodes: list[dict[str, Any]], model: dict[str, Any]
) -> dict[str, Any]:
    labels = list(model.get("state_labels", []))
    outgoing = model.get("outgoing_counts")
    observations = (
        model.get("streaming_transition_estimate", {}).get("state_observation_counts")
        if isinstance(model.get("streaming_transition_estimate"), dict)
        else None
    )
    node_by_id = {
        node.get("id"): node for node in nodes if isinstance(node, dict) and node.get("id")
    }
    blocks = endpoint.get("blocks", [])
    states = []
    for macro_index, block in enumerate(blocks):
        node = node_by_id.get(f"macro:{macro_index}", {})
        member_indices = list(node.get("member_state_indices", block))
        member_labels = list(
            node.get(
                "member_state_labels",
                [labels[index] if index < len(labels) else index for index in member_indices],
            )
        )
        states.append(
            {
                "macro_state_id": f"macro:{macro_index}",
                "label": node.get("label"),
                "member_state_indices": member_indices,
                "member_state_labels": member_labels,
                "observed_outgoing_transitions": _sum_indices(outgoing, member_indices),
                "observations": _sum_indices(observations, member_indices),
            }
        )
    return {
        "status": "observed_counts_available" if outgoing is not None or observations is not None else "model_only",
        "macro_states": states,
        "note": (
            "Observation and transition counts are unavailable for a supplied TPM."
            if outgoing is None and observations is None
            else "Counts describe fitted-state support, not independent intervention samples."
        ),
    }


def _transition_support(
    endpoint: dict[str, Any], model: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    blocks = endpoint.get("blocks", [])
    macro_tpm = endpoint.get("macro_tpm", [])
    counts = _transition_counts(model)
    dominant = next(
        (item for item in evidence if item.get("kind") == "macro_transition_probability"),
        None,
    )
    if dominant is not None:
        source_index = _macro_index(dominant.get("source"))
        target_index = _macro_index(dominant.get("target"))
        if source_index is not None and target_index is not None:
            return {
                "status": "observed_counts_available" if counts is not None else "model_probability_only",
                "macro_source": source_index,
                "macro_target": target_index,
                "model_probability": dominant.get("value"),
                "observed_transition_count": _block_count(counts, blocks, source_index, target_index),
                "observed_source_outgoing_count": _block_source_count(counts, blocks, source_index),
                "note": (
                    "The probability is induced by the macro TPM; the count is an aggregate of fitted microstate transitions."
                    if counts is not None
                    else "No raw transition-count matrix was supplied with this model."
                ),
            }

    summaries = []
    for source_index, row in enumerate(macro_tpm):
        for target_index, probability in enumerate(row):
            summaries.append(
                {
                    "macro_source": source_index,
                    "macro_target": target_index,
                    "model_probability": probability,
                    "observed_transition_count": _block_count(
                        counts, blocks, source_index, target_index
                    ),
                }
            )
    return {
        "status": "observed_counts_available" if counts is not None else "model_probability_only",
        "macro_transitions": summaries,
        "note": (
            "The macro transition table is a model-derived aggregation of the learned microstate TPM."
        ),
    }


def _uncertainty_items(result: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    robustness = result.get("robustness")
    if isinstance(robustness, dict):
        items.append(
            {
                "id": "u:bootstrap_or_resampling",
                "kind": "resampling_stability",
                "status": robustness.get("status", "not_estimated"),
                "method": robustness.get("method"),
                "replicates": robustness.get("replicates"),
                "selected_endpoint_frequency": robustness.get("selected_endpoint_frequency"),
                "positive_emergence_frequency": robustness.get("positive_emergence_frequency"),
                "interval": robustness.get("endpoint_cp_gain_interval"),
                "note": robustness.get("caveat", robustness.get("note")),
            }
        )

    continuous = result.get("continuous_data")
    if isinstance(continuous, dict):
        validation = continuous.get("validation")
        if isinstance(validation, dict):
            items.append(
                {
                    "id": "u:held_out_path",
                    "kind": "held_out_path_reproduction",
                    "status": validation.get("status", "not_available"),
                    "note": "The endpoint selected on training data is scored without rediscovery on held-out trajectories.",
                }
            )
        predictive = continuous.get("predictive_validation", {})
        if isinstance(predictive, dict):
            held_out = predictive.get("validation_micro_tpm", {})
            if isinstance(held_out, dict):
                items.append(
                    {
                        "id": "u:held_out_prediction",
                        "kind": "held_out_predictive_score",
                        "status": held_out.get("status", "not_available"),
                        "mean_negative_log_likelihood": held_out.get("mean_negative_log_likelihood"),
                        "transition_count": held_out.get("transition_count"),
                        "note": "This evaluates the frozen microscale TPM; it is not a CE 2.0 quantity.",
                    }
                )
        for key, label in (
            ("transition_null_validation", "transition_target_null"),
            ("trajectory_time_permutation_validation", "trajectory_time_permutation_null"),
        ):
            null = continuous.get(key)
            if isinstance(null, dict):
                items.append(
                    {
                        "id": f"u:{label}",
                        "kind": label,
                        "status": null.get("status", "not_available"),
                        "replicates": null.get("replicates"),
                        "empirical_upper_tail_probability": null.get("empirical_upper_tail_probability"),
                        "note": null.get(
                            "caveat", null.get("observational_caveat", null.get("note"))
                        ),
                    }
                )
        bootstrap = continuous.get("grouped_bootstrap_validation")
        if isinstance(bootstrap, dict):
            interval = bootstrap.get("endpoint_cp_gain", {})
            items.append(
                {
                    "id": "u:grouped_bootstrap",
                    "kind": "grouped_trajectory_bootstrap",
                    "status": bootstrap.get("status", "not_available"),
                    "replicates": bootstrap.get("replicates"),
                    "selected_endpoint_frequency": _endpoint_frequency_for_selected_result(
                        result, bootstrap
                    ),
                    "positive_emergence_frequency": bootstrap.get(
                        "positive_macro_emergence_frequency"
                    ),
                    "interval": interval,
                    "note": bootstrap.get("observational_caveat"),
                }
            )

    empirical = result.get("empirical_validation")
    if isinstance(empirical, dict):
        for name, value in empirical.items():
            if isinstance(value, dict):
                items.append(
                    {
                        "id": f"u:{name}",
                        "kind": name,
                        "status": value.get("status", "completed"),
                        "summary": {
                            key: item
                            for key, item in value.items()
                            if key
                            in {
                                "replicates",
                                "selected_endpoint_frequency",
                                "positive_emergence_frequency",
                                "empirical_upper_tail_probability",
                                "endpoint_cp_gain_interval",
                                "mean_pairwise_agreement",
                            }
                        },
                    }
                )
    if not items:
        items.append(
            {
                "id": "u:not_estimated",
                "kind": "uncertainty",
                "status": "not_estimated",
                "note": "No resampling, held-out, or null-model check was attached to this result.",
            }
        )
    return items


def _counterevidence_items(
    result: dict[str, Any], endpoint: dict[str, Any], model: dict[str, Any]
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    ce2 = result.get("ce2", {})
    endpoint_id = endpoint.get("partition_id")
    for alternative in ce2.get("top_consistent_scales", []):
        if alternative.get("partition_id") == endpoint_id:
            continue
        items.append(
            {
                "kind": "alternative_dynamically_consistent_scale",
                "partition_id": alternative.get("partition_id"),
                "macro_state_count": alternative.get("macro_state_count"),
                "cp": alternative.get("cp"),
                "cp_gap_from_endpoint": _difference(endpoint.get("cp"), alternative.get("cp")),
                "note": "A different dynamically consistent scale remains a competing model summary.",
            }
        )
    support = result.get("state_support")
    if isinstance(support, dict) and support.get("under_supported_state_indices"):
        items.append(
            {
                "kind": "under_supported_microstates",
                "state_indices": support.get("under_supported_state_indices"),
                "minimum_state_observations": support.get("minimum_state_observations"),
                "minimum_outgoing_transitions": support.get("minimum_outgoing_transitions"),
                "note": "The run was retained as exploratory despite the configured state-support threshold.",
            }
        )
    continuous = result.get("continuous_data")
    if isinstance(continuous, dict):
        validation = continuous.get("validation", {})
        if isinstance(validation, dict) and validation.get("status") == "path_not_reproduced":
            items.append(
                {
                    "kind": "held_out_path_not_reproduced",
                    "details": validation.get("analysis", {}).get("validity", {}).get("errors", []),
                }
            )
        null = continuous.get("transition_null_validation", {})
        if isinstance(null, dict) and null.get("status") == "completed":
            items.append(
                {
                    "kind": "null_comparison",
                    "observed_endpoint_cp_gain": null.get("observed_endpoint_cp_gain"),
                    "empirical_upper_tail_probability": null.get("empirical_upper_tail_probability"),
                    "note": "Interpret this comparison alongside its declared null mechanism; no automatic significance threshold is applied.",
                }
            )
        trajectory_null = continuous.get("trajectory_time_permutation_validation", {})
        if isinstance(trajectory_null, dict) and trajectory_null.get("status") == "completed":
            items.append(
                {
                    "kind": "trajectory_time_permutation_comparison",
                    "observed_endpoint_cp_gain": trajectory_null.get("observed_endpoint_cp_gain"),
                    "empirical_upper_tail_probability": trajectory_null.get(
                        "empirical_upper_tail_probability"
                    ),
                    "note": "This null preserves trajectory membership and occupancy while destroying temporal order; it is not a causal intervention test.",
                }
            )
    if model.get("source", {}).get("causal_interpretation", "").startswith("model_derived"):
        items.append(
            {
                "kind": "observational_causal_identification_limit",
                "note": "Observed model fit does not by itself distinguish intervention effects from confounding, selection, or omitted variables.",
            }
        )
    if not items:
        items.append(
            {
                "kind": "counterevidence_not_estimated",
                "note": "No alternative-scale, support, null-model, or held-out counterevidence was attached to this supplied model.",
            }
        )
    return items


def _transition_counts(model: dict[str, Any]) -> list[list[int]] | None:
    counts = model.get("transition_counts")
    if not isinstance(counts, list) or not counts or not all(isinstance(row, list) for row in counts):
        return None
    return counts


def _sum_indices(values: Any, indices: list[int]) -> int | None:
    if not isinstance(values, list):
        return None
    try:
        return sum(values[index] for index in indices)
    except (IndexError, TypeError):
        return None


def _block_count(
    counts: list[list[int]] | None,
    blocks: list[list[int]],
    source_index: int,
    target_index: int,
) -> int | None:
    if counts is None or source_index >= len(blocks) or target_index >= len(blocks):
        return None
    try:
        return sum(counts[source][target] for source in blocks[source_index] for target in blocks[target_index])
    except (IndexError, TypeError):
        return None


def _block_source_count(
    counts: list[list[int]] | None, blocks: list[list[int]], source_index: int
) -> int | None:
    if counts is None or source_index >= len(blocks):
        return None
    try:
        return sum(sum(counts[source]) for source in blocks[source_index])
    except (IndexError, TypeError):
        return None


def _macro_index(value: Any) -> int | None:
    if not isinstance(value, str) or not value.startswith("macro:"):
        return None
    try:
        return int(value.split(":", 1)[1])
    except ValueError:
        return None


def _difference(left: Any, right: Any) -> float | None:
    if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
        return None
    return left - right


def _endpoint_frequency_for_selected_result(
    result: dict[str, Any], bootstrap: dict[str, Any]
) -> float | None:
    endpoint_id = result.get("ce2", {}).get("endpoint", {}).get("partition_id")
    for item in bootstrap.get("endpoint_partition_frequencies", []):
        if item.get("partition_id") == endpoint_id:
            return item.get("frequency")
    return None
