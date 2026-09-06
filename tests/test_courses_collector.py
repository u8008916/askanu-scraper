"""
Tests for CoursesCollector and LocalDataStore handoff (Day 3 requirements).

Verifies:
- Fetch and parse of an approved single course record.
- IngestionRun metadata and record generation.
- Idempotency: second run records unchanged record count.
- Changed content detection: modifying fixture content updates record_changed count and content_hash.
- Fetch failure handling: preserves last-known-good data and records IngestionRunStatus.FAILED.
- Source URL approval guard: rejecting unapproved URL roots.
"""
from __future__ import annotations

from pathlib import Path
import pytest

from askanu_scraper.common.fetcher import MockFetcher
from askanu_scraper.common.models import IngestionRunStatus, RecordStatus
from askanu_scraper.common.storage import LocalDataStore
from askanu_scraper.sources.courses.collector import CoursesCollector


class TestCoursesCollector:
    def test_single_record_success_new_record(
        self, tmp_path: Path, courses_fixture_path: Path
    ) -> None:
        url = "https://programsandcourses.anu.edu.au/2026/course/COMP1100"
        fetcher = MockFetcher({url: courses_fixture_path})
        store = LocalDataStore(base_dir=tmp_path)
        collector = CoursesCollector(fetcher=fetcher, store=store)

        run, records = collector.run_single(url)

        assert run.status == IngestionRunStatus.SUCCESS
        assert run.records_seen == 1
        assert run.records_added == 1
        assert run.records_changed == 0
        assert run.records_unchanged == 0
        assert len(records) == 1

        rec = records[0]
        assert rec.entity_id == "COMP1100_2026"

        # Verify stored on disk
        stored = store.get_record(rec.record_id)
        assert stored is not None
        assert stored.content_hash == rec.content_hash

    def test_idempotent_rerun_marks_unchanged(
        self, tmp_path: Path, courses_fixture_path: Path
    ) -> None:
        url = "https://programsandcourses.anu.edu.au/2026/course/COMP1100"
        fetcher = MockFetcher({url: courses_fixture_path})
        store = LocalDataStore(base_dir=tmp_path)
        collector = CoursesCollector(fetcher=fetcher, store=store)

        # First run -> NEW
        run1, recs1 = collector.run_single(url)
        assert run1.records_added == 1

        # Second run -> UNCHANGED
        run2, recs2 = collector.run_single(url)
        assert run2.status == IngestionRunStatus.SUCCESS
        assert run2.records_seen == 1
        assert run2.records_added == 0
        assert run2.records_changed == 0
        assert run2.records_unchanged == 1
        assert recs2[0].content_hash == recs1[0].content_hash

    def test_changed_content_detection(
        self, tmp_path: Path, courses_fixture_path: Path
    ) -> None:
        url = "https://programsandcourses.anu.edu.au/2026/course/COMP1100"
        orig_html = courses_fixture_path.read_text(encoding="utf-8")
        modified_html = orig_html.replace(
            "Basic mathematics at Year 10 level.",
            "Advanced calculus and discrete mathematics.",
        )

        file1 = tmp_path / "comp1100_v1.html"
        file2 = tmp_path / "comp1100_v2.html"
        file1.write_text(orig_html, encoding="utf-8")
        file2.write_text(modified_html, encoding="utf-8")

        store = LocalDataStore(base_dir=tmp_path / "store")

        # Run 1: with v1
        fetcher1 = MockFetcher({url: file1})
        collector1 = CoursesCollector(fetcher=fetcher1, store=store)
        run1, recs1 = collector1.run_single(url)
        assert run1.records_added == 1

        # Run 2: with modified content
        fetcher2 = MockFetcher({url: file2})
        collector2 = CoursesCollector(fetcher=fetcher2, store=store)
        run2, recs2 = collector2.run_single(url)
        assert run2.status == IngestionRunStatus.SUCCESS
        assert run2.records_added == 0
        assert run2.records_changed == 1
        assert run2.records_unchanged == 0
        assert recs2[0].content_hash != recs1[0].content_hash

    def test_fetch_failure_preserves_last_known_good(
        self, tmp_path: Path, courses_fixture_path: Path
    ) -> None:
        url = "https://programsandcourses.anu.edu.au/2026/course/COMP1100"
        store = LocalDataStore(base_dir=tmp_path / "store")

        # Initial successful run
        fetcher_ok = MockFetcher({url: courses_fixture_path})
        collector_ok = CoursesCollector(fetcher=fetcher_ok, store=store)
        run_ok, recs_ok = collector_ok.run_single(url)
        assert run_ok.status == IngestionRunStatus.SUCCESS

        # Subsequent failed run (e.g. 404 or network timeout)
        fetcher_fail = MockFetcher({})  # empty mapping triggers FetchError
        collector_fail = CoursesCollector(fetcher=fetcher_fail, store=store)
        run_fail, recs_fail = collector_fail.run_single(url)

        assert run_fail.status == IngestionRunStatus.FAILED
        assert "Fetch failed" in run_fail.error
        assert recs_fail == []

        # Verify existing record in store survived without being wiped
        existing = store.get_record("courses:course:COMP1100_2026")
        assert existing is not None
        assert existing.content_hash == recs_ok[0].content_hash

    def test_unapproved_url_rejected(self, tmp_path: Path) -> None:
        unapproved_url = "https://unapproved-anu-site.com/course/COMP1100"
        store = LocalDataStore(base_dir=tmp_path)
        collector = CoursesCollector(store=store)

        run, recs = collector.run_single(unapproved_url)
        assert run.status == IngestionRunStatus.FAILED
        assert "does not belong to approved canonical root" in run.error
        assert recs == []

    def test_missing_academic_year_is_rejected(self, tmp_path: Path) -> None:
        url = "https://programsandcourses.anu.edu.au/course/ENGN1200"

        html = """
        <div class="course-detail">
            <h1 class="intro-title">ENGN1200 Introduction to Engineering</h1>
            <table class="course-data">
                <tr><th>Course Code</th><td>ENGN1200</td></tr>
            </table>
            <div class="canonical-url">
                <a href="https://programsandcourses.anu.edu.au/course/ENGN1200">
                    https://programsandcourses.anu.edu.au/course/ENGN1200
                </a>
            </div>
        </div>
        """

        fixture = tmp_path / "engn1200_no_year.html"
        fixture.write_text(html, encoding="utf-8")

        fetcher = MockFetcher({url: fixture})
        store = LocalDataStore(base_dir=tmp_path / "store")
        collector = CoursesCollector(fetcher=fetcher, store=store)

        run, records = collector.run_single(url)

        assert run.status == IngestionRunStatus.FAILED
        assert "schema-v1" in run.error
        assert records == []
        assert store.get_record("courses:course:ENGN1200") is None

    def test_missing_course_code_is_rejected(self, tmp_path: Path) -> None:
        url = "https://programsandcourses.anu.edu.au/2026/course/not-a-code"

        html = """
        <div class="course-detail">
            <h1 class="intro-title">Generic Course Page</h1>
            <table class="course-data">
                <tr><th>Academic Year</th><td>2026</td></tr>
            </table>
        </div>
        """

        fixture = tmp_path / "missing_code.html"
        fixture.write_text(html, encoding="utf-8")

        fetcher = MockFetcher({url: fixture})
        store = LocalDataStore(base_dir=tmp_path / "store")
        collector = CoursesCollector(fetcher=fetcher, store=store)

        run, records = collector.run_single(url)

        assert run.status == IngestionRunStatus.FAILED
        assert "schema-v1" in run.error
        assert records == []

    def test_invalid_academic_year_is_rejected(self, tmp_path: Path) -> None:
        url = "https://programsandcourses.anu.edu.au/course/COMP1100"

        html = """
        <div class="course-detail">
            <h1 class="intro-title">COMP1100 Programming as Problem Solving</h1>
            <table class="course-data">
                <tr><th>Course Code</th><td>COMP1100</td></tr>
                <tr><th>Academic Year</th><td>20XX</td></tr>
            </table>
        </div>
        """

        fixture = tmp_path / "invalid_year.html"
        fixture.write_text(html, encoding="utf-8")

        fetcher = MockFetcher({url: fixture})
        store = LocalDataStore(base_dir=tmp_path / "store")
        collector = CoursesCollector(fetcher=fetcher, store=store)

        run, records = collector.run_single(url)

        assert run.status == IngestionRunStatus.FAILED
        assert "schema-v1" in run.error
        assert records == []
