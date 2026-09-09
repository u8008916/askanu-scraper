"""Day 5 bounded catalogue discovery and ingestion tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from askanu_scraper.common.fetcher import MockFetcher
from askanu_scraper.common.models import IngestionRunStatus
from askanu_scraper.common.storage import LocalDataStore
from askanu_scraper.sources.courses.collector import CoursesCollector
from askanu_scraper.sources.courses.discovery import CoursesCatalogueDiscovery


CATALOGUE_URL = "https://programsandcourses.anu.edu.au/2026/search"
COURSE_URL = "https://programsandcourses.anu.edu.au/2026/course/COMP1100"
PROGRAM_URL = "https://programsandcourses.anu.edu.au/2026/program/BACCT"
CANONICAL_ROOT = "https://programsandcourses.anu.edu.au/"


def test_discovery_classifies_all_types_and_deduplicates(
    catalogue_fixture_path: Path,
) -> None:
    result = CoursesCatalogueDiscovery().discover(
        catalogue_fixture_path.read_text(encoding="utf-8"),
        CATALOGUE_URL,
        CANONICAL_ROOT,
    )

    assert result.counts_by_type == {
        "course": 1,
        "program": 1,
        "major": 1,
        "minor": 1,
        "specialisation": 1,
    }
    assert [item.discovery_id for item in result.items] == [
        "course:COMP1100_2026",
        "program:BACCT_2026",
        "major:COMS-MAJ_2026",
        "minor:STAT-MIN_2026",
        "specialisation:ACCT-SPEC_2026",
    ]
    assert result.duplicate_identities == ("course:COMP1100_2026",)
    assert len(result.rejected_links) == 2
    assert [item.discovery_id for item in result.persisted_candidates] == [
        "course:COMP1100_2026",
        "program:BACCT_2026",
    ]


def test_catalogue_run_is_bounded_and_does_not_persist_uncontracted_types(
    tmp_path: Path,
    catalogue_fixture_path: Path,
    courses_fixture_path: Path,
    bacct_fixture_path: Path,
) -> None:
    fetcher = MockFetcher({
        CATALOGUE_URL: catalogue_fixture_path,
        COURSE_URL: courses_fixture_path,
        PROGRAM_URL: bacct_fixture_path,
    })
    store = LocalDataStore(tmp_path / "store")
    collector = CoursesCollector(fetcher=fetcher, store=store)

    run, records, discovery = collector.run_catalogue(
        CATALOGUE_URL,
        max_records=2,
    )

    assert run.status == IngestionRunStatus.SUCCESS
    assert run.records_seen == 2
    assert run.records_added == 2
    assert [record.record_id for record in records] == [
        "courses:course:COMP1100_2026",
        "courses:program:BACCT_2026",
    ]
    assert discovery.counts_by_type["major"] == 1
    assert len(list(store.records_dir.glob("*.json"))) == 2


def test_catalogue_bound_limits_detail_fetches(
    tmp_path: Path,
    catalogue_fixture_path: Path,
    courses_fixture_path: Path,
) -> None:
    collector = CoursesCollector(
        fetcher=MockFetcher({
            CATALOGUE_URL: catalogue_fixture_path,
            COURSE_URL: courses_fixture_path,
        }),
        store=LocalDataStore(tmp_path / "store"),
    )

    run, records, _ = collector.run_catalogue(
        CATALOGUE_URL,
        max_records=1,
    )

    assert run.status == IngestionRunStatus.SUCCESS
    assert run.records_seen == 1
    assert [record.record_id for record in records] == [
        "courses:course:COMP1100_2026"
    ]


def test_preflight_failure_writes_no_records(
    tmp_path: Path,
    catalogue_fixture_path: Path,
    courses_fixture_path: Path,
) -> None:
    store = LocalDataStore(tmp_path / "store")
    collector = CoursesCollector(
        fetcher=MockFetcher({
            CATALOGUE_URL: catalogue_fixture_path,
            COURSE_URL: courses_fixture_path,
            # The selected program detail fixture is intentionally absent.
        }),
        store=store,
    )

    run, records, discovery = collector.run_catalogue(
        CATALOGUE_URL,
        max_records=2,
    )

    assert run.status == IngestionRunStatus.FAILED
    assert "Detail fetch failed" in (run.error or "")
    assert records == []
    assert discovery.counts_by_type["program"] == 1
    assert list(store.records_dir.glob("*.json")) == []


def test_catalogue_rerun_preserves_ids_and_hashes(
    tmp_path: Path,
    catalogue_fixture_path: Path,
    courses_fixture_path: Path,
    bacct_fixture_path: Path,
) -> None:
    fetcher = MockFetcher({
        CATALOGUE_URL: catalogue_fixture_path,
        COURSE_URL: courses_fixture_path,
        PROGRAM_URL: bacct_fixture_path,
    })
    collector = CoursesCollector(
        fetcher=fetcher,
        store=LocalDataStore(tmp_path / "store"),
    )

    first_run, first_records, _ = collector.run_catalogue(
        CATALOGUE_URL,
        max_records=2,
    )
    second_run, second_records, _ = collector.run_catalogue(
        CATALOGUE_URL,
        max_records=2,
    )

    assert first_run.records_added == 2
    assert second_run.records_unchanged == 2
    assert [record.record_id for record in first_records] == [
        record.record_id for record in second_records
    ]
    assert [record.content_hash for record in first_records] == [
        record.content_hash for record in second_records
    ]


def test_catalogue_identity_mismatch_fails_before_write(
    tmp_path: Path,
    catalogue_fixture_path: Path,
    rich_course_fixture_path: Path,
) -> None:
    store = LocalDataStore(tmp_path / "store")
    collector = CoursesCollector(
        fetcher=MockFetcher({
            CATALOGUE_URL: catalogue_fixture_path,
            # COMP1110 content must not be accepted for the COMP1100 link.
            COURSE_URL: rich_course_fixture_path,
        }),
        store=store,
    )

    run, records, _ = collector.run_catalogue(
        CATALOGUE_URL,
        max_records=1,
    )

    assert run.status == IngestionRunStatus.FAILED
    assert "does not match catalogue identifier" in (run.error or "")
    assert records == []
    assert list(store.records_dir.glob("*.json")) == []


def test_zero_supported_candidates_is_suspicious_and_preserves_existing(
    tmp_path: Path,
) -> None:
    catalogue = tmp_path / "unsupported_only.html"
    catalogue.write_text(
        '<a href="/2026/major/COMS-MAJ">Computing Major</a>',
        encoding="utf-8",
    )
    collector = CoursesCollector(
        fetcher=MockFetcher({CATALOGUE_URL: catalogue}),
        store=LocalDataStore(tmp_path / "store"),
    )

    run, records, discovery = collector.run_catalogue(
        CATALOGUE_URL,
        max_records=2,
    )

    assert run.status == IngestionRunStatus.SUSPICIOUS_ZERO
    assert records == []
    assert discovery.counts_by_type["major"] == 1
    assert list(collector._store.records_dir.glob("*.json")) == []


def test_invalid_bound_is_rejected_before_fetch(tmp_path: Path) -> None:
    collector = CoursesCollector(
        fetcher=MockFetcher({}),
        store=LocalDataStore(tmp_path / "store"),
    )

    with pytest.raises(ValueError, match="max_records"):
        collector.run_catalogue(CATALOGUE_URL, max_records=0)


def test_lookalike_domain_is_rejected(tmp_path: Path) -> None:
    malicious_url = (
        "https://programsandcourses.anu.edu.au.evil.example/2026/search"
    )
    collector = CoursesCollector(
        fetcher=MockFetcher({}),
        store=LocalDataStore(tmp_path / "store"),
    )

    run, records, discovery = collector.run_catalogue(
        malicious_url,
        max_records=1,
    )

    assert run.status == IngestionRunStatus.FAILED
    assert records == []
    assert discovery.items == ()
