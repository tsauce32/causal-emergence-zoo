"""End-to-end recovery of a known narrative from noisy continuous observations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from causal_emergence_zoo.continuous import analyze_continuous_csv
from causal_emergence_zoo.synthetic import generate_two_block_continuous_csv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-directory", default="case-study-output")
    parser.add_argument("--transitions", type=int, default=100_000)
    parser.add_argument("--noise", type=float, default=0.08)
    parser.add_argument("--seed", type=int, default=23)
    args = parser.parse_args()

    output = Path(args.output_directory)
    output.mkdir(parents=True, exist_ok=True)
    csv_path = output / "observations.csv.gz"
    truth = generate_two_block_continuous_csv(
        csv_path,
        transition_count=args.transitions,
        noise_standard_deviation=args.noise,
        seed=args.seed,
    )
    result = analyze_continuous_csv(
        csv_path,
        feature_columns=["signal"],
        microstate_count=4,
        trajectory_column="trajectory_id",
        time_column="time",
        reservoir_size=min(10_000, args.transitions * 2),
        random_seed=args.seed,
        consistency_tolerance=0.02,
    )
    report = {
        "ground_truth": truth,
        "recovered_hierarchy": result["causal_hierarchy"],
        "narrative": result["narrative_text"],
        "robustness": result["continuous_data"]["all_data_fixed_path"],
        "full_result_file": "analysis.json",
    }
    (output / "analysis.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(result["narrative_text"])
    print(f"Wrote {output / 'report.json'} and {output / 'analysis.json'}")


if __name__ == "__main__":
    main()

