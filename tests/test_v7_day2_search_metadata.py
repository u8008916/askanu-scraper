"""V7 Day 2 safe resolver terms, temporal values, and collision evidence."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

import pytest

from askanu_scraper.common.normalizer import CANBERRA_TZ
from askanu_scraper.common.search_metadata import (
    SearchMetadataError,
    build_resolver_search_metadata,
    find_duplicate_record_ids,
    find_term_collisions,
)
from askanu_scraper.sources.accommodation.parser import AccommodationParser
from askanu_scraper.sources.courses.parser import CoursesParser
from askanu_scraper.sources.events.parser import EventsParser
from askanu_scraper.sources.events.rubric_adapter import parse_detail
from askanu_scraper.sources.jobs.parser import JobsParser
from askanu_scraper.sources.scholarships.parser import ScholarshipsParser
from askanu_scraper.sources.support.parser import SupportParser


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "fixtures" / "v7" / "day2" / "resolver-search-metadata.json"
OBSERVED_AT = datetime(2026, 9, 22, 12, 0, tzinfo=CANBERRA_TZ)


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


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
    raise AssertionError(f"Unexpected Day 2 parser: {parser}")


def _serialized_terms(metadata) -> list[dict[str, object]]:
    return [
        {
            "kind": term.kind.value,
            "value": term.value,
            "normalized": term.normalized,
            "source_path": term.source_path,
        }
        for term in metadata.lookup_terms
    ]


def _serialized_temporal(metadata) -> list[dict[str, object]]:
    return [
        {
            "kind": value.kind.value,
            "value": value.value,
            "precision": value.precision.value,
            "source_path": value.source_path,
            "timezone": value.timezone,
        }
        for value in metadata.temporal_values
    ]


@pytest.mark.parametrize("case", _manifest()["cases"], ids=lambda case: case["name"])
def test_manifest_matches_parser_output_without_record_mutation(
    case: dict[str, object],
) -> None:
    record = _record(case)
    before = record.model_dump(mode="json")

    metadata = build_resolver_search_metadata(record)

    assert metadata.record_id == case["expected_record_id"]
    assert metadata.source_id == record.source_id
    assert metadata.domain == record.domain
    assert metadata.entity_type == record.metadata_json["entity_type"]
    assert _serialized_terms(metadata) == case["expected_terms"]
    assert _serialized_temporal(metadata) == case["expected_temporal"]
    assert record.model_dump(mode="json") == before


def test_manifest_is_offline_and_covers_every_day1_record_shape() -> None:
    manifest = _manifest()

    assert manifest["network_calls_allowed"] is False
    assert manifest["depends_on"] == "v7-day1-producer-capabilities-v1"
    assert len(manifest["cases"]) == 8
    assert {case["parser"] for case in manifest["cases"]} == {
        "courses",
        "scholarships",
        "jobs",
        "accommodation",
        "support",
        "events",
        "rubric",
    }
    for case in manifest["cases"]:
        fixture = (ROOT / case["source_fixture"]).resolve()
        assert fixture.is_file()
        assert fixture.is_relative_to((ROOT / "fixtures").resolve())


def test_no_unreviewed_aliases_or_magic_wording_are_created() -> None:
    records = [_record(case) for case in _manifest()["cases"]]
    all_terms = [
        term
        for record in records
        for term in build_resolver_search_metadata(record).lookup_terms
    ]

    assert all(term.kind.value != "source_alias" for term in all_terms)
    normalized = {term.normalized for term in all_terms}
    assert "comp1100" in normalized
    assert "yukeembruk" in normalized
    assert "intro to programming" not in normalized
    assert "cheap accommodation" not in normalized
    assert "academic help" not in normalized


def test_missing_job_deadline_stays_absent() -> None:
    raw = (ROOT / "fixtures/jobs/anu_job_open_undated_sample.html").read_text(
        encoding="utf-8"
    )
    record = JobsParser(now_func=lambda: OBSERVED_AT).parse(
        raw,
        "https://jobs.anu.edu.au/jobs/anu-talent-register-canberra-act-australia",
    )[0]

    metadata = build_resolver_search_metadata(record)

    assert metadata.temporal_values == ()
    assert record.metadata_json["closing_date"] is None
    assert record.metadata_json["closing_at"] is None


def test_date_only_job_deadline_does_not_gain_an_invented_time() -> None:
    raw = (ROOT / "fixtures/jobs/anu_job_open_dated_sample.html").read_text(
        encoding="utf-8"
    ).replace(
        "Closing at: Sep 27 2026 - 23:55 AEST",
        "Closing on: Sep 27 2026",
    )
    record = JobsParser(now_func=lambda: OBSERVED_AT).parse(
        raw,
        "https://jobs.anu.edu.au/jobs/senior-consultant-user-experience-hr-systems-projects-canberra-act-act-australia",
    )[0]

    temporal = build_resolver_search_metadata(record).temporal_values

    assert [(item.kind.value, item.value) for item in temporal] == [
        ("closes_on", "2026-09-27")
    ]
    assert record.metadata_json["closing_at"] is None


def test_naive_datetime_is_rejected_instead_of_receiving_a_timezone() -> None:
    job_case = next(
        case for case in _manifest()["cases"] if case["parser"] == "jobs"
    )
    record = _record(job_case)
    invalid_metadata = dict(record.metadata_json)
    invalid_metadata["closing_at"] = "2026-09-27T23:55:00"
    invalid = record.model_copy(update={"metadata_json": invalid_metadata})

    with pytest.raises(SearchMetadataError, match="timezone-aware"):
        build_resolver_search_metadata(invalid)


def test_same_course_code_across_years_is_reported_not_resolved() -> None:
    course_case = _manifest()["cases"][0]
    record_2026 = _record(course_case)
    raw_2027 = (
        ROOT / "fixtures/courses/comp1100_course_sample.html"
    ).read_text(encoding="utf-8").replace("2026", "2027")
    record_2027 = CoursesParser().parse(
        raw_2027,
        "https://programsandcourses.anu.edu.au/2027/course/COMP1100",
    )[0]

    collisions = find_term_collisions([record_2027, record_2026])

    assert [collision.normalized for collision in collisions] == [
        "comp1100",
        "comp1100 programming as problem solving",
    ]
    for collision in collisions:
        assert [item.record_id for item in collision.references] == [
            "courses:course:COMP1100_2026",
            "courses:course:COMP1100_2027",
        ]
    assert record_2026.entity_id != record_2027.entity_id
    assert record_2026.record_id != record_2027.record_id


def test_duplicate_ids_are_reported_without_becoming_term_collisions() -> None:
    record = _record(_manifest()["cases"][0])

    assert find_duplicate_record_ids([record, record]) == (record.record_id,)
    assert find_term_collisions([record, record]) == ()


def test_event_authority_stays_source_specific() -> None:
    event_cases = [
        case
        for case in _manifest()["cases"]
        if case["parser"] in {"events", "rubric"}
    ]
    official, rubric = [
        build_resolver_search_metadata(_record(case)) for case in event_cases
    ]

    assert official.source_id == "events_anu_official"
    assert official.authority.authority_rank == 1
    assert official.authority.approval_status.value == "APPROVED"
    assert rubric.source_id == "rubric_unified_search"
    assert rubric.authority.authority_rank == 3
    assert (
        rubric.authority.approval_status.value
        == "APPROVED_BOUNDED_UNSUPPORTED"
    )
