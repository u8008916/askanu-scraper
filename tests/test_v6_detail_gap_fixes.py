"""Regression tests for gaps quantified by the first full V6 detail audit."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from askanu_scraper import detail_coverage
from askanu_scraper.common.parser import ParseError
from askanu_scraper.common.fetcher import BaseFetcher, FetchError, HttpFetcher
from askanu_scraper.detail_coverage import DetailCandidate, DetailCoverageAuditor
from askanu_scraper.sources.courses.parser import CoursesParser
from askanu_scraper.sources.jobs.discovery import JobsDiscovery
from askanu_scraper.sources.jobs.parser import JobsParser
from askanu_scraper.sources.scholarships.parser import ScholarshipsParser


def test_course_requisite_variants_preserve_source_backed_evidence() -> None:
    html = """
    <h1>Advanced Accounting</h1>
    <h2>Requisite and Incompatibility</h2>
    <p>To enrol in this course you must be studying a Master of Accounting,
    and have completed BUSN7008. To enrol in this course, students in the
    Master of Applied Accounting must be studying or have completed BUSN7008.
    This course is incompatible with BUSN3051 and BUSN7051.</p>
    """
    record = CoursesParser().parse(
        html,
        "https://programsandcourses.anu.edu.au/2026/course/busn6051",
    )[0]

    assert "Master of Accounting" in record.metadata_json["prerequisites"]
    assert record.metadata_json["incompatibilities"] == "BUSN3051 and BUSN7051"


def test_course_incompatible_colon_variant_is_captured() -> None:
    html = """
    <h1>Advanced Mathematics</h1>
    <h2>Requisite and Incompatibility</h2>
    <p>To enrol in this course you must have completed MATH1116.
    Incompatible: MATH3104 and MATH6118</p>
    """
    record = CoursesParser().parse(
        html,
        "https://programsandcourses.anu.edu.au/2026/course/math2322",
    )[0]

    assert record.metadata_json["incompatibilities"] == "MATH3104 and MATH6118"


def test_concurrent_requisite_is_preserved_in_content_without_schema_change() -> None:
    html = """
    <h1>Actuarial Studies</h1>
    <h2>Requisite and Incompatibility</h2>
    <p>To enrol in this course you must have completed or be concurrently
    enrolled in STAT3038.</p>
    """
    record = CoursesParser().parse(
        html,
        "https://programsandcourses.anu.edu.au/2026/course/acst3032",
    )[0]

    assert "concurrently enrolled in STAT3038" in record.content
    assert "corequisites" not in record.metadata_json


def test_program_study_options_keeps_nested_h3_content() -> None:
    html = """
    <head>
      <meta name="program-name" content="Bachelor of Criminology">
      <meta name="program-code" content="BCRIM">
      <meta name="program-year" content="2026">
    </head><body>
      <h1>Bachelor of Criminology</h1>
      <h2>Study Options</h2>
      <h3>Single degree</h3>
      <div>Year 1 study plan with 48 units.</div>
      <h2>Academic Advice</h2><p>Contact the College.</p>
    </body>
    """
    record = CoursesParser().parse(
        html,
        "https://programsandcourses.anu.edu.au/2026/program/bcrim",
    )[0]

    assert "Study Options: Single degree Year 1 study plan with 48 units." in record.content


def test_scholarship_nested_value_is_captured() -> None:
    url = "https://study.anu.edu.au/scholarships/find-scholarship/source-award"
    html = f"""
    <head><link rel="canonical" href="{url}"></head>
    <h1 class="banner-title">Source Award</h1>
    <div><h3>Value</h3><p></p><div><p>Up to $65,000.</p></div></div>
    """
    record = ScholarshipsParser().parse(html, url)[0]

    assert record.metadata_json["value"] == "Up to $65,000."


def test_scholarship_external_canonical_is_rejected() -> None:
    url = "https://study.anu.edu.au/scholarships/find-scholarship/external-award"
    html = """
    <head><link rel="canonical" href="https://external.example/grant"></head>
    <h1 class="banner-title">External Award</h1>
    """

    with pytest.raises(ParseError, match="outside the approved detail boundary"):
        ScholarshipsParser().parse(html, url)


def test_rejected_external_scholarship_is_not_a_field_denominator() -> None:
    class StaticFetcher(BaseFetcher):
        def fetch(self, url: str) -> str:
            del url
            return """
            <head><link rel="canonical" href="https://external.example/grant"></head>
            <h1 class="banner-title">External Award</h1>
            <div><h3>Value</h3><p>$1,000</p></div>
            """

    candidate = DetailCandidate(
        "scholarship",
        "external-award",
        "https://study.anu.edu.au/scholarships/find-scholarship/external-award",
    )
    report = DetailCoverageAuditor(
        StaticFetcher(), min_request_interval_seconds=0
    ).audit([candidate])["entity_classes"]["scholarship"]

    assert report["approved_records"] == 0
    assert report["rejected_records"] == 1
    assert report["fields"]["value"]["source_present"] == 0


def test_future_course_offerings_are_not_counted_for_current_year() -> None:
    class StaticFetcher(BaseFetcher):
        def fetch(self, url: str) -> str:
            del url
            return """
            <h1 class="intro-title">Future-only Course</h1>
            <table class="course-data">
              <tr><th>Course Code</th><td>TEST1000</td></tr>
              <tr><th>Academic Year</th><td>2026</td></tr>
            </table>
            <div class="course-tabs-menu">2027 2028</div>
            <div id="course-tab-1"><table class="table-terms">
              <tr><th>Term</th></tr><tr><td>Semester 1</td></tr>
            </table></div>
            """

    url = "https://programsandcourses.anu.edu.au/2026/course/test1000"
    report = DetailCoverageAuditor(
        StaticFetcher(), min_request_interval_seconds=0
    ).audit([DetailCandidate("course", "TEST1000", url)])

    assert report["entity_classes"]["course"]["fields"]["offerings"] == {
        "source_present": 0,
        "captured": 0,
        "missed": 0,
        "coverage_percent": None,
        "representative_misses": [],
    }


def test_placeholder_program_description_is_source_absent() -> None:
    class StaticFetcher(BaseFetcher):
        def fetch(self, url: str) -> str:
            del url
            return """
            <head>
              <meta name="program-name" content="Test Program">
              <meta name="program-code" content="TEST">
              <meta name="program-year" content="2026">
              <meta name="program-description" content="None">
            </head>
            <h1 class="intro__degree-title">Test Program</h1>
            """

    url = "https://programsandcourses.anu.edu.au/2026/program/test"
    report = DetailCoverageAuditor(
        StaticFetcher(), min_request_interval_seconds=0
    ).audit([DetailCandidate("program", "TEST", url)])

    assert report["entity_classes"]["program"]["fields"]["overview"] == {
        "source_present": 0,
        "captured": 0,
        "missed": 0,
        "coverage_percent": None,
        "representative_misses": [],
    }


def test_jobs_parser_can_use_source_listing_title_fallback() -> None:
    url = "https://jobs.anu.edu.au/jobs/source-backed-role"
    html = f"""
    <head><link rel="canonical" href="{url}"></head>
    <div class="job-component-requisition-identifier"><span>563999</span></div>
    """
    parser = JobsParser(
        now_func=lambda: datetime(2026, 9, 16, tzinfo=ZoneInfo("Australia/Canberra"))
    )
    record = parser.parse(
        html,
        url,
        listing_metadata={"title": "Source-backed Role"},
    )[0]

    assert record.title == "Source-backed Role"


def test_jobs_discovery_preserves_listing_title() -> None:
    listing_url = "https://jobs.anu.edu.au/jobs/search"
    html = """
    <div class="table-counts">Displaying 1 - 1 of 1</div>
    <article class="job-result">
      <h2><a href="/jobs/source-backed-role">Source-backed Role</a></h2>
    </article>
    """
    result = JobsDiscovery().discover(html, listing_url)

    assert result.candidates[0].listing_metadata["title"] == "Source-backed Role"


def test_http_fetcher_rejects_http_200_empty_body(monkeypatch: pytest.MonkeyPatch) -> None:
    class EmptyResponse:
        text = "  "

        @staticmethod
        def raise_for_status() -> None:
            return None

    fetcher = HttpFetcher()
    monkeypatch.setattr(fetcher._session, "get", lambda *_args, **_kwargs: EmptyResponse())

    with pytest.raises(FetchError, match="empty response body"):
        fetcher.fetch("https://jobs.anu.edu.au/jobs/source-backed-role")


def test_detail_audit_stops_after_three_consecutive_empty_responses() -> None:
    class EmptyFetcher(BaseFetcher):
        def __init__(self) -> None:
            self.calls = 0

        def fetch(self, url: str) -> str:
            del url
            self.calls += 1
            return ""

    fetcher = EmptyFetcher()
    candidates = [
        DetailCandidate(
            "job",
            str(index),
            f"https://jobs.anu.edu.au/jobs/source-backed-role-{index}",
        )
        for index in range(5)
    ]
    report = DetailCoverageAuditor(
        fetcher,
        min_request_interval_seconds=0,
    ).audit(candidates)["entity_classes"]["job"]

    assert fetcher.calls == 3
    assert report["detail_pages_attempted"] == 3
    assert report["detail_pages_fetched"] == 0
    assert report["stopped_early"] is True


def test_detail_command_fails_when_traversal_stops_early(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        detail_coverage,
        "discover_candidates",
        lambda *_args, **_kwargs: ([], {}),
    )

    class StoppedAuditor:
        def __init__(self, **_kwargs) -> None:
            pass

        def audit(self, _candidates):
            return {"entity_classes": {"job": {"stopped_early": True}}}

    monkeypatch.setattr(detail_coverage, "DetailCoverageAuditor", StoppedAuditor)

    assert detail_coverage.main(["--domain", "jobs"]) == 1
    assert '"status": "INCOMPLETE"' in capsys.readouterr().out
