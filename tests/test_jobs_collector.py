"""Safe bounded Jobs collector behavior."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from askanu_scraper.common.fetcher import BaseFetcher, FetchError, MockFetcher
from askanu_scraper.common.models import IndexStatus, IngestionRunStatus
from askanu_scraper.common.normalizer import CANBERRA_TZ
from askanu_scraper.common.parser import ParseError
from askanu_scraper.common.storage import LocalDataStore
from askanu_scraper.sources.jobs import LISTING_URL, JobsCollector
from askanu_scraper.sources.jobs.parser import JobsParser


FIXTURES = Path(__file__).parent.parent / "fixtures" / "jobs"
DETAIL_URL = (
    "https://jobs.anu.edu.au/jobs/"
    "senior-consultant-user-experience-hr-systems-projects-canberra-act-act-australia"
)


def _fetcher(detail: Path | None = None) -> MockFetcher:
    return MockFetcher(
        {
            LISTING_URL: FIXTURES / "anu_jobs_listing_complete_one_sample.html",
            DETAIL_URL: detail or FIXTURES / "anu_job_open_dated_sample.html",
        }
    )


def _collector(store: LocalDataStore, detail: Path | None = None) -> JobsCollector:
    parser = JobsParser(
        now_func=lambda: datetime(2026, 9, 14, 12, 0, tzinfo=CANBERRA_TZ)
    )
    return JobsCollector(
        fetcher=_fetcher(detail), store=store, parser=parser,
        min_request_interval_seconds=0,
    )


def test_bounded_jobs_run_is_idempotent(tmp_path: Path) -> None:
    store = LocalDataStore(tmp_path / "store")
    first, first_records, discovery = _collector(store).run_listing(max_details=1)
    second, second_records, _ = _collector(store).run_listing(max_details=1)

    assert first.status == IngestionRunStatus.SUCCESS
    assert first.records_added == 1
    assert second.status == IngestionRunStatus.SUCCESS
    assert second.records_unchanged == 1
    assert first_records[0].record_id == second_records[0].record_id
    assert first_records[0].content_hash == second_records[0].content_hash
    assert discovery is not None


def test_bounded_jobs_run_reports_request_sanity(tmp_path: Path) -> None:
    collector = _collector(LocalDataStore(tmp_path / "store"))
    run, records, _ = collector.run_listing(max_details=1)

    assert run.records_added == 1
    assert len(records) == 1
    assert collector.last_run_sanity["request_count"] == 2
    assert collector.last_run_sanity["detail_request_count"] == 1
    assert collector.last_run_sanity["duplicate_record_id_count"] == 0


def test_jobs_change_marks_record_changed_and_pending(tmp_path: Path) -> None:
    store = LocalDataStore(tmp_path / "store")
    first, first_records, _ = _collector(store).run_listing(max_details=1)
    changed_fixture = tmp_path / "changed-job.html"
    changed_fixture.write_text(
        (FIXTURES / "anu_job_open_dated_sample.html")
        .read_text(encoding="utf-8")
        .replace("Fixed Term", "Continuing"),
        encoding="utf-8",
    )

    changed, changed_records, _ = _collector(
        store, changed_fixture
    ).run_listing(max_details=1)

    assert first.records_added == 1
    assert changed.records_changed == 1
    assert changed_records[0].content_hash != first_records[0].content_hash
    assert changed_records[0].index_status == IndexStatus.PENDING


def test_live_style_run_spaces_listing_and_detail_requests(tmp_path: Path) -> None:
    sleeps: list[float] = []
    collector = JobsCollector(
        fetcher=_fetcher(),
        store=LocalDataStore(tmp_path / "store"),
        parser=JobsParser(
            now_func=lambda: datetime(2026, 9, 14, 12, 0, tzinfo=CANBERRA_TZ)
        ),
        min_request_interval_seconds=1.0,
        sleep_func=sleeps.append,
    )

    run, _, _ = collector.run_listing(max_details=1)

    assert run.status == IngestionRunStatus.SUCCESS
    assert sleeps == [1.0]


def test_detail_failure_falls_back_to_listing_record(tmp_path: Path) -> None:
    store = LocalDataStore(tmp_path / "store")

    success, records, _ = _collector(store).run_listing(max_details=1)
    assert success.status == IngestionRunStatus.SUCCESS

    before = store.get_record(records[0].record_id)

    fallback_collector = _collector(
        store,
        FIXTURES / "anu_job_malformed_sample.html",
    )
    fallback, fallback_records, _ = fallback_collector.run_listing(max_details=1)

    assert fallback.status == IngestionRunStatus.SUCCESS
    assert len(fallback_records) == 1
    assert fallback.records_missing == 0
    assert len(fallback_collector.last_run_sanity["enrichment_failures"]) == 1

    after = store.get_record(records[0].record_id)
    assert before is not None and after is not None
    assert after.canonical_url == before.canonical_url
    assert after.content_hash != before.content_hash
    assert after.metadata_json["role_requirements"] is None


class _AlwaysFailFetcher(BaseFetcher):
    def fetch(self, url: str) -> str:
        del url
        raise FetchError("simulated")


def test_listing_failure_and_suspicious_zero_do_not_write_records(tmp_path: Path) -> None:
    empty_store = LocalDataStore(tmp_path / "empty-store")
    failed, records, _ = JobsCollector(fetcher=_AlwaysFailFetcher(), store=empty_store).run_listing(
        max_details=1
    )
    assert failed.status == IngestionRunStatus.FAILED
    assert records == []

    store = LocalDataStore(tmp_path / "store")
    success, existing_records, _ = _collector(store).run_listing(max_details=1)
    existing = store.get_record(existing_records[0].record_id)
    empty = tmp_path / "empty.html"
    empty.write_text("<html><main>No rendered jobs</main></html>", encoding="utf-8")
    suspicious, suspicious_records, _ = JobsCollector(
        fetcher=MockFetcher({LISTING_URL: empty}), store=store
    ).run_listing(max_details=1)

    assert success.status == IngestionRunStatus.SUCCESS
    assert suspicious.status == IngestionRunStatus.SUSPICIOUS_ZERO
    assert suspicious_records == []
    preserved = store.get_record(existing_records[0].record_id)
    assert existing is not None and preserved is not None
    assert preserved.content_hash == existing.content_hash


def test_drastic_advertised_count_mismatch_fails_before_detail_fetch(
    tmp_path: Path,
) -> None:
    listing = tmp_path / "suspicious-listing.html"
    listing.write_text(
        (FIXTURES / "anu_jobs_listing_sample.html")
        .read_text(encoding="utf-8")
        .replace("Displaying 1 - 1 of 60", "Displaying 1 - 20 of 60"),
        encoding="utf-8",
    )
    collector = JobsCollector(
        fetcher=MockFetcher({LISTING_URL: listing}),
        store=LocalDataStore(tmp_path / "store"),
    )

    run, records, discovery = collector.run_listing(max_details=10)

    assert run.status == IngestionRunStatus.FAILED
    assert "reconcile with advertised total" in (run.error or "")
    assert records == []
    assert discovery is not None
    assert collector.last_run_sanity["detail_request_count"] == 0


def test_direct_collect_rejects_an_unapproved_url_before_fetch(tmp_path: Path) -> None:
    class RecordingFetcher(BaseFetcher):
        def __init__(self) -> None:
            self.urls: list[str] = []

        def fetch(self, url: str) -> str:
            self.urls.append(url)
            raise AssertionError("unapproved URL must not be fetched")

    fetcher = RecordingFetcher()
    collector = JobsCollector(
        fetcher=fetcher,
        store=LocalDataStore(tmp_path / "store"),
    )

    with pytest.raises(ParseError, match="approved"):
        collector.collect("https://example.test/jobs/not-approved")

    assert fetcher.urls == []

def test_detail_cap_does_not_truncate_jobs_population(tmp_path: Path) -> None:
    source = (
        FIXTURES / "anu_jobs_listing_complete_one_sample.html"
    ).read_text(encoding="utf-8")

    source = source.replace(
        "Displaying 1 - 1 of 1 in total",
        "Displaying 1 - 2 of 2 in total",
        1,
    )

    second_url = (
        "https://jobs.anu.edu.au/jobs/"
        "second-population-role-canberra-act-australia"
    )

    second_card = f"""
    <article class="job-result" data-job-id="999999">
        <h2>
            <a href="{second_url}">
                Second Population Role
            </a>
        </h2>
        <p class="category">Professional</p>
        <p class="employment-type">Fixed Term</p>
        <p class="location">Canberra / ACT</p>
        <p class="closing-date">Closing at: Sep 27 2026 - 23:55 AEST</p>
        <p class="summary">Listing-backed second role.</p>
    </article>
    """

    source = source.replace(
        "</main>",
        second_card + "\n</main>",
        1,
    )

    listing = tmp_path / "complete-two-jobs.html"
    listing.write_text(source, encoding="utf-8")

    fetcher = MockFetcher(
        {
            LISTING_URL: listing,
            DETAIL_URL: FIXTURES / "anu_job_open_dated_sample.html",
        }
    )

    collector = JobsCollector(
        fetcher=fetcher,
        store=LocalDataStore(tmp_path / "store"),
        parser=JobsParser(
            now_func=lambda: datetime(
                2026,
                9,
                14,
                12,
                0,
                tzinfo=CANBERRA_TZ,
            )
        ),
        min_request_interval_seconds=0,
    )

    run, records, discovery = collector.run_listing(max_details=1)

    assert run.status == IngestionRunStatus.SUCCESS
    assert discovery is not None
    assert len(discovery.candidates) == 2
    assert len(records) == 2

    assert collector.last_run_sanity["detail_request_count"] == 1
    assert collector.last_run_sanity["enrichment_successes"] == 1
    assert collector.last_run_sanity["enrichment_skipped_count"] == 1
    assert collector.last_run_sanity["over_limit_candidate_count"] == 1

    assert {
        record.canonical_url
        for record in records
    } == {
        DETAIL_URL,
        second_url,
    }


def test_jobs_incomplete_reconciliation_preserves_previous_population(
    tmp_path: Path,
) -> None:
    store = LocalDataStore(tmp_path / "store")

    healthy, records, _ = _collector(store).run_listing(max_details=1)

    assert healthy.status == IngestionRunStatus.SUCCESS
    assert len(records) == 1

    record_id = records[0].record_id
    before = store.get_record(record_id)

    source = (
        FIXTURES / "anu_jobs_listing_complete_one_sample.html"
    ).read_text(encoding="utf-8")

    source = source.replace(
        "Displaying 1 - 1 of 1 in total",
        "Displaying 1 - 2 of 2 in total",
        1,
    )

    incomplete_listing = tmp_path / "incomplete-jobs.html"
    incomplete_listing.write_text(source, encoding="utf-8")

    collector = JobsCollector(
        fetcher=MockFetcher({LISTING_URL: incomplete_listing}),
        store=store,
        min_request_interval_seconds=0,
    )

    failed, failed_records, _ = collector.run_listing(max_details=1)

    assert failed.status == IngestionRunStatus.FAILED
    assert "reconcile with advertised total" in (failed.error or "")
    assert failed_records == []

    after = store.get_record(record_id)

    assert before is not None and after is not None
    assert after.content_hash == before.content_hash
    assert after.canonical_url == before.canonical_url
