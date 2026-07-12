"""Stable, versioned public artifacts for causal-emergence-zoo.

The original public functions intentionally return JSON-compatible mappings.
They remain supported as the compatibility layer.  This module is the v0.2
Python API: small immutable-looking value objects with explicit schema versions,
round-trip serialization, and adapters for the legacy result shapes.

The objects do not hide the underlying scientific evidence.  In particular,
``to_legacy_dict`` preserves the complete result returned by the original
analysis functions, while ``to_dict`` emits the stable v0.2 envelope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.resources import files
import json
from pathlib import Path
from typing import Any, ClassVar, Mapping, Sequence


API_SCHEMA_VERSION = "0.2.0"


class ArtifactValidationError(ValueError):
    """Raised when a mapping cannot be converted to a stable public artifact."""


def _json_clone(value: Any, *, context: str = "value") -> Any:
    """Return a detached JSON-safe copy with an actionable error on failure."""
    try:
        return json.loads(json.dumps(value, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ArtifactValidationError(f"{context} must be JSON serializable with finite numbers.") from exc


def _mapping(value: Any, *, context: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ArtifactValidationError(f"{context} must be a mapping.")
    copied = _json_clone(dict(value), context=context)
    if not all(isinstance(key, str) for key in copied):
        raise ArtifactValidationError(f"{context} keys must be strings.")
    return copied


def _required(payload: Mapping[str, Any], key: str, *, context: str) -> Any:
    if key not in payload:
        raise ArtifactValidationError(f"{context} is missing required field {key!r}.")
    return payload[key]


def _required_mapping(payload: Mapping[str, Any], key: str, *, context: str) -> dict[str, Any]:
    return _mapping(_required(payload, key, context=context), context=f"{context}.{key}")


def _required_string(payload: Mapping[str, Any], key: str, *, context: str, nullable: bool = False) -> str | None:
    value = _required(payload, key, context=context)
    if nullable and value is None:
        return None
    if not isinstance(value, str):
        raise ArtifactValidationError(f"{context}.{key} must be a string{' or null' if nullable else ''}.")
    return value


def _required_int(payload: Mapping[str, Any], key: str, *, context: str, minimum: int | None = None) -> int:
    value = _required(payload, key, context=context)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ArtifactValidationError(f"{context}.{key} must be an integer.")
    if minimum is not None and value < minimum:
        raise ArtifactValidationError(f"{context}.{key} must be at least {minimum}.")
    return value


def _string_tuple(value: Any, *, context: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ArtifactValidationError(f"{context} must be a sequence of strings.")
    if any(not isinstance(item, str) for item in value):
        raise ArtifactValidationError(f"{context} must contain only strings.")
    return tuple(value)


def _mapping_tuple(value: Any, *, context: str) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ArtifactValidationError(f"{context} must be a sequence of mappings.")
    return tuple(_mapping(item, context=f"{context}[{index}]") for index, item in enumerate(value))


def _extensions(payload: Mapping[str, Any], known: set[str]) -> dict[str, Any]:
    return {
        key: _json_clone(value, context=f"extension {key!r}")
        for key, value in payload.items()
        if key not in known
    }


def _document(kind: str, fields: Mapping[str, Any], extensions: Mapping[str, Any]) -> dict[str, Any]:
    result = {"schema_version": API_SCHEMA_VERSION, "kind": kind, **_json_clone(dict(fields))}
    for key, value in extensions.items():
        if key in result:
            raise ArtifactValidationError(f"Extension field {key!r} conflicts with a stable artifact field.")
        result[key] = _json_clone(value, context=f"extension {key!r}")
    return result


@dataclass(frozen=True, slots=True)
class DataProfile:
    """A versioned description of a tabular input, before causal modelling."""

    source: Mapping[str, Any]
    row_count: int
    columns: tuple[str, ...]
    inferred_roles: Mapping[str, Any]
    missing_counts: Mapping[str, int]
    numeric_ranges: Mapping[str, Any]
    trajectory_count: int
    trajectory_length: Mapping[str, int]
    warnings: tuple[str, ...] = ()
    extensions: Mapping[str, Any] = field(default_factory=dict, repr=False)

    KIND: ClassVar[str] = "causal_emergence.data_profile"
    SCHEMA_VERSION: ClassVar[str] = API_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DataProfile":
        payload = _mapping(value, context="DataProfile")
        kind = payload.get("kind")
        if kind not in {None, cls.KIND}:
            raise ArtifactValidationError(f"DataProfile.kind must be {cls.KIND!r} when supplied.")
        context = "DataProfile"
        known = {
            "schema_version", "kind", "source", "row_count", "columns", "inferred_roles",
            "missing_counts", "numeric_ranges", "trajectory_count", "trajectory_length", "warnings",
        }
        return cls(
            source=_required_mapping(payload, "source", context=context),
            row_count=_required_int(payload, "row_count", context=context, minimum=0),
            columns=_string_tuple(_required(payload, "columns", context=context), context="DataProfile.columns"),
            inferred_roles=_required_mapping(payload, "inferred_roles", context=context),
            missing_counts=_required_mapping(payload, "missing_counts", context=context),
            numeric_ranges=_required_mapping(payload, "numeric_ranges", context=context),
            trajectory_count=_required_int(payload, "trajectory_count", context=context, minimum=0),
            trajectory_length=_required_mapping(payload, "trajectory_length", context=context),
            warnings=_string_tuple(payload.get("warnings", []), context="DataProfile.warnings"),
            extensions=_extensions(payload, known),
        )

    def to_dict(self) -> dict[str, Any]:
        return _document(
            self.KIND,
            {
                "source": self.source,
                "row_count": self.row_count,
                "columns": list(self.columns),
                "inferred_roles": self.inferred_roles,
                "missing_counts": self.missing_counts,
                "numeric_ranges": self.numeric_ranges,
                "trajectory_count": self.trajectory_count,
                "trajectory_length": self.trajectory_length,
                "warnings": list(self.warnings),
            },
            self.extensions,
        )


@dataclass(frozen=True, slots=True)
class AnalysisPlan:
    """Declared choices used to turn a profile into a CE2 analysis."""

    entity_column: str | None
    time_column: str | None
    feature_columns: tuple[str, ...]
    resolutions: tuple[int, ...]
    encoder_seeds: tuple[int, ...]
    search_mode: str
    temporal_features: Mapping[str, Any]
    validation_fraction: float
    support: Mapping[str, Any]
    null_replicates: int
    notes: tuple[str, ...] = ()
    extensions: Mapping[str, Any] = field(default_factory=dict, repr=False)

    KIND: ClassVar[str] = "causal_emergence.analysis_plan"
    SCHEMA_VERSION: ClassVar[str] = API_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AnalysisPlan":
        payload = _mapping(value, context="AnalysisPlan")
        kind = payload.get("kind")
        if kind not in {None, cls.KIND}:
            raise ArtifactValidationError(f"AnalysisPlan.kind must be {cls.KIND!r} when supplied.")
        context = "AnalysisPlan"
        known = {
            "schema_version", "kind", "entity_column", "time_column", "feature_columns",
            "resolutions", "encoder_seeds", "search_mode", "temporal_features",
            "validation_fraction", "support", "null_replicates", "notes",
        }
        resolutions = _required(payload, "resolutions", context=context)
        seeds = _required(payload, "encoder_seeds", context=context)
        if not isinstance(resolutions, Sequence) or isinstance(resolutions, (str, bytes)) or any(
            not isinstance(item, int) or isinstance(item, bool) for item in resolutions
        ):
            raise ArtifactValidationError("AnalysisPlan.resolutions must be a sequence of integers.")
        if not isinstance(seeds, Sequence) or isinstance(seeds, (str, bytes)) or any(
            not isinstance(item, int) or isinstance(item, bool) for item in seeds
        ):
            raise ArtifactValidationError("AnalysisPlan.encoder_seeds must be a sequence of integers.")
        validation_fraction = _required(payload, "validation_fraction", context=context)
        if not isinstance(validation_fraction, (int, float)) or isinstance(validation_fraction, bool):
            raise ArtifactValidationError("AnalysisPlan.validation_fraction must be numeric.")
        return cls(
            entity_column=_required_string(payload, "entity_column", context=context, nullable=True),
            time_column=_required_string(payload, "time_column", context=context, nullable=True),
            feature_columns=_string_tuple(
                _required(payload, "feature_columns", context=context), context="AnalysisPlan.feature_columns"
            ),
            resolutions=tuple(resolutions),
            encoder_seeds=tuple(seeds),
            search_mode=_required_string(payload, "search_mode", context=context) or "auto",
            temporal_features=_required_mapping(payload, "temporal_features", context=context),
            validation_fraction=float(validation_fraction),
            support=_required_mapping(payload, "support", context=context),
            null_replicates=_required_int(payload, "null_replicates", context=context, minimum=0),
            notes=_string_tuple(payload.get("notes", []), context="AnalysisPlan.notes"),
            extensions=_extensions(payload, known),
        )

    @classmethod
    def recommend(
        cls,
        profile: DataProfile | Mapping[str, Any],
        *,
        features: Sequence[str] | None = None,
        resolutions: Sequence[int] | None = None,
        seeds: Sequence[int] = (0,),
    ) -> "AnalysisPlan":
        """Create the same documented recommendation as the legacy helper."""
        from causal_emergence_zoo.explore import recommend_analysis_plan

        profile_dict = profile.to_dict() if isinstance(profile, DataProfile) else _mapping(profile, context="profile")
        return cls.from_dict(
            recommend_analysis_plan(profile_dict, features=features, resolutions=resolutions, seeds=seeds)
        )

    def to_dict(self) -> dict[str, Any]:
        return _document(
            self.KIND,
            {
                "entity_column": self.entity_column,
                "time_column": self.time_column,
                "feature_columns": list(self.feature_columns),
                "resolutions": list(self.resolutions),
                "encoder_seeds": list(self.encoder_seeds),
                "search_mode": self.search_mode,
                "temporal_features": self.temporal_features,
                "validation_fraction": self.validation_fraction,
                "support": self.support,
                "null_replicates": self.null_replicates,
                "notes": list(self.notes),
            },
            self.extensions,
        )


@dataclass(frozen=True, slots=True)
class StateModel:
    """The finite state model on which the CE2 hierarchy is evaluated."""

    source: Mapping[str, Any]
    state_labels: tuple[Any, ...]
    state_count: int
    tpm: tuple[tuple[float, ...], ...]
    microscale_metrics: Mapping[str, Any]
    encoder: Mapping[str, Any] | None = None
    transition_estimate: Mapping[str, Any] | None = None
    extensions: Mapping[str, Any] = field(default_factory=dict, repr=False)

    KIND: ClassVar[str] = "causal_emergence.state_model"
    SCHEMA_VERSION: ClassVar[str] = API_SCHEMA_VERSION

    @classmethod
    def from_legacy_report(cls, value: Mapping[str, Any]) -> "StateModel":
        report = _mapping(value, context="legacy narrative report")
        model = _required_mapping(report, "input_model", context="legacy narrative report")
        tpm = _required(model, "tpm", context="legacy narrative report.input_model")
        if not isinstance(tpm, Sequence) or isinstance(tpm, (str, bytes)):
            raise ArtifactValidationError("legacy narrative report.input_model.tpm must be a matrix.")
        matrix: list[tuple[float, ...]] = []
        for index, row in enumerate(tpm):
            if not isinstance(row, Sequence) or isinstance(row, (str, bytes)):
                raise ArtifactValidationError(f"TPM row {index} must be a numeric sequence.")
            try:
                matrix.append(tuple(float(item) for item in row))
            except (TypeError, ValueError) as exc:
                raise ArtifactValidationError(f"TPM row {index} contains a non-numeric value.") from exc
        continuous = report.get("continuous_data")
        encoder = None
        transition_estimate = None
        if isinstance(continuous, Mapping):
            if isinstance(continuous.get("discretizer"), Mapping):
                encoder = _mapping(continuous["discretizer"], context="continuous_data.discretizer")
            if isinstance(continuous.get("transitions"), Mapping):
                transition_estimate = _mapping(continuous["transitions"], context="continuous_data.transitions")
        if encoder is None and isinstance(model.get("continuous_encoder"), Mapping):
            encoder = _mapping(model["continuous_encoder"], context="input_model.continuous_encoder")
        known = {
            "kind", "state_labels", "state_count", "tpm", "microscale_metrics", "source",
            "transition_counts", "outgoing_counts", "continuous_encoder", "streaming_transition_estimate",
            "nonempty_trajectory_count", "estimation_assumptions",
        }
        return cls(
            source=_required_mapping(model, "source", context="legacy narrative report.input_model"),
            state_labels=tuple(_json_clone(_required(model, "state_labels", context="legacy narrative report.input_model"))),
            state_count=_required_int(model, "state_count", context="legacy narrative report.input_model", minimum=1),
            tpm=tuple(matrix),
            microscale_metrics=_required_mapping(model, "microscale_metrics", context="legacy narrative report.input_model"),
            encoder=encoder,
            transition_estimate=transition_estimate,
            extensions=_extensions(model, known),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "StateModel":
        payload = _mapping(value, context="StateModel")
        if payload.get("kind") != cls.KIND:
            raise ArtifactValidationError(f"StateModel.kind must be {cls.KIND!r}.")
        tpm = _required(payload, "tpm", context="StateModel")
        if not isinstance(tpm, Sequence) or isinstance(tpm, (str, bytes)):
            raise ArtifactValidationError("StateModel.tpm must be a matrix.")
        matrix = tuple(tuple(float(item) for item in row) for row in tpm)
        known = {
            "schema_version", "kind", "source", "state_labels", "state_count", "tpm",
            "microscale_metrics", "encoder", "transition_estimate",
        }
        encoder = payload.get("encoder")
        transitions = payload.get("transition_estimate")
        return cls(
            source=_required_mapping(payload, "source", context="StateModel"),
            state_labels=tuple(_json_clone(_required(payload, "state_labels", context="StateModel"))),
            state_count=_required_int(payload, "state_count", context="StateModel", minimum=1),
            tpm=matrix,
            microscale_metrics=_required_mapping(payload, "microscale_metrics", context="StateModel"),
            encoder=_mapping(encoder, context="StateModel.encoder") if isinstance(encoder, Mapping) else None,
            transition_estimate=_mapping(transitions, context="StateModel.transition_estimate") if isinstance(transitions, Mapping) else None,
            extensions=_extensions(payload, known),
        )

    def to_dict(self) -> dict[str, Any]:
        return _document(
            self.KIND,
            {
                "source": self.source,
                "state_labels": list(self.state_labels),
                "state_count": self.state_count,
                "tpm": [list(row) for row in self.tpm],
                "microscale_metrics": self.microscale_metrics,
                "encoder": self.encoder,
                "transition_estimate": self.transition_estimate,
            },
            self.extensions,
        )


@dataclass(frozen=True, slots=True)
class CausalHierarchy:
    """A stable view of CE2 scales, endpoint, and supporting evidence."""

    method: str
    source: Mapping[str, Any]
    microstates: tuple[Mapping[str, Any], ...]
    scales: tuple[Mapping[str, Any], ...]
    endpoint: Mapping[str, Any]
    emergent_complexity: Mapping[str, Any]
    uncertainty: Mapping[str, Any]
    evidence: Mapping[str, Any]
    extensions: Mapping[str, Any] = field(default_factory=dict, repr=False)

    KIND: ClassVar[str] = "causal_emergence.causal_hierarchy"
    SCHEMA_VERSION: ClassVar[str] = API_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CausalHierarchy":
        payload = _mapping(value, context="CausalHierarchy")
        kind = payload.get("kind")
        if kind not in {None, cls.KIND}:
            raise ArtifactValidationError(f"CausalHierarchy.kind must be {cls.KIND!r} when supplied.")
        context = "CausalHierarchy"
        known = {
            "schema_version", "kind", "method", "source", "microstates", "scales", "endpoint",
            "emergent_complexity", "uncertainty", "evidence",
        }
        return cls(
            method=_required_string(payload, "method", context=context) or "",
            source=_required_mapping(payload, "source", context=context),
            microstates=_mapping_tuple(_required(payload, "microstates", context=context), context="CausalHierarchy.microstates"),
            scales=_mapping_tuple(_required(payload, "scales", context=context), context="CausalHierarchy.scales"),
            endpoint=_required_mapping(payload, "endpoint", context=context),
            emergent_complexity=_required_mapping(payload, "emergent_complexity", context=context),
            uncertainty=_required_mapping(payload, "uncertainty", context=context),
            evidence=_required_mapping(payload, "evidence", context=context),
            extensions=_extensions(payload, known),
        )

    def to_dict(self) -> dict[str, Any]:
        return _document(
            self.KIND,
            {
                "method": self.method,
                "source": self.source,
                "microstates": list(self.microstates),
                "scales": list(self.scales),
                "endpoint": self.endpoint,
                "emergent_complexity": self.emergent_complexity,
                "uncertainty": self.uncertainty,
                "evidence": self.evidence,
            },
            self.extensions,
        )


@dataclass(frozen=True, slots=True)
class EvidenceLedger:
    """Claim-level supporting evidence, uncertainty, and counterevidence."""

    source_kind: str | None
    claims: tuple[Mapping[str, Any], ...]
    summary: Mapping[str, Any]
    extensions: Mapping[str, Any] = field(default_factory=dict, repr=False)

    KIND: ClassVar[str] = "causal_emergence.evidence_ledger"
    SCHEMA_VERSION: ClassVar[str] = API_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EvidenceLedger":
        payload = _mapping(value, context="EvidenceLedger")
        kind = payload.get("kind")
        if kind not in {None, cls.KIND}:
            raise ArtifactValidationError(f"EvidenceLedger.kind must be {cls.KIND!r} when supplied.")
        known = {"schema_version", "kind", "claim_count", "source_kind", "claims", "summary"}
        source_kind = payload.get("source_kind")
        if source_kind is not None and not isinstance(source_kind, str):
            raise ArtifactValidationError("EvidenceLedger.source_kind must be a string or null.")
        claims = _mapping_tuple(_required(payload, "claims", context="EvidenceLedger"), context="EvidenceLedger.claims")
        claimed_count = payload.get("claim_count", len(claims))
        if not isinstance(claimed_count, int) or claimed_count != len(claims):
            raise ArtifactValidationError("EvidenceLedger.claim_count must match the number of claims.")
        return cls(
            source_kind=source_kind,
            claims=claims,
            summary=_required_mapping(payload, "summary", context="EvidenceLedger"),
            extensions=_extensions(payload, known),
        )

    def to_dict(self) -> dict[str, Any]:
        return _document(
            self.KIND,
            {
                "claim_count": len(self.claims),
                "source_kind": self.source_kind,
                "claims": list(self.claims),
                "summary": self.summary,
            },
            self.extensions,
        )


@dataclass(frozen=True, slots=True)
class NarrativeReport:
    """Stable top-level object for one CE2 narrative analysis."""

    analysis_type: str
    status: str
    summary_data: Mapping[str, Any]
    narrative_text: str
    state_model: StateModel
    hierarchy: CausalHierarchy
    evidence_ledger: EvidenceLedger
    assumptions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    extensions: Mapping[str, Any] = field(default_factory=dict, repr=False)
    _legacy_payload: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    KIND: ClassVar[str] = "causal_emergence.narrative_report"
    SCHEMA_VERSION: ClassVar[str] = API_SCHEMA_VERSION

    @classmethod
    def from_legacy_dict(cls, value: Mapping[str, Any]) -> "NarrativeReport":
        payload = _mapping(value, context="legacy narrative report")
        if "causal_hierarchy" not in payload or "evidence_ledger" not in payload:
            raise ArtifactValidationError(
                "A legacy narrative report must include causal_hierarchy and evidence_ledger."
            )
        known = {
            "schema_version", "kind", "analysis_type", "status", "summary", "narrative_text",
            "input_model", "ce2", "causal_hierarchy", "selected_macro_model", "narrative_graph",
            "evidence_ledger", "assumptions", "limitations", "robustness", "continuous_data", "search",
            "state_support", "empirical_validation",
        }
        return cls(
            analysis_type=_required_string(payload, "analysis_type", context="legacy narrative report") or "",
            status=_required_string(payload, "status", context="legacy narrative report") or "",
            summary_data=_required_mapping(payload, "summary", context="legacy narrative report"),
            narrative_text=_required_string(payload, "narrative_text", context="legacy narrative report") or "",
            state_model=StateModel.from_legacy_report(payload),
            hierarchy=CausalHierarchy.from_dict(
                _required_mapping(payload, "causal_hierarchy", context="legacy narrative report")
            ),
            evidence_ledger=EvidenceLedger.from_dict(
                _required_mapping(payload, "evidence_ledger", context="legacy narrative report")
            ),
            assumptions=_string_tuple(payload.get("assumptions", []), context="legacy narrative report.assumptions"),
            limitations=_string_tuple(payload.get("limitations", []), context="legacy narrative report.limitations"),
            extensions=_extensions(payload, known),
            _legacy_payload=payload,
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "NarrativeReport":
        payload = _mapping(value, context="NarrativeReport")
        if payload.get("kind") == "causal_emergence.narrative_graph":
            return cls.from_legacy_dict(payload)
        if payload.get("kind") != cls.KIND:
            raise ArtifactValidationError(f"NarrativeReport.kind must be {cls.KIND!r}.")
        known = {
            "schema_version", "kind", "analysis_type", "status", "summary", "narrative_text",
            "state_model", "causal_hierarchy", "evidence_ledger", "assumptions", "limitations",
        }
        return cls(
            analysis_type=_required_string(payload, "analysis_type", context="NarrativeReport") or "",
            status=_required_string(payload, "status", context="NarrativeReport") or "",
            summary_data=_required_mapping(payload, "summary", context="NarrativeReport"),
            narrative_text=_required_string(payload, "narrative_text", context="NarrativeReport") or "",
            state_model=StateModel.from_dict(_required_mapping(payload, "state_model", context="NarrativeReport")),
            hierarchy=CausalHierarchy.from_dict(_required_mapping(payload, "causal_hierarchy", context="NarrativeReport")),
            evidence_ledger=EvidenceLedger.from_dict(_required_mapping(payload, "evidence_ledger", context="NarrativeReport")),
            assumptions=_string_tuple(payload.get("assumptions", []), context="NarrativeReport.assumptions"),
            limitations=_string_tuple(payload.get("limitations", []), context="NarrativeReport.limitations"),
            extensions=_extensions(payload, known),
            _legacy_payload={},
        )

    def summary(self) -> str:
        """Return the short, evidence-linked headline for user interfaces."""
        headline = self.summary_data.get("headline")
        return headline if isinstance(headline, str) else self.narrative_text

    def show_hierarchy(self) -> CausalHierarchy:
        """Return the structured hierarchy without rendering an unsupported plot."""
        return self.hierarchy

    def to_dict(self) -> dict[str, Any]:
        return _document(
            self.KIND,
            {
                "analysis_type": self.analysis_type,
                "status": self.status,
                "summary": self.summary_data,
                "narrative_text": self.narrative_text,
                "state_model": self.state_model.to_dict(),
                "causal_hierarchy": self.hierarchy.to_dict(),
                "evidence_ledger": self.evidence_ledger.to_dict(),
                "assumptions": list(self.assumptions),
                "limitations": list(self.limitations),
            },
            self.extensions,
        )

    def to_legacy_dict(self) -> dict[str, Any]:
        """Return a compatible mapping for legacy renderers and integrations.

        Results created from a legacy analysis preserve the exact original
        mapping. A report loaded from a canonical envelope reconstructs the
        compatible shape from its stable components and additive extensions.
        """
        if self._legacy_payload:
            return _mapping(self._legacy_payload, context="legacy narrative payload")
        model = {
            "kind": self.state_model.extensions.get("kind", "provided_transition_model"),
            "state_labels": list(self.state_model.state_labels),
            "state_count": self.state_model.state_count,
            "tpm": [list(row) for row in self.state_model.tpm],
            "microscale_metrics": _json_clone(self.state_model.microscale_metrics),
            "source": _json_clone(self.state_model.source),
            **_json_clone(self.state_model.extensions),
        }
        if self.state_model.encoder is not None:
            model["continuous_encoder"] = _json_clone(self.state_model.encoder)
        result = _json_clone(self.extensions)
        result.update(
            {
                "schema_version": "0.2.0",
                "kind": "causal_emergence.narrative_graph",
                "analysis_type": self.analysis_type,
                "status": self.status,
                "summary": _json_clone(self.summary_data),
                "narrative_text": self.narrative_text,
                "input_model": model,
                "causal_hierarchy": self.hierarchy.to_dict(),
                "evidence_ledger": self.evidence_ledger.to_dict(),
                "assumptions": list(self.assumptions),
                "limitations": list(self.limitations),
            }
        )
        return result

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, allow_nan=False)

    def write_json(self, path: str | Path, *, indent: int = 2) -> None:
        Path(path).write_text(self.to_json(indent=indent) + "\n", encoding="utf-8")


@dataclass(frozen=True, slots=True)
class ExplorationResult:
    """Stable top-level object for a profile, plan, and multiresolution run."""

    profile: DataProfile
    plan: AnalysisPlan
    reports: tuple[NarrativeReport, ...]
    analysis_data: Mapping[str, Any]
    state_descriptions: tuple[Mapping[str, Any], ...] = ()
    artifacts: Mapping[str, Any] = field(default_factory=dict)
    extensions: Mapping[str, Any] = field(default_factory=dict, repr=False)
    _legacy_payload: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    KIND: ClassVar[str] = "causal_emergence.exploration_result"
    SCHEMA_VERSION: ClassVar[str] = API_SCHEMA_VERSION

    @classmethod
    def from_legacy_dict(cls, value: Mapping[str, Any]) -> "ExplorationResult":
        payload = _mapping(value, context="legacy exploration result")
        analysis = _required_mapping(payload, "analysis", context="legacy exploration result")
        runs = analysis.get("resolution_runs")
        if not isinstance(runs, Sequence) or isinstance(runs, (str, bytes)) or not runs:
            raise ArtifactValidationError("legacy exploration result.analysis.resolution_runs must be non-empty.")
        reports = []
        for index, run in enumerate(runs):
            if not isinstance(run, Mapping) or not isinstance(run.get("result"), Mapping):
                raise ArtifactValidationError(f"resolution_runs[{index}] must contain a narrative result mapping.")
            reports.append(NarrativeReport.from_legacy_dict(run["result"]))
        known = {"schema_version", "kind", "profile", "plan", "analysis", "state_descriptions", "artifacts"}
        descriptions = payload.get("state_descriptions", [])
        return cls(
            profile=DataProfile.from_dict(_required_mapping(payload, "profile", context="legacy exploration result")),
            plan=AnalysisPlan.from_dict(_required_mapping(payload, "plan", context="legacy exploration result")),
            reports=tuple(reports),
            analysis_data=analysis,
            state_descriptions=_mapping_tuple(descriptions, context="legacy exploration result.state_descriptions"),
            artifacts=_mapping(payload.get("artifacts", {}), context="legacy exploration result.artifacts"),
            extensions=_extensions(payload, known),
            _legacy_payload=payload,
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExplorationResult":
        payload = _mapping(value, context="ExplorationResult")
        if payload.get("kind") == "causal_emergence.exploration":
            return cls.from_legacy_dict(payload)
        if payload.get("kind") != cls.KIND:
            raise ArtifactValidationError(f"ExplorationResult.kind must be {cls.KIND!r}.")
        reports_raw = _required(payload, "reports", context="ExplorationResult")
        if not isinstance(reports_raw, Sequence) or isinstance(reports_raw, (str, bytes)):
            raise ArtifactValidationError("ExplorationResult.reports must be a sequence.")
        known = {
            "schema_version", "kind", "profile", "plan", "reports", "analysis",
            "state_descriptions", "artifacts",
        }
        return cls(
            profile=DataProfile.from_dict(_required_mapping(payload, "profile", context="ExplorationResult")),
            plan=AnalysisPlan.from_dict(_required_mapping(payload, "plan", context="ExplorationResult")),
            reports=tuple(NarrativeReport.from_dict(_mapping(item, context="ExplorationResult.reports[]")) for item in reports_raw),
            analysis_data=_required_mapping(payload, "analysis", context="ExplorationResult"),
            state_descriptions=_mapping_tuple(payload.get("state_descriptions", []), context="ExplorationResult.state_descriptions"),
            artifacts=_mapping(payload.get("artifacts", {}), context="ExplorationResult.artifacts"),
            extensions=_extensions(payload, known),
            _legacy_payload={},
        )

    @property
    def best_report(self) -> NarrativeReport:
        """Return the report with the highest recorded endpoint CP gain."""
        runs = self.analysis_data.get("resolution_runs", [])
        if len(runs) != len(self.reports):
            return self.reports[0]
        best_index = max(
            range(len(self.reports)),
            key=lambda index: (
                runs[index].get("endpoint_cp_gain", float("-inf")),
                -runs[index].get("resolution", 0),
                -runs[index].get("seed", 0),
            ),
        )
        return self.reports[best_index]

    def summary(self) -> str:
        return self.best_report.summary()

    def show_hierarchy(self) -> CausalHierarchy:
        return self.best_report.show_hierarchy()

    def to_dict(self) -> dict[str, Any]:
        return _document(
            self.KIND,
            {
                "profile": self.profile.to_dict(),
                "plan": self.plan.to_dict(),
                "reports": [report.to_dict() for report in self.reports],
                "analysis": self.analysis_data,
                "state_descriptions": list(self.state_descriptions),
                "artifacts": self.artifacts,
            },
            self.extensions,
        )

    def to_legacy_dict(self) -> dict[str, Any]:
        if self._legacy_payload:
            return _mapping(self._legacy_payload, context="legacy exploration payload")
        result = _json_clone(self.extensions)
        result.update(
            {
                "schema_version": "0.2.0",
                "kind": "causal_emergence.exploration",
                "profile": self.profile.to_dict(),
                "plan": self.plan.to_dict(),
                "analysis": _json_clone(self.analysis_data),
                "state_descriptions": [
                    _json_clone(description) for description in self.state_descriptions
                ],
                "artifacts": _json_clone(self.artifacts),
            }
        )
        return result

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, allow_nan=False)

    def write_json(self, path: str | Path, *, indent: int = 2) -> None:
        Path(path).write_text(self.to_json(indent=indent) + "\n", encoding="utf-8")

    def export_report(self, path: str | Path) -> None:
        """Render the existing self-contained report for a legacy-backed result."""
        from causal_emergence_zoo.report import render_exploration_report

        destination = Path(path)
        destination.write_text(render_exploration_report(self.to_legacy_dict()), encoding="utf-8")


def data_profile_from_dict(value: Mapping[str, Any]) -> DataProfile:
    return DataProfile.from_dict(value)


def analysis_plan_from_dict(value: Mapping[str, Any]) -> AnalysisPlan:
    return AnalysisPlan.from_dict(value)


def state_model_from_dict(value: Mapping[str, Any]) -> StateModel:
    return StateModel.from_dict(value)


def causal_hierarchy_from_dict(value: Mapping[str, Any]) -> CausalHierarchy:
    return CausalHierarchy.from_dict(value)


def evidence_ledger_from_dict(value: Mapping[str, Any]) -> EvidenceLedger:
    return EvidenceLedger.from_dict(value)


def narrative_report_from_dict(value: Mapping[str, Any]) -> NarrativeReport:
    return NarrativeReport.from_dict(value)


def exploration_result_from_dict(value: Mapping[str, Any]) -> ExplorationResult:
    return ExplorationResult.from_dict(value)


def public_api_schema() -> dict[str, Any]:
    """Load the packaged JSON Schema for canonical v0.2 artifact envelopes."""
    return json.loads(
        files("causal_emergence_zoo")
        .joinpath("schemas", "public-api.schema.json")
        .read_text(encoding="utf-8")
    )


def validate_public_artifact(value: Mapping[str, Any]) -> None:
    """Validate a canonical v0.2 envelope or raise ``ArtifactValidationError``."""
    try:
        import jsonschema

        jsonschema.Draft202012Validator(public_api_schema()).validate(_mapping(value, context="artifact"))
    except jsonschema.ValidationError as exc:
        raise ArtifactValidationError(f"Public artifact schema validation failed: {exc.message}") from exc
