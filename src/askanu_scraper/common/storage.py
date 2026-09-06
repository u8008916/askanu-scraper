"""
Local development storage and DB handoff.

Per V3 Day 3 instructions:
Write normalized record + ingestion-run output to local development storage/DB handoff.
Enforces change comparison via content_hash:
- NEW: insert record
- CHANGED: update record and content_hash, mark index_status=PENDING
- UNCHANGED: update last_seen_at only without changing content or index_status
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from askanu_scraper.common.models import (
    CommonRecord,
    IndexStatus,
    IngestionRun,
    RecordStatus,
)
from askanu_scraper.common.normalizer import now_canberra


class LocalDataStore:
    """Local JSON-based store for development data handoff."""

    def __init__(self, base_dir: Path | str = "local-data") -> None:
        self.base_dir = Path(base_dir)
        self.records_dir = self.base_dir / "records"
        self.runs_dir = self.base_dir / "runs"

        self.records_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def _record_file_path(self, record_id: str) -> Path:
        safe_name = record_id.replace(":", "__").replace("/", "_")
        return self.records_dir / f"{safe_name}.json"

    def _run_file_path(self, run_id: str) -> Path:
        safe_name = run_id.replace(":", "__").replace("/", "_")
        return self.runs_dir / f"{safe_name}.json"

    def get_record(self, record_id: str) -> CommonRecord | None:
        file_path = self._record_file_path(record_id)
        if not file_path.exists():
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return CommonRecord.model_validate(data)

    def save_record(self, record: CommonRecord) -> tuple[RecordStatus, CommonRecord]:
        """
        Save or update record with hash comparison.
        Returns:
            (status, updated_record)
        """
        # Revalidate at the storage boundary so mutated or externally
        # constructed CommonRecord objects cannot bypass schema v1.
        record = CommonRecord.model_validate(
            record.model_dump(mode="python")
        )

        existing = self.get_record(record.record_id)
        current_time = now_canberra()

        if existing is None:
            # NEW RECORD
            record.status = RecordStatus.NEW
            record.index_status = IndexStatus.PENDING
            record.collected_at = current_time
            record.last_seen_at = current_time
            final_record = record
            action_status = RecordStatus.NEW
        elif existing.content_hash != record.content_hash:
            # CHANGED RECORD
            record.status = RecordStatus.CHANGED
            record.index_status = IndexStatus.PENDING
            record.collected_at = existing.collected_at
            record.last_seen_at = current_time
            final_record = record
            action_status = RecordStatus.CHANGED
        else:
            # UNCHANGED RECORD: Keep existing content & indexing, update last_seen_at only
            existing.status = RecordStatus.UNCHANGED
            existing.last_seen_at = current_time
            final_record = existing
            action_status = RecordStatus.UNCHANGED

        # Validate once more after status/timestamp mutations and before
        # anything crosses the serialized storage handoff.
        final_record = CommonRecord.model_validate(
            final_record.model_dump(mode="python")
        )

        file_path = self._record_file_path(final_record.record_id)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(final_record.model_dump_json(indent=2))

        return action_status, final_record

    def save_run(self, run: IngestionRun) -> None:
        file_path = self._run_file_path(run.run_id)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(run.model_dump_json(indent=2))

    def get_run(self, run_id: str) -> IngestionRun | None:
        file_path = self._run_file_path(run_id)
        if not file_path.exists():
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return IngestionRun.model_validate(data)
