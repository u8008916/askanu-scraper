"""Courses collector — fetches ANU Programs & Courses pages."""
from __future__ import annotations

from askanu_scraper.common.fetcher import BaseFetcher, HttpFetcher
from askanu_scraper.common.models import CommonRecord
from askanu_scraper.common.registry import assert_source_allowed
from askanu_scraper.sources.courses.parser import CoursesParser

SOURCE_ID = "courses_programs_and_courses"


class CoursesCollector:
    """
    Collector for ANU Programs & Courses.

    Day 1: Scaffold only — discovery and bulk ingestion are NOT implemented.
    The collector calls assert_source_allowed() before any fetch to enforce
    the approved source registry.

    Day 2 will implement parser for core identifiers, academic year, title,
    career/units/delivery and canonical URL.
    """

    def __init__(self, fetcher: BaseFetcher | None = None) -> None:
        # Enforce registry approval on construction
        self._source = assert_source_allowed(SOURCE_ID)
        self._fetcher = fetcher or HttpFetcher()
        self._parser = CoursesParser()

    def collect(self, url: str) -> list[CommonRecord]:
        """Fetch *url* and return parsed CommonRecords. No mass crawling."""
        raw = self._fetcher.fetch(url)
        return self._parser.parse(raw, url)
