"""V7 Day 3 data/evidence side of the frozen retrieval benchmark."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

import pytest

from askanu_scraper.common.benchmark_evidence import (
    BenchmarkEvidenceError,
    EvidenceClassification,
    EvidenceLocation,
    EvidenceRequirement,
    EvidenceState,
    FreshnessStatus,
    SourceEvidenceStatus,
    assess_requirement,
    audit_benchmark,
    compare_structured_evidence,
    load_benchmark_requirements,
    project_structured_evidence,
)
from askanu_scraper.common.models import Domain
from askanu_scraper.common.normalizer import CANBERRA_TZ
from askanu_scraper.common.search_metadata import build_resolver_search_metadata
from askanu_scraper.sources.accommodation.parser import AccommodationParser
from askanu_scraper.sources.courses.parser import CoursesParser
from askanu_scraper.sources.events.parser import EventsParser
from askanu_scraper.sources.events.rubric_adapter import parse_detail
from askanu_scraper.sources.jobs.parser import JobsParser
from askanu_scraper.sources.scholarships.parser import ScholarshipsParser
from askanu_scraper.sources.support.parser import SupportParser


ROOT = Path(__file__).resolve().parents[1]
DAY2_MANIFEST = ROOT / "fixtures/v7/day2/resolver-search-metadata.json"
DAY3_MANIFEST = ROOT / "fixtures/v7/day3/representative-evidence-audit.json"
OBSERVED_AT = datetime(2026, 9, 23, 12, 0, tzinfo=CANBERRA_TZ)


def _record(case: dict[str, object]):
    raw = (ROOT / str(case["source_fixture"])).read_text(encoding="utf-8")
    parser = case["parser"]
    url = str(case.get("source_url", ""))
    listing_metadata = case.get("listing_metadata")
    if parser == "courses":
        return CoursesParser().parse(raw, url)[0]
    if parser == "scholarships":
        return ScholarshipsParser().parse(
            raw, url, listing_metadata=listing_metadata
        )[0]
    if parser == "jobs":
        return JobsParser(now_func=lambda: OBSERVED_AT).parse(
            raw, url, listing_metadata=listing_metadata
        )[0]
    if parser == "accommodation":
        return AccommodationParser().parse(
            raw, url, listing_metadata=listing_metadata
        )[0]
    if parser == "support":
        return SupportParser().parse(
            raw, url, listing_metadata=listing_metadata
        )[0]
    if parser == "events":
        return EventsParser(now_func=lambda: OBSERVED_AT).parse(raw, url)[0]
    if parser == "rubric":
        return parse_detail(raw, "78459", now_func=lambda: OBSERVED_AT)
    raise AssertionError(f"unexpected parser: {parser}")


def _records():
    day2 = json.loads(DAY2_MANIFEST.read_text(encoding="utf-8"))
    records = [_record(case) for case in day2["cases"]]
    comp2120 = CoursesParser().parse(
        (ROOT / "fixtures/v7/day3/comp2120-requisite-sample.html").read_text(
            encoding="utf-8"
        ),
        "https://programsandcourses.anu.edu.au/2026/course/COMP2120",
    )[0]
    return [*records, comp2120]


def test_manifest_is_explicitly_representative_until_carmen_freezes_queries() -> None:
    raw = json.loads(DAY3_MANIFEST.read_text(encoding="utf-8"))
    version, requirements = load_benchmark_requirements(DAY3_MANIFEST)

    assert version == "v7-day3-representative-evidence-audit-v1"
    assert raw["carmen_benchmark_version"] is None
    assert raw["completion_status"] == "BLOCKED_PENDING_CARMEN_BENCHMARK"
    assert raw["network_calls_allowed"] is False
    assert len(requirements) == 14
    assert {requirement.domain for requirement in requirements} == set(Domain)


def test_comp2120_preserves_completed_or_currently_studying_semantics() -> None:
    record = _records()[-1]

    assert record.metadata_json["prerequisites"] == (
        "successfully completed or be currently studying COMP2100"
    )
    assert not record.metadata_json["prerequisites"].startswith("or ")
    assert (
        "Prerequisites: successfully completed or be currently studying COMP2100"
        in record.content
    )
    assert record.metadata_json["incompatibilities"] == (
        "COMP2130, COMP6120 and COMP6311"
    )


def test_representative_audit_emits_requested_metrics_and_provenance() -> None:
    version, requirements = load_benchmark_requirements(DAY3_MANIFEST)

    report = audit_benchmark(_records(), requirements, benchmark_version=version)

    assert [item.classification for item in report.assessments].count(
        EvidenceClassification.PRESENT_STRUCTURED
    ) == 9
    assert [item.classification for item in report.assessments].count(
        EvidenceClassification.PRESENT_CONTENT_ONLY
    ) == 1
    assert [item.classification for item in report.assessments].count(
        EvidenceClassification.MISSING_SOURCE
    ) == 2
    assert [item.classification for item in report.assessments].count(
        EvidenceClassification.AMBIGUOUS_SOURCE
    ) == 1
    assert [item.classification for item in report.assessments].count(
        EvidenceClassification.INCOMPLETE_POPULATION
    ) == 1
    assert all(item.provenance_complete for item in report.assessments)

    overall = report.metrics["overall"]
    assert overall["requirement_count"] == 14
    assert overall["query_count"] == 14
    assert overall["classification_counts"]["PRESENT_STRUCTURED"] == 9
    assert overall["classification_counts"]["PRESENT_CONTENT_ONLY"] == 1
    assert overall["failure_classification_counts"]["NOT_DATA_FAILURE"] == 10
    assert overall["provenance_complete_percent"] == 100.0
    assert set(report.metrics["by_domain"]) == {domain.value for domain in Domain}


def test_shared_projection_preserves_false_lists_and_asymmetric_missingness() -> None:
    scholarship = next(
        record for record in _records() if record.domain == Domain.SCHOLARSHIPS
    )
    present_metadata = dict(scholarship.metadata_json)
    present_metadata["application_required"] = False
    present = scholarship.model_copy(update={"metadata_json": present_metadata})
    missing_metadata = dict(scholarship.metadata_json)
    missing_metadata["application_required"] = None
    missing = scholarship.model_copy(
        update={
            "record_id": f"{scholarship.record_id}:missing",
            "entity_id": f"{scholarship.entity_id}-missing",
            "metadata_json": missing_metadata,
        }
    )
    before = [record.model_dump(mode="json") for record in (present, missing)]

    rows = compare_structured_evidence([present, missing])
    application = next(
        row for row in rows if row.source_path == "metadata_json.application_required"
    )
    study_levels = next(
        row for row in rows if row.source_path == "metadata_json.study_level"
    )

    assert [(item.state, item.value) for item in application.values] == [
        (EvidenceState.ESTABLISHED, False),
        (EvidenceState.NOT_ESTABLISHED, None),
    ]
    assert study_levels.values[0].value == scholarship.metadata_json["study_level"]
    assert [record.model_dump(mode="json") for record in (present, missing)] == before


def test_all_reviewed_shapes_project_without_record_or_schema_mutation() -> None:
    records = _records()
    before = [record.model_dump(mode="json") for record in records]

    projected = [project_structured_evidence(record) for record in records]

    assert all(projected)
    assert [record.model_dump(mode="json") for record in records] == before
    assert all("benchmark" not in record.metadata_json for record in records)


def test_temporal_precision_and_missing_values_remain_day2_semantics() -> None:
    records = _records()
    scholarship = next(item for item in records if item.domain == Domain.SCHOLARSHIPS)
    job = next(item for item in records if item.domain == Domain.JOBS)
    official = next(
        item for item in records if item.source_id == "events_anu_official"
    )

    assert [
        (item.kind.value, item.value, item.precision.value)
        for item in build_resolver_search_metadata(scholarship).temporal_values
    ] == [
        ("opens_on", "2025-01-16", "date"),
        ("closes_on", "2025-02-07", "date"),
    ]
    assert [
        (item.kind.value, item.value, item.precision.value)
        for item in build_resolver_search_metadata(job).temporal_values
    ] == [
        ("closes_on", "2026-09-27", "date"),
        ("closes_at", "2026-09-27T23:55:00+10:00", "datetime"),
    ]
    assert build_resolver_search_metadata(official).temporal_values[0].timezone == (
        "Australia/Canberra"
    )

    raw = (ROOT / "fixtures/jobs/anu_job_open_undated_sample.html").read_text(
        encoding="utf-8"
    )
    undated = JobsParser(now_func=lambda: OBSERVED_AT).parse(
        raw,
        "https://jobs.anu.edu.au/jobs/anu-talent-register-canberra-act-australia",
    )[0]
    assert build_resolver_search_metadata(undated).temporal_values == ()


def test_data_failure_taxonomy_is_deterministic_and_fail_closed() -> None:
    course = _records()[0]
    base = EvidenceRequirement(
        query_id="taxonomy",
        domain=Domain.COURSES,
        expected_record_id=course.record_id,
        expected_source_id=course.source_id,
        expected_entity_id=course.entity_id,
        fact="course code",
        expected_location=EvidenceLocation.STRUCTURED,
        source_evidence=SourceEvidenceStatus.PRESENT,
        source_path="metadata_json.course_code",
        expected_value="WRONG1000",
        source_reference="fixtures/courses/comp1100_course_sample.html",
    )
    assert assess_requirement([course], base).classification == (
        EvidenceClassification.NORMALISATION_DEFECT
    )

    missing_record = EvidenceRequirement(
        **{
            **base.__dict__,
            "expected_record_id": "courses:course:MISSING1000_2026",
            "expected_entity_id": "MISSING1000_2026",
        }
    )
    assert assess_requirement([course], missing_record).classification == (
        EvidenceClassification.MISSING_INGESTION
    )

    wrong_id = course.model_copy(update={"record_id": f"{course.record_id}:wrong"})
    assert assess_requirement([wrong_id], base).classification == (
        EvidenceClassification.IDENTITY_DEFECT
    )

    stale = EvidenceRequirement(
        **{
            **base.__dict__,
            "expected_value": course.metadata_json["course_code"],
            "requires_current": True,
            "freshness_status": FreshnessStatus.UNKNOWN,
        }
    )
    assert assess_requirement([course], stale).classification == (
        EvidenceClassification.STALE
    )

    unsupported = EvidenceRequirement(
        **{**base.__dict__, "source_path": "metadata_json.magic_filter"}
    )
    with pytest.raises(BenchmarkEvidenceError, match="not a reviewed structured path"):
        assess_requirement([course], unsupported)


def test_content_only_evidence_is_not_promoted_to_a_structured_fact() -> None:
    official = next(
        item for item in _records() if item.source_id == "events_anu_official"
    )
    requirement = EvidenceRequirement(
        query_id="event-description",
        domain=Domain.EVENTS,
        expected_record_id=official.record_id,
        expected_source_id=official.source_id,
        expected_entity_id=official.entity_id,
        fact="event description",
        expected_location=EvidenceLocation.CONTENT,
        source_evidence=SourceEvidenceStatus.PRESENT,
        content_text="Official event description.",
        source_reference="fixtures/events/window-opening.html",
    )

    assessment = assess_requirement([official], requirement)

    assert assessment.classification == EvidenceClassification.PRESENT_CONTENT_ONLY
    assert assessment.failure_classification == EvidenceClassification.NOT_DATA_FAILURE
    assert "description" not in official.metadata_json


def test_official_and_rubric_event_identity_and_authority_remain_distinct() -> None:
    events = [record for record in _records() if record.domain == Domain.EVENTS]
    by_source = {record.source_id: record for record in events}

    assert set(by_source) == {"events_anu_official", "rubric_unified_search"}
    assert by_source["events_anu_official"].record_id == "events:event:1001"
    assert by_source["rubric_unified_search"].record_id == (
        "events:event:rubric-78459"
    )
    official = build_resolver_search_metadata(by_source["events_anu_official"])
    rubric = build_resolver_search_metadata(by_source["rubric_unified_search"])
    assert (official.authority.authority_rank, rubric.authority.authority_rank) == (1, 3)
    assert official.authority.approval_status != rubric.authority.approval_status
    comparison = compare_structured_evidence(
        [by_source["events_anu_official"], by_source["rubric_unified_search"]]
    )
    assert [item.source_id for item in comparison[0].values] == [
        "events_anu_official",
        "rubric_unified_search",
    ]
    assert [item.authority_rank for item in comparison[0].values] == [1, 3]


def test_comparison_refuses_cross_domain_reasoning() -> None:
    course = next(record for record in _records() if record.domain == Domain.COURSES)
    job = next(record for record in _records() if record.domain == Domain.JOBS)

    with pytest.raises(BenchmarkEvidenceError, match="same domain/entity type"):
        compare_structured_evidence([course, job])
