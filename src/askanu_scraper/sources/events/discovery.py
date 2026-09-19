"""Bounded listing discovery for Official ANU Events."""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from askanu_scraper.common.normalizer import normalize_text
from askanu_scraper.common.parser import ParseError
from askanu_scraper.sources.events.parser import normalize_event_url


@dataclass(frozen=True)
class EventCandidate:
    url: str


@dataclass(frozen=True)
class EventDiscoveryPage:
    candidates: list[EventCandidate]
    raw_card_count: int
    rejected_by_reason: dict[str, int]
    advertised_last_page: int | None


def listing_page_number(url: str) -> int | None:
    values = parse_qs(urlsplit(url).query).get("page")
    return int(values[0]) if values and values[0].isdigit() else None


class EventsDiscovery:
    def discover(self, raw_content: str, listing_url: str) -> EventDiscoveryPage:
        soup = BeautifulSoup(raw_content, "lxml")
        cards = soup.select(
            "div.shadow-light.d-flex.flex-column.mb-3.bg-white, article.event-card, .event-card"
        )
        candidates: list[EventCandidate] = []
        rejected: dict[str, int] = {}
        for card in cards:
            link = card.select_one('a[href*="/events/"]')
            if not isinstance(link, Tag) or not isinstance(link.get("href"), str):
                rejected["missing-detail-link"] = rejected.get("missing-detail-link", 0) + 1
                continue
            try:
                candidates.append(EventCandidate(normalize_event_url(urljoin(listing_url, str(link["href"])))))
            except ParseError:
                rejected["outside-approved-detail-boundary"] = rejected.get(
                    "outside-approved-detail-boundary", 0
                ) + 1
        last_page: int | None = None
        for link in soup.select(".pager a[href], nav[aria-label*=pagination i] a[href]"):
            href = link.get("href")
            if isinstance(href, str):
                page = listing_page_number(urljoin(listing_url, href))
                if page is not None:
                    last_page = max(last_page or 0, page)
        if not cards and not normalize_text(soup.get_text(" ", strip=True)):
            raise ParseError("Events listing is empty HTML")
        return EventDiscoveryPage(candidates, len(cards), rejected, last_page)


__all__ = ["EventCandidate", "EventDiscoveryPage", "EventsDiscovery"]
