"""
Support collector — ANUSA Student Assistance + approved ANU support pages.
Source: https://anusa.com.au/student-assistance/

Day 1: Scaffold only.
"""
from __future__ import annotations

from askanu_scraper.common.fetcher import BaseFetcher, HttpFetcher
from askanu_scraper.common.models import CommonRecord
from askanu_scraper.common.registry import assert_source_allowed
from askanu_scraper.sources.support.parser import SupportParser

SOURCE_ID = "support_anusa_student_assistance"


class SupportCollector:
    def __init__(self, fetcher: BaseFetcher | None = None) -> None:
        self._source = assert_source_allowed(SOURCE_ID)
        self._fetcher = fetcher or HttpFetcher()
        self._parser = SupportParser()

    def collect(self, url: str) -> list[CommonRecord]:
        raw = self._fetcher.fetch(url)
        return self._parser.parse(raw, url)
