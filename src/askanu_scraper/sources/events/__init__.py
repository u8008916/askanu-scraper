"""
Events collector — Official ANU Events / calendar.
Source: https://www.anu.edu.au/events

Day 1: Scaffold only.

IMPORTANT: Rubric (rubric_unified_search) is PENDING_APPROVAL and non-production.
The RubricAdapter in this package is a disabled placeholder only.
Do NOT call Rubric's undocumented/internal API (getUnifiedSearch or similar)
until approved access is documented.
"""
from __future__ import annotations

from askanu_scraper.common.fetcher import BaseFetcher, HttpFetcher
from askanu_scraper.common.models import CommonRecord
from askanu_scraper.common.registry import assert_source_allowed
from askanu_scraper.sources.events.parser import EventsParser

SOURCE_ID = "events_anu_official"


class EventsCollector:
    def __init__(self, fetcher: BaseFetcher | None = None) -> None:
        self._source = assert_source_allowed(SOURCE_ID)
        self._fetcher = fetcher or HttpFetcher()
        self._parser = EventsParser()

    def collect(self, url: str) -> list[CommonRecord]:
        raw = self._fetcher.fetch(url)
        return self._parser.parse(raw, url)
