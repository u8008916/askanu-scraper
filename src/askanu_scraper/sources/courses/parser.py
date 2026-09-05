"""
Courses parser — ANU Programs & Courses.

Day 1: Scaffold only. Full implementation in Day 2.
Source: https://programsandcourses.anu.edu.au/
"""
from __future__ import annotations

from askanu_scraper.common.models import CommonRecord
from askanu_scraper.common.parser import BaseParser, ParseError


class CoursesParser(BaseParser):
    """Parser for ANU Programs & Courses HTML pages."""

    SOURCE_ID = "courses_programs_and_courses"

    def parse(self, raw_content: str, url: str) -> list[CommonRecord]:
        """
        Parse a Programs & Courses HTML page into CommonRecords.

        Day 1: Returns empty list — full field extraction implemented in Day 2.
        Must capture: identifier, academic year, title, career, units,
        delivery mode, canonical URL, prerequisites/requirements where present.
        """
        # Day 2: Implement BeautifulSoup parsing here.
        # Do NOT invent fields not present in the HTML.
        return []
