"""Durable PostgreSQL persistence for the approved Day 7 shared schema."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import os
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from askanu_scraper.common.models import (
    CommonRecord,
    IndexStatus,
    IngestionRun,
    RecordStatus,
)
from askanu_scraper.common.normalizer import now_canberra


class PostgresConfigurationError(RuntimeError):
    """Safe configuration error containing no connection material."""

    def __init__(self) -> None:
        super().__init__("PostgreSQL persistence configuration is incomplete")


class PostgresPersistenceError(RuntimeError):
    """Safe database error containing no SQL, credentials, or host details."""

    def __init__(self) -> None:
        super().__init__("PostgreSQL persistence is unavailable")


@dataclass(frozen=True, repr=False)
class PostgresConnectionConfig:
    database_url: str | None = None
    database_name: str | None = None
    database_user: str | None = None
    database_password: str | None = None
    instance_connection_name: str | None = None
    connect_timeout_seconds: int = 5

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "PostgresConnectionConfig":
        env = os.environ if environ is None else environ
        database_url = env.get("DATABASE_URL") or None
        if database_url is not None:
            return cls(database_url=database_url)

        values = (
            env.get("DB_NAME"),
            env.get("DB_USER"),
            env.get("DB_PASSWORD"),
            env.get("CLOUD_SQL_INSTANCE_CONNECTION_NAME"),
        )
        if not all(values):
            raise PostgresConfigurationError()

        return cls(
            database_name=values[0],
            database_user=values[1],
            database_password=values[2],
            instance_connection_name=values[3],
        )

    def connect(self) -> psycopg.Connection[dict[str, Any]]:
        if self.database_url is not None:
            conninfo = self.database_url
            if conninfo.startswith("postgresql+psycopg://"):
                conninfo = "postgresql://" + conninfo.removeprefix(
                    "postgresql+psycopg://"
                )
            return psycopg.connect(
                conninfo,
                connect_timeout=self.connect_timeout_seconds,
                row_factory=dict_row,
            )

        if not all(
            (
                self.database_name,
                self.database_user,
                self.database_password,
                self.instance_connection_name,
            )
        ):
            raise PostgresConfigurationError()

        return psycopg.connect(
            dbname=self.database_name,
            user=self.database_user,
            password=self.database_password,
            host=f"/cloudsql/{self.instance_connection_name}",
            connect_timeout=self.connect_timeout_seconds,
            row_factory=dict_row,
        )


ConnectionFactory = Callable[[], Any]

RECORD_COLUMNS = (
    "record_id", "source_id", "entity_id", "domain", "title", "content",
    "canonical_url", "status", "effective_from", "effective_to",
    "collected_at", "last_seen_at", "content_hash", "embedding_version",
    "index_status", "metadata_json",
)
RUN_COLUMNS = (
    "run_id", "source_id", "started_at", "completed_at", "records_seen",
    "records_added", "records_changed", "records_unchanged",
    "records_missing", "status", "error",
)


class PostgresDataStore:
    """Compare and persist records using the RAG-owned PostgreSQL tables."""

    def __init__(
        self,
        connection_factory: ConnectionFactory,
        *,
        dry_run: bool = False,
    ) -> None:
        self._connection_factory = connection_factory
        self.dry_run = dry_run

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        dry_run: bool = False,
    ) -> "PostgresDataStore":
        config = PostgresConnectionConfig.from_environment(environ)
        return cls(config.connect, dry_run=dry_run)

    @staticmethod
    def _record_values(record: CommonRecord) -> tuple[object, ...]:
        values = record.model_dump(mode="python")
        values["domain"] = record.domain.value
        values["status"] = record.status.value
        values["index_status"] = record.index_status.value
        values["metadata_json"] = Jsonb(record.metadata_json)
        return tuple(values[column] for column in RECORD_COLUMNS)

    def get_record(self, record_id: str) -> CommonRecord | None:
        query = (
            f"SELECT {', '.join(RECORD_COLUMNS)} "
            "FROM course_program_records WHERE record_id = %s"
        )
        try:
            with self._connection_factory() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(query, (record_id,))
                    row = cursor.fetchone()
            return CommonRecord.model_validate(row) if row is not None else None
        except PostgresConfigurationError:
            raise
        except Exception:
            raise PostgresPersistenceError() from None

    def save_record(
        self,
        record: CommonRecord,
    ) -> tuple[RecordStatus, CommonRecord]:
        record = CommonRecord.model_validate(record.model_dump(mode="python"))
        select = (
            f"SELECT {', '.join(RECORD_COLUMNS)} "
            "FROM course_program_records WHERE record_id = %s"
            + ("" if self.dry_run else " FOR UPDATE")
        )
        now = now_canberra()

        try:
            with self._connection_factory() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(select, (record.record_id,))
                    row = cursor.fetchone()
                    existing = (
                        CommonRecord.model_validate(row)
                        if row is not None
                        else None
                    )

                    if existing is None:
                        action = RecordStatus.NEW
                        final = record.model_copy(
                            update={
                                "status": action,
                                "index_status": IndexStatus.PENDING,
                                "embedding_version": None,
                                "collected_at": now,
                                "last_seen_at": now,
                            }
                        )
                        if not self.dry_run:
                            placeholders = ", ".join(["%s"] * len(RECORD_COLUMNS))
                            cursor.execute(
                                f"INSERT INTO course_program_records "
                                f"({', '.join(RECORD_COLUMNS)}) "
                                f"VALUES ({placeholders})",
                                self._record_values(final),
                            )
                    elif existing.content_hash == record.content_hash:
                        action = RecordStatus.UNCHANGED
                        final = existing.model_copy(
                            update={"status": action, "last_seen_at": now}
                        )
                        if not self.dry_run:
                            cursor.execute(
                                "UPDATE course_program_records "
                                "SET status = %s, last_seen_at = %s "
                                "WHERE record_id = %s",
                                (action.value, now, record.record_id),
                            )
                    else:
                        action = RecordStatus.CHANGED
                        final = record.model_copy(
                            update={
                                "status": action,
                                "index_status": IndexStatus.PENDING,
                                "embedding_version": None,
                                "collected_at": existing.collected_at,
                                "last_seen_at": now,
                            }
                        )
                        assignments = ", ".join(
                            f"{column} = %s" for column in RECORD_COLUMNS[1:]
                        )
                        if not self.dry_run:
                            cursor.execute(
                                f"UPDATE course_program_records SET {assignments} "
                                "WHERE record_id = %s",
                                self._record_values(final)[1:] + (record.record_id,),
                            )

            return action, CommonRecord.model_validate(
                final.model_dump(mode="python")
            )
        except PostgresConfigurationError:
            raise
        except Exception:
            raise PostgresPersistenceError() from None

    def save_run(self, run: IngestionRun) -> None:
        """Durably upsert a run; structured stdout remains supplementary."""
        if self.dry_run:
            return
        values = run.model_dump(mode="python")
        values["status"] = run.status.value
        placeholders = ", ".join(["%s"] * len(RUN_COLUMNS))
        updates = ", ".join(
            f"{column} = EXCLUDED.{column}" for column in RUN_COLUMNS[1:]
        )
        query = (
            f"INSERT INTO ingestion_runs ({', '.join(RUN_COLUMNS)}) "
            f"VALUES ({placeholders}) ON CONFLICT (run_id) DO UPDATE SET {updates}"
        )
        try:
            with self._connection_factory() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        query,
                        tuple(values[column] for column in RUN_COLUMNS),
                    )
        except Exception:
            raise PostgresPersistenceError() from None

    def save_records_and_run(
        self,
        records: list[CommonRecord],
        run: IngestionRun,
    ) -> list[tuple[RecordStatus, CommonRecord]]:
        """Persist one preflighted bounded batch and its run atomically.

        The connection context is the production transaction boundary.  Any
        record or ingestion-run write failure causes psycopg to roll back the
        complete batch, preserving the last-known-good rows.
        """
        validated = [
            CommonRecord.model_validate(record.model_dump(mode="python"))
            for record in records
        ]
        record_ids = [record.record_id for record in validated]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("record batch contains duplicate record IDs")

        select = (
            f"SELECT {', '.join(RECORD_COLUMNS)} "
            "FROM course_program_records WHERE record_id = %s"
            + ("" if self.dry_run else " FOR UPDATE")
        )
        observed_at = now_canberra()
        results: list[tuple[RecordStatus, CommonRecord]] = []
        run.records_seen = len(validated)
        run.records_added = 0
        run.records_changed = 0
        run.records_unchanged = 0

        try:
            with self._connection_factory() as connection:
                with connection.cursor() as cursor:
                    for record in validated:
                        cursor.execute(select, (record.record_id,))
                        row = cursor.fetchone()
                        existing = (
                            CommonRecord.model_validate(row)
                            if row is not None
                            else None
                        )

                        if existing is None:
                            action = RecordStatus.NEW
                            final = record.model_copy(
                                update={
                                    "status": action,
                                    "index_status": IndexStatus.PENDING,
                                    "embedding_version": None,
                                    "collected_at": observed_at,
                                    "last_seen_at": observed_at,
                                }
                            )
                            if not self.dry_run:
                                placeholders = ", ".join(
                                    ["%s"] * len(RECORD_COLUMNS)
                                )
                                cursor.execute(
                                    "INSERT INTO course_program_records "
                                    f"({', '.join(RECORD_COLUMNS)}) "
                                    f"VALUES ({placeholders})",
                                    self._record_values(final),
                                )
                        elif existing.content_hash == record.content_hash:
                            action = RecordStatus.UNCHANGED
                            final = existing.model_copy(
                                update={
                                    "status": action,
                                    "last_seen_at": observed_at,
                                }
                            )
                            if not self.dry_run:
                                cursor.execute(
                                    "UPDATE course_program_records "
                                    "SET status = %s, last_seen_at = %s "
                                    "WHERE record_id = %s",
                                    (
                                        action.value,
                                        observed_at,
                                        record.record_id,
                                    ),
                                )
                        else:
                            action = RecordStatus.CHANGED
                            final = record.model_copy(
                                update={
                                    "status": action,
                                    "index_status": IndexStatus.PENDING,
                                    "embedding_version": None,
                                    "collected_at": existing.collected_at,
                                    "last_seen_at": observed_at,
                                }
                            )
                            assignments = ", ".join(
                                f"{column} = %s"
                                for column in RECORD_COLUMNS[1:]
                            )
                            if not self.dry_run:
                                cursor.execute(
                                    "UPDATE course_program_records SET "
                                    f"{assignments} WHERE record_id = %s",
                                    self._record_values(final)[1:]
                                    + (record.record_id,),
                                )

                        final = CommonRecord.model_validate(
                            final.model_dump(mode="python")
                        )
                        results.append((action, final))
                        if action == RecordStatus.NEW:
                            run.records_added += 1
                        elif action == RecordStatus.CHANGED:
                            run.records_changed += 1
                        else:
                            run.records_unchanged += 1

                    if not self.dry_run:
                        values = run.model_dump(mode="python")
                        values["status"] = run.status.value
                        placeholders = ", ".join(
                            ["%s"] * len(RUN_COLUMNS)
                        )
                        updates = ", ".join(
                            f"{column} = EXCLUDED.{column}"
                            for column in RUN_COLUMNS[1:]
                        )
                        cursor.execute(
                            "INSERT INTO ingestion_runs "
                            f"({', '.join(RUN_COLUMNS)}) "
                            f"VALUES ({placeholders}) "
                            "ON CONFLICT (run_id) DO UPDATE SET "
                            f"{updates}",
                            tuple(values[column] for column in RUN_COLUMNS),
                        )
        except PostgresConfigurationError:
            raise
        except Exception:
            raise PostgresPersistenceError() from None

        return results
