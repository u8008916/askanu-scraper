"""Read-only V7 producer capability and lookup-term contract.

This module projects facts from an already validated :class:`CommonRecord`.
It does not add serialized fields, infer aliases, or implement retrieval and
reasoning owned by the RAG repository.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import unicodedata

from askanu_scraper.common.models import CommonRecord, Domain, SourceApprovalStatus
from askanu_scraper.common.normalizer import normalize_whitespace
from askanu_scraper.common.registry import get_source


class EvidenceSupport(str, Enum):
    """How reliably producer data can support a downstream operation."""

    RELIABLE = "reliable"
    STRUCTURED_AND_CONTENT = "structured_and_content"
    CONTENT_ONLY = "content_only"
    ABSENT = "absent"


class LookupTermKind(str, Enum):
    """Source-backed lookup term types; aliases are never guessed."""

    CANONICAL_NAME = "canonical_name"
    IDENTIFIER = "identifier"
    SOURCE_ALIAS = "source_alias"


@dataclass(frozen=True)
class CapabilitySupport:
    operation: str
    support: EvidenceSupport
    basis: str


@dataclass(frozen=True)
class ProducerContract:
    """Frozen inventory for one serialized producer record shape."""

    domain: Domain
    entity_type: str
    source_ids: tuple[str, ...]
    stable_identity_paths: tuple[str, ...]
    identifier_paths: tuple[str, ...]
    source_alias_paths: tuple[str, ...]
    structured_fact_paths: tuple[str, ...]
    content_only_facts: tuple[str, ...]
    absent_facts: tuple[str, ...]
    capabilities: tuple[CapabilitySupport, ...]


@dataclass(frozen=True)
class LookupTerm:
    """One exact source-backed term plus its conservative lookup form."""

    value: str
    normalized: str
    kind: LookupTermKind
    source_path: str


@dataclass(frozen=True)
class SourceAuthority:
    """Reviewed provenance classification copied from the source registry."""

    source_id: str
    authority_rank: int
    approval_status: SourceApprovalStatus


class UnsupportedProducerContractError(ValueError):
    """Raised when a record has no reviewed V7 producer contract."""


def _capabilities(
    *,
    lookup: EvidenceSupport,
    discovery: EvidenceSupport,
    filtering: EvidenceSupport,
    comparison: EvidenceSupport,
    matching: EvidenceSupport,
) -> tuple[CapabilitySupport, ...]:
    values = {
        "lookup": lookup,
        "discovery": discovery,
        "filter": filtering,
        "compare": comparison,
        "match": matching,
    }
    basis = {
        EvidenceSupport.RELIABLE: "structured source-backed fields",
        EvidenceSupport.STRUCTURED_AND_CONTENT: (
            "source-backed structured dimensions support candidate filtering; "
            "prose supports content-assisted relevance; missing evidence stays "
            "unknown; personal eligibility and ranking are unsupported"
        ),
        EvidenceSupport.CONTENT_ONLY: "source wording retained only in content",
        EvidenceSupport.ABSENT: "not represented by approved producer evidence",
    }
    return tuple(
        CapabilitySupport(operation=name, support=support, basis=basis[support])
        for name, support in values.items()
    )


_CONTRACTS: tuple[ProducerContract, ...] = (
    ProducerContract(
        domain=Domain.COURSES,
        entity_type="course",
        source_ids=("courses_programs_and_courses",),
        stable_identity_paths=(
            "record_id",
            "source_id",
            "entity_id",
            "metadata_json.entity_type",
            "metadata_json.course_code",
            "metadata_json.academic_year",
            "canonical_url",
        ),
        identifier_paths=("metadata_json.course_code",),
        source_alias_paths=(),
        structured_fact_paths=(
            "metadata_json.career",
            "metadata_json.units",
            "metadata_json.delivery_mode",
            "metadata_json.prerequisites",
            "metadata_json.incompatibilities",
            "metadata_json.assumed_knowledge",
            "metadata_json.offerings",
        ),
        content_only_facts=("description", "learning_outcomes", "corequisites"),
        absent_facts=("personal_eligibility", "guaranteed_enrolment"),
        capabilities=_capabilities(
            lookup=EvidenceSupport.RELIABLE,
            discovery=EvidenceSupport.RELIABLE,
            filtering=EvidenceSupport.RELIABLE,
            comparison=EvidenceSupport.RELIABLE,
            matching=EvidenceSupport.CONTENT_ONLY,
        ),
    ),
    ProducerContract(
        domain=Domain.COURSES,
        entity_type="program",
        source_ids=("courses_programs_and_courses",),
        stable_identity_paths=(
            "record_id",
            "source_id",
            "entity_id",
            "metadata_json.entity_type",
            "metadata_json.program_code",
            "metadata_json.academic_year",
            "canonical_url",
        ),
        identifier_paths=("metadata_json.program_code",),
        source_alias_paths=(),
        structured_fact_paths=(
            "metadata_json.career",
            "metadata_json.units",
            "metadata_json.duration",
            "metadata_json.delivery_mode",
            "metadata_json.learning_outcomes",
        ),
        content_only_facts=(
            "overview",
            "program_requirements",
            "admission_requirements",
            "prerequisites",
            "minors",
            "elective_study",
            "study_options",
        ),
        absent_facts=("personal_admission_outcome", "guaranteed_entry"),
        capabilities=_capabilities(
            lookup=EvidenceSupport.RELIABLE,
            discovery=EvidenceSupport.RELIABLE,
            filtering=EvidenceSupport.RELIABLE,
            comparison=EvidenceSupport.RELIABLE,
            matching=EvidenceSupport.CONTENT_ONLY,
        ),
    ),
    ProducerContract(
        domain=Domain.SCHOLARSHIPS,
        entity_type="scholarship",
        source_ids=("scholarships_anu_finder",),
        stable_identity_paths=(
            "record_id",
            "source_id",
            "entity_id",
            "metadata_json.entity_type",
            "canonical_url",
        ),
        identifier_paths=(),
        source_alias_paths=(),
        structured_fact_paths=(
            "metadata_json.featured",
            "metadata_json.status",
            "metadata_json.application_required",
            "metadata_json.study_stage",
            "metadata_json.student_type",
            "metadata_json.study_level",
            "metadata_json.area_of_study",
            "metadata_json.value",
            "metadata_json.selection_basis",
            "metadata_json.opening_date",
            "metadata_json.closing_date",
            "metadata_json.eligibility",
        ),
        content_only_facts=(
            "description",
            "application_requirement_wording",
            "application_period_wording",
            "scholarship_type",
            "study_type",
        ),
        absent_facts=(
            "personal_eligibility_decision",
            "award_probability",
            "best_scholarship_ranking",
        ),
        capabilities=_capabilities(
            lookup=EvidenceSupport.RELIABLE,
            discovery=EvidenceSupport.RELIABLE,
            filtering=EvidenceSupport.RELIABLE,
            comparison=EvidenceSupport.RELIABLE,
            matching=EvidenceSupport.STRUCTURED_AND_CONTENT,
        ),
    ),
    ProducerContract(
        domain=Domain.JOBS,
        entity_type="job",
        source_ids=("jobs_anu_search",),
        stable_identity_paths=(
            "record_id",
            "source_id",
            "entity_id",
            "metadata_json.entity_type",
            "metadata_json.job_id",
            "canonical_url",
        ),
        identifier_paths=("metadata_json.job_id",),
        source_alias_paths=(),
        structured_fact_paths=(
            "metadata_json.category",
            "metadata_json.employment_types",
            "metadata_json.location",
            "metadata_json.classification",
            "metadata_json.salary",
            "metadata_json.closing_text",
            "metadata_json.closing_date",
            "metadata_json.closing_at",
            "metadata_json.status",
            "metadata_json.summary",
        ),
        content_only_facts=(),
        absent_facts=("personal_suitability", "application_outcome"),
        capabilities=_capabilities(
            lookup=EvidenceSupport.RELIABLE,
            discovery=EvidenceSupport.RELIABLE,
            filtering=EvidenceSupport.RELIABLE,
            comparison=EvidenceSupport.RELIABLE,
            matching=EvidenceSupport.ABSENT,
        ),
    ),
    ProducerContract(
        domain=Domain.ACCOMMODATION,
        entity_type="residence",
        source_ids=("accommodation_anu_study",),
        stable_identity_paths=(
            "record_id",
            "source_id",
            "entity_id",
            "metadata_json.entity_type",
            "canonical_url",
        ),
        identifier_paths=(),
        source_alias_paths=(),
        structured_fact_paths=(
            "metadata_json.category",
            "metadata_json.location",
            "metadata_json.catering_options",
            "metadata_json.audiences",
            "metadata_json.advertised_rate",
            "metadata_json.cost_period",
            "metadata_json.rooms",
            "metadata_json.features",
            "metadata_json.overview",
            "metadata_json.accessibility",
            "metadata_json.application_text",
            "metadata_json.application_url",
            "metadata_json.eligibility",
            "metadata_json.contact",
            "metadata_json.vacancy_status",
        ),
        content_only_facts=(),
        absent_facts=("inferred_vacancy", "personal_room_offer"),
        capabilities=_capabilities(
            lookup=EvidenceSupport.RELIABLE,
            discovery=EvidenceSupport.RELIABLE,
            filtering=EvidenceSupport.RELIABLE,
            comparison=EvidenceSupport.RELIABLE,
            matching=EvidenceSupport.CONTENT_ONLY,
        ),
    ),
    ProducerContract(
        domain=Domain.SUPPORT,
        entity_type="support_service",
        source_ids=("support_anusa_student_assistance",),
        stable_identity_paths=(
            "record_id",
            "source_id",
            "entity_id",
            "metadata_json.entity_type",
            "canonical_url",
        ),
        identifier_paths=(),
        source_alias_paths=(),
        structured_fact_paths=(
            "metadata_json.category",
            "metadata_json.purpose",
            "metadata_json.audiences",
            "metadata_json.contact",
            "metadata_json.hours",
            "metadata_json.access",
            "metadata_json.cost",
            "metadata_json.topics",
            "metadata_json.referrals",
        ),
        content_only_facts=(),
        absent_facts=("case_specific_advice", "service_outcome"),
        capabilities=_capabilities(
            lookup=EvidenceSupport.RELIABLE,
            discovery=EvidenceSupport.RELIABLE,
            filtering=EvidenceSupport.RELIABLE,
            comparison=EvidenceSupport.CONTENT_ONLY,
            matching=EvidenceSupport.ABSENT,
        ),
    ),
    ProducerContract(
        domain=Domain.EVENTS,
        entity_type="event",
        source_ids=("events_anu_official", "rubric_unified_search"),
        stable_identity_paths=(
            "record_id",
            "source_id",
            "entity_id",
            "metadata_json.entity_type",
            "metadata_json.source_event_id",
            "canonical_url",
        ),
        identifier_paths=("metadata_json.source_event_id",),
        source_alias_paths=(),
        structured_fact_paths=(
            "effective_from",
            "effective_to",
            "metadata_json.start_at",
            "metadata_json.end_at",
            "metadata_json.timezone",
            "metadata_json.organiser_name",
            "metadata_json.venue_name",
            "metadata_json.address",
            "metadata_json.latitude",
            "metadata_json.longitude",
            "metadata_json.category",
            "metadata_json.tags",
            "metadata_json.registration_url",
            "metadata_json.source_status",
            "metadata_json.cancellation_status",
            "metadata_json.audience",
        ),
        content_only_facts=("description", "format", "source_date_wording"),
        absent_facts=("inferred_modality", "inferred_ticket_availability"),
        capabilities=_capabilities(
            lookup=EvidenceSupport.RELIABLE,
            discovery=EvidenceSupport.RELIABLE,
            filtering=EvidenceSupport.RELIABLE,
            comparison=EvidenceSupport.CONTENT_ONLY,
            matching=EvidenceSupport.ABSENT,
        ),
    ),
)


def get_v7_producer_contracts() -> tuple[ProducerContract, ...]:
    """Return the immutable reviewed producer inventory."""

    return _CONTRACTS


def producer_contract_for(record: CommonRecord) -> ProducerContract:
    """Return the reviewed producer contract for a validated record."""

    entity_type = record.metadata_json.get("entity_type")
    for contract in _CONTRACTS:
        if (
            record.domain == contract.domain
            and record.source_id in contract.source_ids
            and entity_type == contract.entity_type
        ):
            return contract
    raise UnsupportedProducerContractError(
        "No V7 producer contract for "
        f"domain={record.domain.value!r}, source_id={record.source_id!r}, "
        f"entity_type={entity_type!r}"
    )


def normalize_lookup_term(value: str) -> str:
    """Normalize exact source text without synonym or punctuation expansion."""

    if not isinstance(value, str):
        raise TypeError("lookup term must be a string")
    normalized = normalize_whitespace(unicodedata.normalize("NFC", value)).casefold()
    if not normalized:
        raise ValueError("lookup term must not be blank")
    return normalized


def _path_value(record: CommonRecord, path: str) -> object:
    if path.startswith("metadata_json."):
        return record.metadata_json.get(path.removeprefix("metadata_json."))
    return getattr(record, path)


def source_backed_lookup_terms(record: CommonRecord) -> tuple[LookupTerm, ...]:
    """Return only canonical names, explicit identifiers, and reviewed aliases."""

    contract = producer_contract_for(record)
    candidates = [
        ("title", record.title, LookupTermKind.CANONICAL_NAME),
        *(
            (path, _path_value(record, path), LookupTermKind.IDENTIFIER)
            for path in contract.identifier_paths
        ),
        *(
            (path, _path_value(record, path), LookupTermKind.SOURCE_ALIAS)
            for path in contract.source_alias_paths
        ),
    ]
    terms: list[LookupTerm] = []
    seen: set[tuple[LookupTermKind, str]] = set()
    for source_path, value, kind in candidates:
        if not isinstance(value, str) or not value.strip():
            continue
        normalized = normalize_lookup_term(value)
        key = (kind, normalized)
        if key in seen:
            continue
        seen.add(key)
        terms.append(
            LookupTerm(
                value=value,
                normalized=normalized,
                kind=kind,
                source_path=source_path,
            )
        )
    return tuple(terms)


def source_authority_for(record: CommonRecord) -> SourceAuthority:
    """Return registry-backed authority without treating approval as equivalence."""

    producer_contract_for(record)
    source = get_source(record.source_id)
    return SourceAuthority(
        source_id=source.source_id,
        authority_rank=source.authority_rank,
        approval_status=source.approval_status,
    )


__all__ = [
    "CapabilitySupport",
    "EvidenceSupport",
    "LookupTerm",
    "LookupTermKind",
    "ProducerContract",
    "SourceAuthority",
    "UnsupportedProducerContractError",
    "get_v7_producer_contracts",
    "normalize_lookup_term",
    "producer_contract_for",
    "source_backed_lookup_terms",
    "source_authority_for",
]
