import json

from causal_emergence_zoo.narrative import analyze_trajectories, narrate_tpm


def _two_block_trajectories():
    labels = ["A", "B", "C", "D"]
    counts = [
        [9, 9, 1, 1],
        [9, 9, 1, 1],
        [1, 1, 9, 9],
        [1, 1, 9, 9],
    ]
    return labels, [
        [labels[source], labels[target]]
        for source, row in enumerate(counts)
        for target, count in enumerate(row)
        for _ in range(count)
    ]


def test_trajectory_narrative_returns_evidence_linked_macro_graph():
    labels, trajectories = _two_block_trajectories()

    result = analyze_trajectories(trajectories, state_labels=labels)

    assert result["status"] == "emergent"
    assert result["selected_macro_model"]["blocks"] == [[0, 1], [2, 3]]
    assert result["narrative_graph"]["nodes"][0]["member_state_labels"] == ["A", "B"]
    claims = result["narrative_graph"]["claims"]
    assert any(claim["type"] == "model_derived_emergent_scale" for claim in claims)
    assert all(claim["evidence_ids"] for claim in claims)
    json.dumps(result, allow_nan=False)


def test_identity_trajectories_return_a_successful_no_emergence_result():
    result = analyze_trajectories(
        [["A", "A"], ["B", "B"], ["C", "C"]],
        state_labels=["A", "B", "C"],
    )

    assert result["status"] == "no_emergence"
    assert result["selected_macro_model"] is None
    assert result["narrative_graph"]["claims"][0]["type"] == "no_supported_macro_emergence"


def test_narrative_bootstrap_is_seeded_and_json_serializable():
    labels, trajectories = _two_block_trajectories()

    first = analyze_trajectories(
        trajectories,
        state_labels=labels,
        bootstrap_replicates=8,
        bootstrap_seed=17,
    )
    second = analyze_trajectories(
        trajectories,
        state_labels=labels,
        bootstrap_replicates=8,
        bootstrap_seed=17,
    )

    assert first["robustness"] == second["robustness"]
    assert first["robustness"]["status"] == "completed"
    json.dumps(first, allow_nan=False)


def test_provided_identity_tpm_does_not_fabricate_an_emergent_narrative():
    result = narrate_tpm(
        [[1.0, 0.0], [0.0, 1.0]],
        state_labels=["off", "on"],
    )

    assert result["status"] == "no_emergence"
    assert "did not yield" in result["narrative_text"]
