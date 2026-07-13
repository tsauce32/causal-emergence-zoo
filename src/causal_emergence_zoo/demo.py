"""A small, reproducible social-system-style onboarding dataset.

The demo is deliberately synthetic. It gives new users a fast way to inspect
the complete exploration workflow without implying that a result describes any
actual country, religion, or population.
"""

from __future__ import annotations

import random
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from causal_emergence_zoo.report import render_exploration_report
from causal_emergence_zoo.tabular import TabularSource


SOCIAL_SYSTEM_DEMO_VERSION = "1.0.0"
SOCIAL_SYSTEM_DEMO_FEATURE_COLUMNS = (
    "poverty_rate",
    "social_capacity",
    "religious_restriction_index",
    "organized_violence_rate",
)
SOCIAL_SYSTEM_DEMO_CAVEAT = (
    "This bundled onboarding dataset is synthetic and deliberately constructed "
    "to contain recurring social-system-style configurations. It is not evidence "
    "about real countries, religion, poverty, or violence."
)

_COUNTRY_CODES = (
    "SYN_A01",
    "SYN_A02",
    "SYN_A03",
    "SYN_A04",
    "SYN_A05",
    "SYN_B01",
    "SYN_B02",
    "SYN_B03",
    "SYN_B04",
    "SYN_B05",
    "SYN_C01",
    "SYN_C02",
    "SYN_C03",
    "SYN_C04",
    "SYN_C05",
    "SYN_D01",
    "SYN_D02",
    "SYN_D03",
    "SYN_D04",
    "SYN_D05",
)
_COLUMNS = ("country_code", "year", *SOCIAL_SYSTEM_DEMO_FEATURE_COLUMNS)
_STATE_CENTERS = (
    (18.0, 78.0, 14.0, 2.5),
    (27.0, 68.0, 24.0, 5.5),
    (57.0, 39.0, 60.0, 23.0),
    (68.0, 28.0, 73.0, 37.0),
)
_STATE_SCALES = (0.15, 0.17, 0.21, 0.12)
_CROSS_BLOCK_PARTNER = (2, 3, 0, 1)


@dataclass(frozen=True)
class SocialSystemDemoSource(TabularSource):
    """Repeatable generated rows for the bundled synthetic country-year demo."""

    seed: int = 73
    years_per_country: int = 41

    def iter_rows(self, columns: Sequence[str]) -> Iterator[dict[str, Any]]:
        requested = _requested_columns(columns)
        for row in self._rows():
            yield {column: row[column] for column in requested}

    def column_names(self) -> list[str]:
        return list(_COLUMNS)

    def source_signature(self) -> dict[str, Any]:
        return {
            "kind": "bundled_synthetic_social_system_demo",
            "version": SOCIAL_SYSTEM_DEMO_VERSION,
            "seed": self.seed,
            "country_count": len(_COUNTRY_CODES),
            "years_per_country": self.years_per_country,
            "row_count": len(_COUNTRY_CODES) * self.years_per_country,
        }

    def descriptor(self) -> dict[str, Any]:
        return {
            "adapter": "bundled synthetic social-system demo",
            "format": "deterministically_generated_rows",
            "bounded_memory": True,
            "memory_semantics": "generated_one_row_at_a_time",
            "reopenable": True,
            "source_signature_policy": "demo_version_and_generation_parameters",
            "synthetic": True,
        }

    def _rows(self) -> Iterator[dict[str, Any]]:
        if self.years_per_country < 2:
            raise ValueError("years_per_country must be at least two.")
        rng = random.Random(self.seed)
        for country_index, country_code in enumerate(_COUNTRY_CODES):
            state = country_index % len(_STATE_CENTERS)
            country_offset = (country_index % 5 - 2) * 0.35
            for year_offset in range(self.years_per_country):
                center = _STATE_CENTERS[state]
                values = [
                    center[index] + country_offset + rng.gauss(0.0, _STATE_SCALES[index])
                    for index in range(len(SOCIAL_SYSTEM_DEMO_FEATURE_COLUMNS))
                ]
                yield {
                    "country_code": country_code,
                    "year": 2000 + year_offset,
                    **dict(zip(SOCIAL_SYSTEM_DEMO_FEATURE_COLUMNS, values)),
                }
                # Nine within-state transitions followed by one switch to the
                # corresponding state in the other macro block gives each
                # source state the same exact macro-level transition profile
                # as its partner. The small feature noise does not alter the
                # underlying discrete sequence.
                if (year_offset + 1) % 10 == 0:
                    state = _CROSS_BLOCK_PARTNER[state]


def social_system_demo_source() -> SocialSystemDemoSource:
    """Return the bundled source used by :command:`cez demo`."""
    return SocialSystemDemoSource()


def social_system_demo_metadata() -> dict[str, Any]:
    """Describe the provenance and fixed analysis choices of the demo."""
    source = social_system_demo_source()
    return {
        "kind": "causal_emergence.bundled_social_system_demo",
        "version": SOCIAL_SYSTEM_DEMO_VERSION,
        "synthetic": True,
        "row_count": len(_COUNTRY_CODES) * source.years_per_country,
        "trajectory_count": len(_COUNTRY_CODES),
        "entity_column": "country_code",
        "time_column": "year",
        "feature_columns": list(SOCIAL_SYSTEM_DEMO_FEATURE_COLUMNS),
        "resolutions": [4, 6],
        "encoder_seed": 17,
        "caveat": SOCIAL_SYSTEM_DEMO_CAVEAT,
    }


def explore_social_system_demo(*, report_path: str | Path | None = None) -> dict[str, Any]:
    """Run the full guided workflow on the bundled synthetic demo.

    The deliberately modest resolutions keep this first run quick. They are
    recorded in the result and should not be mistaken for a recommended state
    count for an unrelated dataset.
    """
    from causal_emergence_zoo.explore import (
        explore_typed,
        profile_source,
        recommend_analysis_plan,
    )

    metadata = social_system_demo_metadata()
    source = social_system_demo_source()
    profile = profile_source(
        source,
        entity=metadata["entity_column"],
        time=metadata["time_column"],
    )
    plan = recommend_analysis_plan(
        profile,
        features=metadata["feature_columns"],
        resolutions=metadata["resolutions"],
        seeds=[metadata["encoder_seed"]],
    )
    # This first-run fixture is intentionally a direct finite-state bridge.
    # Its temporal-difference and volatility variants would be a different
    # teaching model, so they remain an explicit next step for user data.
    plan["temporal_features"] = {"differences": [], "volatility_windows": []}
    plan["validation_fraction"] = 0.0
    plan["notes"].append(
        "The bundled demo disables derived temporal features and holdout splitting "
        "so its intentionally constructed transition structure remains inspectable."
    )
    result = explore_typed(source, plan=plan).to_legacy_dict()
    result["profile"]["source"]["path"] = "Bundled synthetic social-system demo"
    result["analysis"]["limitations"].insert(0, SOCIAL_SYSTEM_DEMO_CAVEAT)
    result["demo"] = metadata
    if report_path is not None:
        destination = Path(report_path)
        destination.write_text(render_exploration_report(result), encoding="utf-8")
        result["artifacts"] = {"html_report": str(destination.resolve())}
    return result


def _requested_columns(columns: Sequence[str]) -> list[str]:
    requested = list(columns)
    if not requested:
        raise ValueError("At least one demo column must be requested.")
    unknown = [column for column in requested if column not in _COLUMNS]
    if unknown:
        raise ValueError(f"Bundled social-system demo has no column(s): {unknown}.")
    if len(set(requested)) != len(requested):
        raise ValueError("Requested demo columns must be unique.")
    return requested
