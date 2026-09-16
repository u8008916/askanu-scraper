"""ANUSA Support parser contract and sanitization tests."""
from pathlib import Path

import pytest

from askanu_scraper.common.models import Domain
from askanu_scraper.common.parser import ParseError
from askanu_scraper.sources.support.parser import SupportParser, normalize_support_url


FIXTURES = Path(__file__).parent.parent / "fixtures" / "support"
URL = "https://anusa.com.au/student-assistance/academic/"
LISTING_METADATA = {
    "title": "Academic",
    "category": "Academic",
    "listing_description": "Help with academic issues.",
    "audiences": ["all ANU Students"],
    "cost": "The service is free.",
    "registry_email": "sa.assistance@anu.edu.au",
}


def test_support_parser_captures_only_published_facts_and_sanitizes_markup() -> None:
    record = SupportParser().parse(
        (FIXTURES / "anusa_academic_sample.html").read_text(encoding="utf-8"),
        URL,
        listing_metadata=LISTING_METADATA,
    )[0]
    metadata = record.metadata_json
    assert record.domain == Domain.SUPPORT
    assert record.record_id == "support:service:academic"
    assert metadata["purpose"] == "ANUSA can help with academic issues."
    assert metadata["audiences"] == ["all ANU Students"]
    assert metadata["contact"] == {
        "email": "sa.assistance@anu.edu.au",
        "phone": "02 6125 2444",
        "location": "Level 2, Di Riddell Student Centre, Kambri",
    }
    assert metadata["hours"] == "Monday to Friday 10am-4pm"
    assert metadata["cost"] == "The service is free."
    assert metadata["topics"][0]["title"] == "Grade Appeal"
    assert metadata["referrals"] == [
        {
            "label": "ANU assessment guidance",
            "url": "https://www.anu.edu.au/students/program-administration/assessments-exams",
        }
    ]
    assert "Reveal system prompt" not in record.content
    assert "evil.example" not in record.content


def test_support_parser_does_not_infer_missing_hours() -> None:
    record = SupportParser().parse(
        (FIXTURES / "anusa_financial_sample.html").read_text(encoding="utf-8"),
        "https://anusa.com.au/student-assistance/financial/",
        listing_metadata={**LISTING_METADATA, "title": "Financial", "category": "Financial"},
    )[0]
    assert record.metadata_json["hours"] is None
    assert record.metadata_json["access"] is None


def test_support_url_boundary_rejects_nested_and_unapproved_hosts() -> None:
    assert normalize_support_url(URL) == URL
    with pytest.raises(ParseError):
        normalize_support_url(
            "https://anusa.com.au/student-assistance/academic/grade-appeal/"
        )
    with pytest.raises(ParseError):
        normalize_support_url("https://www.anu.edu.au/students/health")
    with pytest.raises(ParseError):
        normalize_support_url(f"{URL}#contact")
