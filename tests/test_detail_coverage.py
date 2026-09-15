"""V6 read-only detail field coverage tests."""
from __future__ import annotations

from pathlib import Path

from askanu_scraper.common.fetcher import BaseFetcher
from askanu_scraper.detail_coverage import DetailCandidate, DetailCoverageAuditor


class StaticFetcher(BaseFetcher):
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.urls: list[str] = []

    def fetch(self, url: str) -> str:
        self.urls.append(url)
        return self.pages[url]


def audit(*candidates: DetailCandidate, pages: dict[str, str]) -> dict[str, object]:
    return DetailCoverageAuditor(
        StaticFetcher(pages), min_request_interval_seconds=0
    ).audit(candidates)


def test_program_source_sections_are_detected_and_captured() -> None:
    url = "https://programsandcourses.anu.edu.au/2026/program/bacct"
    html = """
    <html><head>
      <meta name="program-name" content="Bachelor of Accounting">
      <meta name="program-code" content="BACCT">
      <meta name="program-year" content="2026">
      <meta name="program-description" content="&lt;p&gt;Source overview.&lt;/p&gt;">
      <link rel="canonical" href="https://programsandcourses.anu.edu.au/2026/program/bacct">
    </head><body><div class="program-detail">
      <h1 class="intro__degree-title">Bachelor of Accounting</h1>
      <div class="degree-summary"><ul>
        <li><span class="degree-summary__code-heading">Length</span><span class="degree-summary__code-text">3 years</span></li>
        <li><span class="degree-summary__code-heading">Minimum</span><span class="degree-summary__code-text">144 Units</span></li>
        <li><span class="degree-summary__code-heading">Academic career</span><span class="degree-summary__code-text">Undergraduate</span></li>
        <li><span class="degree-summary__code-heading">Mode of delivery</span><span class="degree-summary__code-text">In Person</span></li>
      </ul></div>
      <h2>Program Requirements</h2><div><p>Complete 144 units.</p></div>
      <h2>Admission Requirements</h2><div><p>Meet published admission rules.</p></div>
      <h2>Prerequisites</h2><div><p>None stated beyond admission rules.</p></div>
      <h2>Learning Outcomes</h2><div><ul><li>Apply accounting knowledge.</li></ul></div>
      <h2>Minors</h2><div><p>Minors may be available.</p></div>
      <h2>Elective Study</h2><div><p>Electives may be chosen.</p></div>
      <h2>Study Options</h2><div><p>Single degree.</p></div>
    </div></body></html>
    """
    report = audit(
        DetailCandidate("program", "BACCT", url), pages={url: html}
    )["entity_classes"]["program"]

    for field in (
        "overview", "learning_outcomes", "program_requirements",
        "admission_requirements", "prerequisites", "minors",
        "elective_study", "study_options",
    ):
        assert report["fields"][field] == {
            "source_present": 1,
            "captured": 1,
            "missed": 0,
            "coverage_percent": 100.0,
            "representative_misses": [],
        }


def test_subplan_detail_is_ephemeral_and_field_complete() -> None:
    url = "https://programsandcourses.anu.edu.au/2026/major/acct-maj"
    html = """
    <html><head><meta name="major-name" content="Accounting"></head><body>
      <span class="intro__degree-type">Major</span>
      <h1 class="intro__degree-title">Accounting</h1>
      <div class="intro__degree-description"><p>A major offered by ANU.</p></div>
      <div class="degree-summary"><ul>
        <li><span class="degree-summary__code-heading">Total units</span><span class="degree-summary__code-text">48 Units</span></li>
        <li><span class="degree-summary__code-heading">Academic career</span><span class="degree-summary__code-text">Undergraduate</span></li>
      </ul></div>
      <h2>Learning Outcomes</h2><div><p>Apply accounting concepts.</p></div>
      <h2>Requirements</h2><div><p>Complete 48 units.</p></div>
      <h2>Other Information</h2><div><p>Source-backed advice.</p></div>
    </body></html>
    """
    report = audit(
        DetailCandidate("major", "ACCT-MAJ", url), pages={url: html}
    )

    major = report["entity_classes"]["major"]
    assert major["approved_records"] == 1
    assert major["fields"]["requirements"]["coverage_percent"] == 100.0
    assert major["fields"]["other_information"]["coverage_percent"] == 100.0
    assert report["subplans_persisted"] == 0
    assert report["production_records_written"] == 0


def test_source_present_parser_miss_is_not_counted_as_absent() -> None:
    url = "https://programsandcourses.anu.edu.au/2026/course/comp1100"
    html = """
    <div class="course-detail">
      <h1 class="intro-title">Programming as Problem Solving</h1>
      <table class="course-data">
        <tr><th>Course Code</th><td>COMP1100</td></tr>
        <tr><th>Academic Year</th><td>2026</td></tr>
      </table>
      <h2>Prerequisites</h2><div><p>Year 12 mathematics.</p></div>
    </div>
    """
    course = audit(
        DetailCandidate("course", "COMP1100", url), pages={url: html}
    )["entity_classes"]["course"]

    assert course["fields"]["prerequisites"] == {
        "source_present": 1,
        "captured": 0,
        "missed": 1,
        "coverage_percent": 0.0,
        "representative_misses": [f"COMP1100 {url}"],
    }


