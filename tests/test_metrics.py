from causal_emergence_zoo.coarse_grain import coarse_grain_tpm
from causal_emergence_zoo.metrics import compute_metrics


def test_identity_has_maximal_causal_power():
    tpm = [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]

    metrics = compute_metrics(tpm)

    assert metrics["row_entropy_bits"] == 0.0
    assert metrics["causal_power"] == 1.0


def test_fully_degenerate_system_has_zero_causal_power():
    tpm = [
        [1.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
    ]

    metrics = compute_metrics(tpm)

    assert metrics["determinism"] == 1.0
    assert metrics["causal_power"] == 0.0


def test_two_block_partition_improves_normalized_causal_power():
    tpm = [
        [0.45, 0.45, 0.05, 0.05],
        [0.45, 0.45, 0.05, 0.05],
        [0.05, 0.05, 0.45, 0.45],
        [0.05, 0.05, 0.45, 0.45],
    ]

    micro = compute_metrics(tpm)
    macro_tpm = coarse_grain_tpm(tpm, [[0, 1], [2, 3]])
    macro = compute_metrics(macro_tpm)

    assert macro["causal_power"] > micro["causal_power"]
