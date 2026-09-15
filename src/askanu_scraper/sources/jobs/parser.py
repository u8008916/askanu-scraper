"""Parser for public ANU Jobs detail pages."""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup, NavigableString, Tag

from askanu_scraper.common.models import CommonRecord, Domain
from askanu_scraper.common.normalizer import (
    CANBERRA_TZ,
    make_content_hash,
    normalize_text,
    now_canberra,
)
from askanu_scraper.common.parser import BaseParser, ParseError


SOURCE_ID = "jobs_anu_search"
DETAIL_PATH_RE = re.compile(r"/jobs/([a-z0-9]+(?:-[a-z0-9]+)*)")
JOB_ID_RE = re.compile(r"[0-9]+")


def normalize_job_url(url: str) -> str:
    """Return a canonical public ANU job-detail URL or raise ``ParseError``."""
    try:
        parsed = urlsplit(url.strip())
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise ParseError("Job canonical URL is malformed") from exc
    if (
        parsed.scheme.lower() != "https"
        or parsed.hostname is None
        or parsed.hostname.lower() != "jobs.anu.edu.au"
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or DETAIL_PATH_RE.fullmatch(parsed.path.rstrip("/")) is None
    ):
        raise ParseError("Job canonical URL is outside the approved detail boundary")
    return urlunsplit(("https", "jobs.anu.edu.au", parsed.path.rstrip("/"), "", ""))


def _text(node: Tag | None) -> str | None:
    return normalize_text(node.get_text(" ", strip=True)) if node is not None else None


def _first_text(soup: BeautifulSoup, selectors: tuple[str, ...]) -> str | None:
    for selector in selectors:
        value = _text(soup.select_one(selector))
        if value:
            return value
    return None


def _listing_value(metadata: Mapping[str, object], key: str) -> str | None:
    value = metadata.get(key)
    return normalize_text(value) if isinstance(value, str) else None


def _listing_values(metadata: Mapping[str, object], key: str) -> list[str]:
    value = metadata.get(key)
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        text = normalize_text(item)
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _all_text(soup: BeautifulSoup, selectors: tuple[str, ...]) -> list[str]:
    for selector in selectors:
        values: list[str] = []
        for node in soup.select(selector):
            value = _text(node)
            if value and value not in values:
                values.append(value)
        if values:
            return values
    return []


def _labelled_value(soup: BeautifulSoup, label: str) -> str | None:
    """Read text following a strong detail-page label up to the next line break."""
    for strong in soup.select(".job-description strong"):
        heading = normalize_text(strong.get_text(" ", strip=True))
        if not heading or heading.rstrip(":").casefold() != label.casefold():
            continue
        parts: list[str] = []
        for sibling in strong.next_siblings:
            if isinstance(sibling, Tag) and sibling.name == "br":
                break
            if isinstance(sibling, NavigableString):
                parts.append(str(sibling))
            elif isinstance(sibling, Tag):
                parts.append(sibling.get_text(" ", strip=True))
        return normalize_text(" ".join(parts))
    return None


def _canonical_url(soup: BeautifulSoup, fetched_url: str) -> str:
    fetched_canonical = normalize_job_url(fetched_url)
    canonical = soup.find("link", rel=lambda value: value and "canonical" in value)
    if isinstance(canonical, Tag) and isinstance(canonical.get("href"), str):
        page_canonical = normalize_job_url(str(canonical["href"]))
        if page_canonical != fetched_canonical:
            raise ParseError("Job canonical URL does not match the fetched detail URL")
        return page_canonical
    return fetched_canonical


def _parse_closing(value: str | None) -> tuple[str | None, datetime | None]:
    """Parse source closing wording without inventing a missing time."""
    if value is None:
        return None, None
    stripped = re.sub(r"^Closing\s+(?:at|on)\s*:\s*", "", value, flags=re.IGNORECASE)
    exact = re.fullmatch(
        r"([A-Z][a-z]{2}\s+\d{1,2}\s+\d{4})\s+-\s+(\d{1,2}:\d{2})(?:\s+(AEST|AEDT))?",
        stripped,
    )
    if exact:
        try:
            wall_time = datetime.strptime(
                f"{exact.group(1)} {exact.group(2)}", "%b %d %Y %H:%M"
            )
        except ValueError:
            return None, None
        aware = wall_time.replace(tzinfo=CANBERRA_TZ)
        return aware.date().isoformat(), aware
    try:
        closing_date = datetime.strptime(stripped, "%b %d %Y").date()
    except ValueError:
        return None, None
    return closing_date.isoformat(), None


