"""Pure complete-population planning, including canonical legacy reconciliation."""
from askanu_scraper.common.models import CommonRecord, RecordStatus, IngestionRunStatus

SOURCES = {"jobs_anu_search", "events_anu_official"}


def plan_snapshot(records, previous, run):
    if run.source_id not in SOURCES or run.status != IngestionRunStatus.SUCCESS:
        raise ValueError("Complete snapshots require an approved source and successful discovery")
    if not records:
        raise ValueError("Empty population requires explicit source review")
    if any(r.source_id != run.source_id for r in records):
        raise ValueError("Snapshot contains another source")
    if len({r.record_id for r in records}) != len(records) or len({r.canonical_url for r in records}) != len(records):
        raise ValueError("Duplicate snapshot identity/canonical URL")
    by_url = {}
    for old in previous:
        if old.source_id != run.source_id:
            raise ValueError("Previous snapshot contains another source")
        if old.canonical_url in by_url:
            raise ValueError("Existing duplicate canonical URL requires reconciliation review")
        by_url[old.canonical_url] = old
    reconciled = []
    for record in records:
        old = by_url.get(record.canonical_url)

        if old is not None and record.record_id != old.record_id:
            data = record.model_dump(mode="python")
            data.update(record_id=old.record_id, entity_id=old.entity_id)
            if run.source_id == "jobs_anu_search":
                data["metadata_json"]["job_id"] = old.entity_id
            elif old.entity_id.isdigit():
                data["metadata_json"]["source_event_id"] = old.entity_id
            record = CommonRecord.model_validate(data)

        reconciled.append(record)
    observed = {r.record_id for r in reconciled}
    missing = [r.model_copy(update={"status": RecordStatus.MISSING}) for r in previous
               if r.record_id not in observed and r.status != RecordStatus.MISSING]
    return reconciled, missing
