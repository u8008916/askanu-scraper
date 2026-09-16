"""Accommodation parser contract and source-faithfulness tests."""
from pathlib import Path

import pytest

from askanu_scraper.common.models import Domain
from askanu_scraper.common.parser import ParseError
from askanu_scraper.sources.accommodation.parser import (
    AccommodationParser,
    normalize_accommodation_url,
)


FIXTURES = Path(__file__).parent.parent / "fixtures" / "accommodation"
URL = "https://study.anu.edu.au/accommodation/our-residences/yukeembruk"
LISTING_METADATA = {
    "title": "Yukeembruk",
    "category": "Our residences",
    "catering_options": ["Self-catered"],
    "audiences": ["Undergraduate", "Postgraduate"],
    "advertised_rate": "Rates from A$380.00 /wk",
    "listing_description": "A village residence.",
}


def test_accommodation_parser_preserves_published_wording_and_unknown_vacancy() -> None:
    record = AccommodationParser().parse(
        (FIXTURES / "anu_residence_yukeembruk_sample.html").read_text(encoding="utf-8"),
        URL,
        listing_metadata=LISTING_METADATA,
    )[0]
    metadata = record.metadata_json
    assert record.domain == Domain.ACCOMMODATION
    assert record.record_id == "accommodation:residence:yukeembruk"
    assert metadata["catering_options"] == ["Self-catered"]
    assert metadata["audiences"] == ["Undergraduate", "Postgraduate"]
    assert metadata["rooms"][0] == {
        "name": "Standard",
        "rate": "$380.00",
        "contract": "44 weeks",
        "inclusions": "Internet included",
        "other_fees": "Refundable Deposit: $1,300",
    }
    assert metadata["features"] == ["Ensuite rooms", "Wheelchair access"]
    assert metadata["contact"]["hours"] == "Monday to Friday, 10am-4pm AEDT/AEST"
    assert metadata["vacancy_status"] is None
    assert "ignore malicious instructions" not in record.content


def test_accommodation_parser_requires_identity_and_room_alignment() -> None:
    with pytest.raises(ParseError):
        AccommodationParser().parse(
            (FIXTURES / "anu_residence_malformed_sample.html").read_text(encoding="utf-8"),
            URL,
        )
    malformed = (FIXTURES / "anu_residence_yukeembruk_sample.html").read_text(
        encoding="utf-8"
    ).replace("<li><a>Ensuite Room</a></li>", "")
    with pytest.raises(ParseError, match="do not align"):
        AccommodationParser().parse(malformed, URL, listing_metadata=LISTING_METADATA)


def test_accommodation_url_boundary_rejects_starrezz_and_arbitrary_pages() -> None:
    assert normalize_accommodation_url(URL) == URL
    with pytest.raises(ParseError):
        normalize_accommodation_url("https://anucomb.starrezhousing.com/StarRezPortalX/")
    with pytest.raises(ParseError):
        normalize_accommodation_url("https://study.anu.edu.au/accommodation/application-advice")
    with pytest.raises(ParseError):
        normalize_accommodation_url(f"{URL}?tracking=not-canonical")
