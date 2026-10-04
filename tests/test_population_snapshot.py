"""Population-first snapshot membership and legacy identity regression tests."""
from __future__ import annotations

from askanu_scraper.common.models import (
    CommonRecord,
    IngestionRun,
    IngestionRunStatus,
    RecordStatus,
)
from askanu_scraper.common.normalizer import now_canberra
from askanu_scraper.common.snapshot import plan_snapshot
from askanu_scraper.common.storage import LocalDataStore
from askanu_scraper.sources.events.discovery import EventCandidate
from askanu_scraper.sources.jobs.discovery import JobCandidate
from askanu_scraper.sources.population import listing_event, listing_job


def successful_run(source_id: str, suffix: str) -> IngestionRun:
    return IngestionRun(
        run_id=f"run_population_{suffix}",
        source_id=source_id,
        started_at=now_canberra(),
        status=IngestionRunStatus.SUCCESS,
    )


def job_record(
    slug: str,
    *,
    title: str,
    requisition_id: str,
):
    return listing_job(
        JobCandidate(
            url=f"https://jobs.anu.edu.au/jobs/{slug}",
            listing_metadata={
                "title": title,
                "job_id": requisition_id,
                "category": "Professional",
                "employment_types": ["Fixed Term"],
                "location": "Canberra / ACT",
                "classification": None,
                "salary": None,
                "closing_text": None,
                "source_status": "current",
                "summary": None,
            },
        )
    )


def event_record(
    slug: str,
    *,
    title: str,
    date_text: str,
):
    return listing_event(
        EventCandidate(
            url=f"https://www.anu.edu.au/events/{slug}",
            listing_metadata={
                "title": title,
                "date_text": date_text,
                "venue_name": None,
            },
        )
    )


def test_complete_snapshot_marks_unobserved_job_missing(tmp_path) -> None:
    store = LocalDataStore(tmp_path / "store")

    first = job_record(
        "first-current-role",
        title="First current role",
        requisition_id="111111",
    )
    second = job_record(
        "second-current-role",
        title="Second current role",
        requisition_id="222222",
    )

    first_run = successful_run("jobs_anu_search", "jobs_first")
    first_results = store.save_complete_snapshot(
        [first, second],
        first_run,
    )

    assert len(first_results) == 2
    assert first_run.records_added == 2
    assert first_run.records_missing == 0

    observed_again = job_record(
        "first-current-role",
        title="First current role",
        requisition_id="111111",
    )

    second_run = successful_run("jobs_anu_search", "jobs_second")
    second_results = store.save_complete_snapshot(
        [observed_again],
        second_run,
    )

    assert len(second_results) == 1
    assert second_run.records_missing == 1

    missing = store.get_record(second.record_id)

    assert missing is not None
    assert missing.status == RecordStatus.MISSING


def test_jobs_canonical_reconciliation_preserves_legacy_numeric_identity() -> None:
    listing = job_record(
        "senior-consultant-user-experience",
        title="Senior Consultant",
        requisition_id="563693",
    )

    legacy_data = listing.model_dump(mode="python")
    legacy_data["record_id"] = "jobs:job:563693"
    legacy_data["entity_id"] = "563693"

    legacy_metadata = dict(legacy_data["metadata_json"])
    legacy_metadata["job_id"] = "563693"
    legacy_metadata["requisition_id"] = "563693"
    legacy_data["metadata_json"] = legacy_metadata

    legacy = CommonRecord.model_validate(legacy_data)

    run = successful_run("jobs_anu_search", "jobs_legacy")

    reconciled, missing = plan_snapshot(
        [listing],
        [legacy],
        run,
    )

    assert missing == []
    assert len(reconciled) == 1
    assert reconciled[0].record_id == "jobs:job:563693"
    assert reconciled[0].entity_id == "563693"
    assert reconciled[0].metadata_json["job_id"] == "563693"
    assert reconciled[0].metadata_json["requisition_id"] == "563693"
    assert reconciled[0].canonical_url == listing.canonical_url


def test_events_canonical_reconciliation_preserves_legacy_numeric_identity() -> None:
    listing = event_record(
        "canberra-dst-exhibition",
        title="Canberra DST exhibition",
        date_text="3 October 2026 – 4 October 2026",
    )

    legacy_data = listing.model_dump(mode="python")
    legacy_data["record_id"] = "events:event:1002"
    legacy_data["entity_id"] = "1002"

    legacy_metadata = dict(legacy_data["metadata_json"])
    legacy_metadata["source_event_id"] = "1002"
    legacy_data["metadata_json"] = legacy_metadata

    legacy = CommonRecord.model_validate(legacy_data)

    run = successful_run("events_anu_official", "events_legacy")

    reconciled, missing = plan_snapshot(
        [listing],
        [legacy],
        run,
    )

    assert missing == []
    assert len(reconciled) == 1
    assert reconciled[0].record_id == "events:event:1002"
    assert reconciled[0].entity_id == "1002"
    assert reconciled[0].metadata_json["source_event_id"] == "1002"
    assert reconciled[0].canonical_url == listing.canonical_url
