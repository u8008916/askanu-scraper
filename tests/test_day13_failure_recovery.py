"""Day 13 cross-collector failure, last-known-good, and recovery proof."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from askanu_scraper.common.fetcher import BaseFetcher, FetchError, MockFetcher
from askanu_scraper.common.models import IngestionRunStatus
from askanu_scraper.common.normalizer import CANBERRA_TZ
from askanu_scraper.common.storage import LocalDataStore
from askanu_scraper.job import JobConfig, execute_job
from askanu_scraper.sources.accommodation import (
    LISTING_URL as ACCOMMODATION_LISTING_URL,
    AccommodationCollector,
)
from askanu_scraper.sources.courses.collector import CoursesCollector
from askanu_scraper.sources.events import (
    LISTING_URL as EVENTS_LISTING_URL,
    EventsCollector,
)
from askanu_scraper.sources.jobs import LISTING_URL as JOBS_LISTING_URL, JobsCollector
from askanu_scraper.sources.jobs.parser import JobsParser
from askanu_scraper.sources.scholarships import (
    LISTING_URL as SCHOLARSHIPS_LISTING_URL,
    ScholarshipsCollector,
)
from askanu_scraper.sources.support import (
    LISTING_URL as SUPPORT_LISTING_URL,
    SupportCollector,
)


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
COURSE_URL = "https://programsandcourses.anu.edu.au/2026/course/COMP1100"
SCHOLARSHIP_URL = (
    "https://study.anu.edu.au/scholarships/find-scholarship/"
    "anu-international-achievement-award"
)
JOB_URL = (
    "https://jobs.anu.edu.au/jobs/"
    "senior-consultant-user-experience-hr-systems-projects-"
    "canberra-act-act-australia"
)
ACCOMMODATION_URL = (
    "https://study.anu.edu.au/accommodation/our-residences/yukeembruk"
)
SUPPORT_URL = "https://anusa.com.au/student-assistance/academic/"
EVENT_OPENING_URL = f"{EVENTS_LISTING_URL}/window-opening"
EVENT_DST_URL = f"{EVENTS_LISTING_URL}/dst-event"
EVENT_OUTSIDE_URL = f"{EVENTS_LISTING_URL}/outside-window"


class InjectedFetchFailure(BaseFetcher):
    def __init__(self, message: str) -> None:
        self.message = message

    def fetch(self, url: str) -> str:
        del url
        raise FetchError(self.message)


class FailSuccessfulBatchStore(LocalDataStore):
    """Inject a run-row failure after record comparison for rollback proof."""

    def save_run(self, run) -> None:  # type: ignore[no-untyped-def]
        if run.status == IngestionRunStatus.SUCCESS:
            raise OSError("simulated database run-row failure")
        super().save_run(run)


def _healthy_fetcher(domain: str) -> MockFetcher:
    mappings = {
        "courses": {
            COURSE_URL: FIXTURES / "courses" / "comp1100_course_sample.html",
        },
        "scholarships": {
            SCHOLARSHIPS_LISTING_URL: (
                FIXTURES
                / "scholarships"
                / "anu_scholarship_listing_safety_sample.html"
            ),
            SCHOLARSHIP_URL: (
                FIXTURES
                / "scholarships"
                / "anu_scholarship_open_featured_sample.html"
            ),
        },
        "jobs": {
            JOBS_LISTING_URL: FIXTURES / "jobs" / "anu_jobs_listing_sample.html",
            JOB_URL: FIXTURES / "jobs" / "anu_job_open_dated_sample.html",
        },
        "accommodation": {
            ACCOMMODATION_LISTING_URL: (
                FIXTURES / "accommodation" / "anu_residences_listing_sample.html"
            ),
            ACCOMMODATION_URL: (
                FIXTURES / "accommodation" / "anu_residence_yukeembruk_sample.html"
            ),
        },
        "support": {
            SUPPORT_LISTING_URL: (
                FIXTURES / "support" / "anusa_student_assistance_listing_sample.html"
            ),
            SUPPORT_URL: FIXTURES / "support" / "anusa_academic_sample.html",
        },
        "events": {
            EVENTS_LISTING_URL: FIXTURES / "events" / "listing-page-0.html",
            f"{EVENTS_LISTING_URL}?page=1": FIXTURES / "events" / "listing-page-1.html",
            EVENT_OPENING_URL: FIXTURES / "events" / "window-opening.html",
            EVENT_DST_URL: FIXTURES / "events" / "dst-event.html",
            EVENT_OUTSIDE_URL: FIXTURES / "events" / "outside-window.html",
        },
    }
    return MockFetcher(mappings[domain])


def _malformed_fetcher(domain: str) -> MockFetcher:
    fetcher = _healthy_fetcher(domain)
    replacements = {
        "courses": (
            COURSE_URL,
            FIXTURES / "courses" / "comp1100_missing_identity_sample.html",
        ),
        "scholarships": (
            SCHOLARSHIP_URL,
            FIXTURES / "scholarships" / "anu_scholarship_malformed_sample.html",
        ),
        "jobs": (JOB_URL, FIXTURES / "jobs" / "anu_job_malformed_sample.html"),
        "accommodation": (
            ACCOMMODATION_URL,
            FIXTURES / "accommodation" / "anu_residence_malformed_sample.html",
        ),
        "support": (
            SUPPORT_URL,
            FIXTURES / "support" / "anusa_support_malformed_sample.html",
        ),
        "events": (EVENT_DST_URL, FIXTURES / "events" / "outside-window.html"),
    }
    url, fixture = replacements[domain]
    fetcher._map[url] = fixture  # type: ignore[attr-defined]
    return fetcher


def _run(domain: str, store: LocalDataStore, fetcher: BaseFetcher):
    if domain == "courses":
        return CoursesCollector(fetcher=fetcher, store=store).run_single(COURSE_URL)
    if domain == "scholarships":
        run, records, _ = ScholarshipsCollector(
            fetcher=fetcher,
            store=store,
            min_request_interval_seconds=0,
        ).run_listing(max_details=1)
        return run, records
    if domain == "jobs":
        run, records, _ = JobsCollector(
            fetcher=fetcher,
            store=store,
            parser=JobsParser(
                now_func=lambda: datetime(2026, 9, 17, 12, tzinfo=CANBERRA_TZ)
            ),
            min_request_interval_seconds=0,
        ).run_listing(max_details=1)
        return run, records
    if domain == "accommodation":
        run, records, _ = AccommodationCollector(
            fetcher=fetcher,
            store=store,
            frozen_entity_count=2,
            min_request_interval_seconds=0,
        ).run_listing(max_details=1)
        return run, records
    if domain == "events":
        run, records, _ = EventsCollector(
            fetcher=fetcher,
            store=store,
            min_request_interval_seconds=0,
        ).run_listing(
            max_listing_pages=2,
            max_details=10,
            window_start=date(2026, 9, 19),
            window_days=43,
            expected_event_count=2,
        )
        return run, records
    run, records, _ = SupportCollector(
        fetcher=fetcher,
        store=store,
        frozen_entity_count=2,
        min_request_interval_seconds=0,
    ).run_listing(max_details=1)
    return run, records


def _assert_preserved(before, after) -> None:  # type: ignore[no-untyped-def]
    assert before is not None and after is not None
    assert after.record_id == before.record_id
    assert after.content_hash == before.content_hash
    assert after.content == before.content
    assert after.collected_at == before.collected_at
    assert after.last_seen_at == before.last_seen_at
    assert after.index_status == before.index_status


@pytest.mark.parametrize(
    "domain",
    ["courses", "scholarships", "jobs", "accommodation", "support", "events"],
)
@pytest.mark.parametrize(
    "failure_message",
    ["HTTP 503 Service Unavailable", "request timed out after 30 seconds"],
    ids=["http-5xx", "timeout"],
)
def test_fetch_failure_preserves_last_known_good_then_recovers_unchanged(
    domain: str,
    failure_message: str,
    tmp_path: Path,
) -> None:
    store = LocalDataStore(tmp_path / domain)
    healthy, records = _run(domain, store, _healthy_fetcher(domain))
    assert healthy.status == IngestionRunStatus.SUCCESS
    record_id = records[0].record_id
    before = store.get_record(record_id)

    failed, failed_records = _run(
        domain,
        store,
        InjectedFetchFailure(failure_message),
    )
    assert failed.status == IngestionRunStatus.FAILED
    assert failed_records == []
    _assert_preserved(before, store.get_record(record_id))

    recovered, recovered_records = _run(
        domain,
        store,
        _healthy_fetcher(domain),
    )
    assert recovered.status == IngestionRunStatus.SUCCESS
    assert recovered.records_unchanged == len(records)
    assert recovered.records_missing == 0
    assert recovered_records[0].content_hash == before.content_hash


@pytest.mark.parametrize(
    "domain",
    ["courses", "scholarships", "jobs", "accommodation", "support", "events"],
)
def test_malformed_page_preserves_last_known_good_then_recovers_unchanged(
    domain: str,
    tmp_path: Path,
) -> None:
    store = LocalDataStore(tmp_path / domain)
    healthy, records = _run(domain, store, _healthy_fetcher(domain))
    assert healthy.status == IngestionRunStatus.SUCCESS
    record_id = records[0].record_id
    before = store.get_record(record_id)

    failed, failed_records = _run(domain, store, _malformed_fetcher(domain))
    assert failed.status == IngestionRunStatus.FAILED
    assert failed_records == []
    _assert_preserved(before, store.get_record(record_id))

    recovered, _ = _run(domain, store, _healthy_fetcher(domain))
    assert recovered.status == IngestionRunStatus.SUCCESS
    assert recovered.records_unchanged == len(records)


def test_atomic_run_write_failure_rolls_back_then_recovers_unchanged(
    tmp_path: Path,
) -> None:
    base_dir = tmp_path / "courses"
    healthy_store = LocalDataStore(base_dir)
    healthy, records = _run("courses", healthy_store, _healthy_fetcher("courses"))
    assert healthy.status == IngestionRunStatus.SUCCESS
    record_id = records[0].record_id
    before = healthy_store.get_record(record_id)

    failed, failed_records = _run(
        "courses",
        FailSuccessfulBatchStore(base_dir),
        _healthy_fetcher("courses"),
    )
    assert failed.status == IngestionRunStatus.FAILED
    assert failed_records == []
    _assert_preserved(before, healthy_store.get_record(record_id))

    recovered, _ = _run("courses", healthy_store, _healthy_fetcher("courses"))
    assert recovered.status == IngestionRunStatus.SUCCESS
    assert recovered.records_unchanged == 1


def test_failure_summary_redacts_credentials_and_query_values(tmp_path: Path) -> None:
    secret = "never-print-this"
    config = JobConfig(
        source_id="courses_programs_and_courses",
        domain="courses",
        academic_year="2026",
        course_code=None,
        storage_backend="local",
        max_courses=1,
        max_programs=1,
        dry_run=True,
        simulate_fetch_failure=False,
        storage_path=tmp_path / "dry-run",
        timeout_seconds=30,
        min_request_interval_seconds=1,
    )
    result = execute_job(
        config,
        fetcher=InjectedFetchFailure(
            f"HTTP 503 https://user:{secret}@example.test/path?token={secret}"
        ),
        environ={"SCRAPER_TEST_TOKEN": secret},
        sleep_func=lambda _: None,
    )

    error = str(result.summary["error"])
    assert result.summary["status"] == "FAILED"
    assert secret not in error
    assert "token=" not in error
    assert "[REDACTED]" in error
