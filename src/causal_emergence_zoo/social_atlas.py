"""Country-year social-system data preparation.

This module intentionally does not download or silently impute social data. It
joins already downloaded, long-format source files while preserving provenance,
missingness, and the country-year trajectory contract used by the streaming
continuous analyzer.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable, Sequence


def load_country_year_source(
    path: str | Path,
    *,
    country_column: str = "country_code",
    year_column: str = "year",
    prefix: str = "",
) -> dict[tuple[str, int], dict[str, float | str | int | None]]:
    """Load a numeric long-format country-year CSV into a keyed source table."""
    output: dict[tuple[str, int], dict[str, float | str | int | None]] = {}
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or country_column not in reader.fieldnames or year_column not in reader.fieldnames:
            raise ValueError(f"{path} must contain {country_column!r} and {year_column!r} columns.")
        value_columns = [column for column in reader.fieldnames if column not in {country_column, year_column}]
        for line_number, row in enumerate(reader, start=2):
            country = (row[country_column] or "").strip()
            if not country:
                raise ValueError(f"{path} line {line_number} has an empty country code.")
            try:
                year = int(row[year_column])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{path} line {line_number} has an invalid year.") from exc
            key = (country, year)
            if key in output:
                raise ValueError(f"{path} contains duplicate country-year key {country}-{year}.")
            values: dict[str, float | str | int | None] = {}
            for column in value_columns:
                raw = (row[column] or "").strip()
                if raw in {"", ".", "NA", "NaN", "null"}:
                    values[f"{prefix}{column}"] = None
                else:
                    try:
                        values[f"{prefix}{column}"] = float(raw)
                    except ValueError:
                        raise ValueError(f"{path} line {line_number}, column {column!r} is not numeric.")
            output[key] = values
    return output


def assemble_social_atlas(
    sources: Sequence[tuple[str, dict[tuple[str, int], dict[str, Any]]]],
    *,
    feature_columns: Sequence[str],
    start_year: int,
    end_year: int,
    min_observations: int = 5,
) -> dict[str, Any]:
    """Join source tables into complete country trajectories without imputation."""
    if start_year > end_year:
        raise ValueError("start_year must be no later than end_year.")
    if min_observations < 2:
        raise ValueError("min_observations must be at least two.")
    keys = sorted({key for _, table in sources for key in table if start_year <= key[1] <= end_year})
    countries = sorted({country for country, _ in keys})
    rows: list[dict[str, Any]] = []
    missing_by_feature = {feature: 0 for feature in feature_columns}
    for country in countries:
        country_rows = []
        for year in range(start_year, end_year + 1):
            merged: dict[str, Any] = {"country_code": country, "year": year}
            for _, table in sources:
                merged.update(table.get((country, year), {}))
            for feature in feature_columns:
                value = merged.get(feature)
                if value is None:
                    missing_by_feature[feature] += 1
            if all(merged.get(feature) is not None for feature in feature_columns):
                country_rows.append(merged)
        if len(country_rows) >= min_observations:
            rows.extend(country_rows)
    retained_countries = sorted({row["country_code"] for row in rows})
    return {
        "schema_version": "0.1.0",
        "kind": "causal_emergence.country_year_social_atlas",
        "rows": rows,
        "feature_columns": list(feature_columns),
        "year_range": [start_year, end_year],
        "source_names": [name for name, _ in sources],
        "retained_country_count": len(retained_countries),
        "retained_countries": retained_countries,
        "missing_by_feature_before_complete_case_filter": missing_by_feature,
        "complete_case_policy": "drop country-years with any requested feature missing; retain countries with min_observations",
        "trajectory_count": len(retained_countries),
        "observation_count": len(rows),
    }


def write_social_atlas_csv(atlas: dict[str, Any], path: str | Path) -> None:
    """Write an assembled atlas in the CSV contract expected by the CLI."""
    rows = atlas.get("rows", [])
    if not rows:
        raise ValueError("Cannot write an empty social atlas.")
    fieldnames = ["country_code", "year", *atlas["feature_columns"]]
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({key: row.get(key) for key in fieldnames} for row in rows)

