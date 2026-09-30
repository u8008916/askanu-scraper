# V7 Day 6 — Jobs, Events, Support and data-contract freeze

Owner: Will  
Lane: scraper/data  
Verified: 2026-09-30 (Australia/Sydney)

## Outcome

The producer-side Day 6 contract remains feature-frozen and has been replayed
cleanly onto final Day 5 `b829ffcf943653e5e36496109f29f116bea015a8`.
The exact consumer audit against Carmen RAG Day 6
`1875a4be816eeec2aeeacc0cfb4ff6fd6228f881` is complete: **Jobs FAIL,
Events FAIL, Support PASS**. No producer data was changed to hide the failures.

## Restack proof

- Old Day 6 head: `e9c6ce2817f12d190a07dbe85a297bab6e4c6deb`
- Old parent: `9e50fa0996d1110524da678675f97e1ff8a4378c`
- New parent: `b829ffcf943653e5e36496109f29f116bea015a8`
- Pure replay: `c379cadb631d97aeadc8acb828be4f62915ab9a5`
- Conflicts: **0**
- Manual resolutions: **0**
- Stable Day 6 patch ID before/after: identical,
  `10c0d890296294d984b484ad1da413cd8e6c07f8`

The old and replay trees are not identical solely because the replay inherits
the finalized Day 5 ledger. Their changed-file list is exactly the three Day 5
evidence files. The genuine Day 6 delta remains byte-equivalent.

## Jobs producer capability

Known canonical Job records retain source-backed identity, employment,
location when published, category, classification, salary, closing, status,
and summary fields. They can support factual answers about known records.

The current supported Jobs population is not established as complete. The
latest source-health evidence is `FALLBACK_LAST_KNOWN_GOOD`, and exhaustive
queries must retain `INCOMPLETE_POPULATION` semantics. A zero candidate result
cannot become “there are no technical jobs.” Atomic collection and
last-known-good protection remain unchanged.

The latest bounded audit advertised 56 Jobs but stopped after 7 successful
details and 3 consecutive empty responses. Within those 7 records, employment
type, category and classification were source-present for 7/7; location was
source-present for 0/7. The representative captured fixture proves that
`Canberra / ACT, ACT, Australia, 2601`, `Fixed Term`, `Professional`, and
`ANU Officer 8 (Administration)` are real source-backed shapes, but it does not
make location population-wide reliable.

| Constraint | Producer path | Latest evidence | Safe zero-match meaning |
|---|---|---|---|
| Employment type | `metadata_json.employment_types` | 7/7 before failure; source wording preserved | No supported stored match, while retaining `INCOMPLETE_POPULATION` |
| Category | `metadata_json.category` | 7/7 before failure; source wording preserved | No supported stored match, while retaining `INCOMPLETE_POPULATION` |
| Classification | `metadata_json.classification` | 7/7 before failure; exact value such as `ANU Officer 8 (Administration)` | No supported stored match, while retaining `INCOMPLETE_POPULATION` |
| Location | `metadata_json.location` | 0/7 in the latest partial audit; one older captured fixture has Canberra wording | Cannot reliably apply or verify this filter |
| Remote/work arrangement | none | Not in the frozen producer contract | Cannot reliably apply or verify this filter |
| Role requirements | none | Not in Jobs v1; 0/7 source-present in the audit | Not a producer-supported field |

The RAG Day 6 model requires `role_requirements` and its journey fixtures
populate it, while scraper Jobs v1 requires exactly 12 metadata keys and rejects
that extra key. This is a **SHARED CONTRACT DECISION REQUIRED**; it is not
approval to expand the producer. RAG also cannot treat unsupported remote/work-
arrangement or currently unreliable location constraints as genuine evaluated
zero matches. Jobs therefore **FAILS** consumer alignment.

## Events

Official ANU Events and bounded Rubric community events retain separate source
IDs, identities, authority ranks, and approval states. Upcoming Events may use
official records only; Events chat may use both stored sources. No live App/RAG
Rubric dependency is authorized.

Exact datetimes remain timezone-aware. Missing end times stay null; missing
venues do not imply online modality; source status and cancellation status
remain separate. Ticket availability and modality are not inferred.

Record shape, source identity and official-versus-community provenance pass.
Source-health semantics do not: RAG Day 6 marks Event discovery ResultSets as
population-complete even though official Events remains blocked at 29 eligible
unique records against the frozen denominator 30 and Rubric still lacks a live
denominator. Events therefore **FAILS** until the consumer preserves that gate.

## Support

The producer retains source-backed service identity, purpose, audiences,
contacts, access, hours, cost, topics, and referrals. The Academic fixture
retains the published Grade Appeal topic. No synthetic student-language alias
dictionary or case adjudication is added; natural wording resolution remains
the RAG layer’s responsibility.

RAG consumes the frozen Support shape, keeps referral navigation distinct,
preserves missing contact/hours/access as unknown, and owns the natural-language
routing layer. Support **PASSES**. The producer continues to require external,
credential-free HTTP(S) referral URLs and rejects ANUSA-host referrals.

## Exact consumer mismatch ledger

1. Jobs `role_requirements`: **SHARED CONTRACT DECISION REQUIRED**.
2. Jobs remote/work arrangement: **CONSUMER FIX REQUIRED**; no producer field.
3. Jobs location applicability: **CONSUMER FIX REQUIRED**; current population
   evidence does not support treating this as a reliably evaluated hard filter.
4. Events population completeness: **CONSUMER FIX REQUIRED**.

## Feature freeze and impact

No source, field, inference, parser behaviour, canonical content, persistence,
schedule, production mutation, crawl, migration, backfill, reindex, or
re-embedding was introduced.

- Canonical retrieval content changed: **NO**
- Reindex/re-embedding required: **NO**
- Production actions: **0**

Status: **D6 PRODUCER DATA/EVIDENCE READY; JOBS FAIL; EVENTS FAIL; SUPPORT PASS;
CROSS-REPO ACCEPTANCE FAIL; MERGE HOLD**.
