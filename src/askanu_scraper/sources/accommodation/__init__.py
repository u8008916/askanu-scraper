"""Safe bounded collector for approved public ANU residence pages."""
from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from urllib.parse import urlsplit

from pydantic import ValidationError

from askanu_scraper.common.fetcher import BaseFetcher, FetchError, HttpFetcher
from askanu_scraper.common.models import CommonRecord, Domain, IngestionRun, IngestionRunStatus
from askanu_scraper.common.normalizer import now_canberra
from askanu_scraper.common.parser import ParseError
from askanu_scraper.common.registry import assert_source_allowed
from askanu_scraper.common.storage import DataStore, LocalDataStore
from askanu_scraper.sources.accommodation.discovery import (
    AccommodationDiscovery,
    AccommodationDiscoveryResult,
)
from askanu_scraper.sources.accommodation.parser import (
    AccommodationParser,
    normalize_accommodation_url,
)


SOURCE_ID = "accommodation_anu_study"
LISTING_URL = "https://study.anu.edu.au/accommodation/our-residences"
FROZEN_ENTITY_COUNT = 19


class AccommodationCollector:
    def __init__(
        self,
        fetcher: BaseFetcher | None = None,
        store: DataStore | None = None,
        parser: AccommodationParser | None = None,
        *,
        frozen_entity_count: int = FROZEN_ENTITY_COUNT,
        min_request_interval_seconds: float | None = None,
        sleep_func: Callable[[float], None] | None = None,
    ) -> None:
        self._source = assert_source_allowed(SOURCE_ID)
        self._fetcher = fetcher or HttpFetcher()
        self._store = store or LocalDataStore()
        self._parser = parser or AccommodationParser()
        self._discovery = AccommodationDiscovery()
        if frozen_entity_count < 1:
            raise ValueError("frozen_entity_count must be positive")
        self._frozen_count = frozen_entity_count
        if min_request_interval_seconds is None:
            min_request_interval_seconds = 1.0 if isinstance(self._fetcher, HttpFetcher) else 0.0
        if min_request_interval_seconds < 0:
            raise ValueError("min_request_interval_seconds must be non-negative")
        self._interval = min_request_interval_seconds
        self._sleep = sleep_func or time.sleep
        self._requests = 0
        self._detail_requests = 0
        self.last_run_sanity: dict[str, object] = {}

    @staticmethod
    def _is_listing_url(url: str) -> bool:
        parsed = urlsplit(url)
        return (
            parsed.scheme == "https"
            and parsed.hostname == "study.anu.edu.au"
            and parsed.path.rstrip("/") == "/accommodation/our-residences"
            and not parsed.query
            and not parsed.fragment
        )

    def _fetch(self, url: str, *, detail: bool = False) -> str:
        if self._requests and self._interval:
            self._sleep(self._interval)
        self._requests += 1
        if detail:
            self._detail_requests += 1
        return self._fetcher.fetch(url)

    def _save_failed_run(self, run: IngestionRun) -> None:
        try:
            self._store.save_run(run)
        except Exception:
            pass

    def _sanity(
        self,
        discovery: AccommodationDiscoveryResult | None,
        *,
        duplicate_record_ids: int = 0,
        duplicate_urls: int = 0,
    ) -> None:
        self.last_run_sanity = {
            "request_count": self._requests,
            "detail_request_count": self._detail_requests,
            "frozen_entity_count": self._frozen_count,
            "advertised_total_count": discovery.advertised_total_count if discovery else None,
            "discovered_candidate_count": discovery.discovered_candidate_count if discovery else 0,
            "approved_candidate_count": discovery.approved_candidate_count if discovery else 0,
            "accepted_candidate_count": len(discovery.candidates) if discovery else 0,
            "rejected_candidate_count": len(discovery.rejected_links) if discovery else 0,
            "duplicate_candidate_count": len(discovery.duplicate_links) if discovery else 0,
            "over_limit_candidate_count": discovery.over_limit_count if discovery else 0,
            "duplicate_record_id_count": duplicate_record_ids,
            "duplicate_canonical_url_count": duplicate_urls,
        }

    def collect(self, url: str) -> list[CommonRecord]:
        normalize_accommodation_url(url)
        return self._parser.parse(self._fetch(url, detail=True), url)

    def run_listing(
        self,
        *,
        listing_url: str = LISTING_URL,
        max_details: int | None = 10,
    ) -> tuple[IngestionRun, list[CommonRecord], AccommodationDiscoveryResult | None]:
        if max_details is not None and max_details < 1:
            raise ValueError("max_details must be at least 1")
        self._requests = self._detail_requests = 0
        self.last_run_sanity = {}
        run = IngestionRun(
            run_id=f"run_{uuid.uuid4().hex[:12]}",
            source_id=SOURCE_ID,
            started_at=now_canberra(),
            status=IngestionRunStatus.RUNNING,
        )
        try:
            self._store.save_run(run)
        except Exception:
            run.status = IngestionRunStatus.FAILED
            run.error = "RUNNING ingestion-run write failed; collection not started"
            run.completed_at = now_canberra()
            return run, [], None

        def fail(
            message: str,
            discovery: AccommodationDiscoveryResult | None = None,
            *,
            suspicious_zero: bool = False,
            duplicate_record_ids: int = 0,
            duplicate_urls: int = 0,
        ) -> tuple[IngestionRun, list[CommonRecord], AccommodationDiscoveryResult | None]:
            run.status = (
                IngestionRunStatus.SUSPICIOUS_ZERO
                if suspicious_zero
                else IngestionRunStatus.FAILED
            )
            run.error = message
            run.completed_at = now_canberra()
            self._sanity(
                discovery,
                duplicate_record_ids=duplicate_record_ids,
                duplicate_urls=duplicate_urls,
            )
            self._save_failed_run(run)
            return run, [], discovery

        if not self._is_listing_url(listing_url):
            return fail("Listing URL is outside the approved Accommodation boundary")
        try:
            discovery = self._discovery.discover(
                self._fetch(listing_url), listing_url, max_details=max_details
            )
        except FetchError as exc:
            return fail(f"Listing fetch failed: {exc}")
        except (ParseError, ValueError) as exc:
            return fail(f"Listing discovery failed: {exc}")
        self._sanity(discovery)
        if discovery.approved_candidate_count == 0:
            return fail(
                "Accommodation listing produced zero approved residences",
                discovery,
                suspicious_zero=True,
            )
        if discovery.advertised_total_count is None:
            return fail("Accommodation advertised total is missing", discovery)
        if discovery.approved_candidate_count != discovery.advertised_total_count:
            return fail("Accommodation cards do not reconcile with advertised total", discovery)
        if discovery.approved_candidate_count != self._frozen_count:
            return fail("Accommodation count differs from the frozen universe", discovery)

        records: list[CommonRecord] = []
        try:
            for candidate in discovery.candidates:
                parsed = self._parser.parse(
                    self._fetch(candidate.url, detail=True),
                    candidate.url,
                    listing_metadata=candidate.listing_metadata,
                )
                if len(parsed) != 1:
                    return fail("Expected one Accommodation record per residence", discovery)
                record = parsed[0]
                if (
                    record.domain != Domain.ACCOMMODATION
                    or record.source_id != SOURCE_ID
                    or record.canonical_url != candidate.url
                ):
                    return fail("Accommodation identity/provenance validation failed", discovery)
                records.append(record)
        except FetchError as exc:
            return fail(f"Detail fetch failed: {exc}", discovery)
        except (ParseError, ValidationError, ValueError) as exc:
            return fail(f"Detail parser failed: {exc}", discovery)
        except Exception:
            return fail("Unexpected Accommodation detail parser failure", discovery)

        ids = [record.record_id for record in records]
        urls = [record.canonical_url for record in records]
        duplicate_ids = len(ids) - len(set(ids))
        duplicate_urls = len(urls) - len(set(urls))
        self._sanity(
            discovery,
            duplicate_record_ids=duplicate_ids,
            duplicate_urls=duplicate_urls,
        )
        if duplicate_ids or duplicate_urls:
            return fail(
                "Duplicate Accommodation records detected",
                discovery,
                duplicate_record_ids=duplicate_ids,
                duplicate_urls=duplicate_urls,
            )
        run.status = IngestionRunStatus.SUCCESS
        run.completed_at = now_canberra()
        try:
            results = self._store.save_records_and_run(records, run)
        except Exception:
            run.status = IngestionRunStatus.FAILED
            run.records_added = run.records_changed = run.records_unchanged = 0
            run.error = "Atomic persistence failed; records were not committed"
            run.completed_at = now_canberra()
            self._save_failed_run(run)
            return run, [], discovery
        return run, [record for _action, record in results], discovery


__all__ = ["AccommodationCollector", "AccommodationParser", "LISTING_URL", "SOURCE_ID"]
