"""V7 Day 6 Jobs, Events, Support and producer feature-freeze proof."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from urllib.parse import urlsplit

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
SOURCE_HEALTH = ROOT / "day16-source-health.json"
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

    assert manifest["contract_version"] == "v7-day6-data-contract-freeze-v2"
    assert manifest["parent_day5_sha"] == (
        "b829ffcf943653e5e36496109f29f116bea015a8"
    )
    assert manifest["network_calls_allowed"] is False
    assert manifest["production_writes_allowed"] is False
    restack = manifest["restack"]
    assert restack["old_head"] == (
        "e9c6ce2817f12d190a07dbe85a297bab6e4c6deb"
    )
    assert restack["pure_replay_sha"] == (
        "c379cadb631d97aeadc8acb828be4f62915ab9a5"
    )
    assert restack["conflicts"] == 0
    assert restack["manual_resolutions"] == []
    assert restack["day6_delta_patch_id_before"] == (
        restack["day6_delta_patch_id_after"]
    )
    assert restack["old_tree_equals_replay_tree"] is False
    assert restack["old_tree_vs_replay_changed_files"] == [
        "docs/v7/DAY_05_HANDOFF.md",
        "fixtures/v7/day5/courses-scholarships-evidence.json",
        "tests/test_v7_day5_evidence_readiness.py",
    ]


def test_exact_day6_consumer_mismatches_have_final_ownership() -> None:
    cross_repo = _manifest()["cross_repo"]

    assert cross_repo["carmen_day6_sha"] == (
        "1875a4be816eeec2aeeacc0cfb4ff6fd6228f881"
    )
    assert cross_repo["consumer_matrix_status"] == "FAIL_CONSUMER_ALIGNMENT"
    assert cross_repo["domain_status"] == {
        "jobs": "FAIL",
        "events": "FAIL",
        "support": "PASS",
    }
    assert cross_repo["mismatch_count"] == len(cross_repo["mismatches"]) == 4
    assert {item["classification"] for item in cross_repo["mismatches"]} == {
        "SHARED_CONTRACT_DECISION_REQUIRED",
        "CONSUMER_SEMANTIC_DEFECT",
        "CONSUMER_SOURCE_HEALTH_DEFECT",
    }
    assert all(item["code_change_required"] is True for item in cross_repo["mismatches"])
    assert cross_repo["events_shape_and_provenance"] == "PASS"
    assert cross_repo["events_source_health"] == "FAIL"
    assert cross_repo["support_shape_semantics_and_provenance"] == "PASS"


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


def test_jobs_capability_audit_distinguishes_supported_from_unreliable_filters() -> None:
    capabilities = _manifest()["jobs"]["capability_audit"]
    health = json.loads(SOURCE_HEALTH.read_text(encoding="utf-8"))
    observed = health["entity_classes"]["job"]

    assert capabilities["advertised_population"] == health["entity_census"]["jobs"][
        "advertised_total"
    ] == 56
    assert capabilities["audited_records_before_source_failure"] == observed[
        "approved_records"
    ] == 7
    assert capabilities["detail_traversal_complete"] is False
    assert health["domain_health"]["jobs"]["status"] == (
        "FALLBACK_LAST_KNOWN_GOOD"
    )

    fields = capabilities["fields"]
    for name in ("employment_type", "category", "classification"):
        assert fields[name]["latest_audit_source_present"] == 7
        assert fields[name]["latest_audit_population"] == 7
        assert fields[name]["reliable_hard_constraint"] is True
        assert fields[name]["zero_match_semantics"] == (
            "NO_SUPPORTED_MATCH_IN_STORED_INCOMPLETE_POPULATION"
        )

    assert observed["fields"]["location"]["source_present"] == 0
    assert fields["location"]["reliable_hard_constraint"] is False
    assert fields["location"]["zero_match_semantics"] == (
        "CANNOT_RELIABLY_APPLY_OR_VERIFY_FILTER"
    )
    for name in ("remote_work_arrangement", "role_requirements"):
        assert fields[name]["producer_path"] is None
        assert fields[name]["representative_source_backed_value"] is None
        assert fields[name]["reliable_hard_constraint"] is False


def test_jobs_example_values_are_source_backed_and_not_synthetic_aliases() -> None:
    record = JobsParser(now_func=lambda: OBSERVED_AT).parse(
        (ROOT / "fixtures/jobs/anu_job_open_dated_sample.html").read_text(
            encoding="utf-8"
        ),
        (
            "https://jobs.anu.edu.au/jobs/"
            "senior-consultant-user-experience-hr-systems-projects-"
            "canberra-act-act-australia"
        ),
        listing_metadata={"category": "Professional"},
    )[0]
    fields = _manifest()["jobs"]["capability_audit"]["fields"]

    assert record.metadata_json["location"] == fields["location"][
        "representative_source_backed_value"
    ]
    assert record.metadata_json["employment_types"] == fields["employment_type"][
        "representative_source_backed_value"
    ]
    assert record.metadata_json["category"] == fields["category"][
        "representative_source_backed_value"
    ]
    assert record.metadata_json["classification"] == fields["classification"][
        "representative_source_backed_value"
    ]
    assert "ANU08" not in record.metadata_json.values()
    assert "remote" not in record.metadata_json
    assert "work_arrangement" not in record.metadata_json
    assert "role_requirements" not in record.metadata_json


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

    for referral in record.metadata_json["referrals"]:
        parsed = urlsplit(referral["url"])
        assert parsed.scheme in {"http", "https"}
        assert parsed.hostname not in {"anusa.com.au", "www.anusa.com.au"}


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
        "reembedding_required": False,
        "production_backfill_started": False,
        "production_actions": 0,
    }
