"""Evidence-linked narrative extraction for small discrete causal-emergence models.

The prose produced here is deliberately a rendering of a structured
``narrative_graph``.  Every claim is linked to an explicitly calculated model
quantity, and trajectory-derived models are labelled observational rather than
treated as interventionally identified causal systems.
"""

from __future__ import annotations

import json
import math
import random
from collections.abc import Hashable, Iterable, Sequence
from typing import Any

from causal_emergence_zoo.ce2 import discover_ce2_path
from causal_emergence_zoo.approximate import approximate_ce2_path
from causal_emergence_zoo.estimation import (
    State,
    Trajectory,
    estimate_tpm_from_trajectories,
    materialize_trajectories,
)
from causal_emergence_zoo.metrics import Matrix, compute_metrics
from causal_emergence_zoo.hierarchy import build_causal_hierarchy
from causal_emergence_zoo.evidence import attach_evidence_ledger


def narrate_tpm(
    tpm: Matrix,
    *,
    state_labels: Sequence[Hashable] | None = None,
    max_exhaustive_states: int = 8,
    consistency_horizon: int = 5,
    consistency_tolerance: float = 1e-10,
    gain_tolerance: float = 1e-12,
    edge_probability_threshold: float = 0.0,
    top_k: int = 10,
    search_mode: str = "exact",
    beam_width: int = 20,
    branching_factor: int = 4,
    max_partition_evaluations: int = 100_000,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a CE 2.0 narrative graph from a supplied finite Markov TPM.

    A supplied TPM can represent an interventionally justified causal model, but
    the function does not infer that status on its own.  Pass an explicit source
    description when integrating it with an external causal-modeling workflow.
    """
    if not 0.0 <= edge_probability_threshold <= 1.0:
        raise ValueError("edge_probability_threshold must be between 0 and 1.")

    metrics = compute_metrics(tpm)
    labels = _resolve_labels(len(tpm), state_labels)
    if search_mode == "exact":
        ce2 = discover_ce2_path(tpm, max_exhaustive_states=max_exhaustive_states, consistency_horizon=consistency_horizon, consistency_tolerance=consistency_tolerance, gain_tolerance=gain_tolerance, top_k=top_k)
    elif search_mode == "beam":
        ce2 = approximate_ce2_path(tpm, beam_width=beam_width, branching_factor=branching_factor, max_partition_evaluations=max_partition_evaluations, consistency_horizon=consistency_horizon, consistency_tolerance=consistency_tolerance)
    else:
        raise ValueError("search_mode must be 'exact' or 'beam'.")
    model = {
        "kind": "provided_transition_model",
        "state_labels": labels,
        "state_count": len(tpm),
        "tpm": tpm,
        "microscale_metrics": metrics,
        "source": source
        or {
            "kind": "provided_tpm",
            "causal_interpretation": "caller_must_declare_interventional_semantics",
        },
    }
    result = build_narrative_graph(
        model,
        ce2,
        edge_probability_threshold=edge_probability_threshold,
        gain_tolerance=gain_tolerance,
    )
    return attach_evidence_ledger(result)


def analyze_trajectories(
    trajectories: Iterable[Trajectory],
    *,
    state_labels: Sequence[State] | None = None,
    smoothing: float = 0.0,
    max_exhaustive_states: int = 8,
    consistency_horizon: int = 5,
    consistency_tolerance: float = 1e-10,
    gain_tolerance: float = 1e-12,
    edge_probability_threshold: float = 0.0,
    top_k: int = 10,
    bootstrap_replicates: int = 0,
    bootstrap_seed: int = 0,
) -> dict[str, Any]:
    """Estimate a Markov model from trajectories and narrate its CE 2.0 structure.

    The result is an evidence-backed model narrative, not an assertion that the
    empirical data alone identifies intervention effects.  Bootstrap support is
    optional because exhaustive CE 2.0 discovery grows rapidly with state count.
    """
    if bootstrap_replicates < 0:
        raise ValueError("bootstrap_replicates must be non-negative.")

    copied = materialize_trajectories(trajectories)
    estimated = estimate_tpm_from_trajectories(
        copied,
        state_labels=state_labels,
        smoothing=smoothing,
    )
    result = narrate_tpm(
        estimated["tpm"],
        state_labels=estimated["state_labels"],
        max_exhaustive_states=max_exhaustive_states,
        consistency_horizon=consistency_horizon,
        consistency_tolerance=consistency_tolerance,
        gain_tolerance=gain_tolerance,
        edge_probability_threshold=edge_probability_threshold,
        top_k=top_k,
        source={
            "kind": "empirical_trajectory",
            "causal_interpretation": "model_derived_not_interventionally_identified",
            "estimator": estimated["method"],
            "trajectory_count": estimated["trajectory_count"],
            "transition_count": estimated["transition_count"],
            "smoothing": estimated["smoothing"],
        },
    )
    result["input_model"].update(
        {
            "transition_counts": estimated["transition_counts"],
            "outgoing_counts": estimated["outgoing_counts"],
            "nonempty_trajectory_count": estimated["nonempty_trajectory_count"],
            "estimation_assumptions": estimated["assumptions"],
        }
    )
    result["robustness"] = _bootstrap_stability(
        copied,
        state_labels=estimated["state_labels"],
        smoothing=smoothing,
        original_endpoint_id=result["ce2"]["endpoint"]["partition_id"],
        max_exhaustive_states=max_exhaustive_states,
        consistency_horizon=consistency_horizon,
        consistency_tolerance=consistency_tolerance,
        gain_tolerance=gain_tolerance,
        replicates=bootstrap_replicates,
        seed=bootstrap_seed,
    )
    return attach_evidence_ledger(result)


def build_narrative_graph(
    model: dict[str, Any],
    ce2: dict[str, Any],
    *,
    edge_probability_threshold: float = 0.0,
    gain_tolerance: float = 1e-12,
) -> dict[str, Any]:
    """Render CE 2.0 analysis as a structured, auditable narrative graph."""
    hierarchy = build_causal_hierarchy(model, ce2)
    labels = model["state_labels"]
    endpoint = ce2["endpoint"]
    apportioning = ce2["causal_apportioning"]
    has_emergence = (
        endpoint["macro_state_count"] < model["state_count"]
        and apportioning["has_positive_macro_contribution"]
        and apportioning["endpoint_cp_gain"] > gain_tolerance
    )
    profile = _hierarchy_profile(ce2, gain_tolerance) if has_emergence else "no_emergence"
    evidence, claims, nodes, edges = _graph_components(
        model,
        ce2,
        has_emergence=has_emergence,
        edge_probability_threshold=edge_probability_threshold,
    )
    summary = _summary(model, ce2, has_emergence, profile)

    return {
        "schema_version": "0.2.0",
        "kind": "causal_emergence.narrative_graph",
        "analysis_type": "ce2_multiscale",
        "status": "emergent" if has_emergence else "no_emergence",
        "summary": summary,
        "narrative_text": _render_narrative(model, ce2, has_emergence, profile, nodes),
        "input_model": {
            "kind": model["kind"],
            "state_labels": labels,
            "state_count": model["state_count"],
            "tpm": model["tpm"],
            "microscale_metrics": model["microscale_metrics"],
            "source": model["source"],
        },
        "ce2": ce2,
        "causal_hierarchy": hierarchy,
        "selected_macro_model": _selected_macro_model(endpoint, labels) if has_emergence else None,
        "narrative_graph": {
            "nodes": nodes,
            "edges": edges,
            "claims": claims,
            "evidence": evidence,
            "caveats": _caveats(model),
        },
        "assumptions": [
            "The system is represented as a finite, time-homogeneous, first-order Markov model.",
            "CP is determinism + specificity - 1 under the zoo's uniform intervention convention.",
            "Only hard state partitions and finite-horizon dynamically consistent macro models are considered.",
            "Narrative statements describe the fitted model; they do not by themselves identify real-world intervention effects.",
        ],
        "limitations": [
            "Exact CE 2.0 discovery is deliberately limited to small state spaces because partition enumeration is combinatorial.",
            "Dynamical consistency is checked over the declared finite horizon, not every possible future time step.",
            "This v0 does not yet implement black-boxing, higher-order macrostates, or native continuous-state CE 2.0; bounded beam search is available but is not globally optimal.",
        ],
    }


def _bootstrap_stability(
    trajectories: list[list[State]],
    *,
    state_labels: Sequence[State],
    smoothing: float,
    original_endpoint_id: str,
    max_exhaustive_states: int,
    consistency_horizon: int,
    consistency_tolerance: float,
    gain_tolerance: float,
    replicates: int,
    seed: int,
) -> dict[str, Any]:
    if replicates == 0:
        return {
            "status": "not_requested",
            "replicates": 0,
            "note": "Set bootstrap_replicates to assess trajectory-resampling stability.",
        }

    rng = random.Random(seed)
    successes = 0
    failures = 0
    endpoint_counts: dict[str, int] = {}
    positive_count = 0
    endpoint_gains: list[float] = []

    for _ in range(replicates):
        sample = [trajectories[rng.randrange(len(trajectories))] for _ in trajectories]
        try:
            estimated = estimate_tpm_from_trajectories(
                sample,
                state_labels=state_labels,
                smoothing=smoothing,
            )
            ce2 = discover_ce2_path(
                estimated["tpm"],
                max_exhaustive_states=max_exhaustive_states,
                consistency_horizon=consistency_horizon,
                consistency_tolerance=consistency_tolerance,
                gain_tolerance=gain_tolerance,
                top_k=1,
            )
        except ValueError:
            failures += 1
            continue

        successes += 1
        endpoint = ce2["endpoint"]
        endpoint_counts[endpoint["partition_id"]] = endpoint_counts.get(endpoint["partition_id"], 0) + 1
        gain = ce2["causal_apportioning"]["endpoint_cp_gain"]
        endpoint_gains.append(gain)
        if endpoint["macro_state_count"] < len(state_labels) and gain > gain_tolerance:
            positive_count += 1

    ranked_endpoints = sorted(endpoint_counts.items(), key=lambda item: (-item[1], item[0]))
    return {
        "status": "completed" if successes else "unavailable",
        "method": "resample_independent_trajectories_with_replacement",
        "replicates": replicates,
        "successful_replicates": successes,
        "failed_replicates": failures,
        "seed": seed,
        "selected_endpoint_frequency": endpoint_counts.get(original_endpoint_id, 0) / successes if successes else None,
        "positive_emergence_frequency": positive_count / successes if successes else None,
        "mean_endpoint_cp_gain": sum(endpoint_gains) / successes if successes else None,
        "endpoint_frequencies": [
            {"partition_id": partition_id, "count": count, "frequency": count / successes}
            for partition_id, count in ranked_endpoints
        ],
        "caveat": (
            "Bootstrap frequencies quantify resampling stability of this estimator and search, "
            "not experimental causal identification."
        ),
    }


def _graph_components(
    model: dict[str, Any],
    ce2: dict[str, Any],
    *,
    has_emergence: bool,
    edge_probability_threshold: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    micro_cp = ce2["microscale"]["cp"]
    endpoint = ce2["endpoint"]
    gain = ce2["causal_apportioning"]["endpoint_cp_gain"]
    claim_caveat_ids = _claim_caveat_ids(model)
    evidence: list[dict[str, Any]] = [
        {
            "id": "e:micro-cp",
            "kind": "metric",
            "metric": "cp",
            "value": micro_cp,
            "derivation": "determinism + specificity - 1",
            "scale": "microscale",
        },
        {
            "id": "e:endpoint-cp",
            "kind": "metric",
            "metric": "cp",
            "value": endpoint["cp"],
            "derivation": "determinism + specificity - 1",
            "scale": endpoint["partition_id"],
        },
        {
            "id": "e:endpoint-gain",
            "kind": "path_apportionment",
            "metric": "incremental_cp_total",
            "value": gain,
            "derivation": "endpoint CP minus microscale CP along the selected CE 2.0 path",
        },
    ]
    if not has_emergence:
        return evidence, [
            {
                "id": "claim:no-emergence",
                "type": "no_supported_macro_emergence",
                "status": "supported",
                "statement": "No dynamically consistent coarser endpoint increased CP on the selected CE 2.0 path.",
                "evidence_ids": ["e:micro-cp", "e:endpoint-cp", "e:endpoint-gain"],
                "caveat_ids": claim_caveat_ids,
            }
        ], [], []

    labels = model["state_labels"]
    nodes = []
    outgoing_counts = model.get("outgoing_counts", [])
    for macro_index, block in enumerate(endpoint["blocks"]):
        nodes.append(
            {
                "id": f"macro:{macro_index}",
                "kind": "macro_state",
                "label": _block_label(block, labels),
                "member_state_indices": block,
                "member_state_labels": [labels[state] for state in block],
                "support": {
                    "observed_outgoing_transitions": (
                        sum(outgoing_counts[state] for state in block) if outgoing_counts else None
                    )
                },
            }
        )

    edges = []
    claims = [
        {
            "id": "claim:emergent-scale",
            "type": "model_derived_emergent_scale",
            "status": "supported",
            "statement": (
                f"The endpoint partition {endpoint['partition_id']} raises model CP from "
                f"{micro_cp:.6f} to {endpoint['cp']:.6f} (+{gain:.6f})."
            ),
            "evidence_ids": ["e:micro-cp", "e:endpoint-cp", "e:endpoint-gain"],
            "caveat_ids": claim_caveat_ids,
        }
    ]
    for source_index, row in enumerate(endpoint["macro_tpm"]):
        dominant_target = max(range(len(row)), key=row.__getitem__)
        for target_index, probability in enumerate(row):
            if probability <= edge_probability_threshold:
                continue
            evidence_id = f"e:transition:{source_index}:{target_index}"
            evidence.append(
                {
                    "id": evidence_id,
                    "kind": "macro_transition_probability",
                    "source": f"macro:{source_index}",
                    "target": f"macro:{target_index}",
                    "value": probability,
                    "derivation": "induced macro TPM under uniform within-block intervention",
                }
            )
            edges.append(
                {
                    "id": f"macro:{source_index}->macro:{target_index}",
                    "source": f"macro:{source_index}",
                    "target": f"macro:{target_index}",
                    "relation": "model_transition",
                    "probability": probability,
                    "is_dominant_outgoing_transition": target_index == dominant_target,
                    "evidence_ids": [evidence_id],
                }
            )
        probability = row[dominant_target]
        claims.append(
            {
                "id": f"claim:dominant-transition:{source_index}",
                "type": "model_transition",
                "status": "supported",
                "statement": (
                    f"Within the fitted model, {nodes[source_index]['label']} most strongly transitions to "
                    f"{nodes[dominant_target]['label']} (probability {probability:.6f})."
                ),
                "evidence_ids": [f"e:transition:{source_index}:{dominant_target}"],
                "caveat_ids": claim_caveat_ids,
            }
        )
    return evidence, claims, nodes, edges


def _summary(model: dict[str, Any], ce2: dict[str, Any], has_emergence: bool, profile: str) -> dict[str, Any]:
    endpoint = ce2["endpoint"]
    gain = ce2["causal_apportioning"]["endpoint_cp_gain"]
    if has_emergence:
        headline = (
            f"A dynamically consistent {endpoint['macro_state_count']}-state macro model is supported "
            f"by a CE 2.0 CP gain of {gain:.6f}."
        )
    else:
        headline = "No dynamically consistent coarser model improved CP on the selected CE 2.0 path."
    return {
        "headline": headline,
        "hierarchy_profile": profile,
        "endpoint_partition_id": endpoint["partition_id"],
        "endpoint_macro_state_count": endpoint["macro_state_count"],
        "microscale_cp": ce2["microscale"]["cp"],
        "endpoint_cp": endpoint["cp"],
        "endpoint_cp_gain": gain,
        "emergent_complexity": ce2["emergent_complexity"],
        "source_kind": model["source"]["kind"],
    }


def _render_narrative(
    model: dict[str, Any],
    ce2: dict[str, Any],
    has_emergence: bool,
    profile: str,
    nodes: list[dict[str, Any]],
) -> str:
    endpoint = ce2["endpoint"]
    gain = ce2["causal_apportioning"]["endpoint_cp_gain"]
    source_kind = model["source"]["kind"].replace("_", " ")
    if not has_emergence:
        return (
            f"The {source_kind} model did not yield a dynamically consistent coarser scale with "
            "a positive CE 2.0 CP gain. This is evidence against a supported macro narrative under "
            "the declared model and search assumptions, not evidence that the underlying system has no structure."
        )

    macro_labels = "; ".join(node["label"] for node in nodes)
    complexity = ce2["emergent_complexity"]
    complexity_clause = (
        f" Positive-gain distribution has emergent complexity {complexity['bits']:.6f} bits "
        f"({complexity['normalized']:.6f} normalized), giving a {profile.replace('_', ' ')} profile."
        if complexity["status"] == "defined"
        else " Emergent-complexity entropy is not defined for this signed or empty gain profile."
    )
    return (
        f"CE 2.0 selected the dynamically consistent endpoint {endpoint['partition_id']} with "
        f"{endpoint['macro_state_count']} macro states: {macro_labels}. Its CP is {endpoint['cp']:.6f}, "
        f"a gain of {gain:.6f} over the microscale along the selected path.{complexity_clause} "
        "The transition statements in this graph describe the fitted Markov model and should not be "
        "read as independently identified real-world interventions."
    )


def _selected_macro_model(endpoint: dict[str, Any], labels: list[Hashable]) -> dict[str, Any]:
    return {
        "partition_id": endpoint["partition_id"],
        "blocks": endpoint["blocks"],
        "macro_state_labels": [_block_label(block, labels) for block in endpoint["blocks"]],
        "macro_tpm": endpoint["macro_tpm"],
        "cp": endpoint["cp"],
        "delta_cp_from_microscale": endpoint["delta_cp_from_microscale"],
        "dynamical_consistency": endpoint["dynamical_consistency"],
    }


def _hierarchy_profile(ce2: dict[str, Any], gain_tolerance: float) -> str:
    contributions = [
        step["positive_causal_contribution"]
        for step in ce2["path"][1:]
    ]
    positive_indices = [
        index
        for index, contribution in enumerate(contributions)
        if contribution > gain_tolerance
    ]
    if not positive_indices:
        return "no_emergence"
    if len(positive_indices) == 1:
        return "top_heavy"
    total = sum(contributions)
    endpoint_share = contributions[-1] / total if total else 0.0
    if endpoint_share >= 0.5:
        return "top_heavy"
    complexity = ce2["emergent_complexity"]
    if complexity["status"] == "defined" and complexity["normalized"] >= 0.5:
        return "distributed_multiscale"
    return "mesoscale"


def _caveats(model: dict[str, Any]) -> list[dict[str, Any]]:
    caveats = [
        {
            "id": "c:model_scope",
            "kind": "model_scope",
            "text": "Claims are conditional on the declared finite first-order Markov model and CE 2.0 search conventions.",
        },
        {
            "id": "c:causal_identification",
            "kind": "causal_identification",
            "text": "A model fitted from observations does not by itself establish interventional causal effects.",
        },
    ]
    source_kind = model["source"]["kind"]
    if source_kind in {"empirical_trajectory", "streaming_continuous_csv"}:
        caveats.append(
            {
                "id": "c:empirical_estimation",
                "kind": "estimation",
                "text": "Transition probabilities are empirical estimates and can be sensitive to sample size, smoothing, and state encoding.",
            }
        )
    if source_kind == "streaming_continuous_csv":
        caveats.append(
            {
                "id": "c:continuous_discretization",
                "kind": "continuous_discretization",
                "text": "Continuous observations were mapped to frozen learned microstates; the CE 2.0 result is conditional on feature scaling, reservoir sampling, and the reported encoder.",
            }
        )
    return caveats


def _claim_caveat_ids(model: dict[str, Any]) -> list[str]:
    ids = ["c:model_scope", "c:causal_identification"]
    if model["source"]["kind"] == "streaming_continuous_csv":
        ids.append("c:continuous_discretization")
    return ids


def _resolve_labels(state_count: int, state_labels: Sequence[Hashable] | None) -> list[Hashable]:
    labels = list(state_labels) if state_labels is not None else [f"s{index}" for index in range(state_count)]
    if len(labels) != state_count:
        raise ValueError(f"state_labels must contain exactly {state_count} labels.")
    try:
        if len(set(labels)) != len(labels):
            raise ValueError("state_labels must be unique.")
    except TypeError as exc:
        raise ValueError("state_labels must be hashable.") from exc
    try:
        json.dumps(labels, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("state_labels must be JSON serializable finite values.") from exc
    return labels


def _block_label(block: list[int], labels: Sequence[Hashable]) -> str:
    return "{" + ", ".join(str(labels[state]) for state in block) + "}"
