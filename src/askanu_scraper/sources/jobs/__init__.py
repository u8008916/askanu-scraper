"""Safe collector for the approved public ANU Jobs source."""
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
from askanu_scraper.sources.jobs.discovery import JobDiscoveryResult, JobsDiscovery
from askanu_scraper.sources.jobs.parser import JobsParser, normalize_job_url


SOURCE_ID = "jobs_anu_search"
LISTING_URL = "https://jobs.anu.edu.au/jobs/search"


class JobsCollector:
    def __init__(
        self,
        fetcher: BaseFetcher | None = None,
        store: DataStore | None = None,
        min_request_interval_seconds: float | None = None,
        sleep_func: Callable[[float], None] | None = None,
        parser: JobsParser | None = None,
    ) -> None:
        self._source = assert_source_allowed(SOURCE_ID)
        self._fetcher = fetcher or HttpFetcher()
        if min_request_interval_seconds is None:
            min_request_interval_seconds = 1.0 if isinstance(self._fetcher, HttpFetcher) else 0.0
        if min_request_interval_seconds < 0:
            raise ValueError("min_request_interval_seconds must be non-negative")
        self._store = store or LocalDataStore()
        self._parser = parser or JobsParser()
        self._discovery = JobsDiscovery()
        self._interval = min_request_interval_seconds
        self._sleep = sleep_func or time.sleep
        self._request_count = 0
        self._detail_request_count = 0
        self.last_run_sanity: dict[str, object] = self._empty_sanity()

    @staticmethod
    def _empty_sanity() -> dict[str, object]:
        return {
            "request_count": 0,
            "listing_request_count": 0,
            "detail_request_count": 0,
            "discovered_candidate_count": 0,
            "accepted_candidate_count": 0,
            "rejected_candidate_count": 0,
            "duplicate_candidate_count": 0,
            "over_limit_candidate_count": 0,
            "duplicate_record_id_count": 0,
            "duplicate_canonical_url_count": 0,
            "advertised_page_count": None,
            "advertised_total_count": None,
        }

    def _capture_sanity(
        self,
        discovery: JobDiscoveryResult | None = None,
        *,
        duplicate_record_ids: int = 0,
        duplicate_canonical_urls: int = 0,
    ) -> None:
        self.last_run_sanity = {
            "request_count": self._request_count,
            "listing_request_count": 1 if self._request_count else 0,
            "detail_request_count": self._detail_request_count,
            "discovered_candidate_count": discovery.discovered_candidate_count if discovery else 0,
            "accepted_candidate_count": len(discovery.candidates) if discovery else 0,
            "rejected_candidate_count": len(discovery.rejected_links) if discovery else 0,
            "duplicate_candidate_count": len(discovery.duplicate_links) if discovery else 0,
            "over_limit_candidate_count": discovery.over_limit_count if discovery else 0,
            "duplicate_record_id_count": duplicate_record_ids,
            "duplicate_canonical_url_count": duplicate_canonical_urls,
            "advertised_page_count": discovery.advertised_page_count if discovery else None,
            "advertised_total_count": discovery.advertised_total_count if discovery else None,
        }

    def _fetch(self, url: str, *, detail: bool = False) -> str:
        if self._request_count and self._interval > 0:
            self._sleep(self._interval)
        self._request_count += 1
        if detail:
            self._detail_request_count += 1
        return self._fetcher.fetch(url)

    @staticmethod
    def _is_listing_url(url: str) -> bool:
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError:
            return False
        return (
            parsed.scheme == "https"
            and parsed.hostname == "jobs.anu.edu.au"
            and parsed.username is None
            and parsed.password is None
            and port is None
            and parsed.path.rstrip("/") == "/jobs/search"
            and not parsed.query
            and not parsed.fragment
        )

    def _save_failed_run(self, run: IngestionRun) -> None:
        try:
            self._store.save_run(run)
        except Exception:
            suffix = "Durable ingestion-run write also failed"
            run.error = f"{run.error}; {suffix}" if run.error else suffix

    def collect(self, url: str) -> list[CommonRecord]:
        approved_url = normalize_job_url(url)
        return self._parser.parse(self._fetcher.fetch(approved_url), approved_url)

    def run_listing(
        self,
        *,
        listing_url: str = LISTING_URL,
        max_listing_pages: int = 1,
        max_details: int = 10,
    ) -> tuple[IngestionRun, list[CommonRecord], JobDiscoveryResult | None]:
        if max_listing_pages != 1:
            raise ValueError("Jobs collection is limited to one listing page")
        if not 1 <= max_details <= 10:
            raise ValueError("max_details must be between 1 and 10")
        self._request_count = 0
        self._detail_request_count = 0
        self.last_run_sanity = self._empty_sanity()
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
            self._save_failed_run(run)
            return run, [], None

        def fail(
            message: str,
            discovery: JobDiscoveryResult | None = None,
            *,
            suspicious_zero: bool = False,
            duplicate_record_ids: int = 0,
            duplicate_canonical_urls: int = 0,
        ) -> tuple[IngestionRun, list[CommonRecord], JobDiscoveryResult | None]:
            run.status = IngestionRunStatus.SUSPICIOUS_ZERO if suspicious_zero else IngestionRunStatus.FAILED
            run.error = message
            run.completed_at = now_canberra()
            self._capture_sanity(
                discovery,
                duplicate_record_ids=duplicate_record_ids,
                duplicate_canonical_urls=duplicate_canonical_urls,
            )
            self._save_failed_run(run)
            return run, [], discovery

        if not self._is_listing_url(listing_url):
            return fail("Listing URL is outside the approved Jobs boundary")
        try:
            listing_html = self._fetch(listing_url)
            discovery = self._discovery.discover(listing_html, listing_url, max_details=max_details)
        except FetchError as exc:
            return fail(f"Listing fetch failed: {exc}")
        except Exception as exc:
            return fail(f"Listing discovery failed: {exc}")
        self._capture_sanity(discovery)
        if (
            discovery.advertised_page_count is not None
            and discovery.advertised_page_count >= 4
            and discovery.discovered_candidate_count * 2
            < discovery.advertised_page_count
        ):
            return fail(
                "Jobs listing card count is suspiciously below its advertised page count",
                discovery,
            )
        if not discovery.candidates:
            return fail("Jobs listing produced zero approved detail candidates", discovery, suspicious_zero=True)

        records: list[CommonRecord] = []
        try:
            for candidate in discovery.candidates:
                parsed = self._parser.parse(
                    self._fetch(candidate.url, detail=True),
                    candidate.url,
                    listing_metadata=candidate.listing_metadata,
                )
                if len(parsed) != 1:
                    return fail(f"Expected exactly one record from {candidate.url!r}", discovery)
                record = parsed[0]
                if (
                    record.domain != Domain.JOBS
                    or record.source_id != SOURCE_ID
                    or record.record_id != f"jobs:job:{record.entity_id}"
                    or record.canonical_url != candidate.url
                ):
                    return fail("Job detail failed identity/provenance validation", discovery)
                records.append(record)
        except FetchError as exc:
            return fail(f"Detail fetch failed: {exc}", discovery)
        except (ParseError, ValidationError, ValueError) as exc:
            return fail(f"Detail parser failed: {exc}", discovery)
        except Exception:
            return fail("Unexpected Jobs detail parser failure", discovery)

        record_ids = [record.record_id for record in records]
        urls = [record.canonical_url for record in records]
        duplicate_record_ids = len(record_ids) - len(set(record_ids))
        duplicate_urls = len(urls) - len(set(urls))
        self._capture_sanity(
            discovery,
            duplicate_record_ids=duplicate_record_ids,
            duplicate_canonical_urls=duplicate_urls,
        )
        if duplicate_record_ids or duplicate_urls:
            return fail(
                "Duplicate normalized Jobs records detected",
                discovery,
                duplicate_record_ids=duplicate_record_ids,
                duplicate_canonical_urls=duplicate_urls,
            )
        run.status = IngestionRunStatus.SUCCESS
        run.completed_at = now_canberra()
        try:
            results = self._store.save_records_and_run(records, run)
        except Exception:
            run.status = IngestionRunStatus.FAILED
            run.records_added = run.records_changed = run.records_unchanged = 0
            run.error = "Atomic persistence failed; preflighted records were not committed"
            run.completed_at = now_canberra()
            self._save_failed_run(run)
            return run, [], discovery
        return run, [record for _action, record in results], discovery


__all__ = ["JobsCollector", "JobsParser", "LISTING_URL", "SOURCE_ID"]
