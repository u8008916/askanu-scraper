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

from datetime import date, datetime, timezone
from enum import Enum
import hashlib
import re
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator


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

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_schema_v1(self) -> "CommonRecord":
        """Enforce the serialized schema-v1 boundary."""

        # Required string fields must be present and non-blank.
        required_strings = {
            "record_id": self.record_id,
            "source_id": self.source_id,
            "entity_id": self.entity_id,
            "title": self.title,
            "content": self.content,
            "canonical_url": self.canonical_url,
        }

        for field_name, value in required_strings.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")

        # Stored source URL must be a valid HTTP(S) URL.
        parsed_url = urlparse(self.canonical_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("canonical_url must be a valid HTTP(S) URL")

        # Required timestamps must be timezone-aware.
        for field_name, value in {
            "collected_at": self.collected_at,
            "last_seen_at": self.last_seen_at,
        }.items():
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{field_name} must be timezone-aware")

        # Nullable timestamps must also be timezone-aware when supplied.
        for field_name, value in {
            "effective_from": self.effective_from,
            "effective_to": self.effective_to,
        }.items():
            if value is not None and (
                value.tzinfo is None or value.utcoffset() is None
            ):
                raise ValueError(f"{field_name} must be timezone-aware when present")

        # content_hash must be the lowercase SHA-256 digest of content.
        if re.fullmatch(r"[0-9a-f]{64}", self.content_hash) is None:
            raise ValueError(
                "content_hash must be a 64-character lowercase SHA-256 hex digest"
            )

        expected_hash = hashlib.sha256(
            self.content.encode("utf-8")
        ).hexdigest()

        if self.content_hash != expected_hash:
            raise ValueError("content_hash must match content")

        # Courses/Programs have extra schema-v1 identity requirements.
        metadata = self.metadata_json
        entity_type = metadata.get("entity_type")

        is_courses_program_record = (
            self.domain == Domain.COURSES
            or self.source_id == "courses_programs_and_courses"
            or self.record_id.startswith("courses:")
            or entity_type in {"course", "program"}
        )

        if is_courses_program_record:
            if self.domain != Domain.COURSES:
                raise ValueError(
                    "Courses/Programs records require domain 'courses'"
                )

            if self.source_id != "courses_programs_and_courses":
                raise ValueError(
                    "Courses/Programs records require source_id "
                    "'courses_programs_and_courses'"
                )

            academic_year = metadata.get("academic_year")

            # Normalize documented optional blank scalar values to null.
            course_optional = (
                "career",
                "units",
                "delivery_mode",
                "prerequisites",
                "incompatibilities",
                "assumed_knowledge",
            )
            program_optional = (
                "career",
                "units",
                "duration",
                "delivery_mode",
            )

            optional_fields = (
                course_optional
                if entity_type == "course"
                else program_optional
                if entity_type == "program"
                else ()
            )

            for key in optional_fields:
                value = metadata.get(key)

                if value is None:
                    continue

                if not isinstance(value, str):
                    raise ValueError(
                        f"metadata_json.{key} must be a string or null"
                    )

                if not value.strip():
                    metadata[key] = None

            if entity_type == "course":
                offerings = metadata.get("offerings")

                if offerings is not None:
                    if (
                        not isinstance(offerings, list)
                        or not all(isinstance(item, dict) for item in offerings)
                    ):
                        raise ValueError(
                            "metadata_json.offerings must be "
                            "an array of objects or null"
                        )

            if entity_type == "program":
                learning_outcomes = metadata.get("learning_outcomes")

                if learning_outcomes is not None:
                    if (
                        not isinstance(learning_outcomes, list)
                        or not all(
                            isinstance(item, str)
                            for item in learning_outcomes
                        )
                    ):
                        raise ValueError(
                            "metadata_json.learning_outcomes must be "
                            "an array of strings or null"
                        )

            if entity_type not in {"course", "program"}:
                raise ValueError(
                    "Courses metadata_json.entity_type must be "
                    "'course' or 'program'"
                )

            if (
                not isinstance(academic_year, str)
                or re.fullmatch(r"\d{4}", academic_year) is None
            ):
                raise ValueError(
                    "metadata_json.academic_year must be a four-digit string"
                )

            if entity_type == "course":
                code = metadata.get("course_code")

                if (
                    not isinstance(code, str)
                    or re.fullmatch(r"[A-Z]{4}\d{4}[A-Z]?", code) is None
                ):
                    raise ValueError(
                        "course metadata requires a normalized course_code"
                    )

                expected_entity_id = f"{code}_{academic_year}"
                expected_record_id = (
                    f"courses:course:{expected_entity_id}"
                )

            else:
                code = metadata.get("program_code")

                if not isinstance(code, str) or not code.strip():
                    raise ValueError(
                        "program metadata requires program_code"
                    )

                normalized_code = code.strip().upper()

                if code != normalized_code:
                    raise ValueError(
                        "program_code must be normalized to uppercase"
                    )

                expected_entity_id = (
                    f"{normalized_code}_{academic_year}"
                )
                expected_record_id = (
                    f"courses:program:{expected_entity_id}"
                )

            if self.entity_id != expected_entity_id:
                raise ValueError(
                    "entity_id does not match schema-v1 identity"
                )

            if self.record_id != expected_record_id:
                raise ValueError(
                    "record_id does not match schema-v1 identity"
                )

        is_scholarship_record = (
            self.domain == Domain.SCHOLARSHIPS
            or self.source_id == "scholarships_anu_finder"
            or self.record_id.startswith("scholarships:")
            or entity_type == "scholarship"
        )
        if is_scholarship_record:
            try:
                scholarship_port = parsed_url.port
            except ValueError as exc:
                raise ValueError(
                    "Scholarship canonical_url has an invalid port"
                ) from exc
            if self.domain != Domain.SCHOLARSHIPS:
                raise ValueError("Scholarship records require domain 'scholarships'")
            if self.source_id != "scholarships_anu_finder":
                raise ValueError(
                    "Scholarship records require source_id 'scholarships_anu_finder'"
                )
            if entity_type != "scholarship":
                raise ValueError(
                    "Scholarship metadata_json.entity_type must be 'scholarship'"
                )
            if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", self.entity_id) is None:
                raise ValueError("Scholarship entity_id must be a canonical URL slug")
            expected_record_id = f"scholarships:scholarship:{self.entity_id}"
            if self.record_id != expected_record_id:
                raise ValueError(
                    "Scholarship record_id does not match schema-v1 identity"
                )
            if (
                parsed_url.scheme != "https"
                or parsed_url.hostname != "study.anu.edu.au"
                or parsed_url.username is not None
                or parsed_url.password is not None
                or scholarship_port is not None
                or parsed_url.path
                != f"/scholarships/find-scholarship/{self.entity_id}"
                or parsed_url.query
                or parsed_url.fragment
            ):
                raise ValueError(
                    "Scholarship canonical_url must match its approved ANU slug"
                )

            expected_keys = {
                "entity_type",
                "featured",
                "status",
                "application_required",
                "study_stage",
                "student_type",
                "study_level",
                "area_of_study",
                "value",
                "selection_basis",
                "opening_date",
                "closing_date",
                "eligibility",
            }
            if set(metadata) != expected_keys:
                raise ValueError(
                    "Scholarship metadata_json must match the approved v1 fields"
                )

            for key in ("featured", "application_required"):
                value = metadata[key]
                if value is not None and not isinstance(value, bool):
                    raise ValueError(f"metadata_json.{key} must be boolean or null")

            for key in ("study_stage", "student_type", "study_level", "area_of_study"):
                value = metadata[key]
                if not isinstance(value, list) or not all(
                    isinstance(item, str) and item.strip() for item in value
                ):
                    raise ValueError(
                        f"metadata_json.{key} must be an array of non-empty strings"
                    )

            for key in (
                "status",
                "value",
                "selection_basis",
                "eligibility",
            ):
                value = metadata[key]
                if value is not None and (
                    not isinstance(value, str) or not value.strip()
                ):
                    raise ValueError(f"metadata_json.{key} must be a string or null")

            for key in ("opening_date", "closing_date"):
                value = metadata[key]
                if value is None:
                    continue
                if not isinstance(value, str):
                    raise ValueError(f"metadata_json.{key} must be an ISO date or null")
                try:
                    parsed_date = date.fromisoformat(value)
                except ValueError as exc:
                    raise ValueError(
                        f"metadata_json.{key} must be an ISO date or null"
                    ) from exc
                if parsed_date.isoformat() != value:
                    raise ValueError(f"metadata_json.{key} must be an ISO date or null")

        return self


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
