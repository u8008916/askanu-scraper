"""Safe bounded collector for Official ANU Events.

Rubric uses a separate ingestion adapter so either source can fail independently.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import math
import time
import uuid
from collections.abc import Callable
from urllib.parse import urlencode, urlsplit

from pydantic import ValidationError

from askanu_scraper.common.fetcher import BaseFetcher, FetchError, HttpFetcher
from askanu_scraper.common.models import CommonRecord, Domain, IngestionRun, IngestionRunStatus
from askanu_scraper.common.normalizer import now_canberra
from askanu_scraper.common.parser import ParseError
from askanu_scraper.common.registry import assert_source_allowed
from askanu_scraper.common.storage import DataStore, LocalDataStore
from askanu_scraper.sources.events.discovery import EventCandidate, EventsDiscovery
from askanu_scraper.sources.events.parser import EventsParser, normalize_event_url

SOURCE_ID = "events_anu_official"
LISTING_URL = "https://www.anu.edu.au/events"
SOURCE_ANOMALY = "HTML/ICS displayed-time disagreement observed 2026-09-18; HTML is authoritative"


@dataclass(frozen=True)
class EventsDiscoveryResult:
    candidates: list[EventCandidate]
    raw_card_count: int
    unique_link_count: int
    duplicate_links: list[str]
    rejected_by_reason: dict[str, int]
    pages_traversed: int
    advertised_last_page: int
    pagination_complete: bool
    over_limit_count: int


class EventsCollector:
    def __init__(
        self,
        fetcher: BaseFetcher | None = None,
        store: DataStore | None = None,
        parser: EventsParser | None = None,
        *,
        min_request_interval_seconds: float | None = None,
        sleep_func: Callable[[float], None] | None = None,
    ) -> None:
        self._source = assert_source_allowed(SOURCE_ID)
        self._fetcher = fetcher or HttpFetcher()
        self._store = store or LocalDataStore()
        self._parser = parser or EventsParser()
        self._discovery = EventsDiscovery()
        if min_request_interval_seconds is None:
            min_request_interval_seconds = 1.0 if isinstance(self._fetcher, HttpFetcher) else 0.0
        if min_request_interval_seconds < 0:
            raise ValueError("min_request_interval_seconds must be non-negative")
        if isinstance(self._fetcher, HttpFetcher) and min_request_interval_seconds < 1.0:
            raise ValueError("Live Events requests require at least one-second spacing")
        self._interval = min_request_interval_seconds
        self._sleep = sleep_func or time.sleep
        self._request_count = self._listing_request_count = self._detail_request_count = 0
        self.last_run_sanity: dict[str, object] = self._empty_sanity()

    @staticmethod
    def _empty_sanity() -> dict[str, object]:
        return {
            "request_count": 0, "listing_request_count": 0, "detail_request_count": 0,
            "raw_card_count": 0, "unique_link_count": 0, "duplicate_link_count": 0,
            "duplicate_event_id_count": 0, "duplicate_record_id_count": 0,
            "duplicate_canonical_url_count": 0, "rejected_by_reason": {},
            "pages_traversed": 0, "advertised_last_page": None,
            "pagination_complete": False, "over_limit_candidate_count": 0,
            "eligible_window_count": 0, "accepted_count": 0,
            "frozen_denominator": None, "minimum_accepted_count": None,
            "entity_coverage_percent": None,
            "source_present_fact_numerator": 0, "source_present_fact_denominator": 0,
            "source_present_fact_coverage_percent": None,
            "representative_records": [],
            "source_anomalies": [SOURCE_ANOMALY],
        }

    @staticmethod
    def _is_listing_url(url: str) -> bool:
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError:
            return False
        return (
            parsed.scheme == "https" and parsed.hostname == "www.anu.edu.au"
            and parsed.username is None and parsed.password is None and port is None
            and parsed.path.rstrip("/") == "/events" and not parsed.query and not parsed.fragment
        )

    def _fetch(self, url: str, *, detail: bool = False) -> str:
        if self._request_count and self._interval:
            self._sleep(self._interval)
        self._request_count += 1
        if detail:
            self._detail_request_count += 1
        else:
            self._listing_request_count += 1
        return self._fetcher.fetch(url)

    def _save_failed_run(self, run: IngestionRun) -> None:
        try:
            self._store.save_run(run)
        except Exception:
            suffix = "Durable ingestion-run write also failed"
            run.error = f"{run.error}; {suffix}" if run.error else suffix

    def collect(self, url: str) -> list[CommonRecord]:
        approved = normalize_event_url(url)
        return self._parser.parse(self._fetcher.fetch(approved), approved)

    def discover_full_listing(
        self, *, listing_url: str = LISTING_URL, max_listing_pages: int = 10,
        max_details: int | None = None,
    ) -> EventsDiscoveryResult:
        if not self._is_listing_url(listing_url):
            raise ValueError("Listing URL is outside the approved Events boundary")
        if not 1 <= max_listing_pages <= 100:
            raise ValueError("max_listing_pages must be between 1 and 100")
        if max_details is not None and max_details < 1:
            raise ValueError("max_details must be at least 1")
        first = self._discovery.discover(self._fetch(listing_url), listing_url)
        advertised_last = first.advertised_last_page or 0
        pages = [first]
        for page_number in range(1, min(advertised_last + 1, max_listing_pages)):
            page_url = listing_url + "?" + urlencode({"page": page_number})
            pages.append(self._discovery.discover(self._fetch(page_url), page_url))
        complete = len(pages) == advertised_last + 1
        candidates: list[EventCandidate] = []
        duplicates: list[str] = []
        seen: set[str] = set()
        rejected: dict[str, int] = {}
        over_limit = 0
        for page in pages:
            for reason, count in page.rejected_by_reason.items():
                rejected[reason] = rejected.get(reason, 0) + count
            for candidate in page.candidates:
                if candidate.url in seen:
                    duplicates.append(candidate.url)
                    continue
                seen.add(candidate.url)
                if max_details is not None and len(candidates) >= max_details:
                    over_limit += 1
                else:
                    candidates.append(candidate)
        return EventsDiscoveryResult(
            candidates=candidates, raw_card_count=sum(page.raw_card_count for page in pages),
            unique_link_count=len(seen), duplicate_links=duplicates,
            rejected_by_reason=rejected, pages_traversed=len(pages),
            advertised_last_page=advertised_last, pagination_complete=complete,
            over_limit_count=over_limit,
        )

    @staticmethod
    def _in_window(record: CommonRecord, start: date, end: date) -> bool:
        metadata = record.metadata_json
        event_start = date.fromisoformat(str(metadata["start_date"]))
        event_end = date.fromisoformat(str(metadata["end_date"]))
        return event_start <= end and event_end >= start

    @staticmethod
    def _fact_coverage(records: list[CommonRecord]) -> tuple[int, int]:
        numerator = denominator = 0
        for record in records:
            for value in (record.entity_id, record.title, record.canonical_url, record.metadata_json["start_date"]):
                denominator += 1
                if value:
                    numerator += 1
            for key in (
                "end_date", "start_at", "end_at", "location", "format", "categories", "tags",
                "organiser", "description", "registration_links", "status", "cancellation_text",
            ):
                value = record.metadata_json[key]
                if value not in (None, [], ""):
                    denominator += 1
                    numerator += 1
        return numerator, denominator

    def _capture_sanity(
        self, discovery: EventsDiscoveryResult | None, *, records: list[CommonRecord] | None = None,
        eligible_count: int = 0, expected_count: int | None = None,
        duplicate_event_ids: int = 0, duplicate_record_ids: int = 0, duplicate_urls: int = 0,
        rejected_by_reason: dict[str, int] | None = None,
    ) -> None:
        accepted = records or []
        numerator, denominator = self._fact_coverage(accepted)
        minimum = math.ceil(expected_count * 0.99) if expected_count is not None else None
        entity_denominator = expected_count if expected_count is not None else eligible_count
        self.last_run_sanity = {
            "request_count": self._request_count,
            "listing_request_count": self._listing_request_count,
            "detail_request_count": self._detail_request_count,
            "raw_card_count": discovery.raw_card_count if discovery else 0,
            "unique_link_count": discovery.unique_link_count if discovery else 0,
            "duplicate_link_count": len(discovery.duplicate_links) if discovery else 0,
            "duplicate_event_id_count": duplicate_event_ids,
            "duplicate_record_id_count": duplicate_record_ids,
            "duplicate_canonical_url_count": duplicate_urls,
            "rejected_by_reason": rejected_by_reason or (discovery.rejected_by_reason if discovery else {}),
            "pages_traversed": discovery.pages_traversed if discovery else 0,
            "advertised_last_page": discovery.advertised_last_page if discovery else None,
            "pagination_complete": discovery.pagination_complete if discovery else False,
            "over_limit_candidate_count": discovery.over_limit_count if discovery else 0,
            "eligible_window_count": eligible_count, "accepted_count": len(accepted),
            "frozen_denominator": expected_count, "minimum_accepted_count": minimum,
            "entity_coverage_percent": (
                round(len(accepted) * 100 / entity_denominator, 2) if entity_denominator else None
            ),
            "source_present_fact_numerator": numerator,
            "source_present_fact_denominator": denominator,
            "source_present_fact_coverage_percent": (
                round(numerator * 100 / denominator, 2) if denominator else None
            ),
            "representative_records": [
                {
                    "record_id": record.record_id,
                    "canonical_url": record.canonical_url,
                    "content_hash": record.content_hash,
                }
                for record in accepted[:3]
            ],
            "source_anomalies": [SOURCE_ANOMALY],
        }

    def run_listing(
        self, *, listing_url: str = LISTING_URL, max_listing_pages: int = 10,
        max_details: int | None = 100, window_start: date,
        window_days: int = 43, expected_event_count: int | None = None,
    ) -> tuple[IngestionRun, list[CommonRecord], EventsDiscoveryResult | None]:
        if not 1 <= window_days <= 366:
            raise ValueError("window_days must be between 1 and 366")
        if expected_event_count is not None and expected_event_count < 1:
            raise ValueError("expected_event_count must be positive")
        window_end = window_start + timedelta(days=window_days - 1)
        self._request_count = self._listing_request_count = self._detail_request_count = 0
        self.last_run_sanity = self._empty_sanity()
        run = IngestionRun(run_id=f"run_{uuid.uuid4().hex[:12]}", source_id=SOURCE_ID,
                           started_at=now_canberra(), status=IngestionRunStatus.RUNNING)
        try:
            self._store.save_run(run)
        except Exception:
            run.status = IngestionRunStatus.FAILED
            run.error = "RUNNING ingestion-run write failed; collection not started"
            run.completed_at = now_canberra()
            self._save_failed_run(run)
            return run, [], None

        def fail(message: str, discovery: EventsDiscoveryResult | None = None, *,
                 suspicious_zero: bool = False, records: list[CommonRecord] | None = None,
                 eligible_count: int = 0, duplicate_event_ids: int = 0,
                 duplicate_record_ids: int = 0, duplicate_urls: int = 0,
                 rejected: dict[str, int] | None = None):
            run.status = IngestionRunStatus.SUSPICIOUS_ZERO if suspicious_zero else IngestionRunStatus.FAILED
            run.error = message
            run.completed_at = now_canberra()
            self._capture_sanity(
                discovery, records=records, eligible_count=eligible_count,
                expected_count=expected_event_count, duplicate_event_ids=duplicate_event_ids,
                duplicate_record_ids=duplicate_record_ids, duplicate_urls=duplicate_urls,
                rejected_by_reason=rejected,
            )
            self._save_failed_run(run)
            return run, [], discovery

        try:
            discovery = self.discover_full_listing(
                listing_url=listing_url, max_listing_pages=max_listing_pages,
                max_details=max_details,
            )
        except FetchError as exc:
            return fail(f"Listing fetch failed: {exc}")
        except (ParseError, ValueError) as exc:
            return fail(f"Listing discovery failed: {exc}")
        if not discovery.pagination_complete:
            return fail("Events pagination is incomplete at the configured hard cap", discovery)
        if discovery.raw_card_count == 0 or discovery.unique_link_count == 0:
            return fail("Events listing produced zero approved detail candidates", discovery, suspicious_zero=True)
        if discovery.over_limit_count and expected_event_count is not None:
            return fail("Events detail bound prevents denominator reconciliation", discovery)

        eligible: list[CommonRecord] = []
        parsed_records: list[CommonRecord] = []
        rejected = dict(discovery.rejected_by_reason)
        try:
            for candidate in discovery.candidates:
                parsed = self._parser.parse(self._fetch(candidate.url, detail=True), candidate.url)
                if len(parsed) != 1:
                    return fail(f"Expected exactly one record from {candidate.url!r}", discovery)
                record = parsed[0]
                if (
                    record.domain != Domain.EVENTS or record.source_id != SOURCE_ID
                    or record.record_id != f"events:event:{record.entity_id}"
                    or record.canonical_url != candidate.url
                ):
                    return fail("Event detail failed identity/provenance validation", discovery)
                parsed_records.append(record)
                if self._in_window(record, window_start, window_end):
                    eligible.append(record)
                else:
                    rejected["outside-frozen-window"] = rejected.get("outside-frozen-window", 0) + 1
        except FetchError as exc:
            return fail(f"Detail fetch failed: {exc}", discovery, rejected=rejected)
        except (ParseError, ValidationError, ValueError) as exc:
            return fail(f"Detail parser failed: {exc}", discovery, rejected=rejected)
        except Exception:
            return fail("Unexpected Events detail parser failure", discovery, rejected=rejected)

        event_ids = [record.entity_id for record in parsed_records]
        record_ids = [record.record_id for record in parsed_records]
        urls = [record.canonical_url for record in parsed_records]
        duplicate_event_ids = len(event_ids) - len(set(event_ids))
        duplicate_record_ids = len(record_ids) - len(set(record_ids))
        duplicate_urls = len(urls) - len(set(urls))
        self._capture_sanity(
            discovery, records=eligible, eligible_count=len(eligible), expected_count=expected_event_count,
            duplicate_event_ids=duplicate_event_ids, duplicate_record_ids=duplicate_record_ids,
            duplicate_urls=duplicate_urls, rejected_by_reason=rejected,
        )
        if duplicate_event_ids or duplicate_record_ids or duplicate_urls:
            return fail("Duplicate Event identity or canonical URL detected", discovery,
                        records=eligible, eligible_count=len(eligible),
                        duplicate_event_ids=duplicate_event_ids,
                        duplicate_record_ids=duplicate_record_ids, duplicate_urls=duplicate_urls,
                        rejected=rejected)
        if not eligible:
            return fail("Events frozen window produced zero records", discovery,
                        suspicious_zero=True, rejected=rejected)
        if expected_event_count is not None and len(eligible) < math.ceil(expected_event_count * 0.99):
            return fail("Events accepted count is below 99% of the frozen denominator", discovery,
                        records=eligible, eligible_count=len(eligible), rejected=rejected)

        run.status = IngestionRunStatus.SUCCESS
        run.completed_at = now_canberra()
        try:
            results = self._store.save_records_and_run(eligible, run)
        except Exception:
            run.status = IngestionRunStatus.FAILED
            run.records_added = run.records_changed = run.records_unchanged = 0
            run.error = "Atomic persistence failed; records were not committed"
            run.completed_at = now_canberra()
            self._save_failed_run(run)
            return run, [], discovery
        return run, [record for _action, record in results], discovery


__all__ = ["EventsCollector", "EventsDiscoveryResult", "EventsParser", "LISTING_URL", "SOURCE_ID"]
