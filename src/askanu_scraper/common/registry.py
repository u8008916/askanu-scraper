"""
Machine-readable approved source registry.

Per SOURCE_REGISTRY.md: Only approved sources may enter production.
No collector may target a source missing from this registry or with active=False.

Source approval decisions are owned by Qasim.
Rubric remains PENDING_APPROVAL and non-production until approved access is documented.
"""
from __future__ import annotations

from askanu_scraper.common.models import Domain, PollCadence, SourceRegistryEntry


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
            notes="Residence/catering/resident type/advertised rate/application info.",
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
                "ANUSA student assistance categories, service descriptions, "
                "contact/action URLs and only explicit hours. "
                "Supplementary to official ANU support pages."
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
                "Official ANU Events/calendar. "
                "This is the release-safe source regardless of Rubric approval status."
            ),
        ),
        # ----------------------------------------------------------------
        # PENDING APPROVAL — NOT FOR PRODUCTION USE
        # ----------------------------------------------------------------
        SourceRegistryEntry(
            source_id="rubric_unified_search",
            canonical_root="https://rubric.anu.edu.au",
            domain=Domain.EVENTS,
            authority_rank=3,
            poll_cadence=PollCadence.DISABLED,
            parser_name="askanu_scraper.sources.events.rubric_adapter.RubricAdapter",
            active=False,
            notes=(
                "PENDING_APPROVAL. Non-production. "
                "No use of undocumented/internal API without approved access. "
                "Qasim coordinates approval."
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
    - the source is registered but active=False (e.g., Rubric PENDING_APPROVAL).

    Every collector MUST call this before making any fetch request.
    """
    entry = get_source(source_id)
    if not entry.active:
        raise UnapprovedSourceError(
            f"Source '{source_id}' is registered but not approved for production use. "
            f"Notes: {entry.notes}"
        )
    return entry
