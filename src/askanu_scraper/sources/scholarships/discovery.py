"""Discovery for the approved public ANU scholarship finder."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from askanu_scraper.common.normalizer import normalize_text
from askanu_scraper.common.parser import ParseError
from askanu_scraper.sources.scholarships.parser import normalize_scholarship_url


@dataclass(frozen=True)
class ScholarshipCandidate:
    url: str
    featured: bool
    status: str | None
    application_requirement: str | None

    @property
    def listing_metadata(self) -> dict[str, object]:
        return {
            "featured": self.featured,
            "status": self.status,
            "application_requirement": self.application_requirement,
        }


@dataclass(frozen=True)
class ScholarshipDiscoveryResult:
    candidates: tuple[ScholarshipCandidate, ...]
    discovered_candidate_count: int
    rejected_links: tuple[str, ...]
    duplicate_links: tuple[str, ...]
    over_limit_count: int
    headline_total_count: int | None = None
    rejected_by_reason: dict[str, int] | None = None


class ScholarshipsDiscovery:
    """Discover same-site public detail pages from one finder page."""

    def discover(
        self,
        raw_content: str,
        listing_url: str,
        *,
        max_details: int | None = None,
    ) -> ScholarshipDiscoveryResult:
        if max_details is not None and not 1 <= max_details <= 10:
            raise ValueError("max_details must be between 1 and 10")

        soup = BeautifulSoup(raw_content, "lxml")
        cards: list[Tag] = list(soup.select("article.scholarship-result"))
        cards.extend(
            anchor
            for anchor in soup.select("a.d-block.h100")
            if not anchor.find_parent("article", class_="scholarship-result")
        )
        candidates: list[ScholarshipCandidate] = []
        rejected: list[str] = []
        duplicates: list[str] = []
        seen_urls: set[str] = set()
        over_limit = 0
        headline_total: int | None = None
        headline = soup.select_one(".expanded-filters-results-count")
        if headline is None:
            headline = soup.find(
                string=re.compile(
                    r"\b\d[\d,]*\s+(?:results?|scholarships?)\b", re.I
                )
            )
        if headline is not None:
            headline_text = (
                headline.get_text(" ", strip=True)
                if isinstance(headline, Tag)
                else str(headline)
            )
            match = re.search(r"\b(\d[\d,]*)\b", headline_text)
            if match:
                headline_total = int(match.group(1).replace(",", ""))

        for card in cards:
            anchor = card if card.name == "a" else card.find("a", href=True)
            if not isinstance(anchor, Tag) or not anchor.get("href"):
                rejected.append("missing-detail-link")
                continue

            candidate_url = urljoin(listing_url, str(anchor["href"]))
            card_text = normalize_text(card.get_text(" ", strip=True)) or ""
            if "external scholarship" in card_text.casefold():
                rejected.append("external-scholarship")
                continue
            try:
                candidate_url = normalize_scholarship_url(candidate_url)
            except (ParseError, ValueError):
                rejected.append("outside-approved-detail-boundary")
                continue
            if candidate_url in seen_urls:
                duplicates.append(candidate_url)
                rejected.append("duplicate-detail-link")
                continue
            seen_urls.add(candidate_url)
            if max_details is not None and len(candidates) >= max_details:
                over_limit += 1
                rejected.append("over-detail-limit")
                continue

            status = next(
                (
                    item
                    for item in ("Open for applications", "Application closed")
                    if item.casefold() in card_text.casefold()
                ),
                None,
            )
            requirement = next(
                (
                    item
                    for item in ("Automatic consideration", "Requires application")
                    if item.casefold() in card_text.casefold()
                ),
                None,
            )
            candidates.append(
                ScholarshipCandidate(
                    url=candidate_url,
                    featured="featured" in card_text.casefold(),
                    status=status,
                    application_requirement=requirement,
                )
            )

        rejected_by_reason: dict[str, int] = {}
        for reason in rejected:
            rejected_by_reason[reason] = rejected_by_reason.get(reason, 0) + 1
        return ScholarshipDiscoveryResult(
            candidates=tuple(candidates),
            discovered_candidate_count=len(cards),
            rejected_links=tuple(rejected),
            duplicate_links=tuple(duplicates),
            over_limit_count=over_limit,
            headline_total_count=headline_total,
            rejected_by_reason=rejected_by_reason,
        )
