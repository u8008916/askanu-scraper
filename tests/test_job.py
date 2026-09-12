"""Day 6 one-shot job configuration, summary, and exit semantics."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from askanu_scraper.common.fetcher import BaseFetcher, FetchError, MockFetcher
from askanu_scraper.common.registry import UnapprovedSourceError
from askanu_scraper.common.storage import LocalDataStore
from askanu_scraper.job import (
    EXIT_CONFIGURATION_ERROR,
    EXIT_INGESTION_FAILURE,
    EXIT_SUCCESS,
    JobConfig,
    JobConfigurationError,
    execute_job,
    load_config,
    main,
    sanitize_error,
)


SOURCE_ID = "courses_programs_and_courses"
COURSE_URL = "https://programsandcourses.anu.edu.au/2026/course/COMP1100"
PROGRAM_URL = "https://programsandcourses.anu.edu.au/2026/program/BACCT"
COMP1110_URL = "https://programsandcourses.anu.edu.au/2026/course/COMP1110"
COURSE_ENDPOINT = (
    "https://programsandcourses.anu.edu.au/data/CourseSearch/GetCourses"
)
PROGRAM_ENDPOINT = (
    "https://programsandcourses.anu.edu.au/"
    "data/ProgramSearch/GetProgramsUnderGraduate"
)


class BoundedFixtureFetcher(BaseFetcher):
    """Fixture-backed equivalent of the bounded live catalogue requests."""

    def __init__(self, course_html: str, program_html: str) -> None:
        self._responses = {
            COURSE_ENDPOINT: json.dumps(
                {
                    "Items": [
                        {
                            "CourseCode": "COMP1100",
                            "Name": "Programming as Problem Solving",
                            "Year": 2026,
                        }
                    ],
                    "Suggestion": None,
                    "TotalCount": 1,
                }
            ),
            PROGRAM_ENDPOINT: json.dumps(
                {
                    "Items": [
                        {
                            "AcademicPlanCode": "BACCT",
                            "ProgramName": "Bachelor of Accounting",
                            "ProgramAcademicYear": "2026",
                        }
                    ],
                    "Suggestion": None,
                    "TotalCount": 1,
                }
            ),
            COURSE_URL: course_html,
            PROGRAM_URL: program_html,
        }

    def fetch(self, url: str) -> str:
        lookup = url.split("?", 1)[0]
        try:
            return self._responses[lookup]
        except KeyError as exc:
            raise FetchError("Fixture request was not registered") from exc


class AlwaysFailFetcher(BaseFetcher):
    def fetch(self, url: str) -> str:
        del url
        raise FetchError("simulated network failure")


class EmptyCourseCatalogueFetcher(BaseFetcher):
    def fetch(self, url: str) -> str:
        lookup = url.split("?", 1)[0]
        if lookup == COURSE_ENDPOINT:
            return json.dumps({"Items": [], "TotalCount": 0})
        if lookup == PROGRAM_ENDPOINT:
            return json.dumps(
                {
                    "Items": [
                        {
                            "AcademicPlanCode": "BACCT",
                            "ProgramName": "Bachelor of Accounting",
                            "ProgramAcademicYear": "2026",
                        }
                    ],
                    "TotalCount": 1,
                }
            )
        raise FetchError("Unexpected detail fetch")


def make_config(storage_path: Path, *, dry_run: bool = False) -> JobConfig:
    return JobConfig(
        source_id=SOURCE_ID,
        domain="courses",
        academic_year="2026",
        course_code=None,
        storage_backend="local",
        max_courses=1,
        max_programs=1,
        dry_run=dry_run,
        simulate_fetch_failure=False,
        storage_path=storage_path,
        timeout_seconds=30,
        min_request_interval_seconds=1.0,
    )


def test_successful_job_persists_and_returns_structured_zero_exit(
    tmp_path: Path,
    courses_fixture_html: str,
    bacct_fixture_html: str,
) -> None:
    storage_path = tmp_path / "store"
    result = execute_job(
        make_config(storage_path),
        fetcher=BoundedFixtureFetcher(courses_fixture_html, bacct_fixture_html),
        environ={},
        sleep_func=lambda _: None,
    )

    assert result.exit_code == EXIT_SUCCESS
    assert result.summary["schema_version"] == "2"
    assert result.summary["status"] == "SUCCESS"
    assert result.summary["academic_year"] == "2026"
    assert result.summary["requested_max_courses"] == 1
    assert result.summary["requested_max_programs"] == 1
    assert result.summary["records_seen"] == 2
    assert result.summary["records_added"] == 2
    assert result.summary["error"] is None
    assert result.summary["sanity"] == {
        "request_count": 4,
        "detail_request_count": 2,
        "discovery_counts": {
            "course": 1,
            "program": 1,
            "major": 0,
            "minor": 0,
            "specialisation": 0,
        },
        "duplicate_identity_count": 0,
        "duplicate_record_id_count": 0,
        "duplicate_canonical_url_count": 0,
        "rejected_candidate_count": 0,
    }
    assert len(list((storage_path / "records").glob("*.json"))) == 2
    assert len(list((storage_path / "runs").glob("*.json"))) == 1


def test_targeted_comp1110_job_is_idempotent_and_preserves_evidence(
    tmp_path: Path,
    rich_course_fixture_path: Path,
) -> None:
    storage_path = tmp_path / "store"
    config = replace(
        make_config(storage_path),
        course_code="COMP1110",
    )

    first = execute_job(
        config,
        fetcher=MockFetcher({COMP1110_URL: rich_course_fixture_path}),
        environ={},
    )
    stored_after_first = LocalDataStore(storage_path).get_record(
        "courses:course:COMP1110_2026"
    )

    assert first.exit_code == EXIT_SUCCESS
    assert first.summary["course_code"] == "COMP1110"
    assert first.summary["records_seen"] == 1
    assert first.summary["records_added"] == 1
    assert stored_after_first is not None
    assert stored_after_first.entity_id == "COMP1110_2026"
    assert stored_after_first.canonical_url == COMP1110_URL
    assert (
        stored_after_first.metadata_json["prerequisites"]
        == "COMP1100 or COMP1130"
    )

    second = execute_job(
        config,
        fetcher=MockFetcher({COMP1110_URL: rich_course_fixture_path}),
        environ={},
    )
    stored_after_second = LocalDataStore(storage_path).get_record(
        "courses:course:COMP1110_2026"
    )

    assert second.exit_code == EXIT_SUCCESS
    assert second.summary["records_seen"] == 1
    assert second.summary["records_added"] == 0
    assert second.summary["records_changed"] == 0
    assert second.summary["records_unchanged"] == 1
    assert stored_after_second is not None
    assert stored_after_second.content_hash == stored_after_first.content_hash
    assert stored_after_second.index_status == stored_after_first.index_status
    assert len(list((storage_path / "records").glob("*.json"))) == 1
    assert len(list((storage_path / "runs").glob("*.json"))) == 2

    record_before_failure = next(
        (storage_path / "records").glob("*.json")
    ).read_bytes()
    failed = execute_job(
        config,
        fetcher=AlwaysFailFetcher(),
        environ={},
    )
    record_after_failure = next(
        (storage_path / "records").glob("*.json")
    ).read_bytes()

    assert failed.exit_code == EXIT_INGESTION_FAILURE
    assert failed.summary["status"] == "FAILED"
    assert record_after_failure == record_before_failure


def test_job_accepts_injected_persistence_boundary(
    tmp_path: Path,
    rich_course_fixture_path: Path,
) -> None:
    configured_path = tmp_path / "unused-local-default"
    injected_path = tmp_path / "injected-store"
    config = replace(
        make_config(configured_path),
        course_code="COMP1110",
    )
    store = LocalDataStore(injected_path)

    result = execute_job(
        config,
        fetcher=MockFetcher({COMP1110_URL: rich_course_fixture_path}),
        store=store,
        environ={},
    )

    assert result.exit_code == EXIT_SUCCESS
    assert store.get_record("courses:course:COMP1110_2026") is not None
    assert not configured_path.exists()


def test_atomic_persistence_failure_returns_safe_summary_and_no_records(
    tmp_path: Path,
    rich_course_fixture_path: Path,
) -> None:
    class FailingBatchStore(LocalDataStore):
        def save_records_and_run(self, records, run):
            del records, run
            raise RuntimeError("database detail that must not escape")

    storage_path = tmp_path / "store"
    config = replace(
        make_config(storage_path),
        course_code="COMP1110",
    )
    store = FailingBatchStore(storage_path)

    result = execute_job(
        config,
        fetcher=MockFetcher({COMP1110_URL: rich_course_fixture_path}),
        store=store,
        environ={},
    )

    assert result.exit_code == EXIT_INGESTION_FAILURE
    assert result.summary["status"] == "FAILED"
    assert result.summary["records_seen"] == 1
    assert result.summary["records_added"] == 0
    assert "database detail" not in json.dumps(result.summary)
    assert list((storage_path / "records").glob("*.json")) == []
    assert len(list((storage_path / "runs").glob("*.json"))) == 1


def test_dry_run_compares_but_does_not_change_existing_storage(
    tmp_path: Path,
    courses_fixture_html: str,
    bacct_fixture_html: str,
) -> None:
    storage_path = tmp_path / "store"
    fetcher = BoundedFixtureFetcher(courses_fixture_html, bacct_fixture_html)
    execute_job(
        make_config(storage_path),
        fetcher=fetcher,
        environ={},
        sleep_func=lambda _: None,
    )
    before = {
        path.relative_to(storage_path): path.read_bytes()
        for path in storage_path.rglob("*.json")
    }

    result = execute_job(
        make_config(storage_path, dry_run=True),
        fetcher=BoundedFixtureFetcher(courses_fixture_html, bacct_fixture_html),
        environ={},
        sleep_func=lambda _: None,
    )
    after = {
        path.relative_to(storage_path): path.read_bytes()
        for path in storage_path.rglob("*.json")
    }

    assert result.exit_code == EXIT_SUCCESS
    assert result.summary["dry_run"] is True
    assert result.summary["records_unchanged"] == 2
    assert before == after


def test_dry_run_against_empty_path_creates_no_directory(
    tmp_path: Path,
    courses_fixture_html: str,
    bacct_fixture_html: str,
) -> None:
    storage_path = tmp_path / "never-created"
    result = execute_job(
        make_config(storage_path, dry_run=True),
        fetcher=BoundedFixtureFetcher(courses_fixture_html, bacct_fixture_html),
        environ={},
        sleep_func=lambda _: None,
    )

    assert result.summary["records_added"] == 2
    assert not storage_path.exists()


def test_fetch_failure_is_nonzero_and_preserves_last_known_good(
    tmp_path: Path,
    courses_fixture_html: str,
    bacct_fixture_html: str,
) -> None:
    storage_path = tmp_path / "store"
    execute_job(
        make_config(storage_path),
        fetcher=BoundedFixtureFetcher(courses_fixture_html, bacct_fixture_html),
        environ={},
        sleep_func=lambda _: None,
    )
    record_paths = list((storage_path / "records").glob("*.json"))
    before = {path.name: path.read_bytes() for path in record_paths}

    result = execute_job(
        make_config(storage_path),
        fetcher=AlwaysFailFetcher(),
        environ={},
        sleep_func=lambda _: None,
    )
    after = {path.name: path.read_bytes() for path in record_paths}

    assert result.exit_code == EXIT_INGESTION_FAILURE
    assert result.summary["status"] == "FAILED"
    assert result.summary["records_seen"] == 0
    assert before == after


def test_source_and_domain_must_match_approved_implemented_collector(
    tmp_path: Path,
) -> None:
    wrong_domain = replace(make_config(tmp_path), domain="jobs")

    with pytest.raises(JobConfigurationError, match="does not belong"):
        execute_job(wrong_domain, fetcher=AlwaysFailFetcher(), environ={})


def test_inactive_source_is_rejected_before_fetch(tmp_path: Path) -> None:
    inactive = replace(
        make_config(tmp_path),
        source_id="rubric_unified_search",
        domain="events",
    )

    with pytest.raises(UnapprovedSourceError, match="not approved for production"):
        execute_job(inactive, fetcher=AlwaysFailFetcher(), environ={})


def test_approved_but_unimplemented_domain_is_rejected_before_fetch(
    tmp_path: Path,
) -> None:
    jobs = replace(
        make_config(tmp_path),
        source_id="jobs_anu_search",
        domain="jobs",
    )

    with pytest.raises(JobConfigurationError, match="Only the approved Courses"):
        execute_job(jobs, fetcher=AlwaysFailFetcher(), environ={})


def test_suspicious_zero_is_nonzero_and_writes_no_records(
    tmp_path: Path,
) -> None:
    storage_path = tmp_path / "store"
    result = execute_job(
        make_config(storage_path),
        fetcher=EmptyCourseCatalogueFetcher(),
        environ={},
        sleep_func=lambda _: None,
    )

    assert result.exit_code == EXIT_INGESTION_FAILURE
    assert result.summary["status"] == "SUSPICIOUS_ZERO"
    assert result.summary["sanity"]["request_count"] == 2
    assert result.summary["sanity"]["detail_request_count"] == 0
    assert result.summary["sanity"]["discovery_counts"] == {
        "course": 0,
        "program": 1,
        "major": 0,
        "minor": 0,
        "specialisation": 0,
    }
    assert list((storage_path / "records").glob("*.json")) == []


def test_config_is_environment_driven_and_cli_takes_precedence(tmp_path: Path) -> None:
    env = {
        "SCRAPER_ACADEMIC_YEAR": "2026",
        "SCRAPER_MAX_COURSES": "1",
        "SCRAPER_MAX_PROGRAMS": "1",
        "SCRAPER_DRY_RUN": "true",
        "SCRAPER_STORAGE_PATH": str(tmp_path / "from-env"),
    }

    config = load_config(["--academic-year", "2027", "--no-dry-run"], env)

    assert config.academic_year == "2027"
    assert config.dry_run is False
    assert config.storage_path == tmp_path / "from-env"


def test_course_code_is_normalized_from_environment() -> None:
    config = load_config(
        ["--academic-year", "2026"],
        {"SCRAPER_COURSE_CODE": " comp 1110 "},
    )

    assert config.course_code == "COMP1110"


def test_postgres_storage_backend_is_explicit() -> None:
    config = load_config(
        ["--academic-year", "2026"],
        {"SCRAPER_STORAGE_BACKEND": "postgres"},
    )

    assert config.storage_backend == "postgres"


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        ([], "academic-year"),
        (["--academic-year", "20XX"], "four-digit"),
        (
            ["--academic-year", "2026", "--course-code", "not-a-course"],
            "valid course code",
        ),
        (
            ["--academic-year", "2026", "--storage-backend", "unknown"],
            "local or postgres",
        ),
        (
            [
                "--academic-year",
                "2026",
                "--max-courses",
                "3",
                "--max-programs",
                "2",
            ],
            "must not exceed 4",
        ),
        (
            [
                "--academic-year",
                "2026",
                "--min-request-interval-seconds",
                "0",
            ],
            "between 1.0 and 60.0",
        ),
    ],
)
def test_invalid_configuration_is_rejected(argv: list[str], message: str) -> None:
    with pytest.raises(JobConfigurationError, match=message):
        load_config(argv, {})


def test_error_sanitizer_removes_secret_values_and_url_query() -> None:
    secret = "do-not-print-this"
    message = (
        f"DB failed: {secret}; "
        "https://user:password@example.test/path?token=also-secret"
    )

    sanitized = sanitize_error(message, {"DATABASE_URL": secret})

    assert secret not in sanitized
    assert "password" not in sanitized
    assert "also-secret" not in sanitized
    assert "[REDACTED]" in sanitized


def test_cli_failure_drill_emits_json_and_returns_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(
        [
            "--academic-year",
            "2026",
            "--max-courses",
            "1",
            "--max-programs",
            "1",
            "--storage-path",
            str(tmp_path / "store"),
            "--dry-run",
            "--simulate-fetch-failure",
        ],
        environ={},
    )
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == EXIT_INGESTION_FAILURE
    assert summary["status"] == "FAILED"
    assert summary["exit_code"] == EXIT_INGESTION_FAILURE
    assert not (tmp_path / "store").exists()


def test_cli_configuration_error_is_structured_and_does_not_echo_input(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        ["--academic-year", "invalid", "--source-id", "sensitive-value"],
        environ={},
    )
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == EXIT_CONFIGURATION_ERROR
    assert summary["status"] == "CONFIGURATION_ERROR"
    assert summary["source_id"] is None
    assert "sensitive-value" not in json.dumps(summary)


def test_cli_unapproved_source_does_not_echo_selected_value(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "--academic-year",
            "2026",
            "--source-id",
            "secret-looking-invalid-source",
        ],
        environ={},
    )
    output = capsys.readouterr().out
    summary = json.loads(output)

    assert exit_code == EXIT_CONFIGURATION_ERROR
    assert summary["status"] == "CONFIGURATION_ERROR"
    assert "secret-looking-invalid-source" not in output
