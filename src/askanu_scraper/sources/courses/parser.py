"""
Courses parser — ANU Programs & Courses.
Courses and Programs parser — ANU Programs & Courses.

Day 1: Scaffold only. Full implementation in Day 2.
Source: https://programsandcourses.anu.edu.au/

Rules:
- Capture identifiers, academic year, title, career, units, delivery mode, and canonical URL.
- Capture sessions/offerings, prerequisites, incompatibilities, and assumed knowledge when present.
- Never invent missing fields; leave them None or empty.
- Generate deterministic content_hash (SHA-256) and stable record IDs.
"""
from __future__ import annotations

from askanu_scraper.common.models import CommonRecord
import re
from typing import Any
from bs4 import BeautifulSoup

from askanu_scraper.common.models import CommonRecord, Domain, IndexStatus, RecordStatus
from askanu_scraper.common.normalizer import (
    make_content_hash,
    make_record_id,
    normalize_text,
    normalize_url,
    now_canberra,
)
from askanu_scraper.common.parser import BaseParser, ParseError


class CoursesParser(BaseParser):
    """Parser for ANU Programs & Courses HTML pages."""
    """Parser for ANU Programs & Courses HTML pages (courses and programs)."""

    SOURCE_ID = "courses_programs_and_courses"

    def parse(self, raw_content: str, url: str) -> list[CommonRecord]:
        """
        Parse a Programs & Courses HTML page into CommonRecords.
        Parse raw HTML content into CommonRecord instances.
        Detects whether page is a Course or a Program and extracts accordingly.
        """
        if not raw_content or not raw_content.strip():
            return []


        # Day 2: Implement BeautifulSoup parsing here.
        # Do NOT invent fields not present in the HTML.
        try:
            soup = BeautifulSoup(raw_content, "html.parser")
        except Exception as exc:
            raise ParseError(f"Failed to parse HTML from {url}: {exc}") from exc

        # Determine entity type
        if soup.find("div", class_="course-detail") or "/course/" in url:
            record = self._parse_course(soup, url)
            return [record] if record else []
        elif soup.find("div", class_="program-detail") or "/program/" in url:
            record = self._parse_program(soup, url)
            return [record] if record else []

        # Fallback check based on tables or headers
        summary_table = soup.find("table", class_=re.compile(r"(course-data|program-data)"))
        if summary_table:
            if "course-data" in summary_table.get("class", []):
                record = self._parse_course(soup, url)
            else:
                record = self._parse_program(soup, url)
            return [record] if record else []

        return []

    def _extract_table_data(self, table: Any) -> dict[str, str]:
        """Helper to extract key-value pairs from standard summary tables."""
        data: dict[str, str] = {}
        if not table:
            return data

        for row in table.find_all("tr"):
            th = row.find("th")
            td = row.find("td")
            if th and td:
                key = normalize_text(th.get_text()) or ""
                val = normalize_text(td.get_text()) or ""
                if key:
                    data[key] = val
        return data

    def _extract_canonical_url(self, soup: BeautifulSoup, default_url: str) -> str:
        """Extract canonical URL from page or link tag, defaulting to fetch URL."""
        canonical_link = soup.find("link", rel="canonical")
        if canonical_link and canonical_link.get("href"):
            return normalize_url(canonical_link["href"]) or default_url

        canonical_div = soup.find("div", class_="canonical-url")
        if canonical_div:
            a_tag = canonical_div.find("a")
            if a_tag and a_tag.get("href"):
                return normalize_url(a_tag["href"]) or default_url

        return normalize_url(default_url) or default_url

    def _parse_course(self, soup: BeautifulSoup, url: str) -> CommonRecord | None:
        title_el = soup.find("h1", class_="intro-title") or soup.find("h1")
        raw_title = normalize_text(title_el.get_text()) if title_el else None
        if not raw_title:
            return None

        summary_data = self._extract_table_data(soup.find("table", class_="course-data"))

        course_code = summary_data.get("Course Code")
        academic_year = summary_data.get("Academic Year")
        career = summary_data.get("Career")
        units = summary_data.get("Units")
        delivery_mode = summary_data.get("Mode of Delivery")

        # If code not in summary, extract from title (e.g. 'COMP1100 Programming as Problem Solving')
        if not course_code:
            match = re.match(r"^([A-Z]{4}\d{4})\b", raw_title)
            if match:
                course_code = match.group(1)

        # Fallback year from URL
        if not academic_year:
            year_match = re.search(r"/(\d{4})/", url)
            if year_match:
                academic_year = year_match.group(1)

        entity_id = f"{course_code}_{academic_year}" if (course_code and academic_year) else (course_code or raw_title)
        record_id = make_record_id(Domain.COURSES.value, f"course:{entity_id}")
        canonical_url = self._extract_canonical_url(soup, url)

        # Description
        desc_el = soup.find("div", class_="course-description")
        description = None
        if desc_el:
            p_tag = desc_el.find("p")
            description = normalize_text(p_tag.get_text()) if p_tag else normalize_text(desc_el.get_text())

        # Requirements
        req_el = soup.find("div", class_="requirements")
        prerequisites = None
        incompatibilities = None
        assumed_knowledge = None

        if req_el:
            prereq_block = req_el.find("div", class_="prerequisites")
            if prereq_block:
                p = prereq_block.find("p")
                prerequisites = normalize_text(p.get_text()) if p else normalize_text(prereq_block.get_text())

            incomp_block = req_el.find("div", class_="incompatibilities")
            if incomp_block:
                p = incomp_block.find("p")
                incompatibilities = normalize_text(p.get_text()) if p else normalize_text(incomp_block.get_text())

            assumed_block = req_el.find("div", class_="assumed-knowledge")
            if assumed_block:
                p = assumed_block.find("p")
                assumed_knowledge = normalize_text(p.get_text()) if p else normalize_text(assumed_block.get_text())

        # Offerings
        offerings: list[dict[str, str]] = []
        offerings_table = soup.find("table", class_="offering-data")
        if offerings_table:
            for row in offerings_table.find_all("tr")[1:]:  # skip header
                cols = [normalize_text(td.get_text()) or "" for td in row.find_all("td")]
                if len(cols) >= 3:
                    offerings.append({
                        "session": cols[0],
                        "campus": cols[1],
                        "mode": cols[2],
                    })

        metadata: dict[str, Any] = {
            "entity_type": "course",
            "course_code": course_code,
            "academic_year": academic_year,
            "career": career,
            "units": units,
            "delivery_mode": delivery_mode,
            "prerequisites": prerequisites,
            "incompatibilities": incompatibilities,
            "assumed_knowledge": assumed_knowledge,
            "offerings": offerings,
        }

        # Build canonical text representation for embedding
        content_parts = [
            f"Title: {raw_title}",
            f"Course Code: {course_code}" if course_code else None,
            f"Academic Year: {academic_year}" if academic_year else None,
            f"Career: {career}" if career else None,
            f"Units: {units}" if units else None,
            f"Mode of Delivery: {delivery_mode}" if delivery_mode else None,
            f"Description: {description}" if description else None,
            f"Prerequisites: {prerequisites}" if prerequisites else None,
            f"Incompatibilities: {incompatibilities}" if incompatibilities else None,
            f"Assumed Knowledge: {assumed_knowledge}" if assumed_knowledge else None,
        ]
        if offerings:
            offerings_str = "; ".join(f"{o['session']} ({o['campus']}, {o['mode']})" for o in offerings)
            content_parts.append(f"Offerings: {offerings_str}")

        content = "\n".join([p for p in content_parts if p is not None])
        content_hash = make_content_hash(content)

        return CommonRecord(
            record_id=record_id,
            source_id=self.SOURCE_ID,
            entity_id=entity_id,
            domain=Domain.COURSES,
            title=raw_title,
            content=content,
            canonical_url=canonical_url,
            status=RecordStatus.NEW,
            collected_at=now_canberra(),
            last_seen_at=now_canberra(),
            content_hash=content_hash,
            index_status=IndexStatus.PENDING,
            metadata_json=metadata,
        )

    def _parse_program(self, soup: BeautifulSoup, url: str) -> CommonRecord | None:
        title_el = soup.find("h1", class_="intro-title") or soup.find("h1")
        raw_title = normalize_text(title_el.get_text()) if title_el else None
        if not raw_title:
            return None

        summary_data = self._extract_table_data(soup.find("table", class_="program-data"))

        program_code = summary_data.get("Program Code")
        academic_year = summary_data.get("Academic Year")
        career = summary_data.get("Career")
        units = summary_data.get("Units")
        duration = summary_data.get("Duration")
        delivery_mode = summary_data.get("Mode of Delivery")

        # Fallback year from URL
        if not academic_year:
            year_match = re.search(r"/(\d{4})/", url)
            if year_match:
                academic_year = year_match.group(1)

        entity_id = f"{program_code}_{academic_year}" if (program_code and academic_year) else (program_code or raw_title)
        record_id = make_record_id(Domain.COURSES.value, f"program:{entity_id}")
        canonical_url = self._extract_canonical_url(soup, url)

        # Overview
        desc_el = soup.find("div", class_="program-description")
        overview = None
        if desc_el:
            p_tag = desc_el.find("p")
            overview = normalize_text(p_tag.get_text()) if p_tag else normalize_text(desc_el.get_text())

        # Learning outcomes
        outcomes_el = soup.find("div", class_="learning-outcomes")
        outcomes: list[str] = []
        if outcomes_el:
            for li in outcomes_el.find_all("li"):
                item = normalize_text(li.get_text())
                if item:
                    outcomes.append(item)

        metadata: dict[str, Any] = {
            "entity_type": "program",
            "program_code": program_code,
            "academic_year": academic_year,
            "career": career,
            "units": units,
            "duration": duration,
            "delivery_mode": delivery_mode,
            "learning_outcomes": outcomes,
        }

        # Build canonical text representation for embedding
        content_parts = [
            f"Title: {raw_title}",
            f"Program Code: {program_code}" if program_code else None,
            f"Academic Year: {academic_year}" if academic_year else None,
            f"Career: {career}" if career else None,
            f"Units: {units}" if units else None,
            f"Duration: {duration}" if duration else None,
            f"Mode of Delivery: {delivery_mode}" if delivery_mode else None,
            f"Overview: {overview}" if overview else None,
        ]
        if outcomes:
            content_parts.append("Learning Outcomes: " + "; ".join(outcomes))

        content = "\n".join([p for p in content_parts if p is not None])
        content_hash = make_content_hash(content)

        return CommonRecord(
            record_id=record_id,
            source_id=self.SOURCE_ID,
            entity_id=entity_id,
            domain=Domain.COURSES,
            title=raw_title,
            content=content,
            canonical_url=canonical_url,
            status=RecordStatus.NEW,
            collected_at=now_canberra(),
            last_seen_at=now_canberra(),
            content_hash=content_hash,
            index_status=IndexStatus.PENDING,
            metadata_json=metadata,
        )
