"""Source listing records and optional enrichment; never persist here."""
from urllib.parse import urlsplit
from datetime import datetime
import re
from askanu_scraper.common.models import CommonRecord, Domain
from askanu_scraper.common.normalizer import now_canberra, make_content_hash
from askanu_scraper.common.parser import ParseError


def listing_job(candidate):
    from askanu_scraper.sources.jobs.parser import normalize_job_url, _parse_closing, _normalise_status
    url = normalize_job_url(candidate.url)
    key = urlsplit(url).path.removeprefix("/jobs/")
    m = candidate.listing_metadata
    title = m.get("title")
    if not title:
        raise ParseError("Job listing is missing title evidence")
    now = now_canberra()
    closing_date, closing_at = _parse_closing(m.get("closing_text"))
    status = _normalise_status(m.get("source_status"), closing_date, closing_at, now)
    requisition = m.get("job_id")
    if requisition is not None and not str(requisition).isdigit():
        raise ParseError("Listing requisition is not numeric")
    metadata = {k: m.get(k) for k in ("category", "location", "classification", "salary", "closing_text", "summary")}
    metadata.update(entity_type="job", job_id=key, requisition_id=requisition,
                    employment_types=m.get("employment_types") or [],
                    closing_date=closing_date, closing_at=closing_at.isoformat() if closing_at else None,
                    status=status or "current", role_requirements=None)
    content = "\n".join(f"{k}: {v}" for k, v in {"Title":title, **m}.items() if v)
    return CommonRecord(record_id=f"jobs:job:{key}", entity_id=key, source_id="jobs_anu_search",
        domain=Domain.JOBS, title=title, canonical_url=url, content=content,
        content_hash=make_content_hash(content), collected_at=now, last_seen_at=now, metadata_json=metadata)


def listing_event(candidate):
    from askanu_scraper.sources.events.parser import normalize_event_url
    url = normalize_event_url(candidate.url)
    key = urlsplit(url).path.removeprefix("/events/")
    m = candidate.listing_metadata
    if not m.get("title") or not m.get("date_text"):
        raise ParseError("Event listing is missing title/date evidence")
    # Listing cards publish full month names and may share the year across a range.
    parts = re.split(r"\s+[\u2013\u2014-]\s+", m["date_text"])
    def calendar(value):
        return datetime.strptime(value, "%d %B %Y").date()
    if len(parts) == 2:
        end = calendar(parts[1])
        first = parts[0] if re.search(r"\d{4}$", parts[0]) else f"{parts[0]} {end.year}"
        start = calendar(first)
    elif len(parts) == 1:
        start = end = calendar(parts[0])
    else:
        raise ParseError("Unsupported listing date range")
    if start > end:
        raise ParseError("Listing end date precedes start")
    start_at = end_at = None
    metadata = dict.fromkeys(("source_event_id", "organiser_name", "address", "latitude", "longitude",
                             "category", "registration_url", "source_status", "cancellation_status", "audience"))
    metadata.update(entity_type="event", start_date=start.isoformat(), end_date=end.isoformat() if end else None,
                    start_at=start_at.isoformat() if start_at else None, end_at=end_at.isoformat() if end_at else None,
                    date_precision="timestamp" if start_at else "date", timezone="Australia/Canberra",
                    venue_name=m.get("venue_name"), tags=[])
    content = "\n".join(f"{k}: {v}" for k,v in m.items() if v)
    now = now_canberra()
    return CommonRecord(record_id=f"events:event:{key}", entity_id=key, source_id="events_anu_official",
        domain=Domain.EVENTS, title=m["title"], canonical_url=url, content=content,
        content_hash=make_content_hash(content), collected_at=now, last_seen_at=now,
        effective_from=start_at, effective_to=end_at, metadata_json=metadata)


def enrich(listing, detail):
    if detail.source_id != listing.source_id or detail.domain != listing.domain or detail.canonical_url != listing.canonical_url:
        raise ParseError("Detail canonical/source mismatch")
    m = dict(detail.metadata_json)
    if listing.domain == Domain.JOBS:
        m.update(job_id=listing.entity_id, requisition_id=m["job_id"], role_requirements=m.get("role_requirements"))
        if m.get("status") is None:
            m["status"] = listing.metadata_json["status"]
    else:
        # Detail dates must be supplied by the detail parser, never borrowed from a different occurrence.
        if detail.effective_from is None:
            raise ParseError("Detail lacks exact times; retain listing date evidence")
        m.update(start_date=detail.effective_from.date().isoformat(),
                 end_date=detail.effective_to.date().isoformat() if detail.effective_to else None,
                 date_precision="timestamp")
    data = detail.model_dump(mode="python")
    data.update(entity_id=listing.entity_id, record_id=listing.record_id, metadata_json=m)
    return CommonRecord.model_validate(data)
