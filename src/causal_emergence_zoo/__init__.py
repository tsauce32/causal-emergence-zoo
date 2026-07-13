"""Public API for causal-emergence-zoo."""

__version__ = "0.2.1"

from causal_emergence_zoo.ce2 import (
    MAX_EXACT_STATES,
    analyze_ce2_path,
    check_dynamical_consistency,
    discover_ce2_path,
)
from causal_emergence_zoo.approximate import MAX_APPROXIMATE_STATES, approximate_ce2_path
from causal_emergence_zoo.coarse_grain import coarse_grain_tpm
from causal_emergence_zoo.estimation import (
    estimate_tpm_from_trajectories,
    estimate_tpm_from_transition_counts,
)
from causal_emergence_zoo.io import available_systems, load_system
from causal_emergence_zoo.metrics import compute_metrics
from causal_emergence_zoo.narrative import (
    analyze_trajectories,
    analyze_trajectories_typed,
    build_narrative_graph,
    narrate_tpm,
    narrate_tpm_typed,
)
from causal_emergence_zoo.continuous import (
    analyze_continuous_csv,
    analyze_continuous_typed,
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
from causal_emergence_zoo.demo import (
    SOCIAL_SYSTEM_DEMO_CAVEAT,
    SOCIAL_SYSTEM_DEMO_FEATURE_COLUMNS,
    SocialSystemDemoSource,
    explore_social_system_demo,
    social_system_demo_metadata,
    social_system_demo_source,
)
from causal_emergence_zoo.temporal import derive_temporal_features, temporal_feature_names
from causal_emergence_zoo.explore import (
    explore,
    explore_csv,
    explore_typed,
    profile_csv,
    profile_source,
    profile_typed,
    recommend_analysis_plan,
    recommend_analysis_plan_typed,
    write_exploration_json,
)
from causal_emergence_zoo.api import (
    API_SCHEMA_VERSION,
    AnalysisPlan,
    ArtifactValidationError,
    CausalHierarchy,
    DataProfile,
    EvidenceLedger,
    ExplorationResult,
    NarrativeReport,
    StateModel,
    analysis_plan_from_dict,
    causal_hierarchy_from_dict,
    data_profile_from_dict,
    evidence_ledger_from_dict,
    exploration_result_from_dict,
    narrative_report_from_dict,
    public_api_schema,
    state_model_from_dict,
    validate_public_artifact,
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
    "API_SCHEMA_VERSION",
    "AnalysisPlan",
    "ArtifactValidationError",
    "CausalHierarchy",
    "DataProfile",
    "EvidenceLedger",
    "ExplorationResult",
    "NarrativeReport",
    "StateModel",
    "MAX_APPROXIMATE_STATES",
    "MAX_EXACT_STATES",
    "analyze_ce2_path",
    "analyze_continuous_csv",
    "analyze_continuous_typed",
    "analyze_continuous_multiresolution_csv",
    "analyze_trajectories",
    "analyze_trajectories_typed",
    "analysis_plan_from_dict",
    "adapt_continuous_source",
    "assess_multiresolution_stability",
    "approximate_ce2_path",
    "available_systems",
    "attach_evidence_ledger",
    "branching_greedy_search",
    "build_narrative_graph",
    "build_causal_hierarchy",
    "build_evidence_ledger",
    "causal_hierarchy_from_dict",
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
    "data_profile_from_dict",
    "evidence_ledger_from_dict",
    "explore",
    "explore_csv",
    "explore_social_system_demo",
    "explore_typed",
    "exploration_result_from_dict",
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
    "narrate_tpm_typed",
    "narrative_report_from_dict",
    "PandasDataFrameSource",
    "ParquetTabularSource",
    "PolarsDataFrameSource",
    "profile_csv",
    "profile_source",
    "profile_typed",
    "public_api_schema",
    "recommend_analysis_plan",
    "recommend_analysis_plan_typed",
    "render_exploration_report",
    "SOCIAL_SYSTEM_DEMO_CAVEAT",
    "SOCIAL_SYSTEM_DEMO_FEATURE_COLUMNS",
    "social_system_demo_metadata",
    "social_system_demo_source",
    "SocialSystemDemoSource",
    "write_social_atlas_csv",
    "write_exploration_json",
    "validate_system",
    "temporal_feature_names",
    "TabularSource",
    "state_model_from_dict",
    "trajectory_temporal_permutation_null",
    "validate_continuous_analysis_trajectories",
    "validate_grouped_trajectories",
    "validate_public_artifact",
    "__version__",
]
