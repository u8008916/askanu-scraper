"""
Jobs parser — ANU Jobs Search.

Day 1: Scaffold only. Full implementation in Day 10.
Must collect: title, category, employment type, location, classification,
closing date (Canberra-aware), summary and canonical URL.
Never invent status — derive only from explicit source data.
"""
from __future__ import annotations

from askanu_scraper.common.models import CommonRecord
from askanu_scraper.common.parser import BaseParser


class JobsParser(BaseParser):
    SOURCE_ID = "jobs_anu_search"

    def parse(self, raw_content: str, url: str) -> list[CommonRecord]:
        # Day 10: Implement BeautifulSoup parsing here.
        return []
