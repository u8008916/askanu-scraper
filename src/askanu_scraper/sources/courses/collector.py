"""
Courses collector engine — executes live approved-source fetch and normalization.

Pipeline:
FETCH -> PARSE -> VALIDATE -> COMPARE -> LOCAL STORAGE UPDATE -> INGESTION RUN
"""
from __future__ import annotations

import uuid
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
        self._store = store or LocalDataStore()

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
        if not url.startswith(self._source.canonical_root):
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
            # Validate required identity fields
            if not record.entity_id or not record.canonical_url or not record.title:
                run.status = IngestionRunStatus.FAILED
                run.error = f"Record {record.record_id} missing mandatory identity fields"
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
