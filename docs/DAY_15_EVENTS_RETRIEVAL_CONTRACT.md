# Day 15 stored Events retrieval contract

This handoff is for Carmen/Ben implementation in the unavailable RAG/App
repositories. It does not authorize network calls from a user request path.

## Corpus selection

- Dedicated Upcoming Events: include only `source_id=events_anu_official`.
- Events chat: include stored `events_anu_official` and
  `rubric_unified_search` records.
- Source cards expose the stored `source_id`, canonical URL and source label.
- Freshness is ingestion-owned. `/api/v1/ask` performs no Events/Rubric HTTP
  request.

## Deterministic temporal behavior

Interpret `start_at`/`end_at` in `Australia/Canberra`. The current bounded
official census contains no date-only records. Because the shared persisted
contract has no date-only boundary fields, a future date-only official record
blocks ingestion for contract review rather than receiving invented times. A
Rubric record with no end is a point event for window filtering; retrieval
must not invent duration.

Upcoming excludes records whose known end is before now; when no end exists,
compare the start. Today, tomorrow, Friday, weekend, this week, next week and
explicit ranges are calendar boundaries in Canberra, not model judgment.
Sort chronologically by start, then normalized title, then record ID.

Cancelled records remain retrievable for an exact lookup and must be labelled;
they are excluded from default upcoming recommendations unless the caller asks
about cancellations. Missing timeframe in an exploratory Events question
requires clarification. No match returns no-evidence behavior.

## Cross-source duplicate presentation

Persist both records. At retrieval, consider two cross-source candidates the
same real-world event only when:

1. normalized titles are equal;
2. exact starts are within 15 minutes, or both are date-only on the same date;
3. at least one non-empty strong corroborator matches: normalized
   `venue_name` or `organiser_name`.

Do not merge on title alone. Within a duplicate group, present the official
record and retain the Rubric canonical URL as alternate provenance. Same-title
events at different times or without a matching corroborator remain separate.

## Evidence rules

- Never infer online/in-person from Rubric `eventStatus`.
- Never describe `ticketsPossiblyAvailable` as tickets remaining.
- Never equate a ticket-sale window with the event interval.
- Missing venue, price, availability or registration state stays unknown.
- Registration URLs are shown only when stored.
- `cancellation_status` carries only explicit cancellation semantics;
  `source_status` is separate and remains null when unsupported.

The companion `fixtures/events/events-retrieval-contract.json` freezes the
official-only, broad-chat and duplicate/non-duplicate examples for porting into
the RAG capability suite.
