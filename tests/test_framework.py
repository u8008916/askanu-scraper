"""
Tests for the common scraper framework: fetcher, parser, normalizer.

Key invariants:
- MockFetcher replays local fixtures without network requests.
- MockFetcher raises FetchError for unmapped URLs (simulates real failure).
- BaseParser.safe_parse() returns empty list on ParseError (last-known-good).
- Normalizer functions are deterministic and timezone-aware.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from askanu_scraper.common.fetcher import FetchError, MockFetcher
from askanu_scraper.common.models import CommonRecord, Domain
from askanu_scraper.common.normalizer import (
    CANBERRA_TZ,
    make_content_hash,
    make_record_id,
    normalize_text,
    normalize_url,
    now_canberra,
    parse_date_safe,
    to_canberra,
)
from askanu_scraper.common.parser import BaseParser, ParseError


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# ---------------------------------------------------------------------------
# MockFetcher
# ---------------------------------------------------------------------------

class TestMockFetcher:
    def test_returns_fixture_content_for_mapped_url(
        self, courses_fixture_path: Path
    ) -> None:
        url = "https://programsandcourses.anu.edu.au/2026/course/COMP1100"
        fetcher = MockFetcher({url: courses_fixture_path})
        content = fetcher.fetch(url)
        assert "COMP1100" in content
        assert "Programming as Problem Solving" in content

    def test_raises_fetch_error_for_unmapped_url(
        self, courses_fixture_path: Path
    ) -> None:
        url = "https://programsandcourses.anu.edu.au/2026/course/COMP1100"
        fetcher = MockFetcher({url: courses_fixture_path})
        with pytest.raises(FetchError):
            fetcher.fetch("https://some-unknown.example.com/page")

    def test_raises_fetch_error_for_missing_fixture_file(self) -> None:
        fetcher = MockFetcher(
            {"https://example.com": Path("fixtures/does_not_exist.html")}
        )
        with pytest.raises(FetchError):
            fetcher.fetch("https://example.com")

    def test_courses_fixture_file_exists(self, courses_fixture_path: Path) -> None:
        assert courses_fixture_path.exists()

    def test_scholarships_fixture_file_exists(
        self, scholarships_fixture_path: Path
    ) -> None:
        assert scholarships_fixture_path.exists()


# ---------------------------------------------------------------------------
# BaseParser safe_parse
# ---------------------------------------------------------------------------

class _AlwaysFailParser(BaseParser):
    """Test double: always raises ParseError."""

    def parse(self, raw_content: str, url: str) -> list[CommonRecord]:
        raise ParseError("Simulated parser failure")


class _SucceedParser(BaseParser):
    """Test double: returns a fixed list of records."""

    def __init__(self, records: list[CommonRecord]) -> None:
        self._records = records

    def parse(self, raw_content: str, url: str) -> list[CommonRecord]:
        return self._records


class TestBaseParserSafeParse:
    def test_safe_parse_returns_empty_on_parse_error(self) -> None:
        """
        safe_parse must return empty list on ParseError so the caller
        can preserve last-known-good data rather than wiping the index.
        """
        parser = _AlwaysFailParser()
        result = parser.safe_parse("<html>bad</html>", "https://example.com")
        assert result == []

    def test_safe_parse_returns_records_on_success(self) -> None:
        content = "test"
        record = CommonRecord(
            record_id="courses:TEST",
            source_id="courses_programs_and_courses",
            entity_id="TEST",
            domain=Domain.COURSES,
            title="Test Course",
            content=content,
            canonical_url="https://example.com/course/TEST",
            content_hash=make_content_hash(content),
        )
        parser = _SucceedParser([record])
        result = parser.safe_parse("<html>good</html>", "https://example.com")
        assert len(result) == 1
        assert result[0].entity_id == "TEST"

    def test_parse_raises_on_parse_error(self) -> None:
        """parse() itself propagates ParseError for tests."""
        parser = _AlwaysFailParser()
        with pytest.raises(ParseError):
            parser.parse("<html>bad</html>", "https://example.com")


# ---------------------------------------------------------------------------
# Normalizer — text
# ---------------------------------------------------------------------------

class TestNormalizeText:
    def test_strips_whitespace(self) -> None:
        assert normalize_text("  hello world  ") == "hello world"

    def test_collapses_internal_whitespace(self) -> None:
        assert normalize_text("hello\t\n  world") == "hello world"

    def test_returns_none_for_none(self) -> None:
        assert normalize_text(None) is None

    def test_unicode_normalization_nfc(self) -> None:
        # NFD decomposed 'é' -> NFC composed 'é'
        nfd = "e\u0301"  # e + combining acute accent
        result = normalize_text(nfd)
        assert result == "\xe9"


# ---------------------------------------------------------------------------
# Normalizer — URL
# ---------------------------------------------------------------------------

class TestNormalizeUrl:
    def test_strips_trailing_slash(self) -> None:
        assert normalize_url("https://example.com/page/") == "https://example.com/page"

    def test_strips_whitespace(self) -> None:
        assert normalize_url("  https://example.com  ") == "https://example.com"

    def test_returns_none_for_empty(self) -> None:
        assert normalize_url("") is None

    def test_returns_none_for_none(self) -> None:
        assert normalize_url(None) is None


# ---------------------------------------------------------------------------
# Normalizer — dates
# ---------------------------------------------------------------------------

class TestParseDateSafe:
    def test_parses_iso_date(self) -> None:
        dt = parse_date_safe("2026-10-31")
        assert dt is not None
        assert dt.tzinfo == CANBERRA_TZ
        assert dt.year == 2026
        assert dt.month == 10
        assert dt.day == 31

    def test_parses_day_month_year(self) -> None:
        dt = parse_date_safe("31/10/2026")
        assert dt is not None
        assert dt.year == 2026

    def test_returns_none_for_none(self) -> None:
        assert parse_date_safe(None) is None

    def test_returns_none_for_empty_string(self) -> None:
        assert parse_date_safe("") is None

    def test_returns_none_for_unparseable(self) -> None:
        assert parse_date_safe("Not a date at all") is None


class TestNowCanberra:
    def test_now_canberra_is_aware(self) -> None:
        now = now_canberra()
        assert now.tzinfo is not None

    def test_now_canberra_timezone(self) -> None:
        now = now_canberra()
        assert now.tzinfo == CANBERRA_TZ


# ---------------------------------------------------------------------------
# End-to-end: MockFetcher + courses parser scaffold
# ---------------------------------------------------------------------------

class TestCoursesParserScaffold:
    """
    Verify the Day 1 scaffold: fixture loads, no crash, returns empty list.
    Full parsing implemented in Day 2.
    """

    def test_courses_parser_returns_list(
        self, courses_fixture_path: Path
    ) -> None:
        from askanu_scraper.sources.courses.parser import CoursesParser

        url = "https://programsandcourses.anu.edu.au/2026/course/COMP1100"
        fetcher = MockFetcher({url: courses_fixture_path})
        parser = CoursesParser()
        raw = fetcher.fetch(url)
        result = parser.parse(raw, url)
        assert isinstance(result, list)

    def test_scholarships_parser_returns_list(
        self, scholarships_fixture_path: Path
    ) -> None:
        from askanu_scraper.sources.scholarships.parser import ScholarshipsParser

        url = "https://study.anu.edu.au/scholarships/find-scholarship/anu-humanitarian-scholarship"
        fetcher = MockFetcher({url: scholarships_fixture_path})
        parser = ScholarshipsParser()
        raw = fetcher.fetch(url)
        result = parser.parse(raw, url)
        assert isinstance(result, list)

    def test_reruns_scaffold_produce_identical_results(
        self, courses_fixture_path: Path
    ) -> None:
        """Re-parsing the same fixture twice produces identical IDs, hash, and content."""
        from askanu_scraper.sources.courses.parser import CoursesParser

        url = "https://programsandcourses.anu.edu.au/2026/course/COMP1100"
        fetcher = MockFetcher({url: courses_fixture_path})
        parser = CoursesParser()
        raw = fetcher.fetch(url)
        rec1 = parser.parse(raw, url)[0]
        rec2 = parser.parse(raw, url)[0]
        assert rec1.record_id == rec2.record_id
        assert rec1.entity_id == rec2.entity_id
        assert rec1.content_hash == rec2.content_hash
        assert rec1.content == rec2.content
