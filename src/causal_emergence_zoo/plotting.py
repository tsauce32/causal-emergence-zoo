"""Optional plotting helpers for benchmark systems."""

from __future__ import annotations


def plot_tpm(tpm: list[list[float]], title: str | None = None):
    """Plot a TPM heatmap with matplotlib, if matplotlib is installed."""
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise ImportError("Install causal-emergence-zoo[plots] to use plotting helpers.") from exc

    figure, axis = plt.subplots()
    image = axis.imshow(tpm, vmin=0.0, vmax=1.0, cmap="viridis")
    axis.set_xlabel("Target state")
    axis.set_ylabel("Source state")
    if title:
        axis.set_title(title)
    figure.colorbar(image, ax=axis, label="Transition probability")
    return figure, axis
