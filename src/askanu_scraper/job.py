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


EXIT_SUCCESS = 0
EXIT_INGESTION_FAILURE = 1
EXIT_CONFIGURATION_ERROR = 2
SUMMARY_SCHEMA_VERSION = "1"


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
    academic_year: str
    course_code: str | None
    storage_backend: str
    max_courses: int
    max_programs: int
    dry_run: bool
    simulate_fetch_failure: bool
    storage_path: Path
    timeout_seconds: int
    min_request_interval_seconds: float


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
    academic_year = args.academic_year or env.get("SCRAPER_ACADEMIC_YEAR", "")

    if re.fullmatch(r"\d{4}", academic_year) is None:
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

    if max_courses + max_programs > 4:
        raise JobConfigurationError(
            "The combined course/program sample must not exceed 4 records"
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
        "requested_max_courses": config.max_courses,
        "requested_max_programs": config.max_programs,
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
    if config.source_id != COURSES_SOURCE_ID or config.domain != "courses":
        raise JobConfigurationError(
            "Only the approved Courses collector is implemented for Day 6"
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
    collector = CoursesCollector(
        fetcher=selected_fetcher,
        store=selected_store,
        min_request_interval_seconds=config.min_request_interval_seconds,
        sleep_func=sleep_func,
    )

    started = time.monotonic()
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
    duration_ms = max(0, round((time.monotonic() - started) * 1000))
    return _summary_from_run(
        run,
        config=config,
        duration_ms=duration_ms,
        environ=env,
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
