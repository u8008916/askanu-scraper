"""Safe bounded ScholarshipsCollector ingestion tests."""
from __future__ import annotations

from pathlib import Path

from askanu_scraper.common.fetcher import BaseFetcher, FetchError, MockFetcher
from askanu_scraper.common.models import (
    IndexStatus,
    IngestionRunStatus,
)
from askanu_scraper.common.storage import LocalDataStore
from askanu_scraper.sources.scholarships import (
    LISTING_URL,
    ScholarshipsCollector,
)


FIXTURES = Path(__file__).parent.parent / "fixtures" / "scholarships"
FEATURED_URL = (
    "https://study.anu.edu.au/scholarships/find-scholarship/"
    "anu-international-achievement-award"
)
NON_FEATURED_URL = (
    "https://study.anu.edu.au/scholarships/find-scholarship/"
    "alex-rodgers-travel-grant"
)
CLOSED_URL = (
    "https://study.anu.edu.au/scholarships/find-scholarship/"
    "anu-humanitarian-scholarship"
)


def _fetcher(*, featured: Path | None = None) -> MockFetcher:
    return MockFetcher(
        {
            LISTING_URL: FIXTURES / "anu_scholarship_listing_safety_sample.html",
            FEATURED_URL: featured
            or FIXTURES / "anu_scholarship_open_featured_sample.html",
            NON_FEATURED_URL: (
                FIXTURES / "anu_scholarship_open_non_featured_sample.html"
            ),
            CLOSED_URL: FIXTURES / "anu_humanitarian_scholarship_sample.html",
        }
    )


def _collector(store: LocalDataStore, *, featured: Path | None = None, sleeps=None):
    return ScholarshipsCollector(
        fetcher=_fetcher(featured=featured),
        store=store,
        min_request_interval_seconds=1.0 if sleeps is not None else 0.0,
        sleep_func=(sleeps.append if sleeps is not None else None),
    )


def test_bounded_listing_preflights_and_persists_supported_records(
    tmp_path: Path,
) -> None:
    store = LocalDataStore(tmp_path / "store")
    sleeps: list[float] = []
    collector = _collector(store, sleeps=sleeps)

    run, records, discovery = collector.run_listing(max_details=3)

    assert run.status == IngestionRunStatus.SUCCESS
    assert run.records_seen == 3
    assert run.records_added == 3
    assert {record.record_id for record in records} == {
        "scholarships:scholarship:anu-international-achievement-award",
        "scholarships:scholarship:alex-rodgers-travel-grant",
        "scholarships:scholarship:anu-humanitarian-scholarship",
    }
    assert discovery is not None
    assert collector.last_run_sanity == {
        "request_count": 4,
        "listing_request_count": 1,
        "detail_request_count": 3,
        "discovered_candidate_count": 8,
        "accepted_candidate_count": 3,
        "rejected_candidate_count": 5,
        "duplicate_candidate_count": 1,
        "over_limit_candidate_count": 0,
        "duplicate_record_id_count": 0,
        "duplicate_canonical_url_count": 0,
    }
    assert sleeps == [1.0, 1.0, 1.0]
    assert len(list((tmp_path / "store" / "records").glob("*.json"))) == 3
    assert len(list((tmp_path / "store" / "runs").glob("*.json"))) == 1


def test_rerun_is_unchanged_and_preserves_deterministic_hashes(tmp_path: Path) -> None:
    store = LocalDataStore(tmp_path / "store")
    first, first_records, _ = _collector(store).run_listing(max_details=2)
    second, second_records, _ = _collector(store).run_listing(max_details=2)

    assert first.records_added == 2
    assert second.status == IngestionRunStatus.SUCCESS
    assert second.records_added == 0
    assert second.records_changed == 0
    assert second.records_unchanged == 2
    assert [item.record_id for item in first_records] == [
        item.record_id for item in second_records
    ]
    assert [item.content_hash for item in first_records] == [
        item.content_hash for item in second_records
    ]


def test_supported_change_marks_record_changed_and_pending(tmp_path: Path) -> None:
    store = LocalDataStore(tmp_path / "store")
    first, first_records, _ = _collector(store).run_listing(max_details=1)
    assert first.records_added == 1

    changed_path = tmp_path / "changed.html"
    original = (FIXTURES / "anu_scholarship_open_featured_sample.html").read_text(
        encoding="utf-8"
    )
    changed_path.write_text(
        original.replace(
            "20%, 25% or 50% off tuition fees for up to 4 years.",
            "20% off tuition fees for up to 4 years.",
        ),
        encoding="utf-8",
    )

    changed, records, _ = _collector(
        store, featured=changed_path
    ).run_listing(max_details=1)

    assert changed.status == IngestionRunStatus.SUCCESS
    assert changed.records_changed == 1
    assert changed.records_added == 0
    assert records[0].content_hash != first_records[0].content_hash
    assert records[0].index_status == IndexStatus.PENDING
    assert records[0].embedding_version is None


