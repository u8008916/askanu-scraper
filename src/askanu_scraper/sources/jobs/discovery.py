"""Bounded discovery of public ANU Jobs detail pages."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from askanu_scraper.common.normalizer import normalize_text
from askanu_scraper.common.parser import ParseError
from askanu_scraper.sources.jobs.parser import normalize_job_url


@dataclass(frozen=True)
class JobCandidate:
    url: str
    listing_metadata: dict[str, object]


@dataclass(frozen=True)
class JobDiscoveryResult:
    candidates: list[JobCandidate]
    discovered_candidate_count: int
    rejected_links: list[str]
    duplicate_links: list[str]
    over_limit_count: int
    advertised_page_count: int | None
    advertised_total_count: int | None
    advertised_first: int | None = None
    advertised_last: int | None = None
    rejected_by_reason: dict[str, int] | None = None


def _text(card: Tag, selectors: tuple[str, ...]) -> str | None:
    for selector in selectors:
        node = card.select_one(selector)
        if node is not None:
            value = normalize_text(node.get_text(" ", strip=True))
            if value:
                return value
    return None


def _texts(card: Tag, selectors: tuple[str, ...]) -> list[str]:
    for selector in selectors:
        values: list[str] = []
        for node in card.select(selector):
            value = normalize_text(node.get_text(" ", strip=True))
            if value and value not in values:
                values.append(value)
        if values:
            return values
    return []


class JobsDiscovery:
    def discover(
        self, raw_content: str, listing_url: str, *, max_details: int | None = None
    ) -> JobDiscoveryResult:
        if max_details is not None and max_details < 1:
            raise ValueError("max_details must be at least 1")
        soup = BeautifulSoup(raw_content, "lxml")
        page_count: int | None = None
        total_count: int | None = None
        advertised_first: int | None = None
        advertised_last: int | None = None
        count_node = soup.select_one(".table-counts")
        page_text = (
            count_node.get_text(" ", strip=True)
            if count_node is not None
            else soup.find(
                string=re.compile(
                    r"Displaying\s+\d+\s*-\s*\d+\s+of\s+\d+", re.I
                )
            )
        )
        if page_text is not None:
            count_match = re.search(
                r"Displaying\s+(\d+)[^\d]+(\d+)\s+of\s+(\d+)",
                str(page_text),
                re.I,
            )
            if count_match:
                first, last, total_count = map(int, count_match.groups())
                advertised_first, advertised_last = first, last
                if last >= first:
                    page_count = last - first + 1
        cards = soup.select("article.job-search-results-card-col, article.job-result")
        candidates: list[JobCandidate] = []
        rejected: list[str] = []
        duplicates: list[str] = []
        seen: set[str] = set()
        discovered = 0
        over_limit = 0
        for card in cards:
            link = card.select_one(".job-search-results-card-title a[href], h2 a[href]")
            if not isinstance(link, Tag) or not isinstance(link.get("href"), str):
                rejected.append("missing-detail-link")
                continue
            discovered += 1
            raw_url = urljoin(listing_url, str(link["href"]))
            try:
                canonical_url = normalize_job_url(raw_url)
            except ParseError:
                rejected.append(raw_url)
                continue
            if canonical_url in seen:
                duplicates.append(canonical_url)
                continue
            seen.add(canonical_url)
            if max_details is not None and len(candidates) >= max_details:
                over_limit += 1
                continue
            job_id = card.get("data-job-id")
            metadata: dict[str, object] = {
                "job_id": normalize_text(str(job_id)) if job_id else None,
                "category": _text(card, (".job-component-category", ".category")),
                "employment_types": _texts(
                    card, (".job-component-employment-type", ".employment-type")
                ),
                "location": _text(card, (".job-component-location", ".location")),
                "classification": _text(
                    card, (".job-component-dropdown-field-1", ".classification")
                ),
                "salary": _text(card, (".job-component-salary", ".salary")),
                "closing_text": _text(
                    card, (".job-component-closing-on", ".closing-date")
                ),
                "source_status": _text(card, (".job-status", ".status")),
                "summary": _text(card, (".job-search-results-summary", ".summary")),
            }
            candidates.append(JobCandidate(canonical_url, metadata))
        rejected_by_reason: dict[str, int] = {}
        for reason in rejected:
            key = reason if "://" not in reason else "outside-approved-detail-boundary"
            rejected_by_reason[key] = rejected_by_reason.get(key, 0) + 1
        return JobDiscoveryResult(
            candidates,
            discovered,
            rejected,
            duplicates,
            over_limit,
            page_count,
            total_count,
            advertised_first,
            advertised_last,
            rejected_by_reason,
        )
