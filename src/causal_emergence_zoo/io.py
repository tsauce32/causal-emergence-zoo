"""Loading helpers for benchmark system JSON files."""

from __future__ import annotations

import json
from pathlib import Path


def data_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data"


def available_systems() -> list[str]:
    """Return benchmark system ids available in the local checkout."""
    return sorted(path.stem for path in data_dir().glob("*.json"))


def load_system(system_id: str) -> dict:
    """Load a benchmark system by id, for example ``two_block_noisy_4``."""
    path = data_dir() / f"{system_id}.json"
    if not path.exists():
        choices = ", ".join(available_systems())
        raise FileNotFoundError(f"No benchmark system {system_id!r}. Available: {choices}")
    return json.loads(path.read_text(encoding="utf-8"))
