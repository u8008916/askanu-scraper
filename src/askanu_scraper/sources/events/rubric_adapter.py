"""Bounded Rubric ANU-community Events ingestion.

Rubric has granted written permission for bounded AskANU ingestion, as reported
in Qasim's Day 15 handoff. Its public-search endpoints remain internal,
unsupported and change-sensitive. This module is an ingestion-only adapter; it
must never be imported into a synchronous RAG/chat request path.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
import math
import re
import time
from typing import Any, Protocol
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
import uuid

from bs4 import BeautifulSoup
from pydantic import ValidationError
import requests

from askanu_scraper.common.fetcher import FetchError
from askanu_scraper.common.models import CommonRecord, Domain, IngestionRun, IngestionRunStatus
from askanu_scraper.common.normalizer import CANBERRA_TZ, make_content_hash, normalize_text, now_canberra
from askanu_scraper.common.parser import ParseError
from askanu_scraper.common.registry import assert_source_allowed
from askanu_scraper.common.storage import DataStore, LocalDataStore


SOURCE_ID = "rubric_unified_search"
PUBLIC_ROOT = "https://campus.hellorubric.com"
DETAIL_ENDPOINT = "https://appserver.getqpay.com:9090/AppServerSwapnil/event/details"
UNIVERSITY_ID = "1"
COUNTRY_CODE = "AU"
STATE = "Australian Capital Territory"


class RubricTransport(Protocol):
    """Injectable JSON POST boundary; fixtures never require network access."""

    def post_json(self, url: str, payload: Mapping[str, object]) -> str: ...


class HttpRubricTransport:
    """Stateless, timeout-bounded POST transport with transient retry only."""

    MAX_ATTEMPTS = 3
    TRANSIENT_STATUSES = {408, 425, 429, 500, 502, 503, 504}

    def __init__(
        self,
        *,
        timeout_seconds: int = 30,
        user_agent: str = "AskANU/0.1",
        sleep_func: Callable[[float], None] = time.sleep,
    ) -> None:
        if not 1 <= timeout_seconds <= 300:
            raise ValueError("timeout_seconds must be between 1 and 300")
        self._timeout = timeout_seconds
        self._headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": user_agent,
        }
        self._sleep = sleep_func

    def post_json(self, url: str, payload: Mapping[str, object]) -> str:
        last_error: Exception | None = None
        for attempt in range(self.MAX_ATTEMPTS):
            try:
                response = requests.post(
                    url,
                    json=dict(payload),
                    headers=self._headers,
                    timeout=self._timeout,
                    allow_redirects=False,
                )
                if response.status_code in self.TRANSIENT_STATUSES:
                    raise requests.HTTPError("transient Rubric response")
                response.raise_for_status()
                if not response.text or not response.text.strip():
                    raise FetchError("Rubric returned an empty response")
                return response.text
            except (FetchError, requests.RequestException) as exc:
                last_error = exc
                if attempt < self.MAX_ATTEMPTS - 1:
                    self._sleep(float(2**attempt))
        if isinstance(last_error, FetchError):
            raise last_error
        raise FetchError("Rubric request failed after bounded retries") from last_error


class RubricRecordRejected(ParseError):
    """Expected source exclusion with a stable evidence reason."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class RubricDiscoveryPage:
    event_ids: list[str]
    raw_result_count: int
    total_item_count: int


@dataclass(frozen=True)
class RubricDiscoveryResult:
    event_ids: list[str]
    total_item_count: int
    raw_result_count: int
    duplicate_event_ids: list[str]
    pages_traversed: int
    pagination_complete: bool
    over_limit_count: int


