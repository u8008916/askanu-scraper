"""Shared V7 resolver metadata derived from validated source records.

The projection is deliberately read-only. It preserves stable IDs, hashes and
source values; it does not generate synonyms, rank collisions, infer missing
temporal values, or implement conversational state.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
import re

from askanu_scraper.common.models import CommonRecord, Domain
from askanu_scraper.common.v7_contract import (
    LookupTerm,
    SourceAuthority,
    producer_contract_for,
    source_authority_for,
    source_backed_lookup_terms,
)


class TemporalKind(str, Enum):
    """Source-backed temporal roles understood by the frozen resolver."""

    ACADEMIC_YEAR = "academic_year"
    OPENS_ON = "opens_on"
    CLOSES_ON = "closes_on"
    CLOSES_AT = "closes_at"
    STARTS_AT = "starts_at"
    ENDS_AT = "ends_at"


class TemporalPrecision(str, Enum):
    YEAR = "year"
    DATE = "date"
    DATETIME = "datetime"


@dataclass(frozen=True)
class TemporalValue:
    """An exact validated source value; absence is represented by no entry."""

    kind: TemporalKind
    value: str
    precision: TemporalPrecision
    source_path: str
    timezone: str | None = None


@dataclass(frozen=True)
class ResolverSearchMetadata:
    """Search-facing facts for one complete normalized record."""

    record_id: str
    source_id: str
    domain: Domain
    entity_type: str
    authority: SourceAuthority
    lookup_terms: tuple[LookupTerm, ...]
    temporal_values: tuple[TemporalValue, ...]


@dataclass(frozen=True)
class TermReference:
    record_id: str
    source_id: str
    value: str
    normalized: str
    kind: str


@dataclass(frozen=True)
class TermCollision:
    """Ambiguous normalized term; downstream resolution remains undecided."""

    normalized: str
    references: tuple[TermReference, ...]


@dataclass(frozen=True)
class _TemporalSpec:
    kind: TemporalKind
    source_path: str
    precision: TemporalPrecision
    timezone_path: str | None = None


class SearchMetadataError(ValueError):
    """Raised when a reviewed record exposes invalid temporal search data."""


_TEMPORAL_SPECS: dict[tuple[Domain, str], tuple[_TemporalSpec, ...]] = {
    (Domain.COURSES, "course"): (
        _TemporalSpec(
            TemporalKind.ACADEMIC_YEAR,
            "metadata_json.academic_year",
            TemporalPrecision.YEAR,
        ),
    ),
    (Domain.COURSES, "program"): (
        _TemporalSpec(
            TemporalKind.ACADEMIC_YEAR,
            "metadata_json.academic_year",
            TemporalPrecision.YEAR,
        ),
    ),
    (Domain.SCHOLARSHIPS, "scholarship"): (
        _TemporalSpec(
            TemporalKind.OPENS_ON,
            "metadata_json.opening_date",
            TemporalPrecision.DATE,
        ),
        _TemporalSpec(
            TemporalKind.CLOSES_ON,
            "metadata_json.closing_date",
            TemporalPrecision.DATE,
        ),
    ),
    (Domain.JOBS, "job"): (
        _TemporalSpec(
            TemporalKind.CLOSES_ON,
            "metadata_json.closing_date",
            TemporalPrecision.DATE,
        ),
        _TemporalSpec(
            TemporalKind.CLOSES_AT,
            "metadata_json.closing_at",
            TemporalPrecision.DATETIME,
        ),
    ),
    (Domain.ACCOMMODATION, "residence"): (),
    (Domain.SUPPORT, "support_service"): (),
    (Domain.EVENTS, "event"): (
        _TemporalSpec(
            TemporalKind.STARTS_AT,
            "metadata_json.start_at",
            TemporalPrecision.DATETIME,
            timezone_path="metadata_json.timezone",
        ),
        _TemporalSpec(
            TemporalKind.ENDS_AT,
            "metadata_json.end_at",
            TemporalPrecision.DATETIME,
            timezone_path="metadata_json.timezone",
        ),
    ),
}


def _path_value(record: CommonRecord, path: str) -> object:
    if path.startswith("metadata_json."):
        return record.metadata_json.get(path.removeprefix("metadata_json."))
    return getattr(record, path)


def _validated_temporal_value(
    record: CommonRecord,
    spec: _TemporalSpec,
) -> TemporalValue | None:
    raw = _path_value(record, spec.source_path)
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise SearchMetadataError(f"{spec.source_path} must be a string or null")

    normalized_value = raw
    if spec.precision == TemporalPrecision.YEAR:
        if re.fullmatch(r"\d{4}", raw) is None:
            raise SearchMetadataError(f"{spec.source_path} must be a four-digit year")
    elif spec.precision == TemporalPrecision.DATE:
        try:
            parsed_date = date.fromisoformat(raw)
        except ValueError as exc:
            raise SearchMetadataError(
                f"{spec.source_path} must be an ISO calendar date"
            ) from exc
        if parsed_date.isoformat() != raw:
            raise SearchMetadataError(
                f"{spec.source_path} must be an ISO calendar date"
            )
        normalized_value = parsed_date.isoformat()
    else:
        try:
            parsed_datetime = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise SearchMetadataError(
                f"{spec.source_path} must be an ISO datetime"
            ) from exc
        if (
            parsed_datetime.tzinfo is None
            or parsed_datetime.utcoffset() is None
        ):
            raise SearchMetadataError(
                f"{spec.source_path} must be timezone-aware"
            )
        normalized_value = parsed_datetime.isoformat()

    timezone = None
    if spec.timezone_path is not None:
        raw_timezone = _path_value(record, spec.timezone_path)
        if raw_timezone is not None and not isinstance(raw_timezone, str):
            raise SearchMetadataError(
                f"{spec.timezone_path} must be a string or null"
            )
        timezone = raw_timezone

    return TemporalValue(
        kind=spec.kind,
        value=normalized_value,
        precision=spec.precision,
        source_path=spec.source_path,
        timezone=timezone,
    )


def build_resolver_search_metadata(record: CommonRecord) -> ResolverSearchMetadata:
    """Project one validated record without changing or completing its facts."""

    contract = producer_contract_for(record)
    specs = _TEMPORAL_SPECS.get((record.domain, contract.entity_type))
    if specs is None:
        raise SearchMetadataError(
            "No temporal projection for "
            f"domain={record.domain.value!r}, entity_type={contract.entity_type!r}"
        )

    temporal_values = tuple(
        value
        for spec in specs
        if (value := _validated_temporal_value(record, spec)) is not None
    )
    return ResolverSearchMetadata(
        record_id=record.record_id,
        source_id=record.source_id,
        domain=record.domain,
        entity_type=contract.entity_type,
        authority=source_authority_for(record),
        lookup_terms=source_backed_lookup_terms(record),
        temporal_values=temporal_values,
    )


def find_term_collisions(
    records: list[CommonRecord] | tuple[CommonRecord, ...],
) -> tuple[TermCollision, ...]:
    """Report cross-record term collisions without resolving or ranking them."""

    grouped: dict[str, dict[tuple[str, str, str], TermReference]] = {}
    for record in records:
        metadata = build_resolver_search_metadata(record)
        for term in metadata.lookup_terms:
            reference = TermReference(
                record_id=metadata.record_id,
                source_id=metadata.source_id,
                value=term.value,
                normalized=term.normalized,
                kind=term.kind.value,
            )
            grouped.setdefault(term.normalized, {})[
                (reference.record_id, reference.source_id, reference.kind)
            ] = reference

    collisions: list[TermCollision] = []
    for normalized, references_by_record in grouped.items():
        references = tuple(
            sorted(
                references_by_record.values(),
                key=lambda item: (item.record_id, item.source_id, item.kind),
            )
        )
        if len({item.record_id for item in references}) > 1:
            collisions.append(
                TermCollision(normalized=normalized, references=references)
            )
    return tuple(sorted(collisions, key=lambda item: item.normalized))


def find_duplicate_record_ids(
    records: list[CommonRecord] | tuple[CommonRecord, ...],
) -> tuple[str, ...]:
    """Return repeated stable IDs; do not merge or discard either record."""

    seen: set[str] = set()
    duplicates: set[str] = set()
    for record in records:
        if record.record_id in seen:
            duplicates.add(record.record_id)
        seen.add(record.record_id)
    return tuple(sorted(duplicates))


__all__ = [
    "ResolverSearchMetadata",
    "SearchMetadataError",
    "TemporalKind",
    "TemporalPrecision",
    "TemporalValue",
    "TermCollision",
    "TermReference",
    "build_resolver_search_metadata",
    "find_duplicate_record_ids",
    "find_term_collisions",
]
