"""V7 Day 1 producer capability, identity, and lookup-term handoff."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

import pytest

from askanu_scraper.common.models import Domain
from askanu_scraper.common.normalizer import CANBERRA_TZ
from askanu_scraper.common.registry import get_approved_sources
from askanu_scraper.common.v7_contract import (
    EvidenceSupport,
    UnsupportedProducerContractError,
    get_v7_producer_contracts,
    normalize_lookup_term,
    producer_contract_for,
    source_backed_lookup_terms,
    source_authority_for,
)
from askanu_scraper.sources.accommodation.parser import AccommodationParser
from askanu_scraper.sources.courses.parser import CoursesParser
from askanu_scraper.sources.events.parser import EventsParser
from askanu_scraper.sources.events.rubric_adapter import parse_detail
from askanu_scraper.sources.jobs.parser import JobsParser
from askanu_scraper.sources.scholarships.parser import ScholarshipsParser
from askanu_scraper.sources.support.parser import SupportParser


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "fixtures" / "v7" / "day1" / "producer-capabilities.json"
OBSERVED_AT = datetime(2026, 9, 21, 12, 0, tzinfo=CANBERRA_TZ)


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _record(case: dict[str, object]):
    fixture = ROOT / str(case["source_fixture"])
    raw = fixture.read_text(encoding="utf-8")
    source_id = case["source_id"]
    url = str(case.get("source_url", ""))
    listing_metadata = case.get("listing_metadata")

    if source_id == "courses_programs_and_courses":
        return CoursesParser().parse(raw, url)[0]
    if source_id == "scholarships_anu_finder":
        return ScholarshipsParser().parse(
            raw, url, listing_metadata=listing_metadata
        )[0]
    if source_id == "jobs_anu_search":
        return JobsParser(now_func=lambda: OBSERVED_AT).parse(
            raw, url, listing_metadata=listing_metadata
        )[0]
    if source_id == "accommodation_anu_study":
        return AccommodationParser().parse(
            raw, url, listing_metadata=listing_metadata
        )[0]
    if source_id == "support_anusa_student_assistance":
        return SupportParser().parse(
            raw, url, listing_metadata=listing_metadata
        )[0]
    if source_id == "events_anu_official":
        return EventsParser(now_func=lambda: OBSERVED_AT).parse(raw, url)[0]
    if source_id == "rubric_unified_search":
        return parse_detail(raw, "78459", now_func=lambda: OBSERVED_AT)
    raise AssertionError(f"Unexpected Day 1 source: {source_id}")


def test_inventory_covers_six_domains_all_shapes_and_active_sources() -> None:
    contracts = get_v7_producer_contracts()

    assert {contract.domain for contract in contracts} == set(Domain)
    assert {(contract.domain.value, contract.entity_type) for contract in contracts} == {
        ("courses", "course"),
        ("courses", "program"),
        ("scholarships", "scholarship"),
        ("jobs", "job"),
        ("accommodation", "residence"),
        ("support", "support_service"),
        ("events", "event"),
    }

    inventoried_sources = {
        source_id for contract in contracts for source_id in contract.source_ids
    }
    assert inventoried_sources == {
        source.source_id for source in get_approved_sources()
    }

    for contract in contracts:
        assert [item.operation for item in contract.capabilities] == [
            "lookup",
            "discovery",
            "filter",
            "compare",
            "match",
        ]
        assert all(isinstance(item.support, EvidenceSupport) for item in contract.capabilities)
        assert contract.source_alias_paths == ()


def test_scholarship_matching_keeps_structured_content_and_unknown_boundaries() -> None:
    contract = next(
        contract
        for contract in get_v7_producer_contracts()
        if contract.domain == Domain.SCHOLARSHIPS
    )
    matching = next(
        item for item in contract.capabilities if item.operation == "match"
    )

    assert matching.support == EvidenceSupport.STRUCTURED_AND_CONTENT
    assert "structured dimensions support candidate filtering" in matching.basis
    assert "content-assisted relevance" in matching.basis
    assert "missing evidence stays unknown" in matching.basis
    assert "personal eligibility and ranking are unsupported" in matching.basis
    assert {
        "metadata_json.study_stage",
        "metadata_json.student_type",
        "metadata_json.study_level",
        "metadata_json.area_of_study",
        "metadata_json.status",
        "metadata_json.opening_date",
        "metadata_json.closing_date",
        "metadata_json.eligibility",
        "metadata_json.selection_basis",
    }.issubset(contract.structured_fact_paths)
    assert {
        "personal_eligibility_decision",
        "best_scholarship_ranking",
    }.issubset(contract.absent_facts)


@pytest.mark.parametrize("case", _manifest()["cases"], ids=lambda case: case["name"])
def test_handoff_cases_match_parser_records_and_source_terms(
    case: dict[str, object],
) -> None:
    record = _record(case)
    before = record.model_dump(mode="json")
    contract = producer_contract_for(record)
    terms = source_backed_lookup_terms(record)
    authority = source_authority_for(record)

    assert record.domain.value == case["domain"]
    assert record.source_id == case["source_id"]
    assert record.metadata_json["entity_type"] == case["entity_type"]
    assert record.record_id == case["expected_record_id"]
    assert [
        {"kind": term.kind.value, "value": term.value, "normalized": term.normalized}
        for term in terms
    ] == case["expected_lookup_terms"]
    assert contract.domain == record.domain
    assert authority.source_id == case["source_id"]
    assert authority.authority_rank == case["expected_authority_rank"]
    assert authority.approval_status.value == case["expected_approval_status"]
    assert record.model_dump(mode="json") == before


def test_manifest_is_offline_and_references_only_checked_in_fixtures() -> None:
    manifest = _manifest()

    assert manifest["network_calls_allowed"] is False
    assert len(manifest["cases"]) == 8
    for case in manifest["cases"]:
        fixture = ROOT / case["source_fixture"]
        assert fixture.is_file()
        assert fixture.resolve().is_relative_to((ROOT / "fixtures").resolve())


def test_lookup_normalization_does_not_expand_punctuation_or_synonyms() -> None:
    assert normalize_lookup_term("  CAF\u00c9\u2014Studies\n (ANU)  ") == "caf\u00e9\u2014studies (anu)"

    course_case = _manifest()["cases"][0]
    terms = source_backed_lookup_terms(_record(course_case))
    values = {term.normalized for term in terms}
    assert values == {"comp1100 programming as problem solving", "comp1100"}
    assert "intro to programming" not in values
    assert all(term.kind.value != "source_alias" for term in terms)


def test_unreviewed_source_record_has_no_implicit_contract() -> None:
    record = _record(_manifest()["cases"][0])
    unreviewed = record.model_copy(update={"source_id": "unreviewed_source"})

    with pytest.raises(UnsupportedProducerContractError, match="No V7 producer contract"):
        producer_contract_for(unreviewed)
