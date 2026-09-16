"""Discovery for the explicitly approved ANUSA Student Assistance registry."""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from askanu_scraper.common.normalizer import normalize_text
from askanu_scraper.common.parser import ParseError
from askanu_scraper.sources.support.parser import normalize_support_url


@dataclass(frozen=True)
class SupportCandidate:
    url: str
    listing_metadata: dict[str, object]


@dataclass(frozen=True)
class SupportDiscoveryResult:
    candidates: list[SupportCandidate]
    discovered_candidate_count: int
    approved_candidate_count: int
    rejected_links: list[str]
    duplicate_links: list[str]
    over_limit_count: int


def _text(node: Tag | None) -> str | None:
    return normalize_text(node.get_text(" ", strip=True)) if node else None


class SupportDiscovery:
    """Enumerate only category cards published by the approved registry page."""

    def discover(
        self,
        raw_content: str,
        listing_url: str,
        *,
        max_details: int | None = None,
    ) -> SupportDiscoveryResult:
        if max_details is not None and max_details < 1:
            raise ValueError("max_details must be at least 1")
        soup = BeautifulSoup(raw_content, "lxml")
        main = soup.select_one("main#content, main")
        if main is None:
            raise ParseError("Support registry has no main content")

        page_text = normalize_text(main.get_text(" ", strip=True)) or ""
        audience = "all ANU Students" if "all ANU Students" in page_text else None
        cost = "The service is free." if "service is free" in page_text.casefold() else None
        email_node = main.select_one('a[href^="mailto:"]')
        email = None
        if isinstance(email_node, Tag):
            email = normalize_text(str(email_node.get("href", ""))[7:]) or _text(email_node)
        if email is None:
            import re

            match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", page_text, re.I)
            email = match.group(0) if match else None

        candidates: list[SupportCandidate] = []
        rejected: list[str] = []
        duplicates: list[str] = []
        seen: set[str] = set()
        discovered = 0
        approved = 0
        over_limit = 0
        for card in main.select("a.elementor-cta[href]"):
            title = _text(card.select_one(".elementor-cta__title"))
            if not title:
                continue
            discovered += 1
            raw_url = urljoin(listing_url, str(card.get("href", "")))
            try:
                canonical_url = normalize_support_url(raw_url)
            except ParseError:
                rejected.append(raw_url)
                continue
            # The frozen registry contains top-level category pages only.
            path_parts = [part for part in canonical_url.split("/")[3:] if part]
            if len(path_parts) != 2:
                rejected.append(raw_url)
                continue
            if canonical_url in seen:
                duplicates.append(canonical_url)
                continue
            seen.add(canonical_url)
            approved += 1
            if max_details is not None and len(candidates) >= max_details:
                over_limit += 1
                continue
            candidates.append(
                SupportCandidate(
                    url=canonical_url,
                    listing_metadata={
                        "title": title,
                        "category": title,
                        "listing_description": _text(
                            card.select_one(".elementor-cta__description")
                        ),
                        "audiences": [audience] if audience else [],
                        "cost": cost,
                        "registry_email": email,
                    },
                )
            )
        return SupportDiscoveryResult(
            candidates=candidates,
            discovered_candidate_count=discovered,
            approved_candidate_count=approved,
            rejected_links=rejected,
            duplicate_links=duplicates,
            over_limit_count=over_limit,
        )
