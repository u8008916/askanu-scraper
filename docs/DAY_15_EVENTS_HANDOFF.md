# Day 15 Events handoff

## Release result

The official sixth-domain local ingestion path is implemented against
`https://www.anu.edu.au/events`. The frozen Canberra-local release
window is **19 September through 31 October 2026 inclusive** (43 calendar
days), using interval overlap so an exhibition that began earlier remains
eligible while active in the window.

The final bounded live dry-run was successful and non-persisted:

- local run ID: `run_b4e70788d5ce` (not a Cloud or database run ID)
- six listing pages traversed (`page=0` through `page=5`)
- 34 raw cards, 33 unique detail links, one page-boundary duplicate
- 30 eligible and accepted events; three details outside the window
- entity coverage: 30/30 (100%)
- recognized source-present v1 facts: 320/320 (100%)
- zero duplicate event IDs, record IDs, or canonical URLs

The preliminary denominator of 29 changed by +1 when the implemented collector
recomputed the complete source. The authoritative frozen denominator for this
handoff is therefore 30. Drift is evidence, not deletion proof.

## Contract and safety

Identity is the numeric Drupal node ID cross-checked between
`data-history-node-id` and page metadata. A record uses
`events:event:<node ID>` and an exact same-origin
`https://www.anu.edu.au/events/<slug>` canonical URL. Displayed dates and times
are parsed in `Australia/Canberra`, including the October DST transition.
Date-only pages do not receive invented times. Exact times mirror into
`effective_from` and `effective_to`.

The parser preserves explicit location, format, presenter/organiser,
categories, tags, description, registration destinations, status and
cancellation wording. It does not treat a contact person as organiser, infer a
format, fetch registration destinations, or execute embedded markup. A
published cancellation remains an ingestible event.

The official ICS export disagreed with displayed HTML times during source
inspection. That discrepancy is a source anomaly; displayed HTML is
authoritative and ICS is not used for normalized time values.

## Representative provenance

```text
record_id:     events:event:97875
canonical_url: https://www.anu.edu.au/events/2026-indonesia-update-islamic-diversity-in-indonesia
content_hash:  b63510700c58a845227579e2c2c4ca9ee0156773150da05b0037b08625ed41bc
start_at:      2026-09-18T09:00:00+10:00
end_at:        2026-09-19T17:00:00+10:00
```

This earlier-starting event is included because its published interval overlaps
19 September.

## Reproducible manual fallback

Run from the repository virtual environment in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m askanu_scraper.job `
  --source-id events_anu_official --domain events --dry-run `
  --max-events-listing-pages 6 --max-event-details 100 `
  --events-window-start 2026-09-19 --events-window-days 43 `
  --expected-event-count 30 --storage-path .test-tmp-day15-live
```

The collector waits at least one second between live requests. A zero result,
incomplete pagination, canonical/identity conflict, duplicate normalized
identity, detail failure, or result below `ceil(0.99 * 30) = 30` fails before
record persistence and preserves last-known-good.

## Persistence and freshness gates

Fixture-backed tests prove dry-run, first local `NEW`, identical `UNCHANGED`,
changed hash with stable identity, atomic/failure preservation, temporal edge
cases, cancellation, deduplication, and the coverage gate. The live run above
was dry-run and wrote nothing.

There is no verifiable Events migration or Qasim/Carmen approval reference in
this repository. Consequently:

- `SCRAPER_EVENTS_POSTGRES_APPROVED=false` remains the default;
- no PostgreSQL write was attempted;
- no image was deployed;
- no Cloud Run Job or Scheduler resource was created; and
- no Cloud execution ID or persisted ingestion run ID is claimed.

The proposed future shape is a separate `askanu-scraper-events` Cloud Run Job
with a daily 03:45 `Australia/Canberra` schedule, avoiding the existing 03:15
job. Until migration and release approval are evidenced, the command above is
the manual read-only fallback.

At the time of the official-source run, Rubric had not yet been activated. The
later bounded-ingestion decision is recorded below. No Friday feedback change
was applied because no accepted issue and approved-source example were
provided.

Machine-readable evidence is in `day15-events-evidence.json`.

The final Rubric-inclusive repository regression collected and passed 365/365
tests. Pytest emitted one non-test cache-permission warning; the isolated test
temporary directory and test outcomes were unaffected.

## Rubric bounded-ingestion update (2026-09-20)

Qasim's later full handoff supersedes the old `PENDING_APPROVAL` state. Rubric
is now `APPROVED_BOUNDED_UNSUPPORTED`: approved for paced, cached ingestion,
but not a supported API, an official-ANU classification or a production-write
authorization.

The fixture-backed adapter now proves pagination, ANU university scoping,
deduplication before details, source-qualified identity, optional/missing end
times, request pacing, transient retries, per-run caching, canonical URLs,
draft/window exclusions, dry-run, `NEW`/`UNCHANGED`/`CHANGED`, suspicious zero,
incomplete pagination, detail failure and last-known-good. Ambiguous
`eventStatus`, `ticketsPossiblyAvailable` and sale windows are not normalized
into unsupported user claims.

No live Rubric denominator or combined-source coverage percentage is claimed.
The handoff did not include the exact search request URL or the underlying
sanitized captures, and no such artifact exists in the workspace. The job
therefore requires `SCRAPER_RUBRIC_SEARCH_ENDPOINT` and rejects missing,
off-host or unreviewed targets before any request. The observed all-search
count of 119 is explicitly not the release denominator.

Rubric PostgreSQL writes remain blocked by
`SCRAPER_RUBRIC_POSTGRES_APPROVED=false`. RAG, App, deployment and E2E evidence
remain unavailable because those repositories are not in this workspace. See
`DAY_15_RUBRIC_SOURCE_DECISION.md` and
`DAY_15_EVENTS_RETRIEVAL_CONTRACT.md` for the source and cross-repo handoffs.
