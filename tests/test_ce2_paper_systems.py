import pytest

from causal_emergence_zoo.ce2 import analyze_ce2_path, discover_ce2_path
from causal_emergence_zoo.metrics import compute_metrics
from causal_emergence_zoo.paper_systems import (
    ce2_paper_reference_values,
    figure2_equivalence_class_tpm,
    figure2_path,
    figure3_mesoscale_tpm,
    figure3_top_heavy_tpm,
    figure4_block_model_tpm,
)
from causal_emergence_zoo.search import score_partition


def test_figure2_reproduces_published_cp_and_ce():
    reference = ce2_paper_reference_values()["figure2"]
    result = analyze_ce2_path(figure2_equivalence_class_tpm(), figure2_path())

    assert result["validity"]["is_valid"]
    assert result["microscale"]["cp"] == pytest.approx(reference["micro_cp"])
    assert result["endpoint"]["cp"] == pytest.approx(reference["endpoint_cp"])
    assert result["causal_apportioning"]["endpoint_cp_gain"] == pytest.approx(
        reference["causal_emergence"]
    )


def test_figure3_top_heavy_reproduces_published_emergent_complexity():
    reference = ce2_paper_reference_values()["figure3_top_heavy"]
    result = discover_ce2_path(figure3_top_heavy_tpm())

    assert result["endpoint"]["blocks"] == reference["endpoint_partition"]
    assert result["microscale"]["cp"] == pytest.approx(reference["micro_cp_rounded"], abs=0.005)
    assert result["endpoint"]["cp"] == pytest.approx(reference["endpoint_cp_rounded"], abs=0.005)
    assert result["emergent_complexity"]["bits"] == pytest.approx(
        reference["emergent_complexity_bits_rounded"], abs=0.005
    )


def test_figure3_mesoscale_reproduces_published_endpoint_gain():
    tpm = figure3_mesoscale_tpm()
    micro_cp = compute_metrics(tpm)["causal_power"]
    endpoint = ce2_paper_reference_values()["figure3_mesoscale"]["endpoint_partition"]
    record = score_partition(tpm, endpoint, micro_causal_power=micro_cp)

    assert record["deltaCP"] == pytest.approx(0.13, abs=0.005)


def test_figure4_curve_decreases_from_two_thirds_to_zero():
    reference = ce2_paper_reference_values()["figure4"]
    endpoint = reference["endpoint_partition"]
    gains = []
    for step in range(reference["steps"] + 1):
        tpm = figure4_block_model_tpm(step, steps=reference["steps"])
        micro_cp = compute_metrics(tpm)["causal_power"]
        gains.append(score_partition(tpm, endpoint, micro_causal_power=micro_cp)["deltaCP"])

    assert gains[0] == pytest.approx(reference["initial_ce2"])
    assert gains[-1] == pytest.approx(reference["final_ce2"])
    assert all(left >= right - 1e-12 for left, right in zip(gains, gains[1:]))


@pytest.mark.parametrize("step", [-1, 51])
def test_figure4_generator_rejects_out_of_range_steps(step):
    with pytest.raises(ValueError):
        figure4_block_model_tpm(step)

