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
SECOND_COURSE_URL = "https://programsandcourses.anu.edu.au/2026/course/COMP1110"
SECOND_PROGRAM_URL = "https://programsandcourses.anu.edu.au/2026/program/BFIN"
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
        "course": 2,
        "program": 2,
        "major": 1,
        "minor": 1,
        "specialisation": 1,
    }
    assert [item.discovery_id for item in result.items] == [
        "course:COMP1100_2026",
        "program:BACCT_2026",
        "course:COMP1110_2026",
        "program:BFIN_2026",
        "major:COMS-MAJ_2026",
        "minor:STAT-MIN_2026",
        "specialisation:ACCT-SPEC_2026",
    ]
    assert result.duplicate_identities == ("course:COMP1100_2026",)
    assert len(result.rejected_links) == 2
    assert [item.discovery_id for item in result.persisted_candidates] == [
        "course:COMP1100_2026",
        "program:BACCT_2026",
        "course:COMP1110_2026",
        "program:BFIN_2026",
    ]


def test_catalogue_run_is_bounded_and_does_not_persist_uncontracted_types(
    tmp_path: Path,
    catalogue_fixture_path: Path,
    courses_fixture_path: Path,
    bacct_fixture_path: Path,
    rich_course_fixture_path: Path,
    bfin_fixture_path: Path,
) -> None:
    fetcher = MockFetcher({
        CATALOGUE_URL: catalogue_fixture_path,
        COURSE_URL: courses_fixture_path,
        PROGRAM_URL: bacct_fixture_path,
        SECOND_COURSE_URL: rich_course_fixture_path,
        SECOND_PROGRAM_URL: bfin_fixture_path,
    })
    store = LocalDataStore(tmp_path / "store")
    collector = CoursesCollector(fetcher=fetcher, store=store)

    run, records, discovery = collector.run_catalogue(
        CATALOGUE_URL,
        max_records=4,
    )

    assert run.status == IngestionRunStatus.SUCCESS
    assert run.records_seen == 4
    assert run.records_added == 4
    assert [record.record_id for record in records] == [
        "courses:course:COMP1100_2026",
        "courses:program:BACCT_2026",
        "courses:course:COMP1110_2026",
        "courses:program:BFIN_2026",
    ]
    assert discovery.counts_by_type["major"] == 1
    assert collector.last_run_sanity == {
        "request_count": 5,
        "detail_request_count": 4,
        "discovery_counts": {
            "course": 2,
            "program": 2,
            "major": 1,
            "minor": 1,
            "specialisation": 1,
        },
        "duplicate_identity_count": 1,
        "duplicate_record_id_count": 0,
        "duplicate_canonical_url_count": 0,
        "rejected_candidate_count": 2,
    }
    assert len(list(store.records_dir.glob("*.json"))) == 4


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
    assert discovery.counts_by_type["program"] == 2
    assert list(store.records_dir.glob("*.json")) == []


