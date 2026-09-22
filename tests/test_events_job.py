"""One-shot Events CLI and production gate tests."""
from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Mapping

import pytest

from askanu_scraper.common.fetcher import BaseFetcher, FetchError
from askanu_scraper.job import JobConfig, JobConfigurationError, execute_job, load_config


FIXTURES = Path(__file__).parents[1] / "fixtures" / "events"
RUBRIC_SEARCH_ENDPOINT = "https://api.hellorubric.com/"


def config(path: Path) -> JobConfig:
    return JobConfig(
        source_id="events_anu_official", domain="events", academic_year=None,
        course_code=None, storage_backend="local", max_courses=2, max_programs=2,
        dry_run=True, simulate_fetch_failure=False, storage_path=path,
        timeout_seconds=30, min_request_interval_seconds=1.0,
        max_events_listing_pages=6, max_event_details=100,
        events_window_start=date(2026, 9, 19), events_window_days=43,
        expected_event_count=29,
    )


class NeverFetch(BaseFetcher):
    def fetch(self, url: str) -> str:
        raise FetchError(f"blocked fixture request: {url}")


def test_events_cli_environment_contract() -> None:
    loaded = load_config(
        ["--source-id", "events_anu_official", "--domain", "events"],
        {
            "SCRAPER_EVENTS_WINDOW_START": "2026-09-19",
            "SCRAPER_EVENTS_WINDOW_DAYS": "43",
            "SCRAPER_MAX_EVENTS_LISTING_PAGES": "6",
            "SCRAPER_MAX_EVENT_DETAILS": "100",
            "SCRAPER_EXPECTED_EVENT_COUNT": "29",
            "SCRAPER_DRY_RUN": "true",
        },
    )
    assert loaded.events_window_start == date(2026, 9, 19)
    assert loaded.events_window_days == 43
    assert loaded.max_events_listing_pages == 6
    assert loaded.max_event_details == 100
    assert loaded.expected_event_count == 29
    assert loaded.events_postgres_approved is False


def test_events_postgres_is_fail_closed_before_fetch(tmp_path: Path) -> None:
    with pytest.raises(JobConfigurationError, match="migration and Qasim/Carmen approval"):
        execute_job(
            replace(config(tmp_path), storage_backend="postgres", dry_run=False),
            fetcher=NeverFetch(), environ={},
        )


class RubricFixtureTransport:
    def post_search(self, url: str, payload: Mapping[str, object]) -> str:
        del url
        name = (
            "rubric-search-page-0.json"
            if payload["offset"] == 0
            else "rubric-search-page-1.json"
        )
        return (FIXTURES / name).read_text(encoding="utf-8")

    def post_detail(self, url: str, payload: Mapping[str, object]) -> str:
        del url
        name = f"rubric-detail-{payload['eventId']}.json"
        return (FIXTURES / name).read_text(encoding="utf-8")


def rubric_config(path: Path) -> JobConfig:
    return replace(
        config(path),
        source_id="rubric_unified_search",
        max_rubric_listing_pages=2,
        max_rubric_details=10,
        rubric_search_endpoint=RUBRIC_SEARCH_ENDPOINT,
        expected_event_count=2,
    )


def test_rubric_cli_environment_contract() -> None:
    loaded = load_config(
        ["--source-id", "rubric_unified_search", "--domain", "events"],
        {
            "SCRAPER_RUBRIC_SEARCH_ENDPOINT": RUBRIC_SEARCH_ENDPOINT,
            "SCRAPER_MAX_RUBRIC_LISTING_PAGES": "2",
            "SCRAPER_MAX_RUBRIC_DETAILS": "10",
            "SCRAPER_EVENTS_WINDOW_START": "2026-09-19",
            "SCRAPER_EVENTS_WINDOW_DAYS": "43",
            "SCRAPER_EXPECTED_EVENT_COUNT": "2",
            "SCRAPER_DRY_RUN": "true",
        },
    )
    assert loaded.rubric_search_endpoint == RUBRIC_SEARCH_ENDPOINT
    assert loaded.max_rubric_listing_pages == 2
    assert loaded.max_rubric_details == 10
    assert loaded.rubric_postgres_approved is False


def test_rubric_job_dry_run_reports_bounds_without_writing(tmp_path: Path) -> None:
    path = tmp_path / "dry"
    result = execute_job(
        rubric_config(path),
        rubric_transport=RubricFixtureTransport(),
        environ={},
        sleep_func=lambda _: None,
    )
    assert result.exit_code == 0
    assert result.summary["status"] == "SUCCESS"
    assert result.summary["records_seen"] == 2
    assert result.summary["requested_max_rubric_listing_pages"] == 2
    assert result.summary["requested_max_rubric_details"] == 10
    assert result.summary["requested_events_window_start"] == "2026-09-19"
    assert result.summary["rubric_search_endpoint_configured"] is True
    assert not path.exists()


def test_rubric_job_requires_endpoint_and_postgres_release_go(tmp_path: Path) -> None:
    with pytest.raises(JobConfigurationError, match="exact reviewed"):
        execute_job(
            replace(rubric_config(tmp_path), rubric_search_endpoint=None),
            rubric_transport=RubricFixtureTransport(),
            environ={},
        )
    with pytest.raises(JobConfigurationError, match="release GO"):
        execute_job(
            replace(
                rubric_config(tmp_path),
                storage_backend="postgres",
                dry_run=False,
            ),
            rubric_transport=RubricFixtureTransport(),
            environ={},
        )
