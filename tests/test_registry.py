"""
Tests for the approved source registry.

Key invariants:
- Every V3 domain has an active approved source.
- Rubric is explicitly approved for bounded unsupported ingestion.
- Production writes remain protected by a separate job gate.
"""
from __future__ import annotations

import pytest

from askanu_scraper.common.models import Domain, PollCadence, SourceApprovalStatus
from askanu_scraper.common.registry import (
    UnapprovedSourceError,
    assert_source_allowed,
    get_approved_sources,
    get_source,
)

# ---------------------------------------------------------------------------
# Registry completeness
# ---------------------------------------------------------------------------

EXPECTED_APPROVED_SOURCES = {
    "courses_programs_and_courses",
    "scholarships_anu_finder",
    "jobs_anu_search",
    "accommodation_anu_study",
    "support_anusa_student_assistance",
    "events_anu_official",
    "rubric_unified_search",
}


def test_all_v3_domains_have_active_source() -> None:
    """Every V3 domain has at least one active source in the registry."""
    active = get_approved_sources()
    active_domains = {s.domain for s in active}
    for domain in Domain:
        assert domain in active_domains, (
            f"Domain {domain!r} has no active source in the registry."
        )


def test_all_expected_source_ids_are_active() -> None:
    """The exact set of V3 approved source IDs are present and active."""
    active_ids = {s.source_id for s in get_approved_sources()}
    assert active_ids == EXPECTED_APPROVED_SOURCES


def test_approved_sources_have_daily_poll_cadence() -> None:
    """All active approved sources use DAILY polling."""
    for source in get_approved_sources():
        assert source.poll_cadence == PollCadence.DAILY, (
            f"Source {source.source_id!r} has unexpected cadence: {source.poll_cadence!r}"
        )


def test_approved_sources_have_canonical_roots() -> None:
    """All active approved sources have a non-empty canonical_root."""
    for source in get_approved_sources():
        assert source.canonical_root.startswith("https://"), (
            f"Source {source.source_id!r} has missing/invalid canonical_root."
        )


def test_approved_sources_have_parser_names() -> None:
    """All active approved sources declare a parser module path."""
    for source in get_approved_sources():
        assert "." in source.parser_name, (
            f"Source {source.source_id!r} parser_name doesn't look like a module path."
        )


# ---------------------------------------------------------------------------
# Registry guard — approved source
# ---------------------------------------------------------------------------

def test_assert_source_allowed_returns_entry_for_approved_source() -> None:
    """assert_source_allowed returns the SourceRegistryEntry for an approved source."""
    entry = assert_source_allowed("courses_programs_and_courses")
    assert entry.source_id == "courses_programs_and_courses"
    assert entry.active is True


def test_assert_source_allowed_works_for_all_approved_sources() -> None:
    """assert_source_allowed succeeds for every approved source."""
    for source_id in EXPECTED_APPROVED_SOURCES:
        entry = assert_source_allowed(source_id)
        assert entry.active is True


# ---------------------------------------------------------------------------
# Registry guard — unapproved / missing sources
# ---------------------------------------------------------------------------

def test_assert_source_allowed_raises_for_unknown_source() -> None:
    """Attempting to use an unregistered source raises UnapprovedSourceError."""
    with pytest.raises(UnapprovedSourceError):
        assert_source_allowed("some_invented_source")


def test_assert_source_allowed_returns_bounded_rubric() -> None:
    rubric = assert_source_allowed("rubric_unified_search")
    assert rubric.active is True
    assert rubric.approval_status == SourceApprovalStatus.APPROVED_BOUNDED_UNSUPPORTED


def test_get_source_records_rubric_as_unsupported_and_change_sensitive() -> None:
    rubric = get_source("rubric_unified_search")
    assert rubric.active is True
    assert "internal/unsupported" in rubric.notes
    assert "PostgreSQL" in rubric.notes


def test_rubric_is_in_bounded_approved_sources() -> None:
    active_ids = {s.source_id for s in get_approved_sources()}
    assert "rubric_unified_search" in active_ids


# ---------------------------------------------------------------------------
# Rubric adapter configuration isolation
# ---------------------------------------------------------------------------

def test_rubric_adapter_requires_captured_search_endpoint() -> None:
    from askanu_scraper.sources.events.rubric_adapter import RubricAdapter

    adapter = RubricAdapter(search_endpoint=None, sleep_func=lambda _: None)
    with pytest.raises(ValueError, match="capture is unavailable"):
        adapter.discover()


def test_rubric_rejects_unreviewed_endpoint_before_request() -> None:
    from askanu_scraper.sources.events.rubric_adapter import RubricAdapter

    with pytest.raises(ValueError, match="outside the approved Rubric API boundary"):
        RubricAdapter(
            search_endpoint="https://rubric.example/internal",
            sleep_func=lambda _: None,
        )
