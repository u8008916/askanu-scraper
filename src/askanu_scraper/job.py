"""One-shot scraper entrypoint for local execution and Cloud Run Jobs."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sys
import time
from collections.abc import Callable, Mapping, Sequence

from askanu_scraper.common.fetcher import BaseFetcher, FetchError, HttpFetcher
from askanu_scraper.common.models import IngestionRun, IngestionRunStatus
from askanu_scraper.common.normalizer import now_canberra
from askanu_scraper.common.registry import (
    UnapprovedSourceError,
    assert_source_allowed,
)
from askanu_scraper.common.storage import DataStore, LocalDataStore
from askanu_scraper.sources.courses.collector import (
    SOURCE_ID as COURSES_SOURCE_ID,
    CoursesCollector,
)
from askanu_scraper.sources.scholarships import (
    LISTING_URL as SCHOLARSHIPS_LISTING_URL,
    SOURCE_ID as SCHOLARSHIPS_SOURCE_ID,
    ScholarshipsCollector,
)
from askanu_scraper.sources.jobs import (
    LISTING_URL as JOBS_LISTING_URL,
    SOURCE_ID as JOBS_SOURCE_ID,
    JobsCollector,
)
from askanu_scraper.sources.accommodation import (
    LISTING_URL as ACCOMMODATION_LISTING_URL,
    SOURCE_ID as ACCOMMODATION_SOURCE_ID,
    AccommodationCollector,
)
from askanu_scraper.sources.support import (
    LISTING_URL as SUPPORT_LISTING_URL,
    SOURCE_ID as SUPPORT_SOURCE_ID,
    SupportCollector,
)


EXIT_SUCCESS = 0
EXIT_INGESTION_FAILURE = 1
EXIT_CONFIGURATION_ERROR = 2
SUMMARY_SCHEMA_VERSION = "2"


class JobConfigurationError(ValueError):
    """Raised when job configuration is missing, unsafe, or unsupported."""


class JobArgumentParser(argparse.ArgumentParser):
    """Argument parser that lets configuration failures use JSON output."""

    def error(self, message: str) -> None:
        raise JobConfigurationError(message)


class SimulatedFailureFetcher(BaseFetcher):
    """Deterministic fetch failure used for the documented failure drill."""

    def fetch(self, url: str) -> str:
        del url
        raise FetchError("Simulated fetch failure")


@dataclass(frozen=True)
class JobConfig:
    """Validated environment/CLI configuration for one bounded run."""

    source_id: str
    domain: str
    academic_year: str | None
    course_code: str | None
    storage_backend: str
    max_courses: int
    max_programs: int
    dry_run: bool
    simulate_fetch_failure: bool
    storage_path: Path
    timeout_seconds: int
    min_request_interval_seconds: float
    max_scholarship_listing_pages: int = 1
    max_scholarship_details: int = 10
    scholarship_postgres_approved: bool = False
    max_jobs_listing_pages: int = 1
    max_job_details: int = 10
    jobs_postgres_approved: bool = False
    max_accommodation_details: int = 10
    accommodation_postgres_approved: bool = False
    max_support_details: int = 6
    support_postgres_approved: bool = False


@dataclass(frozen=True)
class JobResult:
    """Structured summary plus the process exit code it represents."""

    summary: dict[str, object]
    exit_code: int


def _parse_bool(value: str, *, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise JobConfigurationError(f"{name} must be true or false")


def _parse_int(value: str, *, name: str, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise JobConfigurationError(f"{name} must be an integer") from exc

    if not minimum <= parsed <= maximum:
        raise JobConfigurationError(
            f"{name} must be between {minimum} and {maximum}"
        )
    return parsed


def _parse_float(
    value: str,
    *,
    name: str,
    minimum: float,
    maximum: float,
) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise JobConfigurationError(f"{name} must be a number") from exc

    if not minimum <= parsed <= maximum:
        raise JobConfigurationError(
            f"{name} must be between {minimum} and {maximum}"
        )
    return parsed


def build_parser() -> JobArgumentParser:
    """Build the CLI parser; environment fallbacks are applied separately."""

    parser = JobArgumentParser(
        prog="askanu-scraper-job",
        description="Run one bounded approved-source scraper ingestion.",
    )
    parser.add_argument("--source-id")
    parser.add_argument("--domain")
    parser.add_argument("--academic-year")
    parser.add_argument("--course-code")
    parser.add_argument("--max-courses")
    parser.add_argument("--max-programs")
    parser.add_argument("--max-scholarship-listing-pages")
    parser.add_argument("--max-scholarship-details")
    parser.add_argument("--max-jobs-listing-pages")
    parser.add_argument("--max-job-details")
    parser.add_argument("--max-accommodation-details")
    parser.add_argument("--max-support-details")
    parser.add_argument("--storage-path")
    parser.add_argument("--storage-backend")
    parser.add_argument("--timeout-seconds")
    parser.add_argument("--min-request-interval-seconds")
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    parser.add_argument(
        "--simulate-fetch-failure",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    return parser


def load_config(
    argv: Sequence[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> JobConfig:
    """Resolve CLI-over-environment configuration and validate bounds."""

    env = os.environ if environ is None else environ
    args = build_parser().parse_args(argv)

    source_id = args.source_id or env.get(
        "SCRAPER_SOURCE_ID", COURSES_SOURCE_ID
    )
    domain = args.domain or env.get("SCRAPER_DOMAIN", "courses")
    raw_academic_year = args.academic_year or env.get("SCRAPER_ACADEMIC_YEAR", "")
    academic_year = raw_academic_year or None
    if source_id == COURSES_SOURCE_ID and (
        academic_year is None
        or re.fullmatch(r"\d{4}", academic_year) is None
    ):
        raise JobConfigurationError(
            "SCRAPER_ACADEMIC_YEAR/--academic-year must be a four-digit year"
        )
    if academic_year is not None and re.fullmatch(r"\d{4}", academic_year) is None:
        raise JobConfigurationError(
            "SCRAPER_ACADEMIC_YEAR/--academic-year must be a four-digit year"
        )

    raw_course_code = args.course_code or env.get("SCRAPER_COURSE_CODE", "")
    course_code = re.sub(r"\s+", "", raw_course_code).upper() or None
    if (
        course_code is not None
        and re.fullmatch(r"[A-Z]{4}\d{4}[A-Z]?", course_code) is None
    ):
        raise JobConfigurationError(
            "SCRAPER_COURSE_CODE/--course-code must be a valid course code"
        )
    if source_id != COURSES_SOURCE_ID and course_code is not None:
        raise JobConfigurationError(
            "SCRAPER_COURSE_CODE/--course-code is only valid for Courses"
        )

    max_courses = _parse_int(
        args.max_courses or env.get("SCRAPER_MAX_COURSES", "2"),
        name="SCRAPER_MAX_COURSES/--max-courses",
        minimum=1,
        maximum=4,
    )
    max_programs = _parse_int(
        args.max_programs or env.get("SCRAPER_MAX_PROGRAMS", "2"),
        name="SCRAPER_MAX_PROGRAMS/--max-programs",
        minimum=1,
        maximum=4,
    )

    if source_id == COURSES_SOURCE_ID and max_courses + max_programs > 4:
        raise JobConfigurationError(
            "The combined course/program sample must not exceed 4 records"
        )
    max_scholarship_listing_pages = _parse_int(
        args.max_scholarship_listing_pages
        or env.get("SCRAPER_MAX_SCHOLARSHIP_LISTING_PAGES", "1"),
        name=(
            "SCRAPER_MAX_SCHOLARSHIP_LISTING_PAGES/"
            "--max-scholarship-listing-pages"
        ),
        minimum=1,
        maximum=100,
    )
    max_scholarship_details = _parse_int(
        args.max_scholarship_details
        or env.get("SCRAPER_MAX_SCHOLARSHIP_DETAILS", "10"),
        name="SCRAPER_MAX_SCHOLARSHIP_DETAILS/--max-scholarship-details",
        minimum=1,
        maximum=2000,
    )
    max_jobs_listing_pages = _parse_int(
        args.max_jobs_listing_pages
        or env.get("SCRAPER_MAX_JOBS_LISTING_PAGES", "1"),
        name="SCRAPER_MAX_JOBS_LISTING_PAGES/--max-jobs-listing-pages",
        minimum=1,
        maximum=100,
    )
    max_job_details = _parse_int(
        args.max_job_details or env.get("SCRAPER_MAX_JOB_DETAILS", "10"),
        name="SCRAPER_MAX_JOB_DETAILS/--max-job-details",
        minimum=1,
        maximum=2000,
    )
    max_accommodation_details = _parse_int(
        args.max_accommodation_details
        or env.get("SCRAPER_MAX_ACCOMMODATION_DETAILS", "10"),
        name="SCRAPER_MAX_ACCOMMODATION_DETAILS/--max-accommodation-details",
        minimum=1,
        maximum=19,
    )
    max_support_details = _parse_int(
        args.max_support_details or env.get("SCRAPER_MAX_SUPPORT_DETAILS", "6"),
        name="SCRAPER_MAX_SUPPORT_DETAILS/--max-support-details",
        minimum=1,
        maximum=6,
    )

    dry_run = (
        args.dry_run
        if args.dry_run is not None
        else _parse_bool(
            env.get("SCRAPER_DRY_RUN", "false"),
            name="SCRAPER_DRY_RUN",
        )
    )
    simulate_fetch_failure = (
        args.simulate_fetch_failure
        if args.simulate_fetch_failure is not None
        else _parse_bool(
            env.get("SCRAPER_SIMULATE_FETCH_FAILURE", "false"),
            name="SCRAPER_SIMULATE_FETCH_FAILURE",
        )
    )
    scholarship_postgres_approved = (
        _parse_bool(
            env.get("SCRAPER_SCHOLARSHIP_POSTGRES_APPROVED", "false"),
            name="SCRAPER_SCHOLARSHIP_POSTGRES_APPROVED",
        )
        if source_id == SCHOLARSHIPS_SOURCE_ID
        else False
    )
    jobs_postgres_approved = (
        _parse_bool(
            env.get("SCRAPER_JOBS_POSTGRES_APPROVED", "false"),
            name="SCRAPER_JOBS_POSTGRES_APPROVED",
        )
        if source_id == JOBS_SOURCE_ID
        else False
    )
    accommodation_postgres_approved = (
        _parse_bool(
            env.get("SCRAPER_ACCOMMODATION_POSTGRES_APPROVED", "false"),
            name="SCRAPER_ACCOMMODATION_POSTGRES_APPROVED",
        )
        if source_id == ACCOMMODATION_SOURCE_ID
        else False
    )
    support_postgres_approved = (
        _parse_bool(
            env.get("SCRAPER_SUPPORT_POSTGRES_APPROVED", "false"),
            name="SCRAPER_SUPPORT_POSTGRES_APPROVED",
        )
        if source_id == SUPPORT_SOURCE_ID
        else False
    )
    timeout_seconds = _parse_int(
        args.timeout_seconds or env.get("SCRAPER_TIMEOUT_SECONDS", "30"),
        name="SCRAPER_TIMEOUT_SECONDS/--timeout-seconds",
        minimum=1,
        maximum=300,
    )
    min_request_interval_seconds = _parse_float(
        args.min_request_interval_seconds
        or env.get("SCRAPER_MIN_REQUEST_INTERVAL_SECONDS", "1"),
        name=(
            "SCRAPER_MIN_REQUEST_INTERVAL_SECONDS/"
            "--min-request-interval-seconds"
        ),
        minimum=1.0,
        maximum=60.0,
    )
    storage_path = Path(
        args.storage_path or env.get("SCRAPER_STORAGE_PATH", "local-data")
    )
    storage_backend = (
        args.storage_backend or env.get("SCRAPER_STORAGE_BACKEND", "local")
    ).strip().lower()
    if storage_backend not in {"local", "postgres"}:
        raise JobConfigurationError(
            "SCRAPER_STORAGE_BACKEND/--storage-backend must be local or postgres"
        )

    return JobConfig(
        source_id=source_id,
        domain=domain,
        academic_year=academic_year,
        course_code=course_code,
        storage_backend=storage_backend,
        max_courses=max_courses,
        max_programs=max_programs,
        dry_run=dry_run,
        simulate_fetch_failure=simulate_fetch_failure,
        storage_path=storage_path,
        timeout_seconds=timeout_seconds,
        min_request_interval_seconds=min_request_interval_seconds,
        max_scholarship_listing_pages=max_scholarship_listing_pages,
        max_scholarship_details=max_scholarship_details,
        scholarship_postgres_approved=scholarship_postgres_approved,
        max_jobs_listing_pages=max_jobs_listing_pages,
        max_job_details=max_job_details,
        jobs_postgres_approved=jobs_postgres_approved,
        max_accommodation_details=max_accommodation_details,
        accommodation_postgres_approved=accommodation_postgres_approved,
        max_support_details=max_support_details,
        support_postgres_approved=support_postgres_approved,
    )


def _isoformat(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _secret_values(environ: Mapping[str, str]) -> tuple[str, ...]:
    sensitive_name = re.compile(
        r"(?:SECRET|TOKEN|PASSWORD|CREDENTIAL|DATABASE_URL|API_KEY|PRIVATE_KEY)",
        re.IGNORECASE,
    )
    return tuple(
        value
        for key, value in environ.items()
        if value and len(value) >= 4 and sensitive_name.search(key)
    )


def sanitize_error(message: str, environ: Mapping[str, str]) -> str:
    """Remove known secret values and URL credentials/query strings."""

    sanitized = message
    for value in sorted(_secret_values(environ), key=len, reverse=True):
        sanitized = sanitized.replace(value, "[REDACTED]")

    sanitized = re.sub(
        r"(https?://)([^\s/@:]+):([^\s/@]+)@",
        r"\1[REDACTED]@",
        sanitized,
    )
    sanitized = re.sub(
        r"(https?://[^\s?#]+)[?#][^\s]+",
        r"\1?[REDACTED]",
        sanitized,
    )
    sanitized = re.sub(
        r"(?i)(password|token|secret|api[_-]?key)\s*[=:]\s*[^\s,;]+",
        r"\1=[REDACTED]",
        sanitized,
    )
    return sanitized[:500]


def _summary_from_run(
    run: IngestionRun,
    *,
    config: JobConfig,
    duration_ms: int,
    environ: Mapping[str, str],
    sanity: Mapping[str, object],
) -> JobResult:
    succeeded = run.status == IngestionRunStatus.SUCCESS
    exit_code = EXIT_SUCCESS if succeeded else EXIT_INGESTION_FAILURE
    summary: dict[str, object] = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "run_id": run.run_id,
        "source_id": config.source_id,
        "domain": config.domain,
        "academic_year": config.academic_year,
        "course_code": config.course_code,
        "storage_backend": config.storage_backend,
        "requested_max_courses": (
            config.max_courses if config.source_id == COURSES_SOURCE_ID else None
        ),
        "requested_max_programs": (
            config.max_programs if config.source_id == COURSES_SOURCE_ID else None
        ),
        "requested_max_scholarship_listing_pages": (
            config.max_scholarship_listing_pages
            if config.source_id == SCHOLARSHIPS_SOURCE_ID
            else None
        ),
        "requested_max_scholarship_details": (
            config.max_scholarship_details
            if config.source_id == SCHOLARSHIPS_SOURCE_ID
            else None
        ),
        "requested_max_jobs_listing_pages": (
            config.max_jobs_listing_pages
            if config.source_id == JOBS_SOURCE_ID
            else None
        ),
        "requested_max_job_details": (
            config.max_job_details if config.source_id == JOBS_SOURCE_ID else None
        ),
        "requested_max_accommodation_details": (
            config.max_accommodation_details
            if config.source_id == ACCOMMODATION_SOURCE_ID
            else None
        ),
        "requested_max_support_details": (
            config.max_support_details
            if config.source_id == SUPPORT_SOURCE_ID
            else None
        ),
        "status": run.status.value,
        "dry_run": config.dry_run,
        "started_at": _isoformat(run.started_at),
        "completed_at": _isoformat(run.completed_at),
        "duration_ms": duration_ms,
        "records_seen": run.records_seen,
        "records_added": run.records_added,
        "records_changed": run.records_changed,
        "records_unchanged": run.records_unchanged,
        "records_missing": run.records_missing,
        "sanity": dict(sanity),
        "exit_code": exit_code,
        "error": (
            sanitize_error(run.error, environ) if run.error is not None else None
        ),
    }
    return JobResult(summary=summary, exit_code=exit_code)


def execute_job(
    config: JobConfig,
    *,
    fetcher: BaseFetcher | None = None,
    store: DataStore | None = None,
    environ: Mapping[str, str] | None = None,
    sleep_func: Callable[[float], None] | None = None,
) -> JobResult:
    """Execute exactly one bounded collector run and return its outcome."""

    env = os.environ if environ is None else environ
    source = assert_source_allowed(config.source_id)

    if source.domain.value != config.domain:
        raise JobConfigurationError(
            "Selected source does not belong to the selected domain"
        )
    supported = {
        (COURSES_SOURCE_ID, "courses"),
        (SCHOLARSHIPS_SOURCE_ID, "scholarships"),
        (JOBS_SOURCE_ID, "jobs"),
        (ACCOMMODATION_SOURCE_ID, "accommodation"),
        (SUPPORT_SOURCE_ID, "support"),
    }
    if (config.source_id, config.domain) not in supported:
        raise JobConfigurationError(
            "The selected approved collector is not implemented"
        )
    if (
        config.source_id == SCHOLARSHIPS_SOURCE_ID
        and config.storage_backend == "postgres"
        and not config.scholarship_postgres_approved
    ):
        raise JobConfigurationError(
            "Scholarships PostgreSQL writes require the cross-repo schema approval gate"
        )
    if (
        config.source_id == JOBS_SOURCE_ID
        and config.storage_backend == "postgres"
        and not config.jobs_postgres_approved
    ):
        raise JobConfigurationError(
            "Jobs PostgreSQL writes require the cross-repo schema approval gate"
        )
    if (
        config.source_id == ACCOMMODATION_SOURCE_ID
        and config.storage_backend == "postgres"
        and not config.accommodation_postgres_approved
    ):
        raise JobConfigurationError(
            "Accommodation PostgreSQL writes require the cross-repo schema approval gate"
        )
    if (
        config.source_id == SUPPORT_SOURCE_ID
        and config.storage_backend == "postgres"
        and not config.support_postgres_approved
    ):
        raise JobConfigurationError(
            "Support PostgreSQL writes require the cross-repo schema approval gate"
        )

    selected_fetcher = fetcher
    if selected_fetcher is None:
        selected_fetcher = (
            SimulatedFailureFetcher()
            if config.simulate_fetch_failure
            else HttpFetcher(timeout=config.timeout_seconds)
        )

    if store is not None:
        selected_store = store
    elif config.storage_backend == "postgres":
        from askanu_scraper.common.postgres_storage import PostgresDataStore

        selected_store = PostgresDataStore.from_environment(
            env,
            dry_run=config.dry_run,
        )
    else:
        selected_store = LocalDataStore(
            config.storage_path,
            dry_run=config.dry_run,
        )
    started = time.monotonic()
    if config.source_id == COURSES_SOURCE_ID:
        collector = CoursesCollector(
            fetcher=selected_fetcher,
            store=selected_store,
            min_request_interval_seconds=config.min_request_interval_seconds,
            sleep_func=sleep_func,
        )
        if config.academic_year is None:
            raise JobConfigurationError("Courses requires an academic year")
        if config.course_code is not None:
            root = source.canonical_root.rstrip("/")
            course_url = (
                f"{root}/{config.academic_year}/course/{config.course_code}"
            )
            run, _ = collector.run_single(course_url)
        else:
            run, _, _ = collector.run_live_catalogue(
                academic_year=config.academic_year,
                max_courses=config.max_courses,
                max_programs=config.max_programs,
            )
    elif config.source_id == SCHOLARSHIPS_SOURCE_ID:
        collector = ScholarshipsCollector(
            fetcher=selected_fetcher,
            store=selected_store,
            min_request_interval_seconds=config.min_request_interval_seconds,
            sleep_func=sleep_func,
        )
        run, _, _ = collector.run_listing(
            listing_url=SCHOLARSHIPS_LISTING_URL,
            max_listing_pages=config.max_scholarship_listing_pages,
            max_details=config.max_scholarship_details,
        )
    elif config.source_id == JOBS_SOURCE_ID:
        collector = JobsCollector(
            fetcher=selected_fetcher,
            store=selected_store,
            min_request_interval_seconds=config.min_request_interval_seconds,
            sleep_func=sleep_func,
        )
        run, _, _ = collector.run_listing(
            listing_url=JOBS_LISTING_URL,
            max_listing_pages=config.max_jobs_listing_pages,
            max_details=config.max_job_details,
        )
    elif config.source_id == ACCOMMODATION_SOURCE_ID:
        collector = AccommodationCollector(
            fetcher=selected_fetcher,
            store=selected_store,
            min_request_interval_seconds=config.min_request_interval_seconds,
            sleep_func=sleep_func,
        )
        run, _, _ = collector.run_listing(
            listing_url=ACCOMMODATION_LISTING_URL,
            max_details=config.max_accommodation_details,
        )
    else:
        collector = SupportCollector(
            fetcher=selected_fetcher,
            store=selected_store,
            min_request_interval_seconds=config.min_request_interval_seconds,
            sleep_func=sleep_func,
        )
        run, _, _ = collector.run_listing(
            listing_url=SUPPORT_LISTING_URL,
            max_details=config.max_support_details,
        )
    duration_ms = max(0, round((time.monotonic() - started) * 1000))
    return _summary_from_run(
        run,
        config=config,
        duration_ms=duration_ms,
        environ=env,
        sanity=collector.last_run_sanity,
    )


def _error_result(
    *,
    status: str,
    exit_code: int,
    error: str,
    started_at: datetime,
) -> JobResult:
    completed_at = now_canberra()
    summary: dict[str, object] = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "run_id": None,
        "source_id": None,
        "domain": None,
        "academic_year": None,
        "course_code": None,
        "storage_backend": None,
        "requested_max_courses": None,
        "requested_max_programs": None,
        "requested_max_scholarship_listing_pages": None,
        "requested_max_scholarship_details": None,
        "requested_max_jobs_listing_pages": None,
        "requested_max_job_details": None,
        "requested_max_accommodation_details": None,
        "requested_max_support_details": None,
        "status": status,
        "dry_run": None,
        "started_at": _isoformat(started_at),
        "completed_at": _isoformat(completed_at),
        "duration_ms": max(
            0, round((completed_at - started_at).total_seconds() * 1000)
        ),
        "records_seen": 0,
        "records_added": 0,
        "records_changed": 0,
        "records_unchanged": 0,
        "records_missing": 0,
        "sanity": None,
        "exit_code": exit_code,
        "error": error,
    }
    return JobResult(summary=summary, exit_code=exit_code)


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> int:
    """CLI boundary: always emit one JSON summary for attempted job runs."""

    env = os.environ if environ is None else environ
    started_at = now_canberra()

    try:
        config = load_config(argv, env)
        result = execute_job(config, environ=env)
    except UnapprovedSourceError:
        result = _error_result(
            status="CONFIGURATION_ERROR",
            exit_code=EXIT_CONFIGURATION_ERROR,
            error="Selected source is not approved for production",
            started_at=started_at,
        )
    except JobConfigurationError as exc:
        result = _error_result(
            status="CONFIGURATION_ERROR",
            exit_code=EXIT_CONFIGURATION_ERROR,
            error=sanitize_error(str(exc), env),
            started_at=started_at,
        )
    except Exception:
        result = _error_result(
            status="FAILED",
            exit_code=EXIT_INGESTION_FAILURE,
            error="Unexpected job failure",
            started_at=started_at,
        )

    print(json.dumps(result.summary, separators=(",", ":"), sort_keys=True))
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