def test_catalogue_rerun_preserves_ids_and_hashes(
    tmp_path: Path,
    catalogue_fixture_path: Path,
    courses_fixture_path: Path,
    bacct_fixture_path: Path,
    rich_course_fixture_path: Path,
    bfin_fixture_path: Path,
) -> None:
    fetcher = MockFetcher({
        CATALOGUE_URL: catalogue_fixture_path,
        COURSE_URL: courses_fixture_path,
        PROGRAM_URL: bacct_fixture_path,
        SECOND_COURSE_URL: rich_course_fixture_path,
        SECOND_PROGRAM_URL: bfin_fixture_path,
    })
    collector = CoursesCollector(
        fetcher=fetcher,
        store=LocalDataStore(tmp_path / "store"),
    )

    first_run, first_records, _ = collector.run_catalogue(
        CATALOGUE_URL,
        max_records=4,
    )
    second_run, second_records, _ = collector.run_catalogue(
        CATALOGUE_URL,
        max_records=4,
    )

    assert first_run.records_added == 4
    assert second_run.records_unchanged == 4
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
    courses_fixture_path: Path,
) -> None:
    catalogue = tmp_path / "unsupported_only.html"
    catalogue.write_text(
        '<a href="/2026/major/COMS-MAJ">Computing Major</a>',
        encoding="utf-8",
    )
    store = LocalDataStore(tmp_path / "store")
    seed_collector = CoursesCollector(
        fetcher=MockFetcher({COURSE_URL: courses_fixture_path}),
        store=store,
    )
    seed_run, _ = seed_collector.run_single(COURSE_URL)
    assert seed_run.status == IngestionRunStatus.SUCCESS
    stored_path = next(store.records_dir.glob("*.json"))
    before = stored_path.read_bytes()

    collector = CoursesCollector(
        fetcher=MockFetcher({CATALOGUE_URL: catalogue}),
        store=store,
    )

    run, records, discovery = collector.run_catalogue(
        CATALOGUE_URL,
        max_records=2,
    )

    assert run.status == IngestionRunStatus.SUSPICIOUS_ZERO
    assert records == []
    assert discovery.counts_by_type["major"] == 1
    assert collector.last_run_sanity["request_count"] == 1
    assert collector.last_run_sanity["detail_request_count"] == 0
    assert collector.last_run_sanity["discovery_counts"]["major"] == 1
    assert list(store.records_dir.glob("*.json")) == [stored_path]
    assert stored_path.read_bytes() == before


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


def test_live_course_api_items_become_catalogue_candidates() -> None:
    payload = {
        "Items": [
            {
                "CourseCode": "ARCH8046",
                "Name": " Microanalysis in Archaeological Science",
                "Session": "",
                "Career": "Postgraduate",
                "Units": 6.0,
                "ModeOfDelivery": "In Person",
                "Year": 2026,
            },
            {
                "CourseCode": "COMP1110",
                "Name": "Structured Programming",
                "Session": "",
                "Career": "Undergraduate",
                "Units": 6.0,
                "ModeOfDelivery": "In Person",
                "Year": 2026,
            },
        ],
        "Suggestion": None,
        "TotalCount": 500,
    }

    result = CoursesCatalogueDiscovery().discover_api_payload(
        payload,
        entity_type="course",
        canonical_root=CANONICAL_ROOT,
    )

    assert result.counts_by_type["course"] == 2
    assert [item.discovery_id for item in result.persisted_candidates] == [
        "course:ARCH8046_2026",
        "course:COMP1110_2026",
    ]
    assert [item.url for item in result.persisted_candidates] == [
        "https://programsandcourses.anu.edu.au/2026/course/ARCH8046",
        "https://programsandcourses.anu.edu.au/2026/course/COMP1110",
    ]


def test_live_program_api_items_become_catalogue_candidates() -> None:
    payload = {
        "Items": [
            {
                "AcademicPlanCode": "BACCT",
                "ProgramName": "Bachelor of Accounting",
                "ProgramAcademicYear": "2026",
                "AcademicCareer": "Undergraduate",
            },
            {
                "AcademicPlanCode": "BFIN",
                "ProgramName": "Bachelor of Finance",
                "ProgramAcademicYear": "2026",
                "AcademicCareer": "Undergraduate",
            },
        ],
        "Suggestion": None,
        "TotalCount": 95,
    }

    result = CoursesCatalogueDiscovery().discover_api_payload(
        payload,
        entity_type="program",
        canonical_root=CANONICAL_ROOT,
    )

    assert result.counts_by_type["program"] == 2
    assert [item.discovery_id for item in result.persisted_candidates] == [
        "program:BACCT_2026",
        "program:BFIN_2026",
    ]
    assert [item.url for item in result.persisted_candidates] == [
        "https://programsandcourses.anu.edu.au/2026/program/BACCT",
        "https://programsandcourses.anu.edu.au/2026/program/BFIN",
    ]


