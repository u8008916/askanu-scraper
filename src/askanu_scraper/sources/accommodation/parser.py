"""
Accommodation parser — ANU Study accommodation.

Day 1: Scaffold only. Full implementation in Day 11.
Must collect: residence name, catering/resident type, advertised rate text,
description, application status/year, and canonical page URL.
Do NOT scrape authenticated StarRez application content.
Never infer vacancy or hours — preserve source wording for sensitive fields.
"""
from __future__ import annotations

from askanu_scraper.common.models import CommonRecord
from askanu_scraper.common.parser import BaseParser


class AccommodationParser(BaseParser):
    SOURCE_ID = "accommodation_anu_study"

    def parse(self, raw_content: str, url: str) -> list[CommonRecord]:
        # Day 11: Implement BeautifulSoup parsing here.
        return []
