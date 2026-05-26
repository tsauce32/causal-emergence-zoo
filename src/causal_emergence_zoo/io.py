"""Loading helpers for benchmark system JSON files."""

from __future__ import annotations

import json
from importlib.resources import files


def data_dir():
    """Return the packaged benchmark data resource directory."""
    return files("causal_emergence_zoo").joinpath("data")


def available_systems() -> list[str]:
    """Return benchmark system ids available in the local checkout."""
    return sorted(
        path.name.removesuffix(".json")
        for path in data_dir().iterdir()
        if path.name.endswith(".json")
    )


def load_system(system_id: str) -> dict:
    """Load a benchmark system by id, for example ``two_block_noisy_4``."""
    path = data_dir() / f"{system_id}.json"
    if not path.is_file():
        choices = ", ".join(available_systems())
        raise FileNotFoundError(f"No benchmark system {system_id!r}. Available: {choices}")
    return json.loads(path.read_text(encoding="utf-8"))
