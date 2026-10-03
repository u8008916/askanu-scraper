"""HTTP-level Scholarship redirect exclusions and atomic failure coverage."""
from pathlib import Path

import pytest
import responses

from askanu_scraper.common.fetcher import HttpFetcher
from askanu_scraper.common.models import IngestionRunStatus
from askanu_scraper.common.storage import LocalDataStore
from askanu_scraper.sources.scholarships import LISTING_URL, ScholarshipsCollector

FIXTURES = Path(__file__).parent.parent / "fixtures" / "scholarships"
GOOD = LISTING_URL + "/anu-international-achievement-award"
REDIRECT = LISTING_URL + "/real-futures-grant"
EXTERNAL = "https://www.realinsurance.com.au/real-futures-grant"


def body():
    return (FIXTURES / "anu_scholarship_open_featured_sample.html").read_text(encoding="utf-8")


def listing(*urls):
    return "".join(f'<a class="d-block h100" href="{url}">Award</a>' for url in urls)


def collector(tmp_path):
    return ScholarshipsCollector(fetcher=HttpFetcher(), store=LocalDataStore(tmp_path),
                                 min_request_interval_seconds=1, sleep_func=lambda _: None)


@responses.activate
def test_external_redirect_excluded_without_request_and_valid_peer_completes(tmp_path):
    responses.get(LISTING_URL, body=listing(REDIRECT, GOOD))
    responses.get(REDIRECT, status=301, headers={"Location": EXTERNAL})
    responses.get(GOOD, body=body())
    c = collector(tmp_path)
    run, records, _ = c.run_listing(max_details=10)
    assert run.status == IngestionRunStatus.SUCCESS
    assert [r.canonical_url for r in records] == [GOOD]
    assert run.records_seen == 1
    assert c.last_run_sanity["rejected_by_reason"]["external-redirect"] == 1
    assert [call.request.url for call in responses.calls] == [LISTING_URL, REDIRECT, GOOD]
    assert len(list((tmp_path / "records").glob("*.json"))) == 1


@responses.activate
def test_valid_scholarship_http_unchanged(tmp_path):
    responses.get(LISTING_URL, body=listing(GOOD))
    responses.get(GOOD, body=body())
    run, records, _ = collector(tmp_path).run_listing()
    assert run.status == IngestionRunStatus.SUCCESS
    assert records[0].canonical_url == GOOD


@pytest.mark.parametrize("failure", ["canonical", "http", "parser", "internal-redirect"])
@responses.activate
def test_unexpected_detail_failure_preserves_last_known_good(tmp_path, monkeypatch, failure):
    monkeypatch.setattr("askanu_scraper.common.fetcher.time.sleep", lambda _: None)
    responses.get(LISTING_URL, body=listing(GOOD))
    responses.get(GOOD, body=body())
    assert collector(tmp_path).run_listing()[0].status == IngestionRunStatus.SUCCESS
    before = {p.name: p.read_bytes() for p in (tmp_path / "records").glob("*.json")}
    responses.reset()
    responses.get(LISTING_URL, body=listing(GOOD, REDIRECT))
    responses.get(GOOD, body=body())
    if failure == "http":
        responses.get(REDIRECT, status=503)
    elif failure == "internal-redirect":
        responses.get(REDIRECT, status=301, headers={"Location": "/scholarships"})
    elif failure == "canonical":
        responses.get(REDIRECT, body=body().replace(GOOD, LISTING_URL))
    else:
        responses.get(REDIRECT, body="<html>Malformed detail</html>")
    c = collector(tmp_path)
    run, records, _ = c.run_listing(max_details=10)
    assert run.status == IngestionRunStatus.FAILED
    assert records == []
    assert "external-redirect" not in c.last_run_sanity.get("rejected_by_reason", {})
    assert {p.name: p.read_bytes() for p in (tmp_path / "records").glob("*.json")} == before
    assert all(call.request.url in {LISTING_URL, GOOD, REDIRECT} for call in responses.calls)


@responses.activate
def test_approved_relative_redirect_keeps_original_identity(tmp_path):
    responses.get(LISTING_URL, body=listing(GOOD))
    responses.get(GOOD, status=302, headers={"Location": GOOD + "/"})
    responses.get(GOOD + "/", body=body())
    run, records, _ = collector(tmp_path).run_listing()
    assert run.status == IngestionRunStatus.SUCCESS
    assert records[0].canonical_url == GOOD


@responses.activate
def test_all_external_redirects_preserve_suspicious_zero_guard(tmp_path):
    responses.get(LISTING_URL, body=listing(REDIRECT))
    responses.get(REDIRECT, status=301, headers={"Location": EXTERNAL})
    run, records, _ = collector(tmp_path).run_listing()
    assert run.status == IngestionRunStatus.SUSPICIOUS_ZERO
    assert records == []
    assert not list((tmp_path / "records").glob("*.json"))
    assert all(call.request.url != EXTERNAL for call in responses.calls)
