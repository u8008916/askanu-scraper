"""Safe collector for the approved public ANU Jobs source."""
from __future__ import annotations

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
from askanu_scraper.sources.jobs.discovery import JobCandidate, JobDiscoveryResult, JobsDiscovery
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
        self._listing_request_count = 0
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
            "rejected_by_reason": {},
            "listing_reconciled": False,
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
            "listing_request_count": self._listing_request_count,
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
            "rejected_by_reason": discovery.rejected_by_reason or {} if discovery else {},
            "listing_reconciled": bool(
                discovery
                and discovery.advertised_total_count is not None
                and len(discovery.candidates) == discovery.advertised_total_count
            ),
        }

    def _fetch(self, url: str, *, detail: bool = False) -> str:
        if self._request_count and self._interval > 0:
            self._sleep(self._interval)
        self._request_count += 1
        if detail:
            self._detail_request_count += 1
        else:
            self._listing_request_count += 1
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

    def discover_full_listing(
        self,
        *,
        listing_url: str = LISTING_URL,
        max_listing_pages: int = 100,
        max_details: int | None = None,
    ) -> JobDiscoveryResult:
        """Enumerate and reconcile Jobs pages without fetching details/writing."""
        if not self._is_listing_url(listing_url):
            raise ValueError("Listing URL is outside the approved Jobs boundary")
        if not 1 <= max_listing_pages <= 100:
            raise ValueError("max_listing_pages must be between 1 and 100")
        if max_details is not None and max_details < 1:
            raise ValueError("max_details must be at least 1")

        self._request_count = 0
        self._detail_request_count = 0
        self._listing_request_count = 0
        self.last_run_sanity = self._empty_sanity()
        page_results: list[JobDiscoveryResult] = []
        first = self._discovery.discover(self._fetch(listing_url), listing_url)
        page_results.append(first)
        advertised_total = first.advertised_total_count
        unique_urls = {candidate.url for candidate in first.candidates}
        for page_number in range(1, max_listing_pages):
            if advertised_total is not None and len(unique_urls) >= advertised_total:
                break
            page_url = listing_url + "?" + urlencode({"page": page_number})
            page = self._discovery.discover(self._fetch(page_url), page_url)
            page_results.append(page)
            before = len(unique_urls)
            unique_urls.update(candidate.url for candidate in page.candidates)
            if page.discovered_candidate_count == 0:
                break
            if len(unique_urls) == before and page_number > 1:
                break

        candidates: list[JobCandidate] = []
        rejected: list[str] = []
        duplicate_links: list[str] = []
        seen: set[str] = set()
        over_limit = 0
        for page in page_results:
            rejected.extend(page.rejected_links)
            duplicate_links.extend(page.duplicate_links)
            over_limit += page.over_limit_count
            for candidate in page.candidates:
                if candidate.url in seen:
                    duplicate_links.append(candidate.url)
                    continue
                seen.add(candidate.url)
                if max_details is not None and len(candidates) >= max_details:
                    over_limit += 1
                    continue
                candidates.append(candidate)
        rejected_by_reason: dict[str, int] = {}
        for reason in rejected:
            key = reason if "://" not in reason else "outside-approved-detail-boundary"
            rejected_by_reason[key] = rejected_by_reason.get(key, 0) + 1
        result = JobDiscoveryResult(
            candidates=candidates,
            discovered_candidate_count=sum(
                page.discovered_candidate_count for page in page_results
            ),
            rejected_links=rejected,
            duplicate_links=duplicate_links,
            over_limit_count=over_limit,
            advertised_page_count=first.advertised_page_count,
            advertised_total_count=advertised_total,
            advertised_first=first.advertised_first,
            advertised_last=first.advertised_last,
            rejected_by_reason=rejected_by_reason,
        )
        self._capture_sanity(result)
        return result

    def run_listing(
        self,
        *,
        listing_url: str = LISTING_URL,
        max_listing_pages: int = 1,
        max_details: int | None = 10,
    ) -> tuple[IngestionRun, list[CommonRecord], JobDiscoveryResult | None]:
        if not 1 <= max_listing_pages <= 100:
            raise ValueError("max_listing_pages must be between 1 and 100")
        if max_details is not None and max_details < 1:
            raise ValueError("max_details must be at least 1")
        self._request_count = 0
        self._detail_request_count = 0
        self._listing_request_count = 0
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
            discovery = self.discover_full_listing(
                listing_url=listing_url,
                max_listing_pages=max_listing_pages,
                max_details=max_details,
            )
        except FetchError as exc:
            return fail(f"Listing fetch failed: {exc}")
        except Exception as exc:
            return fail(f"Listing discovery failed: {exc}")
        self._capture_sanity(discovery)
        if max_listing_pages > 1 and discovery.advertised_total_count is None:
            return fail(
                "Jobs advertised total is missing or malformed",
                discovery,
                suspicious_zero=discovery.discovered_candidate_count == 0,
            )
        if (
            max_listing_pages > 1
            and discovery.advertised_total_count is not None
            and len(discovery.candidates) != discovery.advertised_total_count
        ):
            return fail(
                "Jobs unique approved candidates do not reconcile with advertised total",
                discovery,
                suspicious_zero=len(discovery.candidates) == 0,
            )
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
