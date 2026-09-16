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

        is_job_record = (
            self.domain == Domain.JOBS
            or self.source_id == "jobs_anu_search"
            or self.record_id.startswith("jobs:")
            or entity_type == "job"
        )
        if is_job_record:
            if self.domain != Domain.JOBS:
                raise ValueError("Job records require domain 'jobs'")
            if self.source_id != "jobs_anu_search":
                raise ValueError("Job records require source_id 'jobs_anu_search'")
            if entity_type != "job":
                raise ValueError("Jobs metadata_json.entity_type must be 'job'")
            if re.fullmatch(r"[0-9]+", self.entity_id) is None:
                raise ValueError("Job entity_id must be the numeric requisition ID")
            if self.record_id != f"jobs:job:{self.entity_id}":
                raise ValueError("Job record_id does not match its requisition ID")
            try:
                job_port = parsed_url.port
            except ValueError as exc:
                raise ValueError("Job canonical_url has an invalid port") from exc
            if (
                parsed_url.scheme != "https"
                or parsed_url.hostname != "jobs.anu.edu.au"
                or parsed_url.username is not None
                or parsed_url.password is not None
                or job_port is not None
                or re.fullmatch(r"/jobs/[a-z0-9]+(?:-[a-z0-9]+)*", parsed_url.path)
                is None
                or parsed_url.query
                or parsed_url.fragment
            ):
                raise ValueError("Job canonical_url must be a public ANU job-detail URL")

            expected_keys = {
                "entity_type",
                "job_id",
                "category",
                "employment_types",
                "location",
                "classification",
                "salary",
                "closing_text",
                "closing_date",
                "closing_at",
                "status",
                "summary",
            }
            if set(metadata) != expected_keys:
                raise ValueError("Jobs metadata_json must match the approved v1 fields")
            if metadata["job_id"] != self.entity_id:
                raise ValueError("metadata_json.job_id must match entity_id")
            employment_types = metadata["employment_types"]
            if not isinstance(employment_types, list) or not all(
                isinstance(item, str) and item.strip() for item in employment_types
            ):
                raise ValueError(
                    "metadata_json.employment_types must be an array of non-empty strings"
                )
            for key in (
                "category",
                "location",
                "classification",
                "salary",
                "closing_text",
                "summary",
            ):
                value = metadata[key]
                if value is not None and (
                    not isinstance(value, str) or not value.strip()
                ):
                    raise ValueError(f"metadata_json.{key} must be a string or null")
            status = metadata["status"]
            if status not in {None, "current", "closed"}:
                raise ValueError("metadata_json.status must be current, closed, or null")
            closing_date = metadata["closing_date"]
            if closing_date is not None:
                if not isinstance(closing_date, str):
                    raise ValueError("metadata_json.closing_date must be an ISO date or null")
                try:
                    parsed_closing_date = date.fromisoformat(closing_date)
                except ValueError as exc:
                    raise ValueError(
                        "metadata_json.closing_date must be an ISO date or null"
                    ) from exc
                if parsed_closing_date.isoformat() != closing_date:
                    raise ValueError("metadata_json.closing_date must be an ISO date or null")
            closing_at = metadata["closing_at"]
            if closing_at is not None:
                if not isinstance(closing_at, str):
                    raise ValueError("metadata_json.closing_at must be an aware ISO datetime or null")
                try:
                    parsed_closing_at = datetime.fromisoformat(closing_at)
                except ValueError as exc:
                    raise ValueError(
                        "metadata_json.closing_at must be an aware ISO datetime or null"
                    ) from exc
                if (
                    parsed_closing_at.tzinfo is None
                    or parsed_closing_at.utcoffset() is None
                ):
                    raise ValueError(
                        "metadata_json.closing_at must be an aware ISO datetime or null"
                    )
                if closing_date != parsed_closing_at.date().isoformat():
                    raise ValueError("Jobs closing_date and closing_at must agree")

        is_accommodation_record = (
            self.domain == Domain.ACCOMMODATION
            or self.source_id == "accommodation_anu_study"
            or self.record_id.startswith("accommodation:")
            or entity_type == "residence"
        )
        if is_accommodation_record:
            try:
                accommodation_port = parsed_url.port
            except ValueError as exc:
                raise ValueError(
                    "Accommodation canonical_url has an invalid port"
                ) from exc
            if self.domain != Domain.ACCOMMODATION:
                raise ValueError("Accommodation records require domain 'accommodation'")
            if self.source_id != "accommodation_anu_study":
                raise ValueError(
                    "Accommodation records require source_id 'accommodation_anu_study'"
                )
            if entity_type != "residence":
                raise ValueError(
                    "Accommodation metadata_json.entity_type must be 'residence'"
                )
            if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", self.entity_id) is None:
                raise ValueError("Accommodation entity_id must be a canonical URL slug")
            if self.record_id != f"accommodation:residence:{self.entity_id}":
                raise ValueError("Accommodation record_id does not match its identity")
            if (
                parsed_url.scheme != "https"
                or parsed_url.hostname != "study.anu.edu.au"
                or parsed_url.username is not None
                or parsed_url.password is not None
                or accommodation_port is not None
                or parsed_url.path
                != f"/accommodation/our-residences/{self.entity_id}"
                or parsed_url.query
                or parsed_url.fragment
            ):
                raise ValueError(
                    "Accommodation canonical_url must be an approved residence URL"
                )
            expected_keys = {
                "entity_type",
                "category",
                "location",
                "catering_options",
                "audiences",
                "advertised_rate",
                "cost_period",
                "rooms",
                "features",
                "overview",
                "accessibility",
                "application_text",
                "application_url",
                "eligibility",
                "contact",
                "vacancy_status",
            }
            if set(metadata) != expected_keys:
                raise ValueError(
                    "Accommodation metadata_json must match the approved v1 fields"
                )
            for key in (
                "category",
                "location",
                "advertised_rate",
                "cost_period",
                "overview",
                "accessibility",
                "application_text",
                "eligibility",
                "vacancy_status",
            ):
                value = metadata[key]
                if value is not None and (
                    not isinstance(value, str) or not value.strip()
                ):
                    raise ValueError(f"metadata_json.{key} must be a string or null")
            for key in ("catering_options", "audiences", "features"):
                values = metadata[key]
                if not isinstance(values, list) or not all(
                    isinstance(item, str) and item.strip() for item in values
                ):
                    raise ValueError(
                        f"metadata_json.{key} must be an array of non-empty strings"
                    )
            rooms = metadata["rooms"]
            room_keys = {"name", "rate", "contract", "inclusions", "other_fees"}
            if not isinstance(rooms, list):
                raise ValueError("metadata_json.rooms must be an array")
            for room in rooms:
                if not isinstance(room, dict) or set(room) != room_keys:
                    raise ValueError(
                        "Accommodation room entries must match the approved v1 fields"
                    )
                if not isinstance(room["name"], str) or not room["name"].strip():
                    raise ValueError("Accommodation room names must be non-empty strings")
                for key in room_keys - {"name"}:
                    value = room[key]
                    if value is not None and (
                        not isinstance(value, str) or not value.strip()
                    ):
                        raise ValueError(
                            f"Accommodation room {key} must be a string or null"
                        )
            contact = metadata["contact"]
            contact_keys = {"email", "phone", "location", "hours"}
            if not isinstance(contact, dict) or set(contact) != contact_keys:
                raise ValueError(
                    "Accommodation contact must match the approved v1 fields"
                )
            for key, value in contact.items():
                if value is not None and (
                    not isinstance(value, str) or not value.strip()
                ):
                    raise ValueError(
                        f"Accommodation contact {key} must be a string or null"
                    )
            application_url = metadata["application_url"]
            if application_url is not None:
                if not isinstance(application_url, str):
                    raise ValueError("Accommodation application_url must be a URL or null")
                application_parsed = urlparse(application_url)
                try:
                    application_port = application_parsed.port
                except ValueError as exc:
                    raise ValueError(
                        "Accommodation application_url has an invalid port"
                    ) from exc
                if (
                    application_parsed.scheme != "https"
                    or not application_parsed.hostname
                    or not application_parsed.hostname.endswith(".starrezhousing.com")
                    or application_parsed.username is not None
                    or application_parsed.password is not None
                    or application_port is not None
                ):
                    raise ValueError(
                        "Accommodation application_url must be the published StarRez destination"
                    )

        is_support_record = (
            self.domain == Domain.SUPPORT
            or self.source_id == "support_anusa_student_assistance"
            or self.record_id.startswith("support:")
            or entity_type == "support_service"
        )
        if is_support_record:
            try:
                support_port = parsed_url.port
            except ValueError as exc:
                raise ValueError("Support canonical_url has an invalid port") from exc
            if self.domain != Domain.SUPPORT:
                raise ValueError("Support records require domain 'support'")
            if self.source_id != "support_anusa_student_assistance":
                raise ValueError(
                    "Support records require source_id 'support_anusa_student_assistance'"
                )
            if entity_type != "support_service":
                raise ValueError(
                    "Support metadata_json.entity_type must be 'support_service'"
                )
            if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", self.entity_id) is None:
                raise ValueError("Support entity_id must be a canonical URL slug")
            if self.record_id != f"support:support_service:{self.entity_id}":
                raise ValueError("Support record_id does not match its identity")
            if (
                parsed_url.scheme != "https"
                or parsed_url.hostname != "anusa.com.au"
                or parsed_url.username is not None
                or parsed_url.password is not None
                or support_port is not None
                or parsed_url.path != f"/student-assistance/{self.entity_id}/"
                or parsed_url.query
                or parsed_url.fragment
            ):
                raise ValueError(
                    "Support canonical_url must be an approved ANUSA category URL"
                )
            expected_keys = {
                "entity_type",
                "category",
                "purpose",
                "audiences",
                "contact",
                "hours",
                "access",
                "cost",
                "topics",
                "referrals",
            }
            if set(metadata) != expected_keys:
                raise ValueError("Support metadata_json must match the approved v1 fields")
            for key in ("category", "purpose", "hours", "access", "cost"):
                value = metadata[key]
                if value is not None and (
                    not isinstance(value, str) or not value.strip()
                ):
                    raise ValueError(f"metadata_json.{key} must be a string or null")
            audiences = metadata["audiences"]
            if not isinstance(audiences, list) or not all(
                isinstance(item, str) and item.strip() for item in audiences
            ):
                raise ValueError(
                    "metadata_json.audiences must be an array of non-empty strings"
                )
            contact = metadata["contact"]
            if not isinstance(contact, dict) or set(contact) != {
                "email",
                "phone",
                "location",
            }:
                raise ValueError("Support contact must match the approved v1 fields")
            for key, value in contact.items():
                if value is not None and (
                    not isinstance(value, str) or not value.strip()
                ):
                    raise ValueError(f"Support contact {key} must be a string or null")
            for list_key in ("topics", "referrals"):
                values = metadata[list_key]
                if not isinstance(values, list) or not all(
                    isinstance(item, dict) for item in values
                ):
                    raise ValueError(f"Support {list_key} must be an array of objects")
            for topic in metadata["topics"]:
                if set(topic) != {"title", "description", "url"}:
                    raise ValueError("Support topics must match the approved v1 fields")
                if not isinstance(topic["title"], str) or not topic["title"].strip():
                    raise ValueError("Support topic title must be a non-empty string")
                if topic["description"] is not None and (
                    not isinstance(topic["description"], str)
                    or not topic["description"].strip()
                ):
                    raise ValueError("Support topic description must be a string or null")
                topic_url = urlparse(topic["url"] if isinstance(topic["url"], str) else "")
                try:
                    topic_port = topic_url.port
                except ValueError as exc:
                    raise ValueError("Support topic URL has an invalid port") from exc
                if (
                    topic_url.scheme != "https"
                    or (topic_url.hostname or "").lower()
                    not in {"anusa.com.au", "www.anusa.com.au"}
                    or topic_url.username is not None
                    or topic_url.password is not None
                    or topic_port is not None
                    or re.fullmatch(
                        r"/student-assistance/[a-z0-9]+(?:-[a-z0-9]+)*/"
                        r"[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*/?",
                        topic_url.path,
                    )
                    is None
                    or topic_url.query
                    or topic_url.fragment
                ):
                    raise ValueError(
                        "Support topic URL must be an approved internal Student Assistance URL"
                    )
            for referral in metadata["referrals"]:
                if set(referral) != {"label", "url"}:
                    raise ValueError(
                        "Support referrals must match the approved v1 fields"
                    )
                if not isinstance(referral["label"], str) or not referral["label"].strip():
                    raise ValueError("Support referral label must be a non-empty string")
                referral_url = urlparse(
                    referral["url"] if isinstance(referral["url"], str) else ""
                )
                if referral_url.scheme not in {"http", "https"} or not referral_url.netloc:
                    raise ValueError("Support referral URL must be an HTTP(S) URL")
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
