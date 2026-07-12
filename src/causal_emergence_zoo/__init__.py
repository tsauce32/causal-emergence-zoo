"""Lightweight utilities for the causal-emergence benchmark zoo."""

from causal_emergence_zoo.ce2 import analyze_ce2_path, check_dynamical_consistency, discover_ce2_path
from causal_emergence_zoo.approximate import approximate_ce2_path
from causal_emergence_zoo.coarse_grain import coarse_grain_tpm
from causal_emergence_zoo.estimation import (
    estimate_tpm_from_trajectories,
    estimate_tpm_from_transition_counts,
)
from causal_emergence_zoo.io import available_systems, load_system
from causal_emergence_zoo.metrics import compute_metrics
from causal_emergence_zoo.narrative import analyze_trajectories, build_narrative_graph, narrate_tpm
from causal_emergence_zoo.continuous import (
    analyze_continuous_csv,
    count_continuous_csv_transitions,
    encode_continuous_observation,
    fit_continuous_csv_encoder,
    fit_continuous_state_encoder,
)
from causal_emergence_zoo.tabular import (
    CsvTabularSource,
    PandasDataFrameSource,
    ParquetTabularSource,
    PolarsDataFrameSource,
    TabularSource,
    adapt_continuous_source,
    describe_continuous_source,
)
from causal_emergence_zoo.multiresolution import analyze_continuous_multiresolution_csv
from causal_emergence_zoo.partitions import enumerate_partitions
from causal_emergence_zoo.hierarchy import build_causal_hierarchy
from causal_emergence_zoo.synthetic import generate_two_block_continuous_csv
from causal_emergence_zoo.social_atlas import (
    assemble_social_atlas,
    load_country_year_source,
    write_social_atlas_csv,
)
from causal_emergence_zoo.temporal import derive_temporal_features, temporal_feature_names
from causal_emergence_zoo.explore import (
    explore,
    explore_csv,
    profile_csv,
    profile_source,
    recommend_analysis_plan,
    write_exploration_json,
)
from causal_emergence_zoo.report import render_exploration_report
from causal_emergence_zoo.evidence import attach_evidence_ledger, build_evidence_ledger
from causal_emergence_zoo.empirical_validation import (
    assess_multiresolution_stability,
    compare_macro_assignments,
    grouped_bootstrap_confidence_intervals,
    trajectory_temporal_permutation_null,
    validate_continuous_analysis_trajectories,
    validate_grouped_trajectories,
)
from causal_emergence_zoo.paper_systems import (
    ce2_paper_reference_values,
    figure2_equivalence_class_tpm,
    figure2_path,
    figure3_mesoscale_tpm,
    figure3_top_heavy_tpm,
    figure4_block_model_tpm,
)
from causal_emergence_zoo.search import branching_greedy_search, greedy_completion
from causal_emergence_zoo.validation import validate_system

__all__ = [
    "analyze_ce2_path",
    "analyze_continuous_csv",
    "analyze_continuous_multiresolution_csv",
    "analyze_trajectories",
    "adapt_continuous_source",
    "assess_multiresolution_stability",
    "approximate_ce2_path",
    "available_systems",
    "attach_evidence_ledger",
    "branching_greedy_search",
    "build_narrative_graph",
    "build_causal_hierarchy",
    "build_evidence_ledger",
    "assemble_social_atlas",
    "check_dynamical_consistency",
    "coarse_grain_tpm",
    "compute_metrics",
    "compare_macro_assignments",
    "count_continuous_csv_transitions",
    "CsvTabularSource",
    "discover_ce2_path",
    "derive_temporal_features",
    "describe_continuous_source",
    "explore",
    "explore_csv",
    "enumerate_partitions",
    "estimate_tpm_from_trajectories",
    "estimate_tpm_from_transition_counts",
    "ce2_paper_reference_values",
    "encode_continuous_observation",
    "fit_continuous_csv_encoder",
    "fit_continuous_state_encoder",
    "figure2_equivalence_class_tpm",
    "figure2_path",
    "figure3_mesoscale_tpm",
    "figure3_top_heavy_tpm",
    "figure4_block_model_tpm",
    "greedy_completion",
    "grouped_bootstrap_confidence_intervals",
    "generate_two_block_continuous_csv",
    "load_country_year_source",
    "load_system",
    "narrate_tpm",
    "PandasDataFrameSource",
    "ParquetTabularSource",
    "PolarsDataFrameSource",
    "profile_csv",
    "profile_source",
    "recommend_analysis_plan",
    "render_exploration_report",
    "write_social_atlas_csv",
    "write_exploration_json",
    "validate_system",
    "temporal_feature_names",
    "TabularSource",
    "trajectory_temporal_permutation_null",
    "validate_continuous_analysis_trajectories",
    "validate_grouped_trajectories",
]
