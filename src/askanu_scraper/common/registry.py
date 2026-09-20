"""
Machine-readable approved source registry.

Per SOURCE_REGISTRY.md: Only reviewed sources may be collected. Production
writes remain independently release-gated.
"""
from __future__ import annotations

from askanu_scraper.common.models import (
    Domain,
    PollCadence,
    SourceApprovalStatus,
    SourceRegistryEntry,
)


class UnapprovedSourceError(Exception):
    """Raised when a collector tries to target a source that is not approved."""


# ---------------------------------------------------------------------------
# Approved source catalog (V3 bootstrap)
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, SourceRegistryEntry] = {
    entry.source_id: entry
    for entry in [
        SourceRegistryEntry(
            source_id="courses_programs_and_courses",
            canonical_root="https://programsandcourses.anu.edu.au/",
            domain=Domain.COURSES,
            authority_rank=1,
            poll_cadence=PollCadence.DAILY,
            parser_name="askanu_scraper.sources.courses.parser.CoursesParser",
            active=True,
            notes=(
                "Courses, programs, majors, minors, specialisations. "
                "Preserve year/session/prerequisites/requirements/URL."
            ),
        ),
        SourceRegistryEntry(
            source_id="scholarships_anu_finder",
            canonical_root="https://study.anu.edu.au/scholarships",
            domain=Domain.SCHOLARSHIPS,
            authority_rank=1,
            poll_cadence=PollCadence.DAILY,
            parser_name="askanu_scraper.sources.scholarships.parser.ScholarshipsParser",
            active=True,
            notes="Structured eligibility/status/application/deadline data.",
        ),
        SourceRegistryEntry(
            source_id="jobs_anu_search",
            canonical_root="https://jobs.anu.edu.au/jobs/search",
            domain=Domain.JOBS,
            authority_rank=1,
            poll_cadence=PollCadence.DAILY,
            parser_name="askanu_scraper.sources.jobs.parser.JobsParser",
            active=True,
            notes="Current/open roles; closing-date data; canonical URL.",
        ),
        SourceRegistryEntry(
            source_id="accommodation_anu_study",
            canonical_root="https://study.anu.edu.au/accommodation",
            domain=Domain.ACCOMMODATION,
            authority_rank=1,
            poll_cadence=PollCadence.DAILY,
            parser_name="askanu_scraper.sources.accommodation.parser.AccommodationParser",
            active=True,
            notes=(
                "Frozen 2026-09-16 public registry of 19 residence detail pages. "
                "StarRez remains an outbound link and is never fetched."
            ),
        ),
        SourceRegistryEntry(
            source_id="support_anusa_student_assistance",
            canonical_root="https://anusa.com.au/student-assistance/",
            domain=Domain.SUPPORT,
            authority_rank=2,
            poll_cadence=PollCadence.DAILY,
            parser_name="askanu_scraper.sources.support.parser.SupportParser",
            active=True,
            notes=(
                "Frozen 2026-09-16 registry of six top-level ANUSA Student "
                "Assistance categories. Additional ANU Support targets require "
                "exact approval before registry activation."
            ),
        ),
        SourceRegistryEntry(
            source_id="events_anu_official",
            canonical_root="https://www.anu.edu.au/events",
            domain=Domain.EVENTS,
            authority_rank=1,
            poll_cadence=PollCadence.DAILY,
            parser_name="askanu_scraper.sources.events.parser.EventsParser",
            active=True,
            notes=(
                "Official ANU Events/calendar; official Upcoming Events source. "
                "Frozen window 2026-09-19 through 2026-10-31 inclusive; "
                "bounded local collection is active while PostgreSQL remains gated. "
                "This is the release-safe source regardless of Rubric approval status."
            ),
        ),
        # ----------------------------------------------------------------
        # PENDING APPROVAL — NOT FOR PRODUCTION USE
        # ----------------------------------------------------------------
        SourceRegistryEntry(
            source_id="rubric_unified_search",
            canonical_root="https://campus.hellorubric.com",
            domain=Domain.EVENTS,
            authority_rank=3,
            poll_cadence=PollCadence.DAILY,
            parser_name="askanu_scraper.sources.events.rubric_adapter.RubricAdapter",
            approval_status=SourceApprovalStatus.APPROVED_BOUNDED_UNSUPPORTED,
            active=True,
            notes=(
                "Written permission reported by Qasim for bounded AskANU ingestion. "
                "The public-search endpoints are internal/unsupported and change-sensitive; "
                "use only paced, cached, bounded collection. PostgreSQL and deployment "
                "remain separately gated."
            ),
        ),
    ]
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_source(source_id: str) -> SourceRegistryEntry:
    """Return the registry entry for *source_id*."""
    if source_id not in _REGISTRY:
        raise UnapprovedSourceError(
            f"Source '{source_id}' is not in the approved registry. "
            "Contact Qasim before adding a new production source."
        )
    return _REGISTRY[source_id]


def get_approved_sources() -> list[SourceRegistryEntry]:
    """Return all sources with active=True."""
    return [s for s in _REGISTRY.values() if s.active]


def assert_source_allowed(source_id: str) -> SourceRegistryEntry:
    """
    Assert that *source_id* is registered AND active.

    Raises UnapprovedSourceError if:
    - the source_id is not in the registry, OR
    - the source is registered but active=False.

    Every collector MUST call this before making any fetch request.
    """
    entry = get_source(source_id)
    if not entry.active:
        raise UnapprovedSourceError(
            f"Source '{source_id}' is registered but not approved for production use. "
            f"Notes: {entry.notes}"
        )
    return entry
