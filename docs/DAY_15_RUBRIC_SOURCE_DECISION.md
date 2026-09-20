# Day 15 Rubric source decision

## Decision

Rubric is `APPROVED_BOUNDED_UNSUPPORTED` for AskANU ingestion. Qasim reported
written permission from Rubric to use the endpoints backing its public event
search. This is permission to collect conservatively, not a supported API SLA,
an official-ANU classification, or production-write authorization.

The permission narrative was supplied in the Day 15 full handoff on
2026-09-20. The underlying email/reference and sanitized request/response
captures are not present in this repository. Qasim must attach or cite those
artifacts during PR review. This document deliberately does not invent an
approval ID, correspondent, date, endpoint path, header or payload field.

## Known reviewed contract

- Public search surface: `https://campus.hellorubric.com/search`.
- Search operation: `getUnifiedSearch`.
- ANU selection: country `AU`, state `Australian Capital Territory`, university
  ID `1`, desired type `events`, ascending date order, limit/offset pagination.
- Public detail URL: `https://campus.hellorubric.com/?eid=<eventId>`.
- Known detail endpoint:
  `https://appserver.getqpay.com:9090/AppServerSwapnil/event/details`.
- Primary flow: complete bounded search pagination, deduplicate IDs, fetch one
  detail per unique ID, normalize, validate, then persist only after release
  approval.

The frozen producer identity is `source_event_id=<numeric event ID>`,
`entity_id=rubric-<numeric event ID>`, and
`record_id=events:event:rubric-<numeric event ID>`. The shared persisted
metadata uses the exact Events vocabulary in `DATA_SCHEMA.md`. In particular,
Rubric `eventStatus`, ticket availability, missing price, missing venue,
missing registration and draft state are not converted into unsupported user
claims.

The handoff does not contain the exact search request URL. The implementation
therefore requires `SCRAPER_RUBRIC_SEARCH_ENDPOINT`; it has no guessed default
and accepts only HTTPS port 9090 paths under
`appserver.getqpay.com/AppServerSwapnil/`. This is the quantified blocker for a
live Rubric census.

## Safety boundary

- At least one second between requests; maximum pages/details are explicit.
- One detail request per deduplicated event ID and one in-run cached response.
- Bounded transient retry, timeout, malformed-response and suspicious-zero
  guards preserve last-known-good.
- No cookies, authorization tokens or authenticated endpoints.
- `eventStatus` is not treated as modality.
- `ticketsPossiblyAvailable` is not treated as remaining availability.
- Ticket-sale end is not treated as event end.
- `SCRAPER_RUBRIC_POSTGRES_APPROVED=false` is the default.
- RAG/API code reads stored records and never invokes Rubric synchronously.

The committed JSON fixtures are synthetic sanitized contract fixtures derived
from documented fields. They are not represented as verbatim production
captures and do not replace Qasim's missing artifacts.
