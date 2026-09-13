"""Scholarship detail normalization and bounded discovery tests."""
from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from askanu_scraper.common.models import CommonRecord, Domain
from askanu_scraper.common.parser import ParseError
from askanu_scraper.sources.scholarships.discovery import ScholarshipsDiscovery
from askanu_scraper.sources.scholarships.parser import ScholarshipsParser


FIXTURES = Path(__file__).parent.parent / "fixtures" / "scholarships"


def _parse(name: str, url: str, **listing_metadata):
    html = (FIXTURES / name).read_text(encoding="utf-8")
    return ScholarshipsParser().parse(
        html,
        url,
        listing_metadata=listing_metadata,
    )[0]


def test_open_featured_record_preserves_source_fields_and_stable_identity() -> None:
    url = (
        "https://study.anu.edu.au/scholarships/find-scholarship/"
        "anu-international-achievement-award"
    )
    first = _parse(
        "anu_scholarship_open_featured_sample.html",
        url,
        featured=True,
        status="Open for applications",
        application_requirement="Automatic consideration",
    )
    second = _parse(
        "anu_scholarship_open_featured_sample.html",
        url,
        featured=True,
        status="Open for applications",
        application_requirement="Automatic consideration",
    )

    assert first.domain == Domain.SCHOLARSHIPS
    assert first.source_id == "scholarships_anu_finder"
    assert first.entity_id == "anu-international-achievement-award"
    assert first.record_id == (
        "scholarships:scholarship:anu-international-achievement-award"
    )
    assert first.canonical_url == url
    assert first.metadata_json["featured"] is True
    assert first.metadata_json["status"] == "Open for applications"
    # Detail evidence takes precedence over the shorter listing label.
    assert first.metadata_json["application_required"] is False
    assert first.metadata_json["student_type"] == ["International"]
    assert first.metadata_json["area_of_study"] == [
        "Any eligible program except excluded programs listed by ANU"
    ]
    assert first.metadata_json["study_level"] == [
        "Undergraduate/Bachelor",
        "Honours",
        "Postgraduate/Masters, and Graduate certificate",
    ]
    assert first.metadata_json["selection_basis"] == "Academic merit"
    assert first.metadata_json["closing_date"] is None
    assert first.effective_to is None
    assert first.content == second.content
    assert first.content_hash == second.content_hash


def test_open_non_featured_listing_evidence_is_retained() -> None:
    url = (
        "https://study.anu.edu.au/scholarships/find-scholarship/"
        "alex-rodgers-travel-grant"
    )
    record = _parse(
        "anu_scholarship_open_non_featured_sample.html",
        url,
        featured=False,
        status="Open for applications",
        application_requirement="Requires application",
    )

    assert record.metadata_json["featured"] is False
    assert record.metadata_json["status"] == "Open for applications"
    assert record.metadata_json["application_required"] is True
    assert record.metadata_json["value"].startswith("$5,000")
    assert record.metadata_json["eligibility"].startswith("Applicants must")
    assert "Featured: No" in record.content


def test_closed_period_preserves_dates_without_treating_them_as_record_validity() -> None:
    url = (
        "https://study.anu.edu.au/scholarships/find-scholarship/"
        "anu-humanitarian-scholarship"
    )
    record = _parse(
        "anu_humanitarian_scholarship_sample.html",
        url,
        featured=False,
        status="Application closed",
    )

    assert record.metadata_json["status"] == "Application closed"
    assert record.metadata_json["opening_date"] == "2025-01-16"
    assert record.metadata_json["closing_date"] == "2025-02-07"
    assert "Application Period: 16-Jan-2025 to 07-Feb-2025" in record.content
    assert record.effective_from is None
    assert record.effective_to is None


def test_missing_deadline_and_placeholder_value_remain_null() -> None:
    url = "https://study.anu.edu.au/scholarships/find-scholarship/start-life"
    record = _parse(
        "anu_scholarship_missing_deadline_sample.html",
        url,
        featured=False,
        status="Open for applications",
        application_requirement="Requires application",
    )

    assert record.metadata_json["opening_date"] is None
    assert record.metadata_json["closing_date"] is None
    assert record.metadata_json["value"] is None
    assert record.metadata_json["study_stage"] == []
    assert record.metadata_json["area_of_study"] == []
    assert record.effective_from is None
    assert record.effective_to is None
    assert "Application Closes:" not in record.content
    assert "Value:" not in record.content


