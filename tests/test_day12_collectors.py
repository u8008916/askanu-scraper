"""Independent Day 12 collector safety, persistence, and failure proofs."""
from pathlib import Path

import pytest

from askanu_scraper.common.fetcher import BaseFetcher, FetchError, MockFetcher
from askanu_scraper.common.models import IngestionRunStatus
from askanu_scraper.common.parser import ParseError
from askanu_scraper.common.storage import LocalDataStore
from askanu_scraper.job import JobConfig, JobConfigurationError, execute_job, load_config
from askanu_scraper.sources.accommodation import (
    LISTING_URL as ACCOMMODATION_LISTING_URL,
    AccommodationCollector,
)
from askanu_scraper.sources.support import LISTING_URL as SUPPORT_LISTING_URL, SupportCollector


ROOT = Path(__file__).parent.parent / "fixtures"
ACCOMMODATION = ROOT / "accommodation"
SUPPORT = ROOT / "support"
YUK = "https://study.anu.edu.au/accommodation/our-residences/yukeembruk"
DAVEY = "https://study.anu.edu.au/accommodation/our-residences/davey-lodge"
ACADEMIC = "https://anusa.com.au/student-assistance/academic/"
FINANCIAL = "https://anusa.com.au/student-assistance/financial/"


def _accommodation_fetcher(detail: Path | None = None) -> MockFetcher:
    return MockFetcher(
        {
            ACCOMMODATION_LISTING_URL: ACCOMMODATION / "anu_residences_listing_sample.html",
            YUK: detail or ACCOMMODATION / "anu_residence_yukeembruk_sample.html",
            DAVEY: ACCOMMODATION / "anu_residence_davey_lodge_sample.html",
        }
    )


def _support_fetcher(detail: Path | None = None) -> MockFetcher:
    return MockFetcher(
        {
            SUPPORT_LISTING_URL: SUPPORT / "anusa_student_assistance_listing_sample.html",
            ACADEMIC: detail or SUPPORT / "anusa_academic_sample.html",
            FINANCIAL: SUPPORT / "anusa_financial_sample.html",
        }
    )


@pytest.mark.parametrize("domain", ["accommodation", "support"])
def test_sample_write_and_unchanged_rerun(domain: str, tmp_path: Path) -> None:
    store = LocalDataStore(tmp_path / domain)
    if domain == "accommodation":
        make = lambda: AccommodationCollector(
            fetcher=_accommodation_fetcher(), store=store, frozen_entity_count=2
        )
    else:
        make = lambda: SupportCollector(
            fetcher=_support_fetcher(), store=store, frozen_entity_count=2
        )
    first, first_records, _ = make().run_listing(max_details=1)
    second, second_records, _ = make().run_listing(max_details=1)
    assert first.status == IngestionRunStatus.SUCCESS
    assert first.records_added == 1
    assert second.status == IngestionRunStatus.SUCCESS
    assert second.records_unchanged == 1
    assert first_records[0].record_id == second_records[0].record_id
    assert first_records[0].content_hash == second_records[0].content_hash


def test_collectors_are_independent_and_never_fetch_starrezz(tmp_path: Path) -> None:
    class RecordingFetcher(MockFetcher):
        def __init__(self, mapping: dict[str, Path]) -> None:
            super().__init__(mapping)
            self.urls: list[str] = []

        def fetch(self, url: str) -> str:
            self.urls.append(url)
            return super().fetch(url)

    accommodation_fetcher = RecordingFetcher(_accommodation_fetcher()._map)  # type: ignore[attr-defined]
    support_fetcher = RecordingFetcher(_support_fetcher()._map)  # type: ignore[attr-defined]
    a_run, a_records, _ = AccommodationCollector(
        fetcher=accommodation_fetcher,
        store=LocalDataStore(tmp_path / "a"),
        frozen_entity_count=2,
    ).run_listing(max_details=1)
    s_run, s_records, _ = SupportCollector(
        fetcher=support_fetcher,
        store=LocalDataStore(tmp_path / "s"),
        frozen_entity_count=2,
    ).run_listing(max_details=1)
    assert a_run.status == s_run.status == IngestionRunStatus.SUCCESS
    assert a_records[0].source_id != s_records[0].source_id
    assert all("starrezhousing.com" not in url for url in accommodation_fetcher.urls)


class _FailFetcher(BaseFetcher):
    def fetch(self, url: str) -> str:
        raise FetchError(f"simulated failure: {url}")


@pytest.mark.parametrize("domain", ["accommodation", "support"])
def test_fetch_failure_preserves_last_known_good(domain: str, tmp_path: Path) -> None:
    store = LocalDataStore(tmp_path / domain)
    if domain == "accommodation":
        healthy = AccommodationCollector(
            fetcher=_accommodation_fetcher(), store=store, frozen_entity_count=2
        )
        failed = AccommodationCollector(
            fetcher=_FailFetcher(), store=store, frozen_entity_count=2
        )
    else:
        healthy = SupportCollector(
            fetcher=_support_fetcher(), store=store, frozen_entity_count=2
        )
        failed = SupportCollector(fetcher=_FailFetcher(), store=store, frozen_entity_count=2)
    good_run, good_records, _ = healthy.run_listing(max_details=1)
    before = store.get_record(good_records[0].record_id)
    failed_run, failed_records, _ = failed.run_listing(max_details=1)
    after = store.get_record(good_records[0].record_id)
    assert good_run.status == IngestionRunStatus.SUCCESS
    assert failed_run.status == IngestionRunStatus.FAILED
    assert failed_records == []
    assert before is not None and after is not None
    assert before.content_hash == after.content_hash


