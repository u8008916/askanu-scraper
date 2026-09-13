"""Bounded discovery for the approved ANU scholarship finder."""
from __future__ import annotations

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


class ScholarshipsDiscovery:
    """Discover same-site public detail pages without pagination."""

    def discover(
        self,
        raw_content: str,
        listing_url: str,
        *,
        max_details: int,
    ) -> ScholarshipDiscoveryResult:
        if not 1 <= max_details <= 10:
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
            if len(candidates) >= max_details:
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

        return ScholarshipDiscoveryResult(
            candidates=tuple(candidates),
            discovered_candidate_count=len(cards),
            rejected_links=tuple(rejected),
            duplicate_links=tuple(duplicates),
            over_limit_count=over_limit,
        )
