"""One-shot job selection and configuration for Scholarships."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from askanu_scraper.common.fetcher import MockFetcher
from askanu_scraper.job import (
    EXIT_SUCCESS,
    JobConfig,
    JobConfigurationError,
    execute_job,
    load_config,
)
from askanu_scraper.sources.scholarships import LISTING_URL, SOURCE_ID


FIXTURES = Path(__file__).parent.parent / "fixtures" / "scholarships"
FEATURED_URL = (
    "https://study.anu.edu.au/scholarships/find-scholarship/"
    "anu-international-achievement-award"
)
NON_FEATURED_URL = (
    "https://study.anu.edu.au/scholarships/find-scholarship/"
    "alex-rodgers-travel-grant"
)


def _config(storage_path: Path, *, dry_run: bool = False) -> JobConfig:
    return JobConfig(
        source_id=SOURCE_ID,
        domain="scholarships",
        academic_year=None,
        course_code=None,
        storage_backend="local",
        max_courses=2,
        max_programs=2,
        dry_run=dry_run,
        simulate_fetch_failure=False,
        storage_path=storage_path,
        timeout_seconds=30,
        min_request_interval_seconds=1.0,
        max_scholarship_listing_pages=1,
        max_scholarship_details=2,
    )


def _fetcher() -> MockFetcher:
    return MockFetcher(
        {
            LISTING_URL: FIXTURES / "anu_scholarship_listing_safety_sample.html",
            FEATURED_URL: FIXTURES / "anu_scholarship_open_featured_sample.html",
            NON_FEATURED_URL: (
                FIXTURES / "anu_scholarship_open_non_featured_sample.html"
            ),
        }
    )


def test_job_selects_scholarships_and_reports_domain_specific_bounds(
    tmp_path: Path,
) -> None:
    result = execute_job(
        _config(tmp_path / "store"),
        fetcher=_fetcher(),
        environ={},
        sleep_func=lambda _: None,
    )

    assert result.exit_code == EXIT_SUCCESS
    assert result.summary["source_id"] == SOURCE_ID
    assert result.summary["domain"] == "scholarships"
    assert result.summary["academic_year"] is None
    assert result.summary["requested_max_courses"] is None
    assert result.summary["requested_max_programs"] is None
    assert result.summary["requested_max_scholarship_listing_pages"] == 1
    assert result.summary["requested_max_scholarship_details"] == 2
    assert result.summary["records_added"] == 2
    assert result.summary["sanity"]["request_count"] == 3
    assert result.summary["sanity"]["detail_request_count"] == 2


def test_scholarship_config_does_not_require_academic_year() -> None:
    config = load_config(
        [],
        {
            "SCRAPER_SOURCE_ID": SOURCE_ID,
            "SCRAPER_DOMAIN": "scholarships",
            "SCRAPER_MAX_SCHOLARSHIP_LISTING_PAGES": "1",
            "SCRAPER_MAX_SCHOLARSHIP_DETAILS": "7",
        },
    )

    assert config.academic_year is None
    assert config.max_scholarship_listing_pages == 1
    assert config.max_scholarship_details == 7


@pytest.mark.parametrize(
    ("env", "message"),
    [
        (
            {
                "SCRAPER_SOURCE_ID": SOURCE_ID,
                "SCRAPER_DOMAIN": "scholarships",
                "SCRAPER_MAX_SCHOLARSHIP_LISTING_PAGES": "101",
            },
            "between 1 and 100",
        ),
        (
            {
                "SCRAPER_SOURCE_ID": SOURCE_ID,
                "SCRAPER_DOMAIN": "scholarships",
                "SCRAPER_MAX_SCHOLARSHIP_DETAILS": "2001",
            },
            "between 1 and 2000",
        ),
        (
            {
                "SCRAPER_SOURCE_ID": SOURCE_ID,
                "SCRAPER_DOMAIN": "scholarships",
                "SCRAPER_COURSE_CODE": "COMP1100",
            },
            "only valid for Courses",
        ),
    ],
)
def test_scholarship_job_rejects_unsafe_configuration(
    env: dict[str, str], message: str
) -> None:
    with pytest.raises(JobConfigurationError, match=message):
        load_config([], env)


def test_scholarship_job_dry_run_creates_no_storage(tmp_path: Path) -> None:
    storage_path = tmp_path / "dry-store"
    result = execute_job(
        _config(storage_path, dry_run=True),
        fetcher=_fetcher(),
        environ={},
        sleep_func=lambda _: None,
    )

    assert result.exit_code == EXIT_SUCCESS
    assert result.summary["records_added"] == 2
    assert not storage_path.exists()


def test_scholarship_postgres_requires_explicit_schema_approval(
    tmp_path: Path,
) -> None:
    config = replace(
        _config(tmp_path),
        storage_backend="postgres",
        scholarship_postgres_approved=False,
    )

    with pytest.raises(JobConfigurationError, match="schema approval gate"):
        execute_job(config, fetcher=_fetcher(), environ={})
