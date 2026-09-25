"""Offline evidence audit primitives for the frozen V7 retrieval benchmark.

The scraper does not retrieve, rank, reason, or choose an answer here.  It
checks benchmark requirements against validated producer records so a missing
answer can be assigned to the data lane or handed downstream without changing
the benchmark expectation.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Mapping, Sequence

from askanu_scraper.common.models import CommonRecord, Domain
from askanu_scraper.common.normalizer import normalize_text
from askanu_scraper.common.v7_contract import (
    ProducerContract,
    producer_contract_for,
    source_authority_for,
)


class EvidenceClassification(str, Enum):
    PRESENT_STRUCTURED = "PRESENT_STRUCTURED"
    PRESENT_CONTENT_ONLY = "PRESENT_CONTENT_ONLY"
    MISSING_SOURCE = "MISSING_SOURCE"
    MISSING_INGESTION = "MISSING_INGESTION"
    NORMALISATION_DEFECT = "NORMALISATION_DEFECT"
    IDENTITY_DEFECT = "IDENTITY_DEFECT"
    STALE = "STALE"
    INCOMPLETE_POPULATION = "INCOMPLETE_POPULATION"
    AMBIGUOUS_SOURCE = "AMBIGUOUS_SOURCE"
    NOT_DATA_FAILURE = "NOT_DATA_FAILURE"


class EvidenceLocation(str, Enum):
    STRUCTURED = "structured"
    CONTENT = "content"


class SourceEvidenceStatus(str, Enum):
    PRESENT = "present"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"


class PopulationStatus(str, Enum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    NOT_APPLICABLE = "not_applicable"


class FreshnessStatus(str, Enum):
    CURRENT = "current"
    STALE = "stale"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class EvidenceState(str, Enum):
    ESTABLISHED = "established"
    NOT_ESTABLISHED = "not_established"


class BenchmarkEvidenceError(ValueError):
    """Raised when an audit requests evidence outside the reviewed contract."""


@dataclass(frozen=True)
class StructuredEvidence:
    source_path: str
    state: EvidenceState
    value: object | None


@dataclass(frozen=True)
class ComparedValue:
    record_id: str
    source_id: str
    authority_rank: int
    approval_status: str
    state: EvidenceState
    value: object | None


@dataclass(frozen=True)
class ComparisonRow:
    source_path: str
    values: tuple[ComparedValue, ...]


@dataclass(frozen=True)
class EvidenceRequirement:
    query_id: str
    domain: Domain
    expected_record_id: str
    fact: str
    expected_location: EvidenceLocation
    source_evidence: SourceEvidenceStatus
    expected_source_id: str | None = None
    expected_entity_id: str | None = None
    source_path: str | None = None
    expected_value: object | None = None
    content_text: str | None = None
    population_status: PopulationStatus = PopulationStatus.NOT_APPLICABLE
    requires_complete_population: bool = False
    freshness_status: FreshnessStatus = FreshnessStatus.NOT_APPLICABLE
    requires_current: bool = False
    source_reference: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "query_id", "expected_record_id", "fact", "expected_source_id",
            "expected_entity_id", "source_reference",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise BenchmarkEvidenceError(
                    f"{field_name} must be a non-blank string"
                )
        if not isinstance(self.domain, Domain):
            raise BenchmarkEvidenceError("domain must be a reviewed Domain")
        if not isinstance(self.expected_location, EvidenceLocation):
            raise BenchmarkEvidenceError("expected_location must be reviewed")
        if not isinstance(self.source_evidence, SourceEvidenceStatus):
            raise BenchmarkEvidenceError("source_evidence must be reviewed")
        if not isinstance(self.population_status, PopulationStatus):
            raise BenchmarkEvidenceError("population_status must be reviewed")
        if not isinstance(self.freshness_status, FreshnessStatus):
            raise BenchmarkEvidenceError("freshness_status must be reviewed")
        if not isinstance(self.requires_complete_population, bool):
            raise BenchmarkEvidenceError("requires_complete_population must be boolean")
        if not isinstance(self.requires_current, bool):
            raise BenchmarkEvidenceError("requires_current must be boolean")
        if self.source_evidence == SourceEvidenceStatus.PRESENT:
            if self.expected_location == EvidenceLocation.STRUCTURED:
                if not isinstance(self.source_path, str) or not self.source_path:
                    raise BenchmarkEvidenceError(
                        "source-present structured evidence needs source_path"
                    )
                if not _is_established(self.expected_value):
                    raise BenchmarkEvidenceError(
                        "source-present structured evidence needs expected_value"
                    )
            elif not isinstance(self.content_text, str) or not self.content_text.strip():
                raise BenchmarkEvidenceError(
                    "source-present content evidence needs content_text"
                )


@dataclass(frozen=True)
class EvidenceAssessment:
    query_id: str
    domain: Domain
    expected_record_id: str
    fact: str
    classification: EvidenceClassification
    failure_classification: EvidenceClassification
    provenance_complete: bool
    entity_id: str | None
    source_id: str | None
    canonical_url: str | None
    authority_rank: int | None
    approval_status: str | None
    source_reference: str | None
    population_status: PopulationStatus
    freshness_status: FreshnessStatus
    source_path: str | None
    actual_value: object | None
    reason: str


@dataclass(frozen=True)
class BenchmarkAuditReport:
    benchmark_version: str
    assessments: tuple[EvidenceAssessment, ...]
    metrics: dict[str, object]


def _path_value(record: CommonRecord, path: str) -> object | None:
    serialized = record.model_dump(mode="json")
    if path.startswith("metadata_json."):
        return record.metadata_json.get(path.removeprefix("metadata_json."))
    return serialized.get(path)


def _is_established(value: object | None) -> bool:
    """Conservatively distinguish source evidence from empty placeholders."""

    if value is None:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return any(_is_established(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_is_established(item) for item in value)
    return True


def project_structured_evidence(
    record: CommonRecord,
) -> tuple[StructuredEvidence, ...]:
    """Expose reviewed structured facts, retaining explicit missingness."""

    contract = producer_contract_for(record)
    return tuple(
        StructuredEvidence(
            source_path=path,
            state=(
                EvidenceState.ESTABLISHED
                if _is_established(value := _path_value(record, path))
                else EvidenceState.NOT_ESTABLISHED
            ),
            value=value,
        )
        for path in contract.structured_fact_paths
    )


def _compared_value(record: CommonRecord, path: str) -> ComparedValue:
    value = _path_value(record, path)
    authority = source_authority_for(record)
    return ComparedValue(
        record_id=record.record_id,
        source_id=record.source_id,
        authority_rank=authority.authority_rank,
        approval_status=authority.approval_status.value,
        state=(
            EvidenceState.ESTABLISHED
            if _is_established(value)
            else EvidenceState.NOT_ESTABLISHED
        ),
        value=value,
    )


def compare_structured_evidence(
    records: Sequence[CommonRecord],
) -> tuple[ComparisonRow, ...]:
    """Build an unordered same-shape matrix without filling missing cells."""

    if not records:
        return ()
    contracts = [producer_contract_for(record) for record in records]
    shape = (contracts[0].domain, contracts[0].entity_type)
    if any((contract.domain, contract.entity_type) != shape for contract in contracts):
        raise BenchmarkEvidenceError(
            "structured comparison requires records with the same domain/entity type"
        )

    return tuple(
        ComparisonRow(
            source_path=path,
            values=tuple(
                _compared_value(record, path)
                for record in records
            ),
        )
        for path in contracts[0].structured_fact_paths
    )


def _reviewed_structured_paths(contract: ProducerContract) -> frozenset[str]:
    return frozenset(
        (
            "title",
            "entity_id",
            "source_id",
            "canonical_url",
            *contract.stable_identity_paths,
            *contract.identifier_paths,
            *contract.structured_fact_paths,
        )
    )


def _normalized_content_contains(content: str, expected: str) -> bool:
    normalized_content = (normalize_text(content) or "").casefold()
    normalized_expected = (normalize_text(expected) or "").casefold()
    return bool(normalized_expected) and normalized_expected in normalized_content


def _provenance_complete(
    record: CommonRecord | None,
    requirement: EvidenceRequirement,
) -> bool:
    if record is None:
        return False
    try:
        authority = source_authority_for(record)
    except (KeyError, ValueError):
        return False
    return all(
        (
            record.record_id == requirement.expected_record_id,
            bool(record.entity_id),
            bool(record.source_id),
            bool(record.canonical_url),
            authority.source_id == record.source_id,
            requirement.expected_entity_id in {None, record.entity_id},
            requirement.expected_source_id in {None, record.source_id},
        )
    )


def _assessment(
    requirement: EvidenceRequirement,
    classification: EvidenceClassification,
    *,
    record: CommonRecord | None = None,
    actual_value: object | None = None,
    reason: str,
) -> EvidenceAssessment:
    present = classification in {
        EvidenceClassification.PRESENT_STRUCTURED,
        EvidenceClassification.PRESENT_CONTENT_ONLY,
    }
    try:
        authority = source_authority_for(record) if record is not None else None
    except (KeyError, ValueError):
        authority = None
    return EvidenceAssessment(
        query_id=requirement.query_id,
        domain=requirement.domain,
        expected_record_id=requirement.expected_record_id,
        fact=requirement.fact,
        classification=classification,
        failure_classification=(
            EvidenceClassification.NOT_DATA_FAILURE if present else classification
        ),
        provenance_complete=_provenance_complete(record, requirement),
        entity_id=record.entity_id if record is not None else None,
        source_id=record.source_id if record is not None else None,
        canonical_url=record.canonical_url if record is not None else None,
        authority_rank=authority.authority_rank if authority is not None else None,
        approval_status=(
            authority.approval_status.value if authority is not None else None
        ),
        source_reference=requirement.source_reference,
        population_status=requirement.population_status,
        freshness_status=requirement.freshness_status,
        source_path=requirement.source_path,
        actual_value=actual_value,
        reason=reason,
    )


def assess_requirement(
    records: Sequence[CommonRecord],
    requirement: EvidenceRequirement,
) -> EvidenceAssessment:
    """Classify one frozen requirement without revising its expected answer."""

    matching = [
        record for record in records if record.record_id == requirement.expected_record_id
    ]
    record = matching[0] if len(matching) == 1 else None
    if requirement.source_evidence == SourceEvidenceStatus.MISSING:
        return _assessment(
            requirement,
            EvidenceClassification.MISSING_SOURCE,
            record=record,
            reason="the audited approved source does not publish the required fact",
        )
    if requirement.source_evidence == SourceEvidenceStatus.AMBIGUOUS:
        return _assessment(
            requirement,
            EvidenceClassification.AMBIGUOUS_SOURCE,
            record=record,
            reason="the audited approved source does not support a stronger interpretation",
        )
    if (
        requirement.requires_complete_population
        and requirement.population_status != PopulationStatus.COMPLETE
    ):
        return _assessment(
            requirement,
            EvidenceClassification.INCOMPLETE_POPULATION,
            record=record,
            reason="the supported population was not established as completely evaluated",
        )

    if len(matching) > 1:
        return _assessment(
            requirement,
            EvidenceClassification.IDENTITY_DEFECT,
            reason="the expected stable record ID occurs more than once",
        )
    if record is None:
        identity_candidates = [
            item
            for item in records
            if requirement.expected_entity_id is not None
            and item.entity_id == requirement.expected_entity_id
            and requirement.expected_source_id in {None, item.source_id}
        ]
        if identity_candidates:
            return _assessment(
                requirement,
                EvidenceClassification.IDENTITY_DEFECT,
                reason="the source/entity identity exists under an unexpected record ID",
            )
        return _assessment(
            requirement,
            EvidenceClassification.MISSING_INGESTION,
            reason="the source publishes the fact but the expected record is absent",
        )

    if record.domain != requirement.domain:
        return _assessment(
            requirement,
            EvidenceClassification.IDENTITY_DEFECT,
            record=record,
            reason="the expected record ID resolves to the wrong domain",
        )
    if requirement.expected_source_id not in {None, record.source_id}:
        return _assessment(
            requirement,
            EvidenceClassification.IDENTITY_DEFECT,
            record=record,
            reason="the expected record resolves to the wrong source",
        )
    if requirement.expected_entity_id not in {None, record.entity_id}:
        return _assessment(
            requirement,
            EvidenceClassification.IDENTITY_DEFECT,
            record=record,
            reason="the expected record resolves to the wrong entity identity",
        )
    if (
        requirement.requires_current
        and requirement.freshness_status != FreshnessStatus.CURRENT
    ):
        return _assessment(
            requirement,
            EvidenceClassification.STALE,
            record=record,
            reason="freshness evidence does not support treating the record as current",
        )

    if requirement.expected_location == EvidenceLocation.CONTENT:
        if requirement.content_text is None:
            raise BenchmarkEvidenceError("content requirements need content_text")
        if _normalized_content_contains(record.content, requirement.content_text):
            return _assessment(
                requirement,
                EvidenceClassification.PRESENT_CONTENT_ONLY,
                record=record,
                actual_value=requirement.content_text,
                reason="the exact audited evidence is retained in canonical content",
            )
        return _assessment(
            requirement,
            EvidenceClassification.MISSING_INGESTION,
            record=record,
            reason="the source publishes the fact but canonical content does not retain it",
        )

    if requirement.source_path is None:
        raise BenchmarkEvidenceError("structured requirements need source_path")
    contract = producer_contract_for(record)
    if requirement.source_path not in _reviewed_structured_paths(contract):
        raise BenchmarkEvidenceError(
            f"{requirement.source_path} is not a reviewed structured path for "
            f"{record.domain.value}/{contract.entity_type}"
        )
    actual = _path_value(record, requirement.source_path)
    if actual == requirement.expected_value and _is_established(actual):
        return _assessment(
            requirement,
            EvidenceClassification.PRESENT_STRUCTURED,
            record=record,
            actual_value=actual,
            reason="the reviewed structured field matches the audited source value",
        )
    if requirement.content_text and _normalized_content_contains(
        record.content, requirement.content_text
    ):
        return _assessment(
            requirement,
            EvidenceClassification.PRESENT_CONTENT_ONLY,
            record=record,
            actual_value=requirement.content_text,
            reason="the fact is retained in content but not established in the required field",
        )
    if _is_established(actual):
        return _assessment(
            requirement,
            EvidenceClassification.NORMALISATION_DEFECT,
            record=record,
            actual_value=actual,
            reason="the captured structured value differs from the audited source value",
        )
    return _assessment(
        requirement,
        EvidenceClassification.MISSING_INGESTION,
        record=record,
        actual_value=actual,
        reason="the source publishes the fact but the reviewed field is not established",
    )


def _percentage(numerator: int, denominator: int) -> float | None:
    return round(100 * numerator / denominator, 2) if denominator else None


def _metrics(assessments: Sequence[EvidenceAssessment]) -> dict[str, object]:
    classification_names = [item.value for item in EvidenceClassification]

    def summarize(items: Sequence[EvidenceAssessment]) -> dict[str, object]:
        counts = Counter(item.classification.value for item in items)
        failures = Counter(item.failure_classification.value for item in items)
        query_groups: dict[str, list[EvidenceAssessment]] = defaultdict(list)
        for item in items:
            query_groups[item.query_id].append(item)
        present = {
            EvidenceClassification.PRESENT_STRUCTURED,
            EvidenceClassification.PRESENT_CONTENT_ONLY,
        }
        supported_queries = sum(
            all(item.classification in present for item in group)
            for group in query_groups.values()
        )
        structured_queries = sum(
            all(item.classification == EvidenceClassification.PRESENT_STRUCTURED for item in group)
            for group in query_groups.values()
        )
        content_only_queries = sum(
            all(item.classification in present for item in group)
            and any(
                item.classification == EvidenceClassification.PRESENT_CONTENT_ONLY
                for item in group
            )
            for group in query_groups.values()
        )
        provenance_total = len(items)
        provenance_complete = sum(item.provenance_complete for item in items)
        return {
            "requirement_count": len(items),
            "query_count": len(query_groups),
            "classification_counts": {
                name: counts.get(name, 0) for name in classification_names
            },
            "failure_classification_counts": {
                name: failures.get(name, 0) for name in classification_names
            },
            "questions_with_required_evidence": supported_queries,
            "questions_with_required_evidence_percent": _percentage(
                supported_queries, len(query_groups)
            ),
            "questions_fully_structured": structured_queries,
            "questions_fully_structured_percent": _percentage(
                structured_queries, len(query_groups)
            ),
            "questions_requiring_content": content_only_queries,
            "questions_requiring_content_percent": _percentage(
                content_only_queries, len(query_groups)
            ),
            "provenance_complete": provenance_complete,
            "provenance_total": provenance_total,
            "provenance_complete_percent": _percentage(
                provenance_complete, provenance_total
            ),
        }

    by_domain: dict[str, object] = {}
    for domain in Domain:
        domain_items = [item for item in assessments if item.domain == domain]
        if domain_items:
            by_domain[domain.value] = summarize(domain_items)
    return {"overall": summarize(assessments), "by_domain": by_domain}


def audit_benchmark(
    records: Sequence[CommonRecord],
    requirements: Sequence[EvidenceRequirement],
    *,
    benchmark_version: str,
) -> BenchmarkAuditReport:
    """Audit a fixed requirement set and return per-domain measurable evidence."""

    if not benchmark_version.strip():
        raise BenchmarkEvidenceError("benchmark_version must not be blank")
    assessments = tuple(
        assess_requirement(records, requirement) for requirement in requirements
    )
    return BenchmarkAuditReport(
        benchmark_version=benchmark_version,
        assessments=assessments,
        metrics=_metrics(assessments),
    )


def load_benchmark_requirements(
    path: str | Path,
) -> tuple[str, tuple[EvidenceRequirement, ...]]:
    """Load a checked-in offline benchmark manifest with strict known fields."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("network_calls_allowed") is not False:
        raise BenchmarkEvidenceError("benchmark manifest must explicitly disable network")
    benchmark_version = payload.get("benchmark_version")
    if not isinstance(benchmark_version, str) or not benchmark_version.strip():
        raise BenchmarkEvidenceError("benchmark manifest needs benchmark_version")
    raw_requirements = payload.get("requirements")
    if not isinstance(raw_requirements, list):
        raise BenchmarkEvidenceError("benchmark manifest needs a requirements array")

    allowed = {
        "query_id", "domain", "expected_record_id", "fact", "expected_location",
        "source_evidence", "expected_source_id", "expected_entity_id", "source_path",
        "expected_value", "content_text", "population_status",
        "requires_complete_population", "freshness_status", "requires_current",
        "source_reference",
    }
    required = {
        "query_id", "domain", "expected_record_id", "fact", "expected_location",
        "source_evidence", "expected_source_id", "expected_entity_id",
        "source_reference",
    }
    requirements: list[EvidenceRequirement] = []
    for index, raw in enumerate(raw_requirements):
        if not isinstance(raw, dict):
            raise BenchmarkEvidenceError(f"requirement {index} must be an object")
        unknown = set(raw) - allowed
        missing = required - set(raw)
        if unknown or missing:
            raise BenchmarkEvidenceError(
                f"requirement {index} has unknown={sorted(unknown)} missing={sorted(missing)}"
            )
        for field in (
            "query_id", "domain", "expected_record_id", "fact",
            "expected_location", "source_evidence", "expected_source_id",
            "expected_entity_id", "source_reference",
        ):
            if not isinstance(raw[field], str) or not raw[field].strip():
                raise BenchmarkEvidenceError(
                    f"requirement {index} field {field} must be a non-blank string"
                )
        for flag in ("requires_complete_population", "requires_current"):
            if flag in raw and not isinstance(raw[flag], bool):
                raise BenchmarkEvidenceError(
                    f"requirement {index} field {flag} must be a boolean"
                )
        try:
            requirements.append(
                EvidenceRequirement(
                    query_id=str(raw["query_id"]),
                    domain=Domain(raw["domain"]),
                    expected_record_id=str(raw["expected_record_id"]),
                    fact=str(raw["fact"]),
                    expected_location=EvidenceLocation(raw["expected_location"]),
                    source_evidence=SourceEvidenceStatus(raw["source_evidence"]),
                    expected_source_id=raw.get("expected_source_id"),
                    expected_entity_id=raw.get("expected_entity_id"),
                    source_path=raw.get("source_path"),
                    expected_value=raw.get("expected_value"),
                    content_text=raw.get("content_text"),
                    population_status=PopulationStatus(
                        raw.get("population_status", "not_applicable")
                    ),
                    requires_complete_population=raw.get(
                        "requires_complete_population", False
                    ),
                    freshness_status=FreshnessStatus(
                        raw.get("freshness_status", "not_applicable")
                    ),
                    requires_current=raw.get("requires_current", False),
                    source_reference=raw.get("source_reference"),
                )
            )
        except (TypeError, ValueError) as exc:
            raise BenchmarkEvidenceError(
                f"requirement {index} is invalid: {exc}"
            ) from exc
    return benchmark_version, tuple(requirements)


__all__ = [
    "BenchmarkAuditReport",
    "BenchmarkEvidenceError",
    "ComparedValue",
    "ComparisonRow",
    "EvidenceAssessment",
    "EvidenceClassification",
    "EvidenceLocation",
    "EvidenceRequirement",
    "EvidenceState",
    "FreshnessStatus",
    "PopulationStatus",
    "SourceEvidenceStatus",
    "StructuredEvidence",
    "assess_requirement",
    "audit_benchmark",
    "compare_structured_evidence",
    "load_benchmark_requirements",
    "project_structured_evidence",
]
