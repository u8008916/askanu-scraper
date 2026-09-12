"""Day 7 PostgreSQL persistence contract tests without a live database."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path

import pytest

from askanu_scraper.common.models import (
    IngestionRun,
    IngestionRunStatus,
    IndexStatus,
    RecordStatus,
)
from askanu_scraper.common.postgres_storage import (
    RECORD_COLUMNS,
    RUN_COLUMNS,
    PostgresConfigurationError,
    PostgresConnectionConfig,
    PostgresDataStore,
    PostgresPersistenceError,
)
from askanu_scraper.sources.courses.parser import CoursesParser


def _plain(value):
    return getattr(value, "obj", value)


class FakeCursor:
    def __init__(self, records: dict, runs: dict) -> None:
        self.records = records
        self.runs = runs
        self.result = None
        self.calls: list[tuple[str, tuple]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query: str, parameters: tuple) -> None:
        self.calls.append((query, parameters))
        normalized = " ".join(query.split())
        if normalized.startswith("SELECT"):
            self.result = self.records.get(parameters[0])
        elif normalized.startswith("INSERT INTO course_program_records"):
            row = dict(zip(RECORD_COLUMNS, map(_plain, parameters)))
            self.records[row["record_id"]] = row
        elif normalized.startswith("UPDATE course_program_records SET status"):
            status, last_seen_at, record_id = parameters
            self.records[record_id]["status"] = status
            self.records[record_id]["last_seen_at"] = last_seen_at
        elif normalized.startswith("UPDATE course_program_records SET"):
            record_id = parameters[-1]
            self.records[record_id].update(
                dict(zip(RECORD_COLUMNS[1:], map(_plain, parameters[:-1])))
            )
        elif normalized.startswith("INSERT INTO ingestion_runs"):
            row = dict(zip(RUN_COLUMNS, parameters))
            self.runs[row["run_id"]] = row
        else:
            raise AssertionError(f"Unexpected SQL: {normalized}")

    def fetchone(self):
        return self.result


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    def __enter__(self):
        self._records_snapshot = {
            key: value.copy() for key, value in self._cursor.records.items()
        }
        self._runs_snapshot = {
            key: value.copy() for key, value in self._cursor.runs.items()
        }
        return self

    def __exit__(self, exc_type, *_args):
        if exc_type is not None:
            self._cursor.records.clear()
            self._cursor.records.update(self._records_snapshot)
            self._cursor.runs.clear()
            self._cursor.runs.update(self._runs_snapshot)
        return False

    def cursor(self) -> FakeCursor:
        return self._cursor


def _store():
    records: dict = {}
    runs: dict = {}
    cursor = FakeCursor(records, runs)
    store = PostgresDataStore(lambda: FakeConnection(cursor))
    return store, records, runs, cursor.calls


def _comp1110(path: Path):
    url = "https://programsandcourses.anu.edu.au/2026/course/COMP1110"
    return CoursesParser().parse(path.read_text(encoding="utf-8"), url)[0]


def test_new_unchanged_and_changed_index_transitions(
    rich_course_fixture_path: Path,
) -> None:
    store, records, _runs, calls = _store()
    record = _comp1110(rich_course_fixture_path)

    action, first = store.save_record(record)
    assert action == RecordStatus.NEW
    assert first.index_status == IndexStatus.PENDING
    assert first.embedding_version is None
    assert len(records) == 1

    records[first.record_id]["index_status"] = "INDEXED"
    records[first.record_id]["embedding_version"] = "test-v1"
    action, unchanged = store.save_record(record)
    assert action == RecordStatus.UNCHANGED
    assert unchanged.index_status == IndexStatus.INDEXED
    assert unchanged.embedding_version == "test-v1"
    assert len(records) == 1

    changed_content = record.content + "\nAdditional source-supported evidence."
    changed = record.model_copy(
        update={
            "content": changed_content,
            "content_hash": hashlib.sha256(
                changed_content.encode("utf-8")
            ).hexdigest(),
        }
    )
    action, final = store.save_record(changed)
    assert action == RecordStatus.CHANGED
    assert final.index_status == IndexStatus.PENDING
    assert final.embedding_version is None
    assert len(records) == 1
    assert all("%s" in query for query, _parameters in calls)


def test_dry_run_compares_without_writes(
    rich_course_fixture_path: Path,
) -> None:
    records: dict = {}
    runs: dict = {}
    cursor = FakeCursor(records, runs)
    store = PostgresDataStore(
        lambda: FakeConnection(cursor),
        dry_run=True,
    )

    action, _record = store.save_record(_comp1110(rich_course_fixture_path))
    assert action == RecordStatus.NEW
    assert records == {}


def test_ingestion_run_is_durably_upserted() -> None:
    store, _records, runs, calls = _store()
    observed = datetime(2026, 9, 11, tzinfo=timezone.utc)
    run = IngestionRun(
        run_id="run_day7",
        source_id="courses_programs_and_courses",
        started_at=observed,
        completed_at=observed,
        records_seen=1,
        records_added=1,
        status=IngestionRunStatus.SUCCESS,
    )

    store.save_run(run)
    run.records_added = 0
    run.records_unchanged = 1
    store.save_run(run)

    assert len(runs) == 1
    assert runs["run_day7"]["records_unchanged"] == 1
    query, _parameters = calls[-1]
    assert "ON CONFLICT (run_id) DO UPDATE" in query


def test_batch_commits_records_and_successful_run_together(
    rich_course_fixture_path: Path,
) -> None:
    store, records, runs, calls = _store()
    observed = datetime(2026, 9, 12, tzinfo=timezone.utc)
    run = IngestionRun(
        run_id="run_day8_batch",
        source_id="courses_programs_and_courses",
        started_at=observed,
        completed_at=observed,
        status=IngestionRunStatus.SUCCESS,
    )

    results = store.save_records_and_run(
        [_comp1110(rich_course_fixture_path)],
        run,
    )

    assert [action for action, _record in results] == [RecordStatus.NEW]
    assert run.records_seen == 1
    assert run.records_added == 1
    assert len(records) == 1
    assert runs["run_day8_batch"]["status"] == "SUCCESS"
    assert "FOR UPDATE" in calls[0][0]
    assert calls[-1][0].startswith("INSERT INTO ingestion_runs")


def test_batch_run_write_failure_rolls_back_record_changes(
    rich_course_fixture_path: Path,
) -> None:
    records: dict = {}
    runs: dict = {}

    class RunWriteFailureCursor(FakeCursor):
        def execute(self, query: str, parameters: tuple) -> None:
            if "INSERT INTO ingestion_runs" in query:
                raise RuntimeError("simulated run-row failure")
            super().execute(query, parameters)

    cursor = RunWriteFailureCursor(records, runs)
    store = PostgresDataStore(lambda: FakeConnection(cursor))
    observed = datetime(2026, 9, 12, tzinfo=timezone.utc)
    run = IngestionRun(
        run_id="run_day8_rollback",
        source_id="courses_programs_and_courses",
        started_at=observed,
        completed_at=observed,
        status=IngestionRunStatus.SUCCESS,
    )

    with pytest.raises(PostgresPersistenceError):
        store.save_records_and_run(
            [_comp1110(rich_course_fixture_path)],
            run,
        )

    assert records == {}
    assert runs == {}


def test_incomplete_connection_configuration_fails_without_secret_echo() -> None:
    with pytest.raises(PostgresConfigurationError) as caught:
        PostgresConnectionConfig.from_environment(
            {"DB_PASSWORD": "must-not-appear"}
        )

    assert "must-not-appear" not in str(caught.value)
