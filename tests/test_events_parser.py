"""Events v1 contract, temporal, provenance, and sanitization tests."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from askanu_scraper.common.normalizer import CANBERRA_TZ
from askanu_scraper.common.parser import ParseError
from askanu_scraper.sources.events.parser import EventsParser, normalize_event_url, parse_displayed_interval


FIXTURES = Path(__file__).parents[1] / "fixtures" / "events"
NOW = datetime(2026, 9, 18, 12, 0, tzinfo=CANBERRA_TZ)


def parse_fixture(name: str, url: str):
    return EventsParser(now_func=lambda: NOW).parse(
        (FIXTURES / name).read_text(encoding="utf-8"), url
    )[0]


def test_timed_event_contract_identity_provenance_and_registration() -> None:
    record = parse_fixture(
        "window-opening.html", "https://www.anu.edu.au/events/window-opening"
    )
    assert record.record_id == "events:event:1001"
    assert record.entity_id == "1001"
    assert record.metadata_json["event_id"] == "1001"
    assert set(record.metadata_json) == {
        "entity_type", "event_id", "start_date", "end_date", "start_at", "end_at",
        "timezone", "location", "format", "categories", "tags", "organiser",
        "description", "registration_links", "status", "cancellation_text",
    }
    assert record.metadata_json["organiser"].startswith("Presented by")
    assert len(record.metadata_json["registration_links"]) == 2
    assert "alert" not in record.content
    assert record.effective_from.isoformat() == "2026-09-18T09:00:00+10:00"
    assert record.effective_to.isoformat() == "2026-09-19T17:00:00+10:00"


def test_dst_transition_uses_canberra_offsets() -> None:
    record = parse_fixture("dst-event.html", "https://www.anu.edu.au/events/dst-event")
    assert record.metadata_json["start_at"] == "2026-10-03T21:00:00+10:00"
    assert record.metadata_json["end_at"] == "2026-10-04T16:00:00+11:00"


def test_multiple_published_occurrences_form_the_event_interval() -> None:
    html = (FIXTURES / "dst-event.html").read_text(encoding="utf-8").replace(
        "<li>Sat 3 Oct 2026, 9:00 pm - Sun 4 Oct 2026, 4:00 pm</li>",
        "<li>Tue 15 Sep 2026, 1:00 pm</li>"
        "<li>Tue 22 Sep 2026, 12:30 pm - Tue 22 Sep 2026, 1:00 pm</li>",
    )
    record = EventsParser(now_func=lambda: NOW).parse(
        html, "https://www.anu.edu.au/events/dst-event"
    )[0]
    assert record.metadata_json["start_at"] == "2026-09-15T13:00:00+10:00"
    assert record.metadata_json["end_at"] == "2026-09-22T13:00:00+10:00"


def test_date_only_cancelled_event_does_not_invent_times() -> None:
    record = parse_fixture(
        "date-only-cancelled.html",
        "https://www.anu.edu.au/events/cancelled-exhibition",
    )
    assert record.metadata_json["start_date"] == "2026-09-19"
    assert record.metadata_json["end_date"] == "2026-09-20"
    assert record.metadata_json["start_at"] is None
    assert record.effective_from is None
    assert record.metadata_json["status"] == "cancelled"
    assert record.metadata_json["cancellation_text"] == "Cancelled due to venue closure"


@pytest.mark.parametrize(
    "value",
    [
        "Sun 20 Sep 2026 - Sat 19 Sep 2026",
        "Sat 19 Sep 2026, 9:00 am - Sat 19 Sep 2026",
        "not a date",
    ],
)
def test_invalid_intervals_are_rejected(value: str) -> None:
    with pytest.raises(ParseError):
        parse_displayed_interval(value)


def test_canonical_mismatch_and_identity_conflict_are_rejected() -> None:
    html = (FIXTURES / "window-opening.html").read_text(encoding="utf-8")
    parser = EventsParser(now_func=lambda: NOW)
    with pytest.raises(ParseError, match="canonical URL does not match"):
        parser.parse(html, "https://www.anu.edu.au/events/different")
    with pytest.raises(ParseError, match="identities conflict"):
        parser.parse(html.replace('"entityId":"1001"', '"entityId":"9999"'),
                     "https://www.anu.edu.au/events/window-opening")


@pytest.mark.parametrize(
    "url",
    [
        "https://anu.edu.au/events/example",
        "https://www.anu.edu.au/events/example?token=x",
        "https://www.anu.edu.au/events/example#fragment",
        "https://user:pass@www.anu.edu.au/events/example",
        "https://www.anu.edu.au/news/example",
        "https://www.anu.edu.au/events/podcasts",
        "https://www.anu.edu.au/events/submit-an-event",
    ],
)
def test_event_url_boundary_is_exact(url: str) -> None:
    with pytest.raises(ParseError):
        normalize_event_url(url)
