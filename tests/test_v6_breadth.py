"""V6 full-universe pagination, reconciliation, and persistence-stop tests."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from askanu_scraper.common.fetcher import BaseFetcher, MockFetcher
from askanu_scraper.common.models import IngestionRunStatus
from askanu_scraper.common.storage import LocalDataStore
from askanu_scraper.sources.courses.collector import CoursesCollector
from askanu_scraper.sources.jobs import LISTING_URL as JOBS_LISTING_URL, JobsCollector
from askanu_scraper.sources.scholarships import (
    LISTING_URL as SCHOLARSHIPS_LISTING_URL,
    ScholarshipsCollector,
)


class CatalogueUniverseFetcher(BaseFetcher):
    def __init__(self) -> None:
        self.urls: list[str] = []

    def fetch(self, url: str) -> str:
        self.urls.append(url)
        parsed = urlsplit(url)
        page = int(parse_qs(parsed.query).get("PageIndex", ["0"])[0])
        endpoint = parsed.path.rsplit("/", 1)[-1]
        pages: dict[str, tuple[int, list[list[dict[str, object]]]]] = {
            "GetCourses": (3, [[
                {"CourseCode": "COMP1100", "Year": 2026},
                {"CourseCode": "COMP1110", "Year": 2026},
            ], [{"CourseCode": "MATH1005", "Year": 2026}]]),
            "GetProgramsUnderGraduate": (2, [[
                {"AcademicPlanCode": "BACCT", "ProgramAcademicYear": "2026"},
                {"AcademicPlanCode": "BFIN", "ProgramAcademicYear": "2026"},
            ]]),
            "GetProgramsPostGraduate": (2, [[
                {"AcademicPlanCode": "BFIN", "ProgramAcademicYear": "2026"},
                {"AcademicPlanCode": "MCOMP", "ProgramAcademicYear": "2026"},
            ]]),
            "GetProgramsResearch": (1, [[
                {"AcademicPlanCode": "PHD", "ProgramAcademicYear": "2026"},
            ]]),
            "GetProgramsNonAward": (0, [[]]),
            # Deliberate upstream TotalCount anomaly: only three rows available.
            "GetMajors": (4, [[
                {"SubPlanCode": "COMP-MAJ", "Year": 2026},
                {"SubPlanCode": "ACCT-MAJ", "Year": 2026},
            ], [{"SubPlanCode": "MATH-MAJ", "Year": 2026}]]),
            "GetMinors": (1, [[{"SubPlanCode": "STAT-MIN", "Year": 2026}]]),
            "GetSpecialisations": (1, [[
                {"SubPlanCode": "MEAS-SPEC", "Year": 2026},
            ]]),
        }
        total, response_pages = pages[endpoint]
        items = response_pages[page] if page < len(response_pages) else []
        return json.dumps({"Items": items, "TotalCount": total})


def test_courses_full_universe_enumerates_all_feeds_without_persisting(
    tmp_path: Path,
) -> None:
    fetcher = CatalogueUniverseFetcher()
    store = LocalDataStore(tmp_path / "store")
    collector = CoursesCollector(fetcher=fetcher, store=store)

    result = collector.discover_full_catalogue(
        academic_year="2026", page_size=2
    )

    assert result.counts_by_type == {
        "course": 3,
        "program": 4,
        "major": 3,
        "minor": 1,
        "specialisation": 1,
    }
    assert "program:BFIN_2026" in result.duplicate_identities
    assert any("GetMajors: TotalCount=4, returned_rows=3" in item for item in result.anomalies)
    assert any("GetProgramsNonAward" in item and "TotalCount=0" in item for item in result.anomalies)
    assert result.persisted_candidates and all(
        item.entity_type.value in {"course", "program"}
        for item in result.persisted_candidates
    )
    assert list((tmp_path / "store" / "records").glob("*.json")) == []
    assert list((tmp_path / "store" / "runs").glob("*.json")) == []
    assert collector.last_run_sanity["persistence_scope"] == ["course", "program"]


class MalformedCatalogueFetcher(BaseFetcher):
    def fetch(self, url: str) -> str:
        del url
        return json.dumps({"Items": "not-a-list", "TotalCount": 1})


def test_courses_full_universe_rejects_malformed_api_payload(tmp_path: Path) -> None:
    collector = CoursesCollector(
        fetcher=MalformedCatalogueFetcher(),
        store=LocalDataStore(tmp_path / "store"),
    )
    with pytest.raises(ValueError, match="Items list"):
        collector.discover_full_catalogue(academic_year="2026")
    assert list((tmp_path / "store" / "records").glob("*.json")) == []
    assert list((tmp_path / "store" / "runs").glob("*.json")) == []


def _scholarship_card(url: str, text: str = "Open for applications") -> str:
    return (
        '<article class="scholarship-result"><h2><a href="'
        + url
        + '">Scholarship</a></h2><p>'
        + text
        + "</p></article>"
    )


def test_scholarship_full_listing_reconciles_raw_exclusions_and_duplicates(
    tmp_path: Path,
) -> None:
    fixtures = Path(__file__).parent.parent / "fixtures" / "scholarships"
    urls = [
        "https://study.anu.edu.au/scholarships/find-scholarship/anu-international-achievement-award",
        "https://study.anu.edu.au/scholarships/find-scholarship/alex-rodgers-travel-grant",
        "https://study.anu.edu.au/scholarships/find-scholarship/anu-humanitarian-scholarship",
    ]
    page0 = tmp_path / "sch-0.html"
    page1 = tmp_path / "sch-1.html"
    page2 = tmp_path / "sch-2.html"
    page0.write_text(
        '<div class="expanded-filters-results-count">'
        '<span class="expanded-filters-results-count__number">5</span>'
        '<span>results for you</span></div>'
        + _scholarship_card(urls[0])
        + _scholarship_card(urls[1])
    )
    page1.write_text(_scholarship_card("https://external.example/item", "External scholarship") + _scholarship_card(urls[0]))
    page2.write_text(_scholarship_card(urls[2]))
    fetcher = MockFetcher({
        SCHOLARSHIPS_LISTING_URL: page0,
        SCHOLARSHIPS_LISTING_URL + "?page=1": page1,
        SCHOLARSHIPS_LISTING_URL + "?page=2": page2,
        urls[0]: fixtures / "anu_scholarship_open_featured_sample.html",
        urls[1]: fixtures / "anu_scholarship_open_non_featured_sample.html",
        urls[2]: fixtures / "anu_humanitarian_scholarship_sample.html",
    })
    collector = ScholarshipsCollector(
        fetcher=fetcher, store=LocalDataStore(tmp_path / "store")
    )

    run, records, discovery = collector.run_listing(
        max_listing_pages=3, max_details=None
    )

    assert run.status == IngestionRunStatus.SUCCESS
    assert len(records) == 3
    assert discovery is not None
    assert discovery.discovered_candidate_count == 5
    assert discovery.headline_total_count == 5
    assert discovery.rejected_by_reason == {
        "external-scholarship": 1,
        "duplicate-detail-link": 1,
    }
    assert collector.last_run_sanity["listing_reconciled"] is True
    assert collector.last_run_sanity["listing_request_count"] == 3


def test_scholarship_41_page_census_and_final_partial_page(tmp_path: Path) -> None:
    mapping: dict[str, Path] = {}
    for page_number in range(41):
        path = tmp_path / f"finder-{page_number}.html"
        first_index = page_number * 10
        page_size = 5 if page_number == 40 else 10
        cards: list[str] = []
        for offset in range(page_size):
            index = first_index + offset
            url = (
                "https://study.anu.edu.au/scholarships/find-scholarship/"
                f"scholarship-{index:03d}"
            )
            marker = "External scholarship" if index < 26 else "ANU scholarship"
            cards.append(_scholarship_card(url, marker))
        headline = (
            '<div class="expanded-filters-results-count"><span>405</span>'
            "<span>results for you</span></div>"
            if page_number == 0
            else ""
        )
        path.write_text(headline + "".join(cards), encoding="utf-8")
        request_url = (
            SCHOLARSHIPS_LISTING_URL
            if page_number == 0
            else SCHOLARSHIPS_LISTING_URL + f"?page={page_number}"
        )
        mapping[request_url] = path

    collector = ScholarshipsCollector(
        fetcher=MockFetcher(mapping),
        store=LocalDataStore(tmp_path / "store", dry_run=True),
    )
    result = collector.discover_full_listing(max_listing_pages=41)

    assert result.discovered_candidate_count == 405
    assert len(result.candidates) == 379
    assert result.rejected_by_reason == {"external-scholarship": 26}
    assert collector.last_run_sanity["listing_request_count"] == 41
    assert collector.last_run_sanity["listing_reconciled"] is True


def _job_listing(first: int, last: int, total: int, url: str, job_id: str) -> str:
    return f'''<div class="table-counts"><p>Displaying
      <b>{first}\ufffd-\ufffd{last}</b> of <b>{total}</b> in total</p></div>
    <article class="job-result" data-job-id="{job_id}">
      <h2><a href="{url}">Role</a></h2><p class="status">Current</p>
    </article>'''


def test_jobs_full_listing_deduplicates_base_page_one_and_reconciles(
    tmp_path: Path,
) -> None:
    fixtures = Path(__file__).parent.parent / "fixtures" / "jobs"
    first_url = (
        "https://jobs.anu.edu.au/jobs/"
        "senior-consultant-user-experience-hr-systems-projects-canberra-act-act-australia"
    )
    second_url = "https://jobs.anu.edu.au/jobs/anu-talent-register-canberra-act-australia"
    base = tmp_path / "jobs-base.html"
    duplicate = tmp_path / "jobs-page1.html"
    continuation = tmp_path / "jobs-page2.html"
    base.write_text(_job_listing(1, 1, 2, first_url, "563693"), encoding="utf-8")
    duplicate.write_text(
        _job_listing(1, 1, 2, first_url, "563693"), encoding="utf-8"
    )
    continuation.write_text(
        _job_listing(2, 2, 2, second_url, "999999"), encoding="utf-8"
    )
    collector = JobsCollector(
        fetcher=MockFetcher({
            JOBS_LISTING_URL: base,
            JOBS_LISTING_URL + "?page=1": duplicate,
            JOBS_LISTING_URL + "?page=2": continuation,
            first_url: fixtures / "anu_job_open_dated_sample.html",
            second_url: fixtures / "anu_job_open_undated_sample.html",
        }),
        store=LocalDataStore(tmp_path / "store"),
    )

    run, records, discovery = collector.run_listing(
        max_listing_pages=3, max_details=None
    )

    assert run.status == IngestionRunStatus.SUCCESS
    assert len(records) == 2
    assert discovery is not None
    assert discovery.advertised_total_count == 2
    assert len(discovery.candidates) == 2
    assert discovery.duplicate_links == [first_url]
    assert collector.last_run_sanity["listing_reconciled"] is True
    assert collector.last_run_sanity["listing_request_count"] == 3


def test_jobs_full_listing_fails_before_details_on_total_mismatch(
    tmp_path: Path,
) -> None:
    url = "https://jobs.anu.edu.au/jobs/only-role"
    base = tmp_path / "jobs-base.html"
    page1 = tmp_path / "jobs-page1.html"
    base.write_text(_job_listing(1, 1, 3, url, "1"), encoding="utf-8")
    page1.write_text("<p>Displaying 2 - 2 of 3</p>", encoding="utf-8")
    collector = JobsCollector(
        fetcher=MockFetcher({
            JOBS_LISTING_URL: base,
            JOBS_LISTING_URL + "?page=1": page1,
        }),
        store=LocalDataStore(tmp_path / "store"),
    )

    run, records, _ = collector.run_listing(max_listing_pages=2, max_details=None)

    assert run.status == IngestionRunStatus.FAILED
    assert "do not reconcile" in (run.error or "")
    assert records == []
    assert collector.last_run_sanity["detail_request_count"] == 0
