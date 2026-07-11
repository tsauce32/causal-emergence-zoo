"""Reproduce the RAS3 country-year CE2 pilot without bundling third-party data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from causal_emergence_zoo.continuous import analyze_continuous_csv


FEATURES = {
    "official_religion": "SAX",
    "religious_regulation": "NXX",
    "religious_legislation": "LXX",
    "minority_discrimination": "MXX",
    "societal_discrimination": "WSOCDISX",
    "minority_actions_against_majority": "WMIN2MAJX",
    "societal_relations": "WSOCREGX",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ras3_stata_file", help="RAS3 Stata download from ARDA")
    parser.add_argument("--output-directory", default="ras3-pilot-output")
    parser.add_argument("--microstates", type=int, default=8)
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    try:
        import pandas as pd
    except ImportError as exc:
        raise SystemExit("This optional reproducer requires pandas: pip install pandas") from exc

    raw = pd.read_stata(args.ras3_stata_file, convert_categoricals=False)
    rows = []
    for _, record in raw.iterrows():
        country = record["ISO3"]
        if not isinstance(country, str) or len(country) != 3:
            continue
        for year in range(1990, 2015):
            row = {"country_code": country, "year": year}
            row.update({name: record.get(f"{stem}{year}") for name, stem in FEATURES.items()})
            rows.append(row)
    panel = pd.DataFrame(rows).dropna()
    retained = panel.groupby("country_code").size()
    panel = panel[panel["country_code"].isin(retained[retained >= 20].index)]
    panel = panel.sort_values(["country_code", "year"])

    output = Path(args.output_directory)
    output.mkdir(parents=True, exist_ok=True)
    csv_path = output / "ras3-country-year-complete.csv"
    panel.to_csv(csv_path, index=False)
    result = analyze_continuous_csv(
        csv_path,
        feature_columns=list(FEATURES),
        microstate_count=args.microstates,
        trajectory_column="country_code",
        time_column="year",
        reservoir_size=5_000,
        random_seed=args.seed,
        consistency_tolerance=1e-6,
    )
    result["empirical_pilot"] = {
        "dataset": "RAS3",
        "year_range": [1990, 2014],
        "complete_case_country_count": int(panel["country_code"].nunique()),
        "complete_case_observation_count": int(len(panel)),
        "feature_stems": FEATURES,
        "interpretation": "exploratory country-year model; not an identified causal claim",
    }
    (output / "analysis.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(result["narrative_text"])
    print(f"Wrote {output / 'analysis.json'}")


if __name__ == "__main__":
    main()

