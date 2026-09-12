"""V5 Day 8 evidence checks for bounded future-domain preparation."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from askanu_scraper.common.models import PollCadence
from askanu_scraper.common.registry import get_source


ROOT = Path(__file__).parent.parent


def _fixture(path: str) -> BeautifulSoup:
    return BeautifulSoup((ROOT / path).read_text(encoding="utf-8"), "html.parser")


def test_future_domain_registry_boundaries_remain_explicit() -> None:
    expected = {
        "scholarships_anu_finder": "https://study.anu.edu.au/scholarships",
        "jobs_anu_search": "https://jobs.anu.edu.au/jobs/search",
        "accommodation_anu_study": "https://study.anu.edu.au/accommodation",
        "support_anusa_student_assistance": "https://anusa.com.au/student-assistance/",
        "events_anu_official": "https://www.anu.edu.au/events",
    }

    for source_id, canonical_root in expected.items():
        source = get_source(source_id)
        assert source.active is True
        assert source.canonical_root == canonical_root

    rubric = get_source("rubric_unified_search")
    assert rubric.active is False
    assert rubric.poll_cadence == PollCadence.DISABLED


def test_scholarship_listing_sample_has_supported_provenance_and_fields() -> None:
    soup = _fixture(
        "fixtures/scholarships/anu_scholarship_listing_sample.html"
    )
    source = soup.find("meta", attrs={"name": "fixture-source"})
    item = soup.select_one("article.scholarship-result")

    assert source is not None
    assert source.get("content") == (
        "https://study.anu.edu.au/scholarships/find-scholarship"
    )
    assert item is not None
    assert item.select_one(".status").get_text(strip=True)
    assert item.select_one(".application-requirement").get_text(strip=True)
    assert item.select_one(".value").get_text(strip=True)
    assert item.select_one(".selection-basis").get_text(strip=True)
    assert item.find("a", href=True)["href"].startswith(
        "https://study.anu.edu.au/scholarships/find-scholarship/"
    )


def test_jobs_sample_stays_public_and_excludes_application_flow() -> None:
    soup = _fixture("fixtures/jobs/anu_jobs_listing_sample.html")
    source = soup.find("meta", attrs={"name": "fixture-source"})
    item = soup.select_one("article.job-result")

    assert source is not None
    assert source.get("content") == "https://jobs.anu.edu.au/jobs/search"
    assert item is not None
    assert item.get("data-job-id") == "563693"
    assert item.select_one(".closing-date").get_text(strip=True)
    assert item.select_one(".classification").get_text(strip=True)

    detail_url = item.find("a", href=True)["href"]
    parsed = urlparse(detail_url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "jobs.anu.edu.au"
    assert parsed.path.startswith("/jobs/")
    assert "apply" not in parsed.path.lower()
    assert "candidate" not in parsed.path.lower()
