"""One-shot job configuration and selection for ANU Jobs."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from askanu_scraper.common.fetcher import MockFetcher
from askanu_scraper.job import JobConfig, JobConfigurationError, execute_job, load_config
from askanu_scraper.sources.jobs import LISTING_URL, SOURCE_ID


FIXTURES = Path(__file__).parent.parent / "fixtures" / "jobs"
DETAIL_URL = (
    "https://jobs.anu.edu.au/jobs/"
    "senior-consultant-user-experience-hr-systems-projects-canberra-act-act-australia"
)


def _config(path: Path, *, dry_run: bool = False) -> JobConfig:
    return JobConfig(
        source_id=SOURCE_ID,
        domain="jobs",
        academic_year=None,
        course_code=None,
        storage_backend="local",
        max_courses=2,
        max_programs=2,
        dry_run=dry_run,
        simulate_fetch_failure=False,
        storage_path=path,
        timeout_seconds=30,
        min_request_interval_seconds=1.0,
        max_jobs_listing_pages=1,
        max_job_details=1,
    )


def _fetcher() -> MockFetcher:
    return MockFetcher(
        {
            LISTING_URL: FIXTURES / "anu_jobs_listing_sample.html",
            DETAIL_URL: FIXTURES / "anu_job_open_dated_sample.html",
        }
    )


def test_job_selects_jobs_and_reports_domain_bounds(tmp_path: Path) -> None:
    result = execute_job(
        _config(tmp_path / "store"), fetcher=_fetcher(), environ={}, sleep_func=lambda _: None
    )

    assert result.exit_code == 0
    assert result.summary["source_id"] == SOURCE_ID
    assert result.summary["requested_max_jobs_listing_pages"] == 1
    assert result.summary["requested_max_job_details"] == 1
    assert result.summary["requested_max_courses"] is None
    assert result.summary["records_added"] == 1


def test_jobs_config_has_safe_bounds_and_no_academic_year() -> None:
    config = load_config(
        [],
        {
            "SCRAPER_SOURCE_ID": SOURCE_ID,
            "SCRAPER_DOMAIN": "jobs",
            "SCRAPER_MAX_JOBS_LISTING_PAGES": "1",
            "SCRAPER_MAX_JOB_DETAILS": "7",
        },
    )

    assert config.academic_year is None
    assert config.max_jobs_listing_pages == 1
    assert config.max_job_details == 7


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SCRAPER_MAX_JOBS_LISTING_PAGES", "101"),
        ("SCRAPER_MAX_JOB_DETAILS", "2001"),
    ],
)
def test_jobs_config_rejects_unsafe_bounds(name: str, value: str) -> None:
    with pytest.raises(JobConfigurationError, match="between"):
        load_config([], {"SCRAPER_SOURCE_ID": SOURCE_ID, "SCRAPER_DOMAIN": "jobs", name: value})


def test_jobs_dry_run_creates_no_storage(tmp_path: Path) -> None:
    path = tmp_path / "dry-store"
    result = execute_job(
        _config(path, dry_run=True), fetcher=_fetcher(), environ={}, sleep_func=lambda _: None
    )

    assert result.exit_code == 0
    assert result.summary["records_added"] == 1
    assert not path.exists()


def test_jobs_postgres_requires_contract_approval(tmp_path: Path) -> None:
    config = replace(
        _config(tmp_path), storage_backend="postgres", jobs_postgres_approved=False
    )
    with pytest.raises(JobConfigurationError, match="schema approval gate"):
        execute_job(config, fetcher=_fetcher(), environ={})
