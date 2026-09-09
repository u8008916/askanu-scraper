"""
Shared test fixtures for the askanu-scraper test suite.
"""
from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def courses_fixture_path() -> Path:
    return FIXTURES_DIR / "courses" / "comp1100_course_sample.html"


@pytest.fixture
def bacct_fixture_path() -> Path:
    return FIXTURES_DIR / "courses" / "bacct_program_sample.html"


@pytest.fixture
def catalogue_fixture_path() -> Path:
    return FIXTURES_DIR / "courses" / "catalogue_multi_entity_sample.html"


@pytest.fixture
def rich_course_fixture_path() -> Path:
    return FIXTURES_DIR / "courses" / "comp1110_rich_course_sample.html"


@pytest.fixture
def missing_course_fixture_path() -> Path:
    return FIXTURES_DIR / "courses" / "comp1110_missing_fields_sample.html"


@pytest.fixture
def malformed_course_fixture_path() -> Path:
    return FIXTURES_DIR / "courses" / "comp1110_malformed_optional_sample.html"


@pytest.fixture
def incompatibility_only_course_fixture_path() -> Path:
    return FIXTURES_DIR / "courses" / "comp1110_incompatibility_only_sample.html"


@pytest.fixture
def scholarships_fixture_path() -> Path:
    return FIXTURES_DIR / "scholarships" / "anu_humanitarian_scholarship_sample.html"


@pytest.fixture
def courses_fixture_html(courses_fixture_path: Path) -> str:
    return courses_fixture_path.read_text(encoding="utf-8")


@pytest.fixture
def bacct_fixture_html(bacct_fixture_path: Path) -> str:
    return bacct_fixture_path.read_text(encoding="utf-8")


@pytest.fixture
def scholarships_fixture_html(scholarships_fixture_path: Path) -> str:
    return scholarships_fixture_path.read_text(encoding="utf-8")
