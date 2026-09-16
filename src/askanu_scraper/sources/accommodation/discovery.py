"""Discovery for the approved public ANU accommodation residence listing."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from askanu_scraper.common.normalizer import normalize_text
from askanu_scraper.common.parser import ParseError
from askanu_scraper.sources.accommodation.parser import normalize_accommodation_url


@dataclass(frozen=True)
class AccommodationCandidate:
    url: str
    listing_metadata: dict[str, object]


@dataclass(frozen=True)
class AccommodationDiscoveryResult:
    candidates: list[AccommodationCandidate]
    discovered_candidate_count: int
    approved_candidate_count: int
    advertised_total_count: int | None
    rejected_links: list[str]
    duplicate_links: list[str]
    over_limit_count: int


def _text(node: Tag | None) -> str | None:
    return normalize_text(node.get_text(" ", strip=True)) if node else None


class AccommodationDiscovery:
    """Enumerate residence cards without following application-portal links."""

    def discover(
        self,
        raw_content: str,
        listing_url: str,
        *,
        max_details: int | None = None,
    ) -> AccommodationDiscoveryResult:
        if max_details is not None and max_details < 1:
            raise ValueError("max_details must be at least 1")
        soup = BeautifulSoup(raw_content, "lxml")
        main = soup.select_one("main")
        if main is None:
            raise ParseError("Accommodation listing has no main content")

        total_match = re.search(
            r"\b(\d+)\s+results?\s+found\b",
            main.get_text(" ", strip=True),
            re.IGNORECASE,
        )
        advertised_total = int(total_match.group(1)) if total_match else None

        candidates: list[AccommodationCandidate] = []
        rejected: list[str] = []
        duplicates: list[str] = []
        seen: set[str] = set()
        discovered = 0
        approved = 0
        over_limit = 0

        for card in main.select(".acc-card"):
            link = card.select_one("p.h3 a[href]")
            if not isinstance(link, Tag) or not isinstance(link.get("href"), str):
                rejected.append("missing-detail-link")
                continue
            discovered += 1
            raw_url = urljoin(listing_url, str(link["href"]))
            try:
                canonical_url = normalize_accommodation_url(raw_url)
            except ParseError:
                rejected.append(raw_url)
                continue
            if canonical_url in seen:
                duplicates.append(canonical_url)
                continue
            seen.add(canonical_url)
            approved += 1

            profile = _text(card.select_one(".small.text-unigrey"))
            catering_options: list[str] = []
            audiences: list[str] = []
            if profile:
                left, separator, right = profile.partition("|")
                catering_options = [
                    value
                    for part in left.split(",")
                    if (value := normalize_text(part))
                ]
                if separator:
                    audiences = [
                        value
                        for part in right.split(",")
                        if (value := normalize_text(part))
                    ]

            rate_node = card.select_one(".bg-black")
            advertised_rate = _text(rate_node)
            description = _text(card.select_one("p.my-1 .nounderline"))
            title = _text(link)
            if not title:
                rejected.append(canonical_url)
                approved -= 1
                continue
            if max_details is not None and len(candidates) >= max_details:
                over_limit += 1
                continue
            candidates.append(
                AccommodationCandidate(
                    url=canonical_url,
                    listing_metadata={
                        "title": title,
                        "category": "Our residences",
                        "catering_options": catering_options,
                        "audiences": audiences,
                        "advertised_rate": advertised_rate,
                        "listing_description": description,
                    },
                )
            )

        return AccommodationDiscoveryResult(
            candidates=candidates,
            discovered_candidate_count=discovered,
            approved_candidate_count=approved,
            advertised_total_count=advertised_total,
            rejected_links=rejected,
            duplicate_links=duplicates,
            over_limit_count=over_limit,
        )
