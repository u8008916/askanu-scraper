"""
Accommodation collector — ANU Study accommodation pages.
Source: https://study.anu.edu.au/accommodation

Day 1: Scaffold only.
"""
from __future__ import annotations

from askanu_scraper.common.fetcher import BaseFetcher, HttpFetcher
from askanu_scraper.common.models import CommonRecord
from askanu_scraper.common.registry import assert_source_allowed
from askanu_scraper.sources.accommodation.parser import AccommodationParser

SOURCE_ID = "accommodation_anu_study"


class AccommodationCollector:
    def __init__(self, fetcher: BaseFetcher | None = None) -> None:
        self._source = assert_source_allowed(SOURCE_ID)
        self._fetcher = fetcher or HttpFetcher()
        self._parser = AccommodationParser()

    def collect(self, url: str) -> list[CommonRecord]:
        raw = self._fetcher.fetch(url)
        return self._parser.parse(raw, url)
