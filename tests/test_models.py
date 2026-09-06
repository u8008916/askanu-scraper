"""
Tests for Pydantic models: CommonRecord, SourceRegistryEntry, IngestionRun.

Key invariants:
- content_hash is deterministic — same content always produces same hash.
- make_record_id is stable — same inputs always produce same ID.
- Models validate required fields.
- Status enums serialize and deserialize correctly.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from askanu_scraper.common.models import (
    CommonRecord,
    Domain,
    IndexStatus,
    IngestionRun,
    IngestionRunStatus,
    PollCadence,
    RecordStatus,
    SourceRegistryEntry,
)
from askanu_scraper.common.normalizer import make_content_hash, make_record_id


# ---------------------------------------------------------------------------
# content_hash determinism
# ---------------------------------------------------------------------------

def test_content_hash_is_deterministic() -> None:
    """The same content always produces the same SHA-256 hash."""
    content = "COMP1100 Programming as Problem Solving, 6 units, 2026"
    h1 = make_content_hash(content)
    h2 = make_content_hash(content)
    assert h1 == h2


def test_content_hash_differs_for_different_content() -> None:
    """Different content strings produce different hashes."""
    h1 = make_content_hash("Course A content")
    h2 = make_content_hash("Course B content")
    assert h1 != h2


def test_content_hash_is_hex_string() -> None:
    """Hash is a 64-character hex string (SHA-256)."""
    h = make_content_hash("test content")
    assert len(h) == 64
    int(h, 16)  # should not raise


# ---------------------------------------------------------------------------
# stable record ID
# ---------------------------------------------------------------------------

def test_make_record_id_format() -> None:
    record_id = make_record_id("courses", "course:COMP1100_2026")
    assert record_id == "courses:course:COMP1100_2026"


def test_make_record_id_is_stable() -> None:
    id1 = make_record_id("scholarships", "anu-humanitarian-2026")
    id2 = make_record_id("scholarships", "anu-humanitarian-2026")
    assert id1 == id2


# ---------------------------------------------------------------------------
# SourceRegistryEntry
# ---------------------------------------------------------------------------

def test_source_registry_entry_valid() -> None:
    entry = SourceRegistryEntry(
        source_id="courses_programs_and_courses",
        canonical_root="https://programsandcourses.anu.edu.au/",
        domain=Domain.COURSES,
        authority_rank=1,
        poll_cadence=PollCadence.DAILY,
        parser_name="askanu_scraper.sources.courses.parser.CoursesParser",
        active=True,
    )
    assert entry.source_id == "courses_programs_and_courses"
    assert entry.active is True
    assert entry.domain == Domain.COURSES


def test_source_registry_entry_requires_source_id() -> None:
    with pytest.raises(ValidationError):
        SourceRegistryEntry(  # type: ignore[call-arg]
            canonical_root="https://example.com",
            domain=Domain.COURSES,
            authority_rank=1,
            parser_name="some.parser",
            active=True,
        )


def test_source_registry_entry_authority_rank_ge_1() -> None:
    with pytest.raises(ValidationError):
        SourceRegistryEntry(
            source_id="test",
            canonical_root="https://example.com",
            domain=Domain.COURSES,
            authority_rank=0,  # invalid
            parser_name="some.parser",
            active=True,
        )


# ---------------------------------------------------------------------------
# CommonRecord
# ---------------------------------------------------------------------------

def test_common_record_valid() -> None:
    content = "Test course content"

    record = CommonRecord(
        record_id="courses:course:COMP1100_2026",
        source_id="courses_programs_and_courses",
        entity_id="COMP1100_2026",
        domain=Domain.COURSES,
        title="Programming as Problem Solving",
        content=content,
        canonical_url=(
            "https://programsandcourses.anu.edu.au/"
            "2026/course/COMP1100"
        ),
        content_hash=make_content_hash(content),
        metadata_json={
            "entity_type": "course",
            "course_code": "COMP1100",
            "academic_year": "2026",
            "career": None,
            "units": None,
            "delivery_mode": None,
            "prerequisites": None,
            "incompatibilities": None,
            "assumed_knowledge": None,
            "offerings": None,
        },
    )

    assert record.domain == Domain.COURSES
    assert record.entity_id == "COMP1100_2026"
    assert record.record_id == "courses:course:COMP1100_2026"
    assert record.index_status == IndexStatus.PENDING
    assert record.status == RecordStatus.NEW
    assert record.metadata_json["entity_type"] == "course"

def test_common_record_hash_matches_content() -> None:
    """Stored content_hash matches canonical content."""
    content = "Stable content for COMP1100"

    record = CommonRecord(
        record_id="courses:course:COMP1100_2026",
        source_id="courses_programs_and_courses",
        entity_id="COMP1100_2026",
        domain=Domain.COURSES,
        title="COMP1100",
        content=content,
        canonical_url=(
            "https://programsandcourses.anu.edu.au/"
            "2026/course/COMP1100"
        ),
        content_hash=make_content_hash(content),
        metadata_json={
            "entity_type": "course",
            "course_code": "COMP1100",
            "academic_year": "2026",
        },
    )

    assert record.content_hash == make_content_hash(content)

def test_common_record_optional_fields_default_none() -> None:
    """Nullable top-level schema-v1 fields default to None."""
    content = "Test course content"

    record = CommonRecord(
        record_id="courses:course:COMP1100_2026",
        source_id="courses_programs_and_courses",
        entity_id="COMP1100_2026",
        domain=Domain.COURSES,
        title="COMP1100",
        content=content,
        canonical_url=(
            "https://programsandcourses.anu.edu.au/"
            "2026/course/COMP1100"
        ),
        content_hash=make_content_hash(content),
        metadata_json={
            "entity_type": "course",
            "course_code": "COMP1100",
            "academic_year": "2026",
        },
    )

    assert record.effective_from is None
    assert record.effective_to is None
    assert record.embedding_version is None


def _valid_course_record_kwargs() -> dict:
    """Return one valid schema-v1 course record for negative tests."""
    content = "Valid COMP1100 content"

    return {
        "record_id": "courses:course:COMP1100_2026",
        "source_id": "courses_programs_and_courses",
        "entity_id": "COMP1100_2026",
        "domain": Domain.COURSES,
        "title": "Programming as Problem Solving",
        "content": content,
        "canonical_url": (
            "https://programsandcourses.anu.edu.au/"
            "2026/course/COMP1100"
        ),
        "content_hash": make_content_hash(content),
        "metadata_json": {
            "entity_type": "course",
            "course_code": "COMP1100",
            "academic_year": "2026",
        },
    }


def test_common_record_rejects_legacy_record_id() -> None:
    values = _valid_course_record_kwargs()
    values["record_id"] = "courses:COMP1100_2026"

    with pytest.raises(ValidationError):
        CommonRecord(**values)


def test_common_record_rejects_invalid_content_hash() -> None:
    values = _valid_course_record_kwargs()
    values["content_hash"] = "0" * 64

    with pytest.raises(ValidationError):
        CommonRecord(**values)


def test_common_record_rejects_invalid_canonical_url() -> None:
    values = _valid_course_record_kwargs()
    values["canonical_url"] = "not-a-valid-url"

    with pytest.raises(ValidationError):
        CommonRecord(**values)


def test_common_record_rejects_naive_collected_at() -> None:
    values = _valid_course_record_kwargs()
    values["collected_at"] = datetime(2026, 9, 6, 12, 0, 0)

    with pytest.raises(ValidationError):
        CommonRecord(**values)


def test_common_record_rejects_missing_course_code() -> None:
    values = _valid_course_record_kwargs()
    metadata = dict(values["metadata_json"])
    metadata.pop("course_code")
    values["metadata_json"] = metadata

    with pytest.raises(ValidationError):
        CommonRecord(**values)


# ---------------------------------------------------------------------------
# IngestionRun
# ---------------------------------------------------------------------------

def test_ingestion_run_defaults() -> None:
    run = IngestionRun(run_id="run-001", source_id="courses_programs_and_courses")
    assert run.records_seen == 0
    assert run.status == IngestionRunStatus.RUNNING
    assert run.error is None


def test_ingestion_run_failed_status() -> None:
    run = IngestionRun(
        run_id="run-002",
        source_id="courses_programs_and_courses",
        status=IngestionRunStatus.FAILED,
        error="Connection timeout after 30s",
    )
    assert run.status == IngestionRunStatus.FAILED
    assert "timeout" in run.error.lower()


def test_ingestion_run_suspicious_zero_status() -> None:
    """SUSPICIOUS_ZERO status is correctly set; data must not be wiped."""
    run = IngestionRun(
        run_id="run-003",
        source_id="courses_programs_and_courses",
        records_seen=0,
        status=IngestionRunStatus.SUSPICIOUS_ZERO,
        error="Saw 0 records from a source that previously had >100",
    )
    assert run.status == IngestionRunStatus.SUSPICIOUS_ZERO