@pytest.mark.parametrize("domain", ["accommodation", "support"])
def test_parser_failure_preserves_last_known_good(domain: str, tmp_path: Path) -> None:
    store = LocalDataStore(tmp_path / domain)
    if domain == "accommodation":
        healthy = AccommodationCollector(
            fetcher=_accommodation_fetcher(), store=store, frozen_entity_count=2
        )
        failed = AccommodationCollector(
            fetcher=_accommodation_fetcher(ACCOMMODATION / "anu_residence_malformed_sample.html"),
            store=store,
            frozen_entity_count=2,
        )
    else:
        healthy = SupportCollector(
            fetcher=_support_fetcher(), store=store, frozen_entity_count=2
        )
        failed = SupportCollector(
            fetcher=_support_fetcher(SUPPORT / "anusa_support_malformed_sample.html"),
            store=store,
            frozen_entity_count=2,
        )
    _, records, _ = healthy.run_listing(max_details=1)
    before = store.get_record(records[0].record_id)
    failed_run, _, _ = failed.run_listing(max_details=1)
    after = store.get_record(records[0].record_id)
    assert failed_run.status == IngestionRunStatus.FAILED
    assert before is not None and after is not None and before.content_hash == after.content_hash


@pytest.mark.parametrize("domain", ["accommodation", "support"])
def test_drastic_count_guard_stops_before_detail_fetch(domain: str, tmp_path: Path) -> None:
    if domain == "accommodation":
        collector = AccommodationCollector(
            fetcher=_accommodation_fetcher(),
            store=LocalDataStore(tmp_path / domain),
            frozen_entity_count=19,
        )
    else:
        collector = SupportCollector(
            fetcher=_support_fetcher(),
            store=LocalDataStore(tmp_path / domain),
            frozen_entity_count=6,
        )
    run, records, _ = collector.run_listing(max_details=1)
    assert run.status == IngestionRunStatus.FAILED
    assert records == []
    assert collector.last_run_sanity["detail_request_count"] == 0


def test_zero_result_guards_are_suspicious(tmp_path: Path) -> None:
    empty_a = tmp_path / "a.html"
    empty_s = tmp_path / "s.html"
    empty_a.write_text("<main><p>0 results found</p></main>", encoding="utf-8")
    empty_s.write_text("<main id='content'><p>No services</p></main>", encoding="utf-8")
    a_run, _, _ = AccommodationCollector(
        fetcher=MockFetcher({ACCOMMODATION_LISTING_URL: empty_a}),
        store=LocalDataStore(tmp_path / "a"),
    ).run_listing(max_details=1)
    s_run, _, _ = SupportCollector(
        fetcher=MockFetcher({SUPPORT_LISTING_URL: empty_s}),
        store=LocalDataStore(tmp_path / "s"),
    ).run_listing(max_details=1)
    assert a_run.status == s_run.status == IngestionRunStatus.SUSPICIOUS_ZERO


@pytest.mark.parametrize(
    "collector,url",
    [
        (AccommodationCollector, "https://example.test/residence"),
        (SupportCollector, "https://example.test/support"),
    ],
)
def test_direct_collect_rejects_unapproved_url_before_fetch(collector, url: str) -> None:
    class RecordingFetcher(BaseFetcher):
        def __init__(self) -> None:
            self.called = False

        def fetch(self, url: str) -> str:
            self.called = True
            raise AssertionError

    fetcher = RecordingFetcher()
    with pytest.raises(ParseError):
        collector(fetcher=fetcher).collect(url)
    assert fetcher.called is False


@pytest.mark.parametrize(
    "source_id,domain,approval_field",
    [
        ("accommodation_anu_study", "accommodation", "accommodation_postgres_approved"),
        ("support_anusa_student_assistance", "support", "support_postgres_approved"),
    ],
)
def test_day12_postgres_gate_rejects_before_fetch(
    source_id: str, domain: str, approval_field: str, tmp_path: Path
) -> None:
    config = JobConfig(
        source_id=source_id,
        domain=domain,
        academic_year=None,
        course_code=None,
        storage_backend="postgres",
        max_courses=1,
        max_programs=1,
        dry_run=False,
        simulate_fetch_failure=False,
        storage_path=tmp_path,
        timeout_seconds=30,
        min_request_interval_seconds=1,
    )
    assert getattr(config, approval_field) is False
    with pytest.raises(JobConfigurationError, match="schema approval gate"):
        execute_job(config, fetcher=_FailFetcher(), environ={})


def test_day12_cli_bounds_are_loaded() -> None:
    accommodation = load_config(
        [
            "--source-id", "accommodation_anu_study",
            "--domain", "accommodation",
            "--max-accommodation-details", "19",
        ],
        environ={},
    )
    support = load_config(
        [
            "--source-id", "support_anusa_student_assistance",
            "--domain", "support",
            "--max-support-details", "6",
        ],
        environ={},
    )
    assert accommodation.max_accommodation_details == 19
    assert support.max_support_details == 6
