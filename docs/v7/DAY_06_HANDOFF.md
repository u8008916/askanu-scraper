# V7 Day 6 — Jobs, Events, Support and data-contract freeze

Owner: Will  
Lane: scraper/data  
Prepared: 2026-09-28 (Australia/Sydney)

## Outcome

The producer-side Day 6 contract is feature-frozen. The checkpoint adds no
source, field, inference, parser behaviour, canonical content, persistence,
schedule, or production mutation. It records and tests the existing Jobs,
Events, and Support evidence boundaries.

Final consumer acceptance remains pending because no Carmen Day 6 RAG SHA was
published when this checkpoint was prepared. The mismatch count is therefore
unknown rather than zero.

## Jobs

Known canonical Job records retain source-backed identity, employment,
location, classification, salary, closing, status, and summary fields. They
can support a factual answer about a known record.

The current supported Jobs population is not established as complete. The
last source-health evidence is `FALLBACK_LAST_KNOWN_GOOD`, and exhaustive
queries must retain `INCOMPLETE_POPULATION` semantics. A zero candidate result
cannot become “there are no technical jobs.” Atomic collection and
last-known-good protection remain unchanged.

## Events

Official ANU Events and approved bounded Rubric community events retain
separate source IDs, identities, authority ranks, and approval states. The
Upcoming Events product surface may select official records only; Events chat
may use both stored sources. This is enabled by provenance metadata and does
not authorize a live Rubric request from App or RAG.

Exact datetimes remain timezone-aware. Missing end times stay null; missing
venues do not imply online modality; source status and cancellation status
remain separate. Ticket availability and modality are not inferred.

## Support

The producer retains source-backed service identity, purpose, audiences,
contacts, access, hours, cost, topics, and referrals. The Academic fixture
retains the published Grade Appeal topic. No synthetic student-language alias
dictionary or case adjudication is added; natural wording resolution remains
the RAG layer’s responsibility.

## Feature freeze

Frozen for the release candidate:

- approved source scope and authority;
- canonical identity and six-domain record semantics;
- lookup/search, freshness, temporal, missing/unknown, and population
  completeness semantics;
- Accommodation price evidence;
- Jobs atomicity and incomplete-population behaviour;
- official/Rubric Events distinction;
- Scholarship matching versus eligibility boundary; and
- Support evidence versus reasoning boundary.

After this checkpoint, only verified correctness, identity, normalisation,
provenance, safety, and release-blocking defects may change producer behaviour.

## Change and release impact

- Canonical retrieval content changed: **NO**
- Reindex required: **NONE**
- Production backfill initiated: **NO**
- Production writes, migrations, scheduler changes: **NO**

Status: **D6 PRODUCER DATA/EVIDENCE READY; DATA CONTRACT FEATURE FREEZE;
CROSS-REPO ACCEPTANCE PENDING**.
