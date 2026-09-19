"""Events discovery, safe persistence, coverage, and recovery tests."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from askanu_scraper.common.fetcher import BaseFetcher, FetchError
from askanu_scraper.common.models import IngestionRunStatus
from askanu_scraper.common.storage import LocalDataStore
from askanu_scraper.sources.events import EventsCollector, LISTING_URL


FIXTURES = Path(__file__).parents[1] / "fixtures" / "events"


class EventsFixtureFetcher(BaseFetcher):
    def __init__(self, *, changed: bool = False, fail_details: bool = False) -> None:
        opening = (FIXTURES / "window-opening.html").read_text(encoding="utf-8")
        if changed:
            opening = opening.replace("Official event description.", "Updated official description.")
        self.responses = {
            LISTING_URL: (FIXTURES / "listing-page-0.html").read_text(encoding="utf-8"),
            f"{LISTING_URL}?page=1": (FIXTURES / "listing-page-1.html").read_text(encoding="utf-8"),
            f"{LISTING_URL}/window-opening": opening,
            f"{LISTING_URL}/dst-event": (FIXTURES / "dst-event.html").read_text(encoding="utf-8"),
            f"{LISTING_URL}/outside-window": (FIXTURES / "outside-window.html").read_text(encoding="utf-8"),
        }
        self.fail_details = fail_details
        self.requested: list[str] = []

    def fetch(self, url: str) -> str:
        self.requested.append(url)
        if self.fail_details and url.startswith(f"{LISTING_URL}/"):
            raise FetchError("fixture failure")
        try:
            return self.responses[url]
        except KeyError as exc:
            raise FetchError(f"Unexpected fixture URL: {url}") from exc


def run(collector: EventsCollector, **kwargs):
    return collector.run_listing(
        max_listing_pages=2, max_details=10, window_start=date(2026, 9, 19),
        window_days=43, expected_event_count=2, **kwargs
    )


def test_listing_reconciles_page_boundary_duplicate_and_window() -> None:
    collector = EventsCollector(fetcher=EventsFixtureFetcher(), sleep_func=lambda _: None)
    discovery = collector.discover_full_listing(max_listing_pages=2, max_details=10)
    assert discovery.raw_card_count == 4
    assert discovery.unique_link_count == 3
    assert len(discovery.duplicate_links) == 1
    assert discovery.pages_traversed == 2
    assert discovery.pagination_complete is True
    assert [candidate.url for candidate in discovery.candidates] == [
        f"{LISTING_URL}/window-opening", f"{LISTING_URL}/dst-event",
        f"{LISTING_URL}/outside-window",
    ]


def test_first_write_unchanged_and_changed_hash(tmp_path: Path) -> None:
    store = LocalDataStore(tmp_path / "store")
    first, records, _ = run(EventsCollector(fetcher=EventsFixtureFetcher(), store=store))
    assert first.status == IngestionRunStatus.SUCCESS
    assert first.records_added == 2
    hashes = {record.record_id: record.content_hash for record in records}
    second, _, _ = run(EventsCollector(fetcher=EventsFixtureFetcher(), store=store))
    assert second.records_unchanged == 2
    changed, changed_records, _ = run(
        EventsCollector(fetcher=EventsFixtureFetcher(changed=True), store=store)
    )
    assert changed.records_changed == 1
    assert {record.record_id: record.content_hash for record in changed_records} != hashes


def test_dry_run_writes_nothing_and_reports_coverage(tmp_path: Path) -> None:
    path = tmp_path / "dry"
    collector = EventsCollector(fetcher=EventsFixtureFetcher(), store=LocalDataStore(path, dry_run=True))
    result, records, _ = run(collector)
    assert result.status == IngestionRunStatus.SUCCESS
    assert len(records) == 2
    assert collector.last_run_sanity["entity_coverage_percent"] == 100.0
    assert collector.last_run_sanity["source_present_fact_coverage_percent"] == 100.0
    assert collector.last_run_sanity["rejected_by_reason"]["outside-frozen-window"] == 1
    assert not path.exists()


def test_incomplete_pagination_fails_before_detail_fetch(tmp_path: Path) -> None:
    fetcher = EventsFixtureFetcher()
    collector = EventsCollector(fetcher=fetcher, store=LocalDataStore(tmp_path / "store"))
    result, records, _ = collector.run_listing(
        max_listing_pages=1, max_details=10, window_start=date(2026, 9, 19),
        window_days=43, expected_event_count=2,
    )
    assert result.status == IngestionRunStatus.FAILED
    assert records == []
    assert fetcher.requested == [LISTING_URL]


def test_fetch_failure_preserves_last_known_good(tmp_path: Path) -> None:
    path = tmp_path / "store"
    store = LocalDataStore(path)
    good, _, _ = run(EventsCollector(fetcher=EventsFixtureFetcher(), store=store))
    assert good.status == IngestionRunStatus.SUCCESS
    before = {file.name: file.read_bytes() for file in (path / "records").glob("*.json")}
    failed, _, _ = run(
        EventsCollector(fetcher=EventsFixtureFetcher(fail_details=True), store=store)
    )
    after = {file.name: file.read_bytes() for file in (path / "records").glob("*.json")}
    assert failed.status == IngestionRunStatus.FAILED
    assert before == after


def test_99_percent_gate_prevents_write(tmp_path: Path) -> None:
    path = tmp_path / "store"
    collector = EventsCollector(fetcher=EventsFixtureFetcher(), store=LocalDataStore(path))
    result, records, _ = collector.run_listing(
        max_listing_pages=2, max_details=10, window_start=date(2026, 9, 19),
        window_days=43, expected_event_count=3,
    )
    assert result.status == IngestionRunStatus.FAILED
    assert records == []
    assert list((path / "records").glob("*.json")) == []


def test_duplicate_numeric_identity_fails_before_write(tmp_path: Path) -> None:
    fetcher = EventsFixtureFetcher()
    fetcher.responses[f"{LISTING_URL}/dst-event"] = fetcher.responses[
        f"{LISTING_URL}/dst-event"
    ].replace('"entityId":1002', '"entityId":1001').replace(
        'data-history-node-id="1002"', 'data-history-node-id="1001"'
    )
    path = tmp_path / "store"
    result, records, _ = run(
        EventsCollector(fetcher=fetcher, store=LocalDataStore(path))
    )
    assert result.status == IngestionRunStatus.FAILED
    assert "Duplicate Event identity" in result.error
    assert records == []
    assert list((path / "records").glob("*.json")) == []


def test_detail_parser_failure_preserves_last_known_good(tmp_path: Path) -> None:
    path = tmp_path / "store"
    store = LocalDataStore(path)
    good, _, _ = run(EventsCollector(fetcher=EventsFixtureFetcher(), store=store))
    assert good.status == IngestionRunStatus.SUCCESS
    before = {file.name: file.read_bytes() for file in (path / "records").glob("*.json")}
    fetcher = EventsFixtureFetcher()
    fetcher.responses[f"{LISTING_URL}/dst-event"] = "<html>malformed</html>"
    failed, _, _ = run(EventsCollector(fetcher=fetcher, store=store))
    after = {file.name: file.read_bytes() for file in (path / "records").glob("*.json")}
    assert failed.status == IngestionRunStatus.FAILED
    assert "Detail parser failed" in failed.error
    assert before == after


def test_atomic_persistence_failure_writes_no_event_records(tmp_path: Path) -> None:
    class FailingStore(LocalDataStore):
        def save_records_and_run(self, records, run):
            del records, run
            raise RuntimeError("fixture transaction failure")

    path = tmp_path / "store"
    result, records, _ = run(
        EventsCollector(fetcher=EventsFixtureFetcher(), store=FailingStore(path))
    )
    assert result.status == IngestionRunStatus.FAILED
    assert result.error == "Atomic persistence failed; records were not committed"
    assert records == []
    assert list((path / "records").glob("*.json")) == []
