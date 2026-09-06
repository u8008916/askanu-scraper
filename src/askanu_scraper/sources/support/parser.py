"""
Support parser — ANUSA Student Assistance.

Day 1: Scaffold only. Full implementation in Day 11.
Must collect: categories, service descriptions, contact/action URLs,
and only EXPLICIT hours (never infer).
"""
from __future__ import annotations

from askanu_scraper.common.models import CommonRecord
from askanu_scraper.common.parser import BaseParser


class SupportParser(BaseParser):
    SOURCE_ID = "support_anusa_student_assistance"

    def parse(self, raw_content: str, url: str) -> list[CommonRecord]:
        # Day 11: Implement BeautifulSoup parsing here.
        return []
