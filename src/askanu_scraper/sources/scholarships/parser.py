"""
Scholarships parser — ANU Scholarship Finder.

Day 1: Scaffold only. Full implementation in Day 9.
Must collect: featured flag, status, application requirement,
study stage/type/level/area, value, selection basis, dates,
eligibility and canonical URL.
Do NOT invent missing deadlines — preserve as None (unknown).
"""
from __future__ import annotations

from askanu_scraper.common.models import CommonRecord
from askanu_scraper.common.parser import BaseParser


class ScholarshipsParser(BaseParser):
    SOURCE_ID = "scholarships_anu_finder"

    def parse(self, raw_content: str, url: str) -> list[CommonRecord]:
        # Day 9: Implement BeautifulSoup parsing here.
        return []
