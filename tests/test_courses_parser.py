"""
Tests for the ANU Programs & Courses parser (CoursesParser).

Verifies:
- Parsing of course pages (e.g. COMP1100).
- Parsing of program pages (e.g. BACCT).
- Extraction of required identifiers, academic year, title, career, units, delivery mode, canonical URL.
- Extraction of prerequisites, incompatibilities, assumed knowledge, and offerings when present.
- Stable ID generation and deterministic content_hash (SHA-256).
- Idempotency: re-parsing the exact same HTML fixture produces identical records and hashes.
- Preservation of missing fields (no invented fields).
"""
from __future__ import annotations

from pathlib import Path
import pytest

from askanu_scraper.common.fetcher import MockFetcher
from askanu_scraper.common.models import Domain, IndexStatus, RecordStatus
from askanu_scraper.sources.courses.parser import CoursesParser


class TestCoursesParser:
    def test_parse_comp1100_course(self, courses_fixture_path: Path) -> None:
        url = "https://programsandcourses.anu.edu.au/2026/course/COMP1100"
        fetcher = MockFetcher({url: courses_fixture_path})
        parser = CoursesParser()

        raw_html = fetcher.fetch(url)
        records = parser.parse(raw_html, url)

        assert len(records) == 1
        rec = records[0]

        # Basic identity & schema
        assert rec.domain == Domain.COURSES
        assert rec.source_id == "courses_programs_and_courses"
        assert rec.entity_id == "COMP1100_2026"
        assert rec.record_id == "courses:course:COMP1100_2026"
        assert rec.title == "COMP1100 Programming as Problem Solving"
        assert rec.canonical_url == "https://programsandcourses.anu.edu.au/2026/course/COMP1100"
        assert rec.status == RecordStatus.NEW
        assert rec.index_status == IndexStatus.PENDING

        # Metadata
        meta = rec.metadata_json
        assert meta["entity_type"] == "course"
        assert meta["course_code"] == "COMP1100"
        assert meta["academic_year"] == "2026"
        assert meta["career"] == "Undergraduate"
        assert meta["units"] == "6"
        assert meta["delivery_mode"] == "In Person"
        assert meta["incompatibilities"] == "COMP1130"
        assert meta["assumed_knowledge"] == "Basic mathematics at Year 10 level."
        assert meta["prerequisites"] is None

        # Offerings
        assert len(meta["offerings"]) == 2
        assert meta["offerings"][0]["session"] == "Semester 1, 2026"
        assert meta["offerings"][1]["session"] == "Semester 2, 2026"

        # Content and Hash
        assert "Programming as Problem Solving" in rec.content
        assert "COMP1100" in rec.content
        assert len(rec.content_hash) == 64

    def test_parse_bacct_program(self, bacct_fixture_path: Path) -> None:
        url = "https://programsandcourses.anu.edu.au/2026/program/BACCT"
        fetcher = MockFetcher({url: bacct_fixture_path})
        parser = CoursesParser()

        raw_html = fetcher.fetch(url)
        records = parser.parse(raw_html, url)

        assert len(records) == 1
        rec = records[0]

        # Basic identity & schema
        assert rec.domain == Domain.COURSES
        assert rec.source_id == "courses_programs_and_courses"
        assert rec.entity_id == "BACCT_2026"
        assert rec.record_id == "courses:program:BACCT_2026"
        assert rec.title == "Bachelor of Accounting"
        assert rec.canonical_url == "https://programsandcourses.anu.edu.au/2026/program/BACCT"

        # Metadata
        meta = rec.metadata_json
        assert meta["entity_type"] == "program"
        assert meta["program_code"] == "BACCT"
        assert meta["academic_year"] == "2026"
        assert meta["career"] == "Undergraduate"
        assert meta["units"] == "144"
        assert meta["duration"] == "3 years full-time"
        assert meta["delivery_mode"] == "In Person"
        assert len(meta["learning_outcomes"]) == 3
        assert "financial theories" in meta["learning_outcomes"][0]

        # Content and Hash
        assert "Bachelor of Accounting" in rec.content
        assert len(rec.content_hash) == 64

    def test_idempotency_same_hash_and_ids(self, courses_fixture_path: Path) -> None:
        url = "https://programsandcourses.anu.edu.au/2026/course/COMP1100"
        fetcher = MockFetcher({url: courses_fixture_path})
        parser = CoursesParser()

        raw_html = fetcher.fetch(url)
        run1 = parser.parse(raw_html, url)[0]
        run2 = parser.parse(raw_html, url)[0]

        assert run1.record_id == run2.record_id
        assert run1.entity_id == run2.entity_id
        assert run1.content_hash == run2.content_hash
        assert run1.content == run2.content

    def test_no_invented_fields_on_sparse_html(self) -> None:
        sparse_html = """
        <div class="course-detail">
            <h1 class="intro-title">ENGN1200 Introduction to Engineering</h1>
            <table class="course-data">
                <tr><th>Course Code</th><td>ENGN1200</td></tr>
                <tr><th>Academic Year</th><td>2026</td></tr>
            </table>
        </div>
        """
        parser = CoursesParser()
        records = parser.parse(sparse_html, "https://programsandcourses.anu.edu.au/2026/course/ENGN1200")
        assert len(records) == 1
        rec = records[0]

        meta = rec.metadata_json
        assert meta["course_code"] == "ENGN1200"
        assert meta["academic_year"] == "2026"
        assert meta["career"] is None
        assert meta["units"] is None
        assert meta["delivery_mode"] is None
        assert meta["prerequisites"] is None
        assert meta["incompatibilities"] is None
        assert meta["assumed_knowledge"] is None
        assert meta["offerings"] is None

    def test_course_code_with_trailing_letter_is_supported(self) -> None:
        html = """
        <div class="course-detail">
            <h1 class="intro-title">Advanced Biology</h1>
            <table class="course-data">
                <tr><th>Academic Year</th><td>2026</td></tr>
            </table>
        </div>
        """

        parser = CoursesParser()
        records = parser.parse(
            html,
            "https://programsandcourses.anu.edu.au/2026/course/BIOL9001P",
        )

        assert len(records) == 1
        rec = records[0]
        assert rec.metadata_json["course_code"] == "BIOL9001P"
        assert rec.entity_id == "BIOL9001P_2026"
        assert rec.record_id == "courses:course:BIOL9001P_2026"

    def test_present_but_empty_optional_field_becomes_none(self) -> None:
        html = """
        <div class="course-detail">
            <h1 class="intro-title">COMP1100 Programming as Problem Solving</h1>
            <table class="course-data">
                <tr><th>Course Code</th><td>COMP1100</td></tr>
                <tr><th>Academic Year</th><td>2026</td></tr>
                <tr><th>Career</th><td></td></tr>
                <tr><th>Units</th><td>   </td></tr>
                <tr><th>Mode of Delivery</th><td></td></tr>
            </table>
        </div>
        """

        parser = CoursesParser()
        records = parser.parse(
            html,
            "https://programsandcourses.anu.edu.au/2026/course/COMP1100",
        )

        assert len(records) == 1

        metadata = records[0].metadata_json
        assert metadata["career"] is None
        assert metadata["units"] is None
        assert metadata["delivery_mode"] is None

    def test_empty_offerings_section_becomes_none(self) -> None:
        html = """
        <div class="course-detail">
            <h1 class="intro-title">COMP1100 Programming as Problem Solving</h1>
            <table class="course-data">
                <tr><th>Course Code</th><td>COMP1100</td></tr>
                <tr><th>Academic Year</th><td>2026</td></tr>
            </table>
            <table class="offering-data">
                <tr>
                    <th>Session</th>
                    <th>Campus</th>
                    <th>Mode</th>
                </tr>
            </table>
        </div>
        """

        parser = CoursesParser()
        record = parser.parse(
            html,
            "https://programsandcourses.anu.edu.au/2026/course/COMP1100",
        )[0]

        assert record.metadata_json["offerings"] is None

    def test_empty_learning_outcomes_section_becomes_none(self) -> None:
        html = """
        <div class="program-detail">
            <h1 class="intro-title">Bachelor of Accounting</h1>
            <table class="program-data">
                <tr><th>Program Code</th><td>BACCT</td></tr>
                <tr><th>Academic Year</th><td>2026</td></tr>
            </table>
            <div class="learning-outcomes"></div>
        </div>
        """

        parser = CoursesParser()
        record = parser.parse(
            html,
            "https://programsandcourses.anu.edu.au/2026/program/BACCT",
        )[0]

        assert record.metadata_json["learning_outcomes"] is None
