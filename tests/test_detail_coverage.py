"""V6 read-only detail field coverage tests."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from askanu_scraper import detail_coverage
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


def test_combined_live_requisite_section_has_independent_presence_detection() -> None:
    url = "https://programsandcourses.anu.edu.au/2026/course/comp1110"
    html = """
    <div class="course-detail">
      <h1 class="intro-title">Structured Programming</h1>
      <table class="course-data">
        <tr><th>Course Code</th><td>COMP1110</td></tr>
        <tr><th>Academic Year</th><td>2026</td></tr>
      </table>
      <h2>Requisite and Incompatibility</h2>
      <div>To enrol in this course you must have completed: COMP1100.
      You are not able to enrol in this course if you have completed COMP1140.</div>
    </div>
    """
    course = audit(
        DetailCandidate("course", "COMP1110", url), pages={url: html}
    )["entity_classes"]["course"]

    assert course["fields"]["prerequisites"]["source_present"] == 1
    assert course["fields"]["prerequisites"]["captured"] == 1
    assert course["fields"]["incompatibilities"]["source_present"] == 1
    assert course["fields"]["incompatibilities"]["captured"] == 1


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


def test_accommodation_source_present_fields_and_manifest_are_audited() -> None:
    url = "https://study.anu.edu.au/accommodation/our-residences/yukeembruk"
    html = (
        Path(__file__).resolve().parents[1]
        / "fixtures" / "accommodation" / "anu_residence_yukeembruk_sample.html"
    ).read_text(encoding="utf-8")
    result = audit(
        DetailCandidate(
            "residence",
            "yukeembruk",
            url,
            {
                "title": "Yukeembruk",
                "category": "Our residences",
                "catering_options": ["Self-catered"],
                "audiences": ["Undergraduate"],
                "advertised_rate": "From $380 per week",
            },
        ),
        pages={url: html},
    )["entity_classes"]["residence"]

    assert result["approved_records"] == 1
    for field_name in ("rooms", "features", "overview", "contact"):
        assert result["fields"][field_name]["coverage_percent"] == 100.0
    assert result["fields"]["vacancy_status"]["source_present"] == 0
    assert result["identity_manifest"][0]["record_id"].startswith(
        "accommodation:residence:"
    )
    assert result["identity_manifest"][0]["content_hash"]


def test_support_source_present_fields_and_absent_fields_are_audited() -> None:
    url = "https://anusa.com.au/student-assistance/academic/"
    html = (
        Path(__file__).resolve().parents[1]
        / "fixtures" / "support" / "anusa_academic_sample.html"
    ).read_text(encoding="utf-8")
    result = audit(
        DetailCandidate(
            "support_service",
            "academic",
            url,
            {
                "title": "Academic Support",
                "category": "Academic",
                "audiences": ["all ANU Students"],
                "cost": "The service is free.",
                "registry_email": "sa.assistance@anu.edu.au",
            },
        ),
        pages={url: html},
    )["entity_classes"]["support_service"]

    assert result["approved_records"] == 1
    for field_name in ("purpose", "contact", "hours", "access", "topics", "referrals"):
        assert result["fields"][field_name]["coverage_percent"] == 100.0


def test_support_access_link_is_captured_without_internal_referral_false_positive() -> None:
    url = "https://anusa.com.au/student-assistance/physical-and-mental-health/"
    html = (
        Path(__file__).resolve().parents[1]
        / "fixtures" / "support" / "anusa_access_link_sample.html"
    ).read_text(encoding="utf-8")
    result = audit(
        DetailCandidate(
            "support_service",
            "physical-and-mental-health",
            url,
            {"category": "Physical and Mental Health"},
        ),
        pages={url: html},
    )["entity_classes"]["support_service"]

    assert result["fields"]["access"]["source_present"] == 1
    assert result["fields"]["access"]["captured"] == 1
    assert result["fields"]["referrals"]["source_present"] == 0


def test_events_window_filter_and_source_presence_are_audited() -> None:
    fixture_root = Path(__file__).resolve().parents[1] / "fixtures" / "events"
    inside_url = "https://www.anu.edu.au/events/window-opening"
    outside_url = "https://www.anu.edu.au/events/outside-window"
    result = DetailCoverageAuditor(
        StaticFetcher(
            {
                inside_url: (fixture_root / "window-opening.html").read_text(encoding="utf-8"),
                outside_url: (fixture_root / "outside-window.html").read_text(encoding="utf-8"),
            }
        ),
        min_request_interval_seconds=0,
        events_window_start=date(2026, 9, 19),
        events_window_days=43,
    ).audit(
        [
            DetailCandidate("event", "window-opening", inside_url),
            DetailCandidate("event", "outside-window", outside_url),
        ]
    )["entity_classes"]["event"]

    assert result["parsed_records"] == 2
    assert result["approved_records"] == 1
    assert result["outside_window"] == 1
    assert result["rejected_by_reason"] == {"outside-frozen-window": 1}
    for field_name in (
        "event_id", "start_date", "end_date", "start_at", "end_at",
        "location", "categories", "tags", "organiser", "description",
        "registration_links",
    ):
        assert result["fields"][field_name]["coverage_percent"] == 100.0


def test_event_mail_registration_is_not_counted_as_http_registration() -> None:
    fixture_root = Path(__file__).resolve().parents[1] / "fixtures" / "events"
    url = "https://www.anu.edu.au/events/window-opening"
    html = (fixture_root / "window-opening.html").read_text(encoding="utf-8").replace(
        "</body>", '<a href="mailto:events@anu.edu.au">Register through mail</a></body>'
    ).replace(
        "https://tickets.example/register/in-person", "mailto:events@anu.edu.au"
    ).replace("https://zoom.example/register", "mailto:events@anu.edu.au")
    result = audit(
        DetailCandidate("event", "window-opening", url),
        pages={url: html},
    )["entity_classes"]["event"]

    assert result["fields"]["registration_links"]["source_present"] == 0


def test_events_discovery_refuses_incomplete_pagination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeEventsCollector:
        def __init__(self, **_kwargs) -> None:
            pass

        def discover_full_listing(self, **_kwargs):
            return SimpleNamespace(
                pagination_complete=False,
                unique_link_count=12,
            )

    monkeypatch.setattr(detail_coverage, "EventsCollector", FakeEventsCollector)
    with pytest.raises(RuntimeError, match="pagination is incomplete"):
        detail_coverage.discover_candidates(
            "events",
            academic_year="2026",
            max_listing_pages=1,
            interval=0,
        )



def test_detail_discovery_refuses_unreconciled_scholarship_listing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeScholarshipsCollector:
        def __init__(self, **_kwargs) -> None:
            pass

        def discover_full_listing(self, **_kwargs):
            return SimpleNamespace(
                headline_total_count=405,
                discovered_candidate_count=404,
                candidates=(),
            )

    monkeypatch.setattr(
        detail_coverage,
        "ScholarshipsCollector",
        FakeScholarshipsCollector,
    )

    with pytest.raises(
        RuntimeError,
        match="Scholarships listing is unreconciled",
    ):
        detail_coverage.discover_candidates(
            "scholarships",
            academic_year="2026",
            max_listing_pages=100,
            interval=0,
        )


def test_detail_discovery_refuses_missing_scholarship_total(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeScholarshipsCollector:
        def __init__(self, **_kwargs) -> None:
            pass

        def discover_full_listing(self, **_kwargs):
            return SimpleNamespace(
                headline_total_count=None,
                discovered_candidate_count=379,
                candidates=(),
            )

    monkeypatch.setattr(
        detail_coverage,
        "ScholarshipsCollector",
        FakeScholarshipsCollector,
    )

    with pytest.raises(
        RuntimeError,
        match="Scholarships headline total is missing",
    ):
        detail_coverage.discover_candidates(
            "scholarships",
            academic_year="2026",
            max_listing_pages=100,
            interval=0,
        )


def test_detail_discovery_refuses_unreconciled_jobs_listing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeJobsCollector:
        def __init__(self, **_kwargs) -> None:
            pass

        def discover_full_listing(self, **_kwargs):
            return SimpleNamespace(
                advertised_total_count=55,
                candidates=[SimpleNamespace()] * 54,
            )

    monkeypatch.setattr(
        detail_coverage,
        "JobsCollector",
        FakeJobsCollector,
    )

    with pytest.raises(
        RuntimeError,
        match="Jobs listing is unreconciled",
    ):
        detail_coverage.discover_candidates(
            "jobs",
            academic_year="2026",
            max_listing_pages=100,
            interval=0,
        )


def test_detail_discovery_refuses_zero_jobs_total(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeJobsCollector:
        def __init__(self, **_kwargs) -> None:
            pass

        def discover_full_listing(self, **_kwargs):
            return SimpleNamespace(
                advertised_total_count=0,
                candidates=[],
            )

    monkeypatch.setattr(
        detail_coverage,
        "JobsCollector",
        FakeJobsCollector,
    )

    with pytest.raises(
        RuntimeError,
        match="Jobs advertised total is suspiciously zero",
    ):
        detail_coverage.discover_candidates(
            "jobs",
            academic_year="2026",
            max_listing_pages=100,
            interval=0,
        )


def test_detail_discovery_uses_dry_run_store_without_creating_local_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    class FakeCoursesCollector:
        def __init__(
            self,
            *,
            store,
            min_request_interval_seconds,
        ) -> None:
            observed["dry_run"] = store.dry_run
            observed["interval"] = min_request_interval_seconds

        def discover_full_catalogue(self, *, academic_year):
            observed["academic_year"] = academic_year
            return SimpleNamespace(
                primary_feeds_reconciled=True,
                items=(),
                counts_by_type={},
            )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        detail_coverage,
        "CoursesCollector",
        FakeCoursesCollector,
    )

    candidates, census = detail_coverage.discover_candidates(
        "courses",
        academic_year="2026",
        max_listing_pages=100,
        interval=0,
    )

    assert candidates == []
    assert census["courses"]["observed_unique"] == {}
    assert census["courses"]["frozen_denominators"]["course"] == 500
    assert census["courses"]["count_drift"]["course"] == -500
    assert observed == {
        "dry_run": True,
        "interval": 0,
        "academic_year": "2026",
    }
    assert not (tmp_path / "local-data").exists()


def test_detail_coverage_refuses_to_overwrite_stale_evidence_artifact() -> None:
    with pytest.raises(SystemExit, match="2"):
        detail_coverage.main(
            ["--output", "detail-coverage-evidence.json"]
        )
