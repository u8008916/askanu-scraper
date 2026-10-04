"""Jobs population-first bounds regressions."""

from pathlib import Path

from askanu_scraper.common.fetcher import BaseFetcher, FetchError
from askanu_scraper.common.models import IngestionRunStatus
from askanu_scraper.common.storage import LocalDataStore
from askanu_scraper.job import load_config
from askanu_scraper.sources.jobs import JobsCollector, SOURCE_ID
from askanu_scraper.sources.jobs.discovery import (
    JobCandidate,
    JobDiscoveryResult,
)


class FailingDetailFetcher(BaseFetcher):
    def __init__(self) -> None:
        self.requested: list[str] = []

    def fetch(self, url: str) -> str:
        self.requested.append(url)
        raise FetchError("simulated detail failure")


def candidate(slug: str, title: str) -> JobCandidate:
    return JobCandidate(
        url=f"https://jobs.anu.edu.au/jobs/{slug}",
        listing_metadata={
            "title": title,
            "category": "Professional",
            "employment_types": ["Full Time"],
            "location": "Canberra / ACT",
            "classification": None,
            "salary": None,
            "closing_text": None,
            "summary": f"{title} listing summary",
            "job_id": None,
            "source_status": None,
        },
    )


def test_jobs_default_allows_complete_listing_population() -> None:
    config = load_config(
        [],
        {
            "SCRAPER_SOURCE_ID": SOURCE_ID,
            "SCRAPER_DOMAIN": "jobs",
        },
    )

    assert config.max_jobs_listing_pages == 100
    assert config.max_job_details == 10


def test_detail_bound_does_not_truncate_listing_population(
    tmp_path: Path,
    monkeypatch,
) -> None:
    candidates = [
        candidate(
            "population-role-one-canberra-act-australia",
            "Population role one",
        ),
        candidate(
            "population-role-two-canberra-act-australia",
            "Population role two",
        ),
    ]

    discovery = JobDiscoveryResult(
        candidates=candidates,
        discovered_candidate_count=2,
        rejected_links=[],
        duplicate_links=[],
        over_limit_count=0,
        advertised_page_count=1,
        advertised_total_count=2,
        advertised_first=1,
        advertised_last=2,
        rejected_by_reason={},
    )

    fetcher = FailingDetailFetcher()

    collector = JobsCollector(
        fetcher=fetcher,
        store=LocalDataStore(tmp_path / "store"),
        sleep_func=lambda _: None,
    )

    observed: dict[str, object] = {}

    def fake_discover_full_listing(
        *,
        listing_url: str,
        max_listing_pages: int,
        max_details: int | None,
    ) -> JobDiscoveryResult:
        observed["listing_url"] = listing_url
        observed["max_listing_pages"] = max_listing_pages
        observed["max_details"] = max_details
        return discovery

    monkeypatch.setattr(
        collector,
        "discover_full_listing",
        fake_discover_full_listing,
    )

    run, records, returned = collector.run_listing(
        max_listing_pages=100,
        max_details=1,
    )

    assert run.status == IngestionRunStatus.SUCCESS
    assert returned is discovery

    # Discovery receives no detail cap.
    assert observed["max_listing_pages"] == 100
    assert observed["max_details"] is None

    # Both listing-backed records survive.
    assert len(records) == 2
    assert {record.entity_id for record in records} == {
        "population-role-one-canberra-act-australia",
        "population-role-two-canberra-act-australia",
    }

    # Only one optional detail enrichment was attempted.
    assert fetcher.requested == [candidates[0].url]

    assert collector.last_run_sanity["enrichment_skipped_count"] == 1
