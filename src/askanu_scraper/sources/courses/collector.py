"""
Courses collector engine — executes live approved-source fetch and normalization.

Pipeline:
FETCH -> PARSE -> VALIDATE -> COMPARE -> LOCAL STORAGE UPDATE -> INGESTION RUN
"""
from __future__ import annotations

import re
import uuid
from urllib.parse import urlparse

from pydantic import ValidationError
from askanu_scraper.common.fetcher import BaseFetcher, FetchError, HttpFetcher
from askanu_scraper.common.models import (
    CommonRecord,
    IngestionRun,
    IngestionRunStatus,
    RecordStatus,
)
from askanu_scraper.common.normalizer import now_canberra
from askanu_scraper.common.registry import assert_source_allowed
from askanu_scraper.common.storage import LocalDataStore
from askanu_scraper.sources.courses.discovery import (
    CatalogueDiscoveryResult,
    CoursesCatalogueDiscovery,
)
from askanu_scraper.sources.courses.parser import CoursesParser

SOURCE_ID = "courses_programs_and_courses"


class CoursesCollector:
    """
    Collector for ANU Programs & Courses.
    Executes single-record fetch, parsing, validation, and safe local handoff.
    """

    def __init__(
        self,
        fetcher: BaseFetcher | None = None,
        store: LocalDataStore | None = None,
    ) -> None:
        self._source = assert_source_allowed(SOURCE_ID)
        self._fetcher = fetcher or HttpFetcher()
        self._parser = CoursesParser()
        self._discovery = CoursesCatalogueDiscovery()
        self._store = store or LocalDataStore()

    def _url_belongs_to_source(self, url: str) -> bool:
        candidate = urlparse(url)
        approved = urlparse(self._source.canonical_root)
        return (
            candidate.scheme == approved.scheme
            and candidate.netloc == approved.netloc
        )

    def _validate_record(self, record: CommonRecord) -> bool:
        """Apply collector-boundary schema-v1 identity checks."""
        metadata = record.metadata_json
        entity_type = metadata.get("entity_type")
        academic_year = metadata.get("academic_year")

        code: str | None = None
        if entity_type == "course":
            raw_code = metadata.get("course_code")
            if isinstance(raw_code, str):
                normalized_code = re.sub(r"\s+", "", raw_code).upper()
                if re.fullmatch(r"[A-Z]{4}\d{4}[A-Z]?", normalized_code):
                    code = normalized_code
        elif entity_type == "program":
            raw_code = metadata.get("program_code")
            if isinstance(raw_code, str):
                normalized_code = raw_code.strip().upper()
                if normalized_code:
                    code = normalized_code

        year_valid = (
            isinstance(academic_year, str)
            and re.fullmatch(r"\d{4}", academic_year) is not None
        )
        expected_entity_id = (
            f"{code}_{academic_year}"
            if code is not None and year_valid
            else None
        )
        expected_record_id = (
            f"courses:{entity_type}:{expected_entity_id}"
            if expected_entity_id is not None
            and entity_type in {"course", "program"}
            else None
        )

        return bool(
            record.canonical_url
            and self._url_belongs_to_source(record.canonical_url)
            and record.title
            and record.content
            and record.content_hash
            and code
            and year_valid
            and record.entity_id == expected_entity_id
            and record.record_id == expected_record_id
            and record.source_id == SOURCE_ID
        )

    def run_single(self, url: str) -> tuple[IngestionRun, list[CommonRecord]]:
        """
        Execute a single-record ingestion run for the provided approved course URL.

        Steps:
        1. Create IngestionRun.
        2. Validate URL belongs to approved canonical root.
        3. Fetch page. On failure: status=FAILED, preserve last-known-good, save run.
        4. Parse and validate required identity, year, and canonical URL.
        5. Save record with content_hash comparison.
        6. Complete IngestionRun with statistics.
        """
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        run = IngestionRun(
            run_id=run_id,
            source_id=SOURCE_ID,
            started_at=now_canberra(),
            status=IngestionRunStatus.RUNNING,
        )

        # 1. URL root validation
        if not self._url_belongs_to_source(url):
            run.status = IngestionRunStatus.FAILED
            run.error = f"URL {url!r} does not belong to approved canonical root {self._source.canonical_root!r}"
            run.completed_at = now_canberra()
            self._store.save_run(run)
            return run, []

        # 2. Fetch
        try:
            raw_html = self._fetcher.fetch(url)
        except FetchError as exc:
            run.status = IngestionRunStatus.FAILED
            run.error = f"Fetch failed: {exc}"
            run.completed_at = now_canberra()
            self._store.save_run(run)
            return run, []

        # 3. Parse
        try:
            records = self._parser.parse(raw_html, url)
        except ValidationError as exc:
            run.status = IngestionRunStatus.FAILED
            run.error = f"schema-v1 validation failed: {exc}"
            run.completed_at = now_canberra()
            self._store.save_run(run)
            return run, []
        except Exception as exc:
            run.status = IngestionRunStatus.FAILED
            run.error = f"Parser failed: {exc}"
            run.completed_at = now_canberra()
            self._store.save_run(run)
            return run, []

        if not records:
            run.status = IngestionRunStatus.FAILED
            run.error = f"No entity records parsed from {url}"
            run.completed_at = now_canberra()
            self._store.save_run(run)
            return run, []

        saved_records: list[CommonRecord] = []
        run.records_seen = len(records)

        # 4. Validate and save with hash comparison
        for record in records:
            if not self._validate_record(record):
                run.status = IngestionRunStatus.FAILED
                run.error = (
                    f"Record {record.record_id} failed schema-v1 "
                    "identity/provenance validation"
                )
                run.completed_at = now_canberra()
                self._store.save_run(run)
                return run, []

            action, final_rec = self._store.save_record(record)
            if action == RecordStatus.NEW:
                run.records_added += 1
            elif action == RecordStatus.CHANGED:
                run.records_changed += 1
            elif action == RecordStatus.UNCHANGED:
                run.records_unchanged += 1

            saved_records.append(final_rec)

        run.status = IngestionRunStatus.SUCCESS
        run.completed_at = now_canberra()
        self._store.save_run(run)

        return run, saved_records

    def run_catalogue(
        self,
        catalogue_url: str,
        *,
        max_records: int,
    ) -> tuple[IngestionRun, list[CommonRecord], CatalogueDiscoveryResult]:
        """Run a bounded, preflighted course/program sample from a catalogue."""
        if max_records < 1:
            raise ValueError("max_records must be at least 1")

        run = IngestionRun(
            run_id=f"run_{uuid.uuid4().hex[:12]}",
            source_id=SOURCE_ID,
            started_at=now_canberra(),
            status=IngestionRunStatus.RUNNING,
        )
        empty_discovery = CatalogueDiscoveryResult((), {}, (), ())

        def fail(
            message: str,
            discovery: CatalogueDiscoveryResult = empty_discovery,
            *,
            suspicious_zero: bool = False,
        ) -> tuple[IngestionRun, list[CommonRecord], CatalogueDiscoveryResult]:
            run.status = (
                IngestionRunStatus.SUSPICIOUS_ZERO
                if suspicious_zero
                else IngestionRunStatus.FAILED
            )
            run.error = message
            run.completed_at = now_canberra()
            self._store.save_run(run)
            return run, [], discovery

        if not self._url_belongs_to_source(catalogue_url):
            return fail(
                f"URL {catalogue_url!r} does not belong to approved "
                f"canonical root {self._source.canonical_root!r}"
            )

        try:
            catalogue_html = self._fetcher.fetch(catalogue_url)
        except FetchError as exc:
            return fail(f"Catalogue fetch failed: {exc}")

        discovery = self._discovery.discover(
            catalogue_html,
            catalogue_url,
            self._source.canonical_root,
        )
        candidates = discovery.persisted_candidates[:max_records]
        if not candidates:
            return fail(
                "Catalogue discovery produced zero schema-v1 course/program "
                "candidates; no records were updated",
                discovery,
                suspicious_zero=True,
            )

        # Parse and validate every bounded candidate before the first write.
        preflight_records: list[CommonRecord] = []
        try:
            for candidate in candidates:
                detail_html = self._fetcher.fetch(candidate.url)
                parsed_records = self._parser.parse(detail_html, candidate.url)
                if len(parsed_records) != 1:
                    return fail(
                        f"Expected exactly one record from {candidate.url!r}",
                        discovery,
                    )
                record = parsed_records[0]
                if not self._validate_record(record):
                    return fail(
                        f"Record {record.record_id} failed schema-v1 "
                        "identity/provenance validation",
                        discovery,
                    )
                if (
                    record.metadata_json["entity_type"]
                    != candidate.entity_type.value
                    or record.metadata_json["academic_year"]
                    != candidate.academic_year
                ):
                    return fail(
                        f"Record {record.record_id} does not match its "
                        "catalogue discovery identity",
                        discovery,
                    )
                code_key = (
                    "course_code"
                    if candidate.entity_type.value == "course"
                    else "program_code"
                )
                if record.metadata_json[code_key] != candidate.identifier:
                    return fail(
                        f"Record {record.record_id} does not match catalogue "
                        f"identifier {candidate.identifier}",
                        discovery,
                    )
                preflight_records.append(record)
        except FetchError as exc:
            return fail(f"Detail fetch failed: {exc}", discovery)
        except ValidationError as exc:
            return fail(f"schema-v1 validation failed: {exc}", discovery)
        except Exception as exc:
            return fail(f"Parser failed: {exc}", discovery)

        record_ids = [record.record_id for record in preflight_records]
        canonical_urls = [record.canonical_url for record in preflight_records]
        if len(record_ids) != len(set(record_ids)):
            return fail(
                "Duplicate normalized record identities detected; no records "
                "were updated",
                discovery,
            )
        if len(canonical_urls) != len(set(canonical_urls)):
            return fail(
                "Duplicate normalized canonical URLs detected; no records "
                "were updated",
                discovery,
            )

        run.records_seen = len(preflight_records)
        saved_records: list[CommonRecord] = []
        for record in preflight_records:
            action, final_record = self._store.save_record(record)
            if action == RecordStatus.NEW:
                run.records_added += 1
            elif action == RecordStatus.CHANGED:
                run.records_changed += 1
            elif action == RecordStatus.UNCHANGED:
                run.records_unchanged += 1
            saved_records.append(final_record)

        run.status = IngestionRunStatus.SUCCESS
        run.completed_at = now_canberra()
        self._store.save_run(run)
        return run, saved_records, discovery