def test_catalogue_run_spaces_requests_without_real_sleep(
    tmp_path: Path,
    catalogue_fixture_path: Path,
    courses_fixture_path: Path,
    bacct_fixture_path: Path,
) -> None:
    sleeps: list[float] = []

    collector = CoursesCollector(
        fetcher=MockFetcher({
            CATALOGUE_URL: catalogue_fixture_path,
            COURSE_URL: courses_fixture_path,
            PROGRAM_URL: bacct_fixture_path,
        }),
        store=LocalDataStore(tmp_path / "store"),
        min_request_interval_seconds=1.0,
        sleep_func=sleeps.append,
    )

    run, records, _ = collector.run_catalogue(
        CATALOGUE_URL,
        max_records=2,
    )

    assert run.status == IngestionRunStatus.SUCCESS
    assert len(records) == 2

    # catalogue request + 2 detail requests = 3 requests,
    # therefore 2 waits between requests.
    assert sleeps == [1.0, 1.0]


def test_live_catalogue_run_uses_api_results_and_ingests_courses_and_programs(
    tmp_path: Path,
    courses_fixture_path: Path,
    rich_course_fixture_path: Path,
    bacct_fixture_path: Path,
    bfin_fixture_path: Path,
) -> None:
    import json

    course_endpoint = (
        "https://programsandcourses.anu.edu.au/"
        "data/CourseSearch/GetCourses"
    )
    program_endpoint = (
        "https://programsandcourses.anu.edu.au/"
        "data/ProgramSearch/GetProgramsUnderGraduate"
    )

    responses = {
        course_endpoint: json.dumps({
            "Items": [
                {
                    "CourseCode": "COMP1100",
                    "Name": "Programming as Problem Solving",
                    "Year": 2026,
                },
                {
                    "CourseCode": "COMP1110",
                    "Name": "Structured Programming",
                    "Year": 2026,
                },
            ],
            "Suggestion": None,
            "TotalCount": 500,
        }),
        program_endpoint: json.dumps({
            "Items": [
                {
                    "AcademicPlanCode": "BACCT",
                    "ProgramName": "Bachelor of Accounting",
                    "ProgramAcademicYear": "2026",
                },
                {
                    "AcademicPlanCode": "BFIN",
                    "ProgramName": "Bachelor of Finance",
                    "ProgramAcademicYear": "2026",
                },
            ],
            "Suggestion": None,
            "TotalCount": 95,
        }),
        COURSE_URL: courses_fixture_path.read_text(encoding="utf-8"),
        SECOND_COURSE_URL: rich_course_fixture_path.read_text(encoding="utf-8"),
        PROGRAM_URL: bacct_fixture_path.read_text(encoding="utf-8"),
        SECOND_PROGRAM_URL: bfin_fixture_path.read_text(encoding="utf-8"),
    }

    class LiveApiFixtureFetcher:
        def __init__(self) -> None:
            self.requested_urls: list[str] = []

        def fetch(self, url: str) -> str:
            self.requested_urls.append(url)

            # Ignore query-string ordering for the two API requests.
            base_url = url.split("?", 1)[0]

            if base_url in responses:
                return responses[base_url]

            if url in responses:
                return responses[url]

            raise AssertionError(f"Unexpected fetch: {url}")

    fetcher = LiveApiFixtureFetcher()

    collector = CoursesCollector(
        fetcher=fetcher,
        store=LocalDataStore(tmp_path / "store"),
    )

    run, records, discovery = collector.run_live_catalogue(
        academic_year="2026",
        max_courses=2,
        max_programs=2,
    )

    assert run.status == IngestionRunStatus.SUCCESS

    assert [record.record_id for record in records] == [
        "courses:course:COMP1100_2026",
        "courses:course:COMP1110_2026",
        "courses:program:BACCT_2026",
        "courses:program:BFIN_2026",
    ]

    assert discovery.counts_by_type["course"] == 2
    assert discovery.counts_by_type["program"] == 2

    assert len(fetcher.requested_urls) == 6


def test_request_spacing_defaults_safe_for_live_and_fast_for_mock(
    tmp_path: Path,
) -> None:
    from askanu_scraper.common.fetcher import HttpFetcher

    live_collector = CoursesCollector(
        fetcher=HttpFetcher(),
        store=LocalDataStore(tmp_path / "live"),
    )

    mock_collector = CoursesCollector(
        fetcher=MockFetcher({}),
        store=LocalDataStore(tmp_path / "mock"),
    )

    assert live_collector._min_request_interval_seconds == 1.0
    assert mock_collector._min_request_interval_seconds == 0.0
