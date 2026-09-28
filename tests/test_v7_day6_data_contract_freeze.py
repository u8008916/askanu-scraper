"""V7 Day 6 Jobs, Events, Support and producer feature-freeze proof."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from askanu_scraper.common.normalizer import CANBERRA_TZ
from askanu_scraper.common.search_metadata import build_resolver_search_metadata
from askanu_scraper.common.v7_contract import (
    get_v7_producer_contracts,
    source_authority_for,
)
from askanu_scraper.sources.events.parser import EventsParser
from askanu_scraper.sources.events.rubric_adapter import parse_detail
from askanu_scraper.sources.jobs.parser import JobsParser
from askanu_scraper.sources.support.parser import SupportParser


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "fixtures/v7/day6/data-contract-freeze.json"
OBSERVED_AT = datetime(2026, 9, 21, 12, 0, tzinfo=CANBERRA_TZ)


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _contract(entity_type: str):
    return next(
        item
        for item in get_v7_producer_contracts()
        if item.entity_type == entity_type
    )


def test_manifest_is_offline_read_only_and_stacked_from_day5() -> None:
    manifest = _manifest()

    assert manifest["contract_version"] == "v7-day6-data-contract-freeze-v1"
    assert manifest["parent_day5_sha"] == (
        "9e50fa0996d1110524da678675f97e1ff8a4378c"
    )
    assert manifest["network_calls_allowed"] is False
    assert manifest["production_writes_allowed"] is False
    assert manifest["cross_repo"]["consumer_matrix_status"] == (
        "BLOCKED_PENDING_CARMEN_DAY6_SHA"
    )
    assert manifest["cross_repo"]["mismatch_count"] is None


def test_all_day6_field_matrices_match_frozen_producer_contracts() -> None:
    manifest = _manifest()

    for key, entity_type in (("jobs", "job"), ("events", "event"), ("support", "support_service")):
        expected = manifest[key]
        contract = _contract(entity_type)
        assert expected["source_ids"] == list(contract.source_ids)
        assert expected["structured_paths"] == list(contract.structured_fact_paths)
        assert expected["content_only_facts"] == list(contract.content_only_facts)
        assert expected["unsupported_facts"] == list(contract.absent_facts)


def test_jobs_known_record_facts_do_not_claim_complete_population() -> None:
    record = JobsParser(now_func=lambda: OBSERVED_AT).parse(
        (ROOT / "fixtures/jobs/anu_job_open_dated_sample.html").read_text(
            encoding="utf-8"
        ),
        (
            "https://jobs.anu.edu.au/jobs/"
            "senior-consultant-user-experience-hr-systems-projects-"
            "canberra-act-act-australia"
        ),
        listing_metadata={
            "category": "Professional",
            "summary": "Create user-friendly HR systems documentation and websites.",
        },
    )[0]
    jobs = _manifest()["jobs"]

    assert record.record_id == "jobs:job:563693"
    assert record.metadata_json["status"] == "current"
    assert record.metadata_json["closing_date"] == "2026-09-27"
    assert jobs["population_health"] == "FALLBACK_LAST_KNOWN_GOOD"
    assert jobs["exhaustive_query_semantics"] == "INCOMPLETE_POPULATION"
    assert jobs["atomicity_weakened"] is False


def test_jobs_date_only_and_exact_time_remain_distinct() -> None:
    record = JobsParser(now_func=lambda: OBSERVED_AT).parse(
        (ROOT / "fixtures/jobs/anu_job_open_dated_sample.html").read_text(
            encoding="utf-8"
        ),
        (
            "https://jobs.anu.edu.au/jobs/"
            "senior-consultant-user-experience-hr-systems-projects-"
            "canberra-act-act-australia"
        ),
    )[0]
    temporal = build_resolver_search_metadata(record).temporal_values

    assert [(item.kind.value, item.precision.value) for item in temporal] == [
        ("closes_on", "date"),
        ("closes_at", "datetime"),
    ]
    assert record.effective_from is None
    assert record.effective_to is None


def test_official_and_rubric_events_keep_separate_identity_and_authority() -> None:
    official = EventsParser(now_func=lambda: OBSERVED_AT).parse(
        (ROOT / "fixtures/events/window-opening.html").read_text(encoding="utf-8"),
        "https://www.anu.edu.au/events/window-opening",
    )[0]
    rubric = parse_detail(
        (ROOT / "fixtures/events/rubric-detail-78459.json").read_text(
            encoding="utf-8"
        ),
        "78459",
        now_func=lambda: OBSERVED_AT,
    )

    assert official.record_id == "events:event:1001"
    assert rubric.record_id == "events:event:rubric-78459"
    assert official.source_id != rubric.source_id
    assert source_authority_for(official).authority_rank == 1
    assert source_authority_for(rubric).authority_rank == 3
    assert source_authority_for(official).approval_status.value == "APPROVED"
    assert source_authority_for(rubric).approval_status.value == (
        "APPROVED_BOUNDED_UNSUPPORTED"
    )
    assert _manifest()["events"]["product_boundary"] == {
        "upcoming_ui": ["events_anu_official"],
        "chat": ["events_anu_official", "rubric_unified_search"],
        "live_question_time_source_call": False,
    }


def test_event_missing_end_venue_and_status_are_not_inferred() -> None:
    record = parse_detail(
        (ROOT / "fixtures/events/rubric-detail-78460.json").read_text(
            encoding="utf-8"
        ),
        "78460",
        now_func=lambda: OBSERVED_AT,
    )

    assert record.metadata_json["end_at"] is None
    assert record.effective_to is None
    assert record.metadata_json["venue_name"] is None
    assert record.metadata_json["source_status"] is None
    assert record.metadata_json["cancellation_status"] is None
    assert "online" not in record.metadata_json


def test_support_preserves_source_topics_without_synthetic_student_aliases() -> None:
    record = SupportParser().parse(
        (ROOT / "fixtures/support/anusa_academic_sample.html").read_text(
            encoding="utf-8"
        ),
        "https://anusa.com.au/student-assistance/academic/",
        listing_metadata={
            "title": "Academic",
            "category": "Academic",
            "listing_description": "Help with academic issues.",
            "audiences": ["all ANU Students"],
            "cost": "The service is free.",
            "registry_email": "sa.assistance@anu.edu.au",
        },
    )[0]
    topics = {item["title"] for item in record.metadata_json["topics"]}

    assert record.record_id == "support:support_service:academic"
    assert record.metadata_json["purpose"] == "ANUSA can help with academic issues."
    assert "Grade Appeal" in topics
    assert "aliases" not in record.metadata_json
    assert _manifest()["support"]["synthetic_alias_system_added"] is False
    assert _manifest()["support"]["adjudication_supported"] is False


def test_day6_freezes_contract_without_content_churn_or_reindex() -> None:
    manifest = _manifest()
    freeze = manifest["feature_freeze"]

    assert freeze["status"] == "DATA_CONTRACT_FEATURE_FREEZE"
    assert all(
        freeze[key] is True
        for key in (
            "approved_source_scope_frozen",
            "source_authority_frozen",
            "canonical_identity_frozen",
            "six_domain_record_semantics_frozen",
            "freshness_and_temporal_semantics_frozen",
            "missing_unknown_semantics_frozen",
            "population_completeness_semantics_frozen",
        )
    )
    assert all(
        freeze[key] is False
        for key in (
            "new_fields_after_freeze",
            "new_sources_after_freeze",
            "new_inferences_after_freeze",
        )
    )
    assert manifest["change_impact"] == {
        "canonical_retrieval_content_changed": False,
        "reindex_required": "none",
        "production_backfill_started": False,
    }