def test_malformed_detail_raises_instead_of_returning_empty() -> None:
    url = "https://study.anu.edu.au/scholarships/find-scholarship/malformed-sample"
    html = (FIXTURES / "anu_scholarship_malformed_sample.html").read_text(
        encoding="utf-8"
    )
    with pytest.raises(ParseError, match="title is missing"):
        ScholarshipsParser().parse(html, url)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.test/scholarships/find-scholarship/not-approved",
        "https://study.anu.edu.au/apply/scholarship-account",
        "http://study.anu.edu.au/scholarships/find-scholarship/valid",
    ],
)
def test_parser_rejects_urls_outside_exact_public_detail_boundary(url: str) -> None:
    html = (FIXTURES / "anu_scholarship_open_featured_sample.html").read_text(
        encoding="utf-8"
    ).replace(
        "https://study.anu.edu.au/scholarships/find-scholarship/"
        "anu-international-achievement-award",
        url,
    )
    with pytest.raises(ParseError, match="approved"):
        ScholarshipsParser().parse(html, url)


@pytest.mark.parametrize(
    "suffix",
    ["/", "?tracking=source", "#details", "/?tracking=source#details"],
)
def test_parser_strips_non_identity_url_components(suffix: str) -> None:
    base = (
        "https://study.anu.edu.au/scholarships/find-scholarship/"
        "anu-international-achievement-award"
    )
    html = (FIXTURES / "anu_scholarship_open_featured_sample.html").read_text(
        encoding="utf-8"
    ).replace(base, base + suffix)
    record = ScholarshipsParser().parse(html, base + suffix)[0]

    assert record.canonical_url == base
    assert record.entity_id == "anu-international-achievement-award"
    assert record.record_id == (
        "scholarships:scholarship:anu-international-achievement-award"
    )


def test_common_record_rejects_the_superseded_scholarship_identity() -> None:
    record = _parse(
        "anu_scholarship_open_featured_sample.html",
        "https://study.anu.edu.au/scholarships/find-scholarship/"
        "anu-international-achievement-award",
    )
    payload = record.model_dump()
    payload["record_id"] = f"scholarships:{record.entity_id}"

    with pytest.raises(ValidationError, match="Scholarship record_id"):
        CommonRecord.model_validate(payload)


def test_common_record_rejects_metadata_outside_qasim_v1_contract() -> None:
    record = _parse(
        "anu_scholarship_open_featured_sample.html",
        "https://study.anu.edu.au/scholarships/find-scholarship/"
        "anu-international-achievement-award",
    )
    payload = record.model_dump()
    payload["metadata_json"]["application_requirement"] = "Automatic consideration"

    with pytest.raises(ValidationError, match="approved v1 fields"):
        CommonRecord.model_validate(payload)


def test_discovery_deduplicates_rejects_and_enforces_detail_limit() -> None:
    html = (FIXTURES / "anu_scholarship_listing_safety_sample.html").read_text(
        encoding="utf-8"
    )
    result = ScholarshipsDiscovery().discover(
        html,
        "https://study.anu.edu.au/scholarships/find-scholarship",
        max_details=2,
    )

    assert [candidate.url for candidate in result.candidates] == [
        "https://study.anu.edu.au/scholarships/find-scholarship/"
        "anu-international-achievement-award",
        "https://study.anu.edu.au/scholarships/find-scholarship/"
        "alex-rodgers-travel-grant",
    ]
    assert result.candidates[0].featured is True
    assert result.candidates[1].featured is False
    assert result.discovered_candidate_count == 8
    assert len(result.duplicate_links) == 1
    assert result.over_limit_count == 1
    assert len(result.rejected_links) == 6


@pytest.mark.parametrize("bound", [0, 11])
def test_discovery_rejects_unapproved_bounds(bound: int) -> None:
    with pytest.raises(ValueError, match="between 1 and 10"):
        ScholarshipsDiscovery().discover(
            "<html></html>",
            "https://study.anu.edu.au/scholarships/find-scholarship",
            max_details=bound,
        )