def _load_object(raw: str, *, context: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ParseError(f"Rubric {context} response is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ParseError(f"Rubric {context} response must be an object")
    return value


def parse_discovery_page(raw: str) -> RubricDiscoveryPage:
    root = _load_object(raw, context="discovery")
    if root.get("success") is not True:
        raise ParseError("Rubric discovery response did not report success")
    body = root.get("data") if isinstance(root.get("data"), dict) else root
    if not isinstance(body, dict):
        raise ParseError("Rubric discovery data is malformed")
    for key, expected in {
        "selectedCountryCode": COUNTRY_CODE,
        "selectedState": STATE,
    }.items():
        if body.get(key) != expected:
            raise ParseError(f"Rubric discovery {key} does not match the ANU boundary")
    if str(body.get("selectedUniversityId")) != UNIVERSITY_ID:
        raise ParseError("Rubric discovery university does not match ANU")
    total = body.get("totalItemCount")
    results = body.get("results")
    if isinstance(total, bool) or not isinstance(total, int) or total < 0:
        raise ParseError("Rubric discovery totalItemCount is invalid")
    if not isinstance(results, list):
        raise ParseError("Rubric discovery results must be an array")
    event_ids: list[str] = []
    for result in results:
        if not isinstance(result, dict):
            raise ParseError("Rubric discovery result must be an object")
        event_id = str(result.get("eventId", "")).strip()
        if re.fullmatch(r"[0-9]+", event_id) is None:
            raise ParseError("Rubric discovery result is missing a numeric eventId")
        event_ids.append(event_id)
    return RubricDiscoveryPage(event_ids, len(results), total)


def normalize_rubric_event_url(url: str, event_id: str) -> str:
    if re.fullmatch(r"[0-9]+", event_id) is None:
        raise ParseError("Rubric event ID must be numeric")
    try:
        parsed = urlsplit(url.strip())
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise ParseError("Rubric canonical URL is malformed") from exc
    query = parse_qs(parsed.query, keep_blank_values=True)
    if (
        parsed.scheme.lower() != "https"
        or (parsed.hostname or "").lower() != "campus.hellorubric.com"
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.path != "/"
        or query != {"eid": [event_id]}
        or parsed.fragment
    ):
        raise ParseError("Rubric canonical URL is outside the approved public event boundary")
    return urlunsplit(("https", "campus.hellorubric.com", "/", urlencode({"eid": event_id}), ""))


def _parse_datetime(value: object, *, field: str) -> datetime | None:
    if value is None or value == "":
        return None
    parsed: datetime
    if isinstance(value, bool):
        raise ParseError(f"Rubric {field} is not a supported datetime")
    if isinstance(value, (int, float)) or (
        isinstance(value, str) and re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value.strip())
    ):
        numeric = float(value)
        if numeric > 100_000_000_000:
            numeric /= 1000
        try:
            parsed = datetime.fromtimestamp(numeric, tz=timezone.utc)
        except (OverflowError, OSError, ValueError) as exc:
            raise ParseError(f"Rubric {field} epoch is invalid") from exc
    elif isinstance(value, str):
        normalized = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ParseError(f"Rubric {field} is not an ISO datetime") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=CANBERRA_TZ)
    else:
        raise ParseError(f"Rubric {field} is not a supported datetime")
    return parsed.astimezone(CANBERRA_TZ)


def _clean_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    soup = BeautifulSoup(value, "lxml")
    for node in soup.select("script, style, iframe, object, embed"):
        node.decompose()
    return normalize_text(soup.get_text(" ", strip=True))


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        candidate: object = item
        if isinstance(item, dict):
            candidate = item.get("name") or item.get("label") or item.get("title")
        normalized = _clean_text(candidate)
        if normalized and normalized not in output:
            output.append(normalized)
    return output


