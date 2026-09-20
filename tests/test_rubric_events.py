"""Bounded Rubric Events ingestion, normalization and recovery tests."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Mapping

import pytest
import requests

from askanu_scraper.common.fetcher import BaseFetcher, FetchError
from askanu_scraper.common.models import IngestionRunStatus
from askanu_scraper.common.normalizer import CANBERRA_TZ
from askanu_scraper.common.parser import ParseError
from askanu_scraper.common.storage import LocalDataStore
from askanu_scraper.sources.events import EventsCollector, LISTING_URL
from askanu_scraper.sources.events.rubric_adapter import (
    HttpRubricTransport,
    RubricAdapter,
    RubricRecordRejected,
    normalize_rubric_event_url,
    parse_detail,
    parse_discovery_page,
)


FIXTURES = Path(__file__).parents[1] / "fixtures" / "events"
SEARCH_ENDPOINT = (
    "https://appserver.getqpay.com:9090/"
    "AppServerSwapnil/search/getUnifiedSearch"
)
NOW = datetime(2026, 9, 20, 9, 0, tzinfo=CANBERRA_TZ)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FixtureTransport:
    def __init__(self, *, fail_event_id: str | None = None, zero: bool = False) -> None:
        self.fail_event_id = fail_event_id
        self.zero = zero
        self.calls: list[tuple[str, dict[str, object]]] = []

    def post_json(self, url: str, payload: Mapping[str, object]) -> str:
        values = dict(payload)
        self.calls.append((url, values))
        if "desiredType" in values:
            if self.zero:
                return (
                    '{"success":true,"totalItemCount":0,'
                    '"selectedCountryCode":"AU",'
                    '"selectedState":"Australian Capital Territory",'
                    '"selectedUniversityId":1,"results":[]}'
                )
            return fixture(
                "rubric-search-page-0.json"
                if values["offset"] == 0
                else "rubric-search-page-1.json"
            )
        event_id = str(values["eventId"])
        if event_id == self.fail_event_id:
            raise FetchError("fixture timeout")
        return fixture(f"rubric-detail-{event_id}.json")


class OfficialFixtureFetcher(BaseFetcher):
    def __init__(self, *, fail_details: bool = False) -> None:
        self.fail_details = fail_details
        self.responses = {
            LISTING_URL: fixture("listing-page-0.html"),
            f"{LISTING_URL}?page=1": fixture("listing-page-1.html"),
            f"{LISTING_URL}/window-opening": fixture("window-opening.html"),
            f"{LISTING_URL}/dst-event": fixture("dst-event.html"),
            f"{LISTING_URL}/outside-window": fixture("outside-window.html"),
        }

    def fetch(self, url: str) -> str:
        if self.fail_details and url.startswith(f"{LISTING_URL}/"):
            raise FetchError("official fixture timeout")
        return self.responses[url]


def adapter(path: Path, transport: FixtureTransport, *, dry_run: bool = False) -> RubricAdapter:
    return RubricAdapter(
        search_endpoint=SEARCH_ENDPOINT,
        transport=transport,
        store=LocalDataStore(path, dry_run=dry_run),
        min_request_interval_seconds=1,
        sleep_func=lambda _: None,
        now_func=lambda: NOW,
    )


def run(instance: RubricAdapter):
    return instance.run_listing(
        max_listing_pages=2,
        max_details=10,
        window_start=date(2026, 9, 19),
        window_days=43,
        expected_event_count=2,
    )


def test_discovery_contract_and_anu_boundary() -> None:
    page = parse_discovery_page(fixture("rubric-search-page-0.json"))
    assert page.total_item_count == 4
    assert page.event_ids == ["78459", "78460"]
    invalid = fixture("rubric-search-page-0.json").replace(
        '"selectedUniversityId": 1', '"selectedUniversityId": 2'
    )
    with pytest.raises(ParseError, match="does not match ANU"):
        parse_discovery_page(invalid)


@pytest.mark.parametrize(
    "raw",
    [
        "not-json",
        "[]",
        '{"success":false}',
        '{"success":true,"totalItemCount":1,"selectedCountryCode":"AU",'
        '"selectedState":"Australian Capital Territory",'
        '"selectedUniversityId":1,"results":[{}]}',
    ],
)
def test_malformed_discovery_is_rejected(raw: str) -> None:
    with pytest.raises(ParseError):
        parse_discovery_page(raw)


def test_detail_normalizes_source_identity_and_does_not_overinterpret_ticket_fields() -> None:
    record = parse_detail(
        fixture("rubric-detail-78459.json"), "78459", now_func=lambda: NOW
    )
    assert record.record_id == "events:event:rubric-78459"
    assert record.entity_id == "rubric-78459"
    assert record.source_id == "rubric_unified_search"
    assert record.canonical_url == "https://campus.hellorubric.com/?eid=78459"
    assert record.metadata_json["source_status"] is None
    assert record.metadata_json["cancellation_status"] is None
    assert "9989" not in record.content
    assert "Available" not in record.content
    assert "bad()" not in record.content
    assert record.metadata_json["registration_url"] == (
        "https://example.org/anuisa/bonfire-registration"
    )


def test_missing_end_and_optional_fields_remain_null_without_inference() -> None:
    record = parse_detail(
        fixture("rubric-detail-78460.json"), "78460", now_func=lambda: NOW
    )
    assert record.effective_from is not None
    assert record.effective_to is None
    assert record.metadata_json["end_at"] is None
    assert record.metadata_json["venue_name"] is None
    assert record.metadata_json["tags"] == ["Social", "Sport"]


def test_draft_is_an_explicit_exclusion() -> None:
    with pytest.raises(RubricRecordRejected, match="draft"):
        parse_detail(
            fixture("rubric-detail-draft.json"), "70000", now_func=lambda: NOW
        )


def test_detail_identity_conflict_and_invalid_range_are_rejected() -> None:
    raw = fixture("rubric-detail-78459.json")
    with pytest.raises(ParseError, match="conflicts"):
        parse_detail(raw, "99999", now_func=lambda: NOW)
    with pytest.raises(ParseError, match="precedes"):
        parse_detail(
            raw.replace(
                '"2026-09-20T21:00:00+10:00"',
                '"2026-09-20T17:00:00+10:00"',
            ),
            "78459",
            now_func=lambda: NOW,
        )


@pytest.mark.parametrize(
    "url",
    [
        "http://campus.hellorubric.com/?eid=78459",
        "https://campus.hellorubric.com/?eid=other",
        "https://user:pass@campus.hellorubric.com/?eid=78459",
        "https://campus.hellorubric.com/event/78459",
    ],
)
def test_rubric_public_canonical_boundary(url: str) -> None:
    with pytest.raises(ParseError):
        normalize_rubric_event_url(url, "78459")


def test_complete_run_reconciles_duplicates_window_and_request_cache(tmp_path: Path) -> None:
    transport = FixtureTransport()
    collector = adapter(tmp_path / "store", transport, dry_run=True)
    result, records, discovery = run(collector)
    assert result.status == IngestionRunStatus.SUCCESS
    assert len(records) == 2
    assert discovery is not None
    assert discovery.raw_result_count == 4
    assert discovery.event_ids == ["78459", "78460", "90000"]
    assert discovery.duplicate_event_ids == ["78459"]
    assert collector.last_run_sanity["accepted_count"] == 2
    assert collector.last_run_sanity["entity_coverage_percent"] == 100.0
    assert collector.last_run_sanity["source_present_fact_coverage_percent"] == 100.0
    assert collector.last_run_sanity["rejected_by_reason"] == {
        "outside-frozen-window": 1
    }
    detail_ids = [str(payload["eventId"]) for _, payload in transport.calls if "eventId" in payload]
    assert detail_ids == ["78459", "78460", "90000"]
    assert not (tmp_path / "store").exists()


def test_first_write_unchanged_and_changed_hash(tmp_path: Path) -> None:
    path = tmp_path / "store"
    first, records, _ = run(adapter(path, FixtureTransport()))
    assert first.records_added == 2
    first_hash = records[0].content_hash
    second, _, _ = run(adapter(path, FixtureTransport()))
    assert second.records_unchanged == 2

    class ChangedTransport(FixtureTransport):
        def post_json(self, url: str, payload: Mapping[str, object]) -> str:
            raw = super().post_json(url, payload)
            if str(payload.get("eventId")) == "78459":
                return raw.replace("A community event for ANU students.", "Updated source description.")
            return raw

    changed, changed_records, _ = run(adapter(path, ChangedTransport()))
    assert changed.records_changed == 1
    assert changed_records[0].record_id == "events:event:rubric-78459"
    assert changed_records[0].content_hash != first_hash


def test_detail_failure_preserves_last_known_good(tmp_path: Path) -> None:
    path = tmp_path / "store"
    good, _, _ = run(adapter(path, FixtureTransport()))
    assert good.status == IngestionRunStatus.SUCCESS
    before = {item.name: item.read_bytes() for item in (path / "records").glob("*.json")}
    failed, records, _ = run(adapter(path, FixtureTransport(fail_event_id="78460")))
    after = {item.name: item.read_bytes() for item in (path / "records").glob("*.json")}
    assert failed.status == IngestionRunStatus.FAILED
    assert "fixture timeout" in failed.error
    assert records == []
    assert before == after


def test_official_and_rubric_failures_are_source_isolated(tmp_path: Path) -> None:
    path = tmp_path / "shared-events-store"
    store = LocalDataStore(path)
    official, _, _ = EventsCollector(
        fetcher=OfficialFixtureFetcher(),
        store=store,
        min_request_interval_seconds=0,
    ).run_listing(
        max_listing_pages=2,
        max_details=10,
        window_start=date(2026, 9, 19),
        window_days=43,
        expected_event_count=2,
    )
    rubric, _, _ = run(
        RubricAdapter(
            search_endpoint=SEARCH_ENDPOINT,
            transport=FixtureTransport(),
            store=store,
            min_request_interval_seconds=1,
            sleep_func=lambda _: None,
            now_func=lambda: NOW,
        )
    )
    assert official.status == rubric.status == IngestionRunStatus.SUCCESS
    record_dir = path / "records"
    official_before = {
        item.name: item.read_bytes()
        for item in record_dir.glob("events__event__*.json")
        if "__rubric__" not in item.name
    }
    rubric_before = {
        item.name: item.read_bytes()
        for item in record_dir.glob("events__event__rubric__*.json")
    }

    official_failed, _, _ = EventsCollector(
        fetcher=OfficialFixtureFetcher(fail_details=True),
        store=store,
        min_request_interval_seconds=0,
    ).run_listing(
        max_listing_pages=2,
        max_details=10,
        window_start=date(2026, 9, 19),
        window_days=43,
        expected_event_count=2,
    )
    assert official_failed.status == IngestionRunStatus.FAILED
    assert rubric_before == {
        item.name: item.read_bytes()
        for item in record_dir.glob("events__event__rubric__*.json")
    }

    rubric_failed, _, _ = run(
        RubricAdapter(
            search_endpoint=SEARCH_ENDPOINT,
            transport=FixtureTransport(fail_event_id="78460"),
            store=store,
            min_request_interval_seconds=1,
            sleep_func=lambda _: None,
            now_func=lambda: NOW,
        )
    )
    assert rubric_failed.status == IngestionRunStatus.FAILED
    assert official_before == {
        item.name: item.read_bytes()
        for item in record_dir.glob("events__event__*.json")
        if "__rubric__" not in item.name
    }


def test_suspicious_zero_and_incomplete_pagination_write_no_records(tmp_path: Path) -> None:
    zero, _, _ = run(adapter(tmp_path / "zero", FixtureTransport(zero=True)))
    assert zero.status == IngestionRunStatus.SUSPICIOUS_ZERO

    collector = adapter(tmp_path / "incomplete", FixtureTransport())
    incomplete, _, _ = collector.run_listing(
        max_listing_pages=1,
        max_details=10,
        window_start=date(2026, 9, 19),
        window_days=43,
        expected_event_count=2,
    )
    assert incomplete.status == IngestionRunStatus.FAILED
    assert "pagination" in incomplete.error.lower()
    assert list((tmp_path / "incomplete" / "records").glob("*.json")) == []


def test_http_transport_retries_transient_failure_without_cookies(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class Response:
        def __init__(self, status: int, text: str) -> None:
            self.status_code = status
            self.text = text

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise requests.HTTPError("failed")

    responses = [Response(503, "temporary"), Response(200, '{"success":true}')]

    def fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return responses.pop(0)

    monkeypatch.setattr(
        "askanu_scraper.sources.events.rubric_adapter.requests.post", fake_post
    )
    waits: list[float] = []
    transport = HttpRubricTransport(sleep_func=waits.append)
    assert transport.post_json(SEARCH_ENDPOINT, {"safe": True}) == '{"success":true}'
    assert waits == [1.0]
    assert len(calls) == 2
    assert "Cookie" not in calls[0]["headers"]
    assert "Authorization" not in calls[0]["headers"]


def test_http_transport_retries_timeout_then_succeeds(monkeypatch) -> None:
    class Response:
        status_code = 200
        text = '{"success":true}'

        def raise_for_status(self) -> None:
            return None

    outcomes: list[object] = [requests.Timeout("timeout"), Response()]

    def fake_post(*args, **kwargs):
        del args, kwargs
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(
        "askanu_scraper.sources.events.rubric_adapter.requests.post", fake_post
    )
    waits: list[float] = []
    transport = HttpRubricTransport(sleep_func=waits.append)
    assert transport.post_json(SEARCH_ENDPOINT, {}) == '{"success":true}'
    assert waits == [1.0]


def test_rubric_adapter_enforces_live_request_spacing(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="one-second"):
        RubricAdapter(
            search_endpoint=SEARCH_ENDPOINT,
            transport=FixtureTransport(),
            store=LocalDataStore(tmp_path / "unused", dry_run=True),
            min_request_interval_seconds=0.5,
            sleep_func=lambda _: None,
        )