def test_dry_run_compares_without_writing(tmp_path: Path) -> None:
    storage_path = tmp_path / "dry-store"
    store = LocalDataStore(storage_path, dry_run=True)
    run, records, _ = _collector(store).run_listing(max_details=1)

    assert run.status == IngestionRunStatus.SUCCESS
    assert run.records_added == 1
    assert len(records) == 1
    assert not storage_path.exists()


def test_detail_failure_preserves_last_known_good_and_writes_no_partial_batch(
    tmp_path: Path,
) -> None:
    store = LocalDataStore(tmp_path / "store")
    first, records, _ = _collector(store).run_listing(max_details=2)
    assert first.status == IngestionRunStatus.SUCCESS
    before = {
        record.record_id: store.get_record(record.record_id).content_hash
        for record in records
    }

    malformed = FIXTURES / "anu_scholarship_malformed_sample.html"
    failed, failed_records, _ = _collector(
        store, featured=malformed
    ).run_listing(max_details=2)

    assert failed.status == IngestionRunStatus.FAILED
    assert failed_records == []
    after = {
        record_id: store.get_record(record_id).content_hash for record_id in before
    }
    assert after == before


class _AlwaysFailFetcher(BaseFetcher):
    def fetch(self, url: str) -> str:
        del url
        raise FetchError("simulated fetch failure")


def test_listing_fetch_failure_preserves_last_known_good(tmp_path: Path) -> None:
    store = LocalDataStore(tmp_path / "store")
    success, records, _ = _collector(store).run_listing(max_details=1)
    assert success.status == IngestionRunStatus.SUCCESS
    before = store.get_record(records[0].record_id)

    failed_collector = ScholarshipsCollector(
        fetcher=_AlwaysFailFetcher(), store=store
    )
    failed, failed_records, _ = failed_collector.run_listing(max_details=1)

    assert failed.status == IngestionRunStatus.FAILED
    assert "Listing fetch failed" in (failed.error or "")
    assert failed_records == []
    after = store.get_record(records[0].record_id)
    assert after is not None and before is not None
    assert after.content_hash == before.content_hash


def test_zero_candidate_parse_is_suspicious_and_preserves_records(
    tmp_path: Path,
) -> None:
    store = LocalDataStore(tmp_path / "store")
    success, records, _ = _collector(store).run_listing(max_details=1)
    assert success.status == IngestionRunStatus.SUCCESS
    existing = store.get_record(records[0].record_id)

    empty_listing = tmp_path / "empty.html"
    empty_listing.write_text("<html><main>No results rendered</main></html>")
    collector = ScholarshipsCollector(
        fetcher=MockFetcher({LISTING_URL: empty_listing}),
        store=store,
    )
    run, result, _ = collector.run_listing(max_details=1)

    assert run.status == IngestionRunStatus.SUSPICIOUS_ZERO
    assert result == []
    assert collector.last_run_sanity["detail_request_count"] == 0
    preserved = store.get_record(records[0].record_id)
    assert preserved is not None and existing is not None
    assert preserved.content_hash == existing.content_hash


def test_unapproved_listing_is_rejected_before_fetch(tmp_path: Path) -> None:
    collector = ScholarshipsCollector(
        fetcher=_AlwaysFailFetcher(),
        store=LocalDataStore(tmp_path / "store"),
    )
    run, records, discovery = collector.run_listing(
        listing_url="https://example.test/scholarships/find-scholarship",
        max_details=1,
    )

    assert run.status == IngestionRunStatus.FAILED
    assert records == []
    assert discovery is None
    assert collector.last_run_sanity["request_count"] == 0


def test_malformed_listing_port_is_rejected_before_fetch(tmp_path: Path) -> None:
    collector = ScholarshipsCollector(
        fetcher=_AlwaysFailFetcher(),
        store=LocalDataStore(tmp_path / "store"),
    )
    run, records, _ = collector.run_listing(
        listing_url=(
            "https://study.anu.edu.au:invalid/"
            "scholarships/find-scholarship"
        ),
        max_details=1,
    )

    assert run.status == IngestionRunStatus.FAILED
    assert records == []
    assert collector.last_run_sanity["request_count"] == 0
