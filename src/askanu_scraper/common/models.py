"""
Pydantic models matching the V3 DATA_SCHEMA.md contract.

Field types, nullability and status semantics are the V3 bootstrap outline.
Precise cross-repo type resolution is coordinated by Qasim/Carmen/Will;
do not independently invent incompatible mappings.

Authoritative shared contracts:
  askanu-rag/docs/API_CONTRACT.md
  askanu-rag/docs/CONVERSATION_CONTRACT.md
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Domain(str, Enum):
    COURSES = "courses"
    SCHOLARSHIPS = "scholarships"
    JOBS = "jobs"
    ACCOMMODATION = "accommodation"
    SUPPORT = "support"
    EVENTS = "events"


class PollCadence(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    DISABLED = "DISABLED"


class RecordStatus(str, Enum):
    NEW = "NEW"
    CHANGED = "CHANGED"
    UNCHANGED = "UNCHANGED"
    MISSING = "MISSING"


class IndexStatus(str, Enum):
    PENDING = "PENDING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


class IngestionRunStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SUSPICIOUS_ZERO = "SUSPICIOUS_ZERO"


# ---------------------------------------------------------------------------
# Source Registry Entry
# ---------------------------------------------------------------------------

class SourceRegistryEntry(BaseModel):
    """Machine-readable record for one approved source."""

    source_id: str = Field(description="Stable, unique identifier for this source.")
    canonical_root: str = Field(description="Root URL for this source.")
    domain: Domain = Field(description="Which AskANU domain this source belongs to.")
    authority_rank: int = Field(
        ge=1, description="Lower is more authoritative (1 = official ANU)."
    )
    poll_cadence: PollCadence = Field(default=PollCadence.DAILY)
    parser_name: str = Field(description="Dotted module path of the parser class.")
    active: bool = Field(
        description=(
            "If False, no collector may target this source in production. "
            "PENDING_APPROVAL sources must have active=False."
        )
    )
    notes: str = Field(default="")


# ---------------------------------------------------------------------------
# Common Record
# ---------------------------------------------------------------------------

class CommonRecord(BaseModel):
    """
    Normalised record written by a collector after parse + validate.

    Rules (from DATA_SCHEMA.md):
    - Never invent missing fields; leave them None.
    - canonical_url comes from the source, never constructed.
    - Timezone: Australia/Canberra.
    - content_hash is SHA-256 of the canonical content representation.
    - DB success + embedding failure must not appear fully indexed.
    """

    record_id: str = Field(description="Stable deterministic record identifier.")
    source_id: str = Field(description="Foreign key to SourceRegistryEntry.source_id.")
    entity_id: str = Field(description="Domain-scoped stable entity identifier.")
    domain: Domain
    title: str
    content: str = Field(description="Normalized text content for embedding.")
    canonical_url: str = Field(description="Official source URL; comes from source data.")
    status: RecordStatus = Field(default=RecordStatus.NEW)
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content_hash: str = Field(description="SHA-256 of canonical content.")
    embedding_version: str | None = None
    index_status: IndexStatus = Field(default=IndexStatus.PENDING)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Ingestion Run
# ---------------------------------------------------------------------------

class IngestionRun(BaseModel):
    """
    Log of one scraper execution for a single source.

    On fetch/parser failure: status=FAILED, preserve last-known-good data.
    On suspicious many-to-zero: status=SUSPICIOUS_ZERO, never wipe current data.
    """

    run_id: str
    source_id: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    records_seen: int = 0
    records_added: int = 0
    records_changed: int = 0
    records_unchanged: int = 0
    records_missing: int = 0
    status: IngestionRunStatus = Field(default=IngestionRunStatus.RUNNING)
    error: str | None = None