def parse_detail(raw: str, expected_event_id: str, *, now_func: Callable[[], datetime] = now_canberra) -> CommonRecord:
    root = _load_object(raw, context="detail")
    if root.get("success") is not True:
        raise ParseError("Rubric detail response did not report success")
    detail = root.get("data") if isinstance(root.get("data"), dict) else root
    if not isinstance(detail, dict):
        raise ParseError("Rubric detail data is malformed")
    event_id = str(detail.get("eventId", "")).strip()
    if event_id != expected_event_id or re.fullmatch(r"[0-9]+", event_id) is None:
        raise ParseError("Rubric detail eventId conflicts with discovery identity")
    if detail.get("draft") in {True, 1, "true", "True"}:
        raise RubricRecordRejected("draft")
    title = _clean_text(detail.get("eventName"))
    if not title:
        raise ParseError("Rubric detail is missing eventName")
    start_at = _parse_datetime(detail.get("eventTime"), field="eventTime")
    if start_at is None:
        raise ParseError("Rubric detail is missing eventTime")
    end_at = _parse_datetime(detail.get("eventEndTime"), field="eventEndTime")
    if end_at is not None and end_at < start_at:
        raise ParseError("Rubric eventEndTime precedes eventTime")
    canonical_url = normalize_rubric_event_url(
        f"{PUBLIC_ROOT}/?{urlencode({'eid': event_id})}", event_id
    )
    location = _clean_text(detail.get("eventAddress"))
    organiser = _clean_text(detail.get("eventOrganizer"))
    description = _clean_text(detail.get("eventDescription"))
    categories = _string_list(detail.get("categories"))
    tags = _string_list(detail.get("tags"))
    registration_links: list[dict[str, str]] = []
    event_url = detail.get("eventURL")
    if isinstance(event_url, str) and event_url.strip():
        try:
            parsed_event_url = urlsplit(event_url.strip())
            parsed_event_url.port
        except ValueError:
            parsed_event_url = urlsplit("")
        if (
            parsed_event_url.scheme.lower() in {"http", "https"}
            and parsed_event_url.hostname
            and parsed_event_url.username is None
            and parsed_event_url.password is None
        ):
            registration_links.append({"label": "Event link", "url": event_url.strip()})
    metadata: dict[str, object] = {
        "entity_type": "event",
        "event_id": event_id,
        "start_date": start_at.date().isoformat(),
        "end_date": end_at.date().isoformat() if end_at else None,
        "start_at": start_at.isoformat(),
        "end_at": end_at.isoformat() if end_at else None,
        "timezone": "Australia/Canberra",
        "location": location,
        "format": None,
        "categories": categories,
        "tags": tags,
        "organiser": organiser,
        "description": description,
        "registration_links": registration_links,
        "status": None,
        "cancellation_text": None,
    }
    labels = (
        ("Title", title),
        ("Start", start_at.isoformat()),
        ("End", end_at.isoformat() if end_at else None),
        ("Location", location),
        ("Presented by", organiser),
        ("Categories", "; ".join(categories) or None),
        ("Tags", "; ".join(tags) or None),
        ("Description", description),
        ("Registration", registration_links[0]["url"] if registration_links else None),
        ("Source", "Rubric ANU community events"),
    )
    content = "\n".join(f"{label}: {value}" for label, value in labels if value)
    observed_at = now_func()
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ParseError("Rubric parser clock must be timezone-aware")
    return CommonRecord(
        record_id=f"events:event:rubric:{event_id}",
        source_id=SOURCE_ID,
        entity_id=f"rubric:{event_id}",
        domain=Domain.EVENTS,
        title=title,
        content=content,
        canonical_url=canonical_url,
        effective_from=start_at,
        effective_to=end_at,
        collected_at=observed_at,
        last_seen_at=observed_at,
        content_hash=make_content_hash(content),
        metadata_json=metadata,
    )