def _normalise_status(
    source_status: str | None,
    closing_date: str | None,
    closing_at: datetime | None,
    observed_at: datetime,
) -> str | None:
    if source_status:
        lowered = source_status.casefold()
        if "closed" in lowered or "expired" in lowered:
            return "closed"
        if "open" in lowered or "current" in lowered:
            return "current"
    current = observed_at.astimezone(CANBERRA_TZ)
    if closing_at is not None:
        return "closed" if current > closing_at else "current"
    if closing_date is not None:
        parsed_date = datetime.strptime(closing_date, "%Y-%m-%d").date()
        return "closed" if current.date() > parsed_date else "current"
    return None


class JobsParser(BaseParser):
    """Convert one public ANU Jobs detail page into one normalized record."""

    SOURCE_ID = SOURCE_ID

    def __init__(self, now_func: Callable[[], datetime] | None = None) -> None:
        self._now = now_func or now_canberra

    def parse(
        self,
        raw_content: str,
        url: str,
        *,
        listing_metadata: Mapping[str, object] | None = None,
    ) -> list[CommonRecord]:
        metadata = listing_metadata or {}
        soup = BeautifulSoup(raw_content, "lxml")
        canonical_url = _canonical_url(soup, url)
        title = _first_text(
            soup, ("h3.job-title", "h1 .editor-placeholder", "h1")
        ) or _listing_value(metadata, "title")
        job_id = _first_text(
            soup,
            (".job-component-requisition-identifier span", "[data-job-id]"),
        ) or _listing_value(metadata, "job_id")
        if not title:
            raise ParseError("Job detail is missing a title")
        if not job_id or JOB_ID_RE.fullmatch(job_id) is None:
            raise ParseError("Job detail is missing a numeric requisition identifier")

        category = _listing_value(metadata, "category") or _first_text(
            soup, (".job-component-category span", ".category")
        )
        employment_types = _all_text(
            soup, (".job-component-employment-type span", ".employment-type")
        ) or _listing_values(metadata, "employment_types")
        location = _first_text(
            soup, (".job-component-location span", ".location")
        ) or _listing_value(metadata, "location")
        classification = (
            _labelled_value(soup, "Classification")
            or _first_text(soup, (".job-component-dropdown-field-1 span", ".classification"))
            or _listing_value(metadata, "classification")
        )
        salary = (
            _labelled_value(soup, "Salary package")
            or _labelled_value(soup, "Salary")
            or _first_text(soup, (".job-component-salary span", ".salary"))
            or _listing_value(metadata, "salary")
        )
        closing_text = _first_text(
            soup,
            (
                ".job-component-closing-at span",
                ".job-component-closing-on span",
                ".closing-date",
            ),
        ) or _listing_value(metadata, "closing_text")
        source_status = _first_text(soup, (".job-status", ".status")) or _listing_value(
            metadata, "source_status"
        )
        summary = _listing_value(metadata, "summary") or _first_text(
            soup, (".job-summary", ".job-search-results-summary")
        )

        closing_date, closing_at = _parse_closing(closing_text)
        observed_at = self._now()
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ParseError("Jobs parser clock must be timezone-aware")
        job_status = _normalise_status(
            source_status, closing_date, closing_at, observed_at
        )

        normalized_metadata: dict[str, object] = {
            "entity_type": "job",
            "job_id": job_id,
            "category": category,
            "employment_types": employment_types,
            "location": location,
            "classification": classification,
            "salary": salary,
            "closing_text": closing_text,
            "closing_date": closing_date,
            "closing_at": closing_at.isoformat() if closing_at else None,
            "status": job_status,
            "summary": summary,
        }
        labels = (
            ("Title", title),
            ("Job ID", job_id),
            ("Category", category),
            ("Employment types", "; ".join(employment_types)),
            ("Location", location),
            ("Classification", classification),
            ("Salary", salary),
            ("Closing", closing_text),
            ("Status", job_status),
            ("Summary", summary),
        )
        content = "\n".join(f"{label}: {value}" for label, value in labels if value)
        return [
            CommonRecord(
                record_id=f"jobs:job:{job_id}",
                source_id=SOURCE_ID,
                entity_id=job_id,
                domain=Domain.JOBS,
                title=title,
                content=content,
                canonical_url=canonical_url,
                collected_at=observed_at,
                last_seen_at=observed_at,
                content_hash=make_content_hash(content),
                metadata_json=normalized_metadata,
            )
        ]