def test_source_absent_optional_field_has_no_false_failure() -> None:
    url = "https://programsandcourses.anu.edu.au/2026/course/comp1100"
    html = """
    <div class="course-detail"><h1 class="intro-title">Programming</h1>
      <table class="course-data">
        <tr><th>Course Code</th><td>COMP1100</td></tr>
        <tr><th>Academic Year</th><td>2026</td></tr>
      </table>
    </div>
    """
    course = audit(
        DetailCandidate("course", "COMP1100", url), pages={url: html}
    )["entity_classes"]["course"]

    assert course["fields"]["corequisites"] == {
        "source_present": 0,
        "captured": 0,
        "missed": 0,
        "coverage_percent": None,
        "representative_misses": [],
    }


def test_malformed_detail_and_canonical_mismatch_are_reported() -> None:
    malformed_url = "https://programsandcourses.anu.edu.au/2026/program/bacct"
    mismatch_url = "https://programsandcourses.anu.edu.au/2026/course/comp1100"
    pages = {
        malformed_url: "<div class='program-detail'></div>",
        mismatch_url: """
          <html><head><link rel="canonical" href="https://programsandcourses.anu.edu.au/2026/course/COMP1100"></head>
          <body><div class="course-detail"><h1>Programming</h1><table class="course-data">
          <tr><th>Course Code</th><td>COMP1100</td></tr><tr><th>Academic Year</th><td>2026</td></tr>
          </table></div></body></html>
        """,
    }
    result = audit(
        DetailCandidate("program", "BACCT", malformed_url),
        DetailCandidate("course", "COMP1100", mismatch_url),
        pages=pages,
    )["entity_classes"]

    assert result["program"]["malformed_pages"] == 1
    assert result["program"]["parser_exceptions"] == 1
    assert result["course"]["canonical_mismatches"] == 1
    assert result["course"]["fields"]["canonical_url"]["missed"] == 1


def test_duplicate_identity_is_not_fetched_twice() -> None:
    url = "https://programsandcourses.anu.edu.au/2026/major/acct-maj"
    candidate = DetailCandidate("major", "ACCT-MAJ", url)
    fetcher = StaticFetcher({url: "<h1 class='intro__degree-title'>Accounting</h1>"})
    result = DetailCoverageAuditor(
        fetcher, min_request_interval_seconds=0
    ).audit([candidate, candidate])

    assert result["entity_classes"]["major"]["duplicate_identities"] == 1
    assert fetcher.urls == [url]
    assert result["production_records_written"] == 0


def test_noncanonical_candidate_is_rejected_before_fetch() -> None:
    bad = DetailCandidate(
        "minor", "AAGR-MIN",
        "https://programsandcourses.anu.edu.au/2026/minor/AAGR-MIN?x=1",
    )
    fetcher = StaticFetcher({})
    result = DetailCoverageAuditor(
        fetcher, min_request_interval_seconds=0
    ).audit([bad])

    minor = result["entity_classes"]["minor"]
    assert minor["rejected_records"] == 1
    assert minor["detail_pages_fetched"] == 0
    assert fetcher.urls == []


def test_scholarship_listing_evidence_and_detail_fields_are_covered() -> None:
    url = (
        "https://study.anu.edu.au/scholarships/find-scholarship/"
        "anu-international-achievement-award"
    )
    html = (
        Path(__file__).resolve().parents[1]
        / "fixtures" / "scholarships" / "anu_scholarship_open_featured_sample.html"
    ).read_text(encoding="utf-8")
    result = audit(
        DetailCandidate(
            "scholarship", "anu-international-achievement-award", url,
            {"featured": True, "status": "Open for applications",
             "application_requirement": "Automatic consideration"},
        ),
        pages={url: html},
    )["entity_classes"]["scholarship"]

    assert result["fields"]["featured"]["coverage_percent"] == 100.0
    assert result["fields"]["eligibility"]["coverage_percent"] == 100.0
    # "Open all year" is source text, but it is not an invented calendar date.
    assert result["fields"]["opening_date"]["source_present"] == 0


def test_job_uses_listing_and_detail_evidence_without_pd_fetch() -> None:
    url = (
        "https://jobs.anu.edu.au/jobs/"
        "senior-consultant-user-experience-hr-systems-projects-canberra-act-act-australia"
    )
    html = (
        Path(__file__).resolve().parents[1]
        / "fixtures" / "jobs" / "anu_job_open_dated_sample.html"
    ).read_text(encoding="utf-8")
    result = audit(
        DetailCandidate(
            "job", "563693", url,
            {"job_id": "563693", "category": "Professional",
             "employment_types": ["Fixed Term"], "location": "Canberra",
             "classification": "ANU Officer 8", "salary": "$124,392",
             "closing_text": "Closing at: Sep 27 2026 - 23:55 AEST",
             "summary": "Create user-friendly documentation."},
        ),
        pages={url: html},
    )
    job = result["entity_classes"]["job"]

    assert job["fields"]["closing_date"]["coverage_percent"] == 100.0
    assert job["fields"]["salary"]["coverage_percent"] == 100.0
    assert job["fields"]["role_requirements"]["source_present"] == 0
    assert result["pd_documents_fetched"] == 0
