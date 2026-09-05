"""
Events parser — Official ANU Events / calendar.

Day 1: Scaffold only. Full implementation in Day 12.
Must collect: event ID, title, start/end datetime, venue, organiser,
description, and canonical URL.
"""
from __future__ import annotations

from askanu_scraper.common.models import CommonRecord
from askanu_scraper.common.parser import BaseParser


class EventsParser(BaseParser):
    SOURCE_ID = "events_anu_official"

    def parse(self, raw_content: str, url: str) -> list[CommonRecord]:
        # Day 12: Implement BeautifulSoup parsing here.
        return []