def _validate_api_endpoint(url: str, *, name: str) -> str:
    try:
        parsed = urlsplit(url.strip())
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} is malformed") from exc
    if (
        parsed.scheme.lower() != "https"
        or (parsed.hostname or "").lower() != "appserver.getqpay.com"
        or parsed.username is not None
        or parsed.password is not None
        or port != 9090
        or not parsed.path.startswith("/AppServerSwapnil/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{name} is outside the approved Rubric API boundary")
    return urlunsplit(("https", "appserver.getqpay.com:9090", parsed.path, "", ""))


class RubricAdapter:
    """Discover, normalize and safely persist a bounded Rubric Events run."""

    def __init__(
        self,
        *,
        search_endpoint: str | None,
        transport: RubricTransport | None = None,
        store: DataStore | None = None,
        timeout_seconds: int = 30,
        min_request_interval_seconds: float = 1.0,
        sleep_func: Callable[[float], None] = time.sleep,
        now_func: Callable[[], datetime] = now_canberra,
    ) -> None:
        self._source = assert_source_allowed(SOURCE_ID)
        self._search_endpoint = (
            _validate_api_endpoint(search_endpoint, name="Rubric search endpoint")
            if search_endpoint
            else None
        )
        self._detail_endpoint = _validate_api_endpoint(
            DETAIL_ENDPOINT, name="Rubric detail endpoint"
        )
        if min_request_interval_seconds < 1.0:
            raise ValueError("Rubric requests require at least one-second spacing")
        self._transport = transport or HttpRubricTransport(
            timeout_seconds=timeout_seconds, sleep_func=sleep_func
        )
        self._store = store or LocalDataStore()
        self._interval = min_request_interval_seconds
        self._sleep = sleep_func
        self._now = now_func
        self._requests = self._search_requests = self._detail_requests = 0
        self._detail_success_count = 0
        self._detail_cache: dict[str, str] = {}
        self.last_run_sanity: dict[str, object] = self._empty_sanity()

    @staticmethod
    def _empty_sanity() -> dict[str, object]:
        return {
            "request_count": 0,
            "search_request_count": 0,
            "detail_request_count": 0,
            "pages_traversed": 0,
            "reported_total_item_count": None,
            "raw_result_count": 0,
            "unique_event_id_count": 0,
            "duplicate_event_id_count": 0,
            "over_limit_count": 0,
            "pagination_complete": False,
            "detail_success_count": 0,
            "detail_failure_count": 0,
            "accepted_count": 0,
            "rejected_by_reason": {},
            "duplicate_record_id_count": 0,
            "duplicate_canonical_url_count": 0,
            "frozen_denominator": None,
            "minimum_accepted_count": None,
            "entity_coverage_percent": None,
            "source_present_fact_numerator": 0,
            "source_present_fact_denominator": 0,
            "source_present_fact_coverage_percent": None,
            "representative_records": [],
            "source_policy": "APPROVED_BOUNDED_UNSUPPORTED",
        }

    def _post(self, url: str, payload: Mapping[str, object], *, detail: bool = False) -> str:
        if self._requests:
            self._sleep(self._interval)
        self._requests += 1
        if detail:
            self._detail_requests += 1
        else:
            self._search_requests += 1
        return self._transport.post_json(url, payload)

    def _detail(self, event_id: str) -> str:
        if event_id not in self._detail_cache:
            canonical = f"{PUBLIC_ROOT}/?{urlencode({'eid': event_id})}"
            self._detail_cache[event_id] = self._post(
                self._detail_endpoint,
                {
                    "eventId": event_id,
                    "currentUrl": canonical,
                    "device": "web_portal",
                    "version": 4,
                    "timestamp": round(self._now().timestamp() * 1000),
                },
                detail=True,
            )
        return self._detail_cache[event_id]

    def discover(
        self,
        *,
        max_listing_pages: int = 20,
        max_details: int | None = 250,
        page_size: int = 12,
    ) -> RubricDiscoveryResult:
        if self._search_endpoint is None:
            raise ValueError(
                "Rubric search endpoint capture is unavailable; configure the reviewed exact endpoint"
            )
        if not 1 <= max_listing_pages <= 100:
            raise ValueError("max_listing_pages must be between 1 and 100")
        if not 1 <= page_size <= 50:
            raise ValueError("page_size must be between 1 and 50")
        if max_details is not None and max_details < 1:
            raise ValueError("max_details must be positive")
        pages: list[RubricDiscoveryPage] = []
        raw_count = 0
        expected_total: int | None = None
        for page_number in range(max_listing_pages):
            page = parse_discovery_page(
                self._post(
                    self._search_endpoint,
                    {
                        "firstCall": False,
                        "sortType": "date",
                        "desiredType": "events",
                        "limit": page_size,
                        "offset": page_number * page_size,
                        "sortDirection": "asc",
                        "searchQuery": "",
                        "eventsPeriodFilter": "All",
                        "countryCode": COUNTRY_CODE,
                        "state": STATE,
                        "selectedUniversityId": UNIVERSITY_ID,
                    },
                )
            )
            if expected_total is None:
                expected_total = page.total_item_count
            elif page.total_item_count != expected_total:
                raise ParseError("Rubric totalItemCount changed during pagination")
            pages.append(page)
            raw_count += page.raw_result_count
            if raw_count >= expected_total:
                break
            if page.raw_result_count == 0:
                break
        total = expected_total or 0
        pagination_complete = raw_count >= total
        event_ids: list[str] = []
        duplicates: list[str] = []
        seen: set[str] = set()
        over_limit = 0
        for page in pages:
            for event_id in page.event_ids:
                if event_id in seen:
                    duplicates.append(event_id)
                    continue
                seen.add(event_id)
                if max_details is not None and len(event_ids) >= max_details:
                    over_limit += 1
                else:
                    event_ids.append(event_id)
        return RubricDiscoveryResult(
            event_ids=event_ids,
            total_item_count=total,
            raw_result_count=raw_count,
            duplicate_event_ids=duplicates,
            pages_traversed=len(pages),
            pagination_complete=pagination_complete,
            over_limit_count=over_limit,
        )

    @staticmethod
    def _in_window(record: CommonRecord, window_start: date, window_end: date) -> bool:
        start = date.fromisoformat(str(record.metadata_json["start_date"]))
        raw_end = record.metadata_json["end_date"]
        end = date.fromisoformat(str(raw_end)) if raw_end else start
        return start <= window_end and end >= window_start

    def _capture_sanity(
        self,
        discovery: RubricDiscoveryResult | None,
        *,
        records: list[CommonRecord] | None = None,
        rejected: Mapping[str, int] | None = None,
        expected_count: int | None = None,
        duplicate_record_ids: int = 0,
        duplicate_urls: int = 0,
    ) -> None:
        accepted = records or []
        minimum = math.ceil(expected_count * 0.99) if expected_count else None
        denominator = expected_count if expected_count else len(accepted)
        fact_numerator = fact_denominator = 0
        for record in accepted:
            for value in (
                record.entity_id,
                record.title,
                record.canonical_url,
                record.metadata_json["start_date"],
                record.metadata_json["start_at"],
            ):
                fact_denominator += 1
                if value:
                    fact_numerator += 1
            for key in (
                "end_date",
                "end_at",
                "location",
                "categories",
                "tags",
                "organiser",
                "description",
                "registration_links",
            ):
                value = record.metadata_json[key]
                if value not in (None, "", []):
                    fact_denominator += 1
                    fact_numerator += 1
        self.last_run_sanity = {
            "request_count": self._requests,
            "search_request_count": self._search_requests,
            "detail_request_count": self._detail_requests,
            "pages_traversed": discovery.pages_traversed if discovery else 0,
            "reported_total_item_count": discovery.total_item_count if discovery else None,
            "raw_result_count": discovery.raw_result_count if discovery else 0,
            "unique_event_id_count": len(discovery.event_ids) if discovery else 0,
            "duplicate_event_id_count": len(discovery.duplicate_event_ids) if discovery else 0,
            "over_limit_count": discovery.over_limit_count if discovery else 0,
            "pagination_complete": discovery.pagination_complete if discovery else False,
            "detail_success_count": self._detail_success_count,
            "detail_failure_count": self._detail_requests - self._detail_success_count,
            "accepted_count": len(accepted),
            "rejected_by_reason": dict(rejected or {}),
            "duplicate_record_id_count": duplicate_record_ids,
            "duplicate_canonical_url_count": duplicate_urls,
            "frozen_denominator": expected_count,
            "minimum_accepted_count": minimum,
            "entity_coverage_percent": (
                round(len(accepted) * 100 / denominator, 2) if denominator else None
            ),
            "source_present_fact_numerator": fact_numerator,
            "source_present_fact_denominator": fact_denominator,
            "source_present_fact_coverage_percent": (
                round(fact_numerator * 100 / fact_denominator, 2)
                if fact_denominator
                else None
            ),
            "representative_records": [
                {
                    "record_id": record.record_id,
                    "canonical_url": record.canonical_url,
                    "content_hash": record.content_hash,
                }
                for record in accepted[:3]
            ],
            "source_policy": "APPROVED_BOUNDED_UNSUPPORTED",
        }

    def _save_failed_run(self, run: IngestionRun) -> None:
        try:
            self._store.save_run(run)
        except Exception:
            pass

    def run_listing(
        self,
        *,
        max_listing_pages: int = 20,
        max_details: int | None = 250,
        window_start: date,
        window_days: int = 43,
        expected_event_count: int | None = None,
    ) -> tuple[IngestionRun, list[CommonRecord], RubricDiscoveryResult | None]:
        if not 1 <= window_days <= 366:
            raise ValueError("window_days must be between 1 and 366")
        if expected_event_count is not None and expected_event_count < 1:
            raise ValueError("expected_event_count must be positive")
        window_end = window_start + timedelta(days=window_days - 1)
        self._requests = self._search_requests = self._detail_requests = 0
        self._detail_success_count = 0
        self._detail_cache.clear()
        self.last_run_sanity = self._empty_sanity()
        run = IngestionRun(
            run_id=f"run_{uuid.uuid4().hex[:12]}",
            source_id=SOURCE_ID,
            started_at=self._now(),
            status=IngestionRunStatus.RUNNING,
        )
        try:
            self._store.save_run(run)
        except Exception:
            run.status = IngestionRunStatus.FAILED
            run.error = "RUNNING ingestion-run write failed; collection not started"
            run.completed_at = self._now()
            return run, [], None

        def fail(
            message: str,
            discovery: RubricDiscoveryResult | None = None,
            *,
            suspicious_zero: bool = False,
            records: list[CommonRecord] | None = None,
            rejected: Mapping[str, int] | None = None,
            duplicate_record_ids: int = 0,
            duplicate_urls: int = 0,
        ) -> tuple[IngestionRun, list[CommonRecord], RubricDiscoveryResult | None]:
            run.status = IngestionRunStatus.SUSPICIOUS_ZERO if suspicious_zero else IngestionRunStatus.FAILED
            run.error = message
            run.completed_at = self._now()
            self._capture_sanity(
                discovery,
                records=records,
                rejected=rejected,
                expected_count=expected_event_count,
                duplicate_record_ids=duplicate_record_ids,
                duplicate_urls=duplicate_urls,
            )
            self._save_failed_run(run)
            return run, [], discovery

        try:
            discovery = self.discover(
                max_listing_pages=max_listing_pages,
                max_details=max_details,
            )
        except FetchError as exc:
            return fail(f"Rubric discovery fetch failed: {exc}")
        except (ParseError, ValueError) as exc:
            return fail(f"Rubric discovery failed: {exc}")
        if discovery.total_item_count == 0:
            return fail("Rubric discovery produced a suspicious zero", discovery, suspicious_zero=True)
        if not discovery.pagination_complete:
            return fail("Rubric pagination did not reconcile with totalItemCount", discovery)
        if discovery.over_limit_count:
            return fail("Rubric detail bound prevents complete denominator reconciliation", discovery)

        accepted: list[CommonRecord] = []
        rejected: dict[str, int] = {}
        try:
            for event_id in discovery.event_ids:
                try:
                    raw_detail = self._detail(event_id)
                    self._detail_success_count += 1
                    record = parse_detail(raw_detail, event_id, now_func=self._now)
                except RubricRecordRejected as exc:
                    rejected[exc.reason] = rejected.get(exc.reason, 0) + 1
                    continue
                if self._in_window(record, window_start, window_end):
                    accepted.append(record)
                else:
                    rejected["outside-frozen-window"] = rejected.get("outside-frozen-window", 0) + 1
        except FetchError as exc:
            return fail(f"Rubric detail fetch failed: {exc}", discovery, rejected=rejected)
        except (ParseError, ValidationError, ValueError) as exc:
            return fail(f"Rubric detail parser failed: {exc}", discovery, rejected=rejected)
        except Exception:
            return fail("Unexpected Rubric detail failure", discovery, rejected=rejected)

        record_ids = [record.record_id for record in accepted]
        urls = [record.canonical_url for record in accepted]
        duplicate_record_ids = len(record_ids) - len(set(record_ids))
        duplicate_urls = len(urls) - len(set(urls))
        self._capture_sanity(
            discovery,
            records=accepted,
            rejected=rejected,
            expected_count=expected_event_count,
            duplicate_record_ids=duplicate_record_ids,
            duplicate_urls=duplicate_urls,
        )
        if duplicate_record_ids or duplicate_urls:
            return fail(
                "Duplicate normalized Rubric Event identity detected",
                discovery,
                records=accepted,
                rejected=rejected,
                duplicate_record_ids=duplicate_record_ids,
                duplicate_urls=duplicate_urls,
            )
        if not accepted:
            return fail(
                "Rubric frozen window produced zero accepted events",
                discovery,
                suspicious_zero=True,
                rejected=rejected,
            )
        if expected_event_count is not None and len(accepted) < math.ceil(expected_event_count * 0.99):
            return fail(
                "Rubric accepted count is below 99% of the frozen denominator",
                discovery,
                records=accepted,
                rejected=rejected,
            )
        run.status = IngestionRunStatus.SUCCESS
        run.completed_at = self._now()
        try:
            results = self._store.save_records_and_run(accepted, run)
        except Exception:
            run.status = IngestionRunStatus.FAILED
            run.records_added = run.records_changed = run.records_unchanged = 0
            run.error = "Atomic persistence failed; records were not committed"
            run.completed_at = self._now()
            self._save_failed_run(run)
            return run, [], discovery
        return run, [record for _action, record in results], discovery


__all__ = [
    "DETAIL_ENDPOINT",
    "HttpRubricTransport",
    "RubricAdapter",
    "RubricDiscoveryResult",
    "RubricTransport",
    "SOURCE_ID",
    "normalize_rubric_event_url",
    "parse_detail",
    "parse_discovery_page",
]
