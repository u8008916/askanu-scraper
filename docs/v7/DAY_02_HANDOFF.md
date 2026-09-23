# AskANU V7 Day 2 scraper/data handoff

**Gate:** Safe aliases and normalized resolver metadata

**Owner:** Will

**Reviewed merged Day 1 baseline:**
`b1aa0b9b96f34dd393ac3fdd99bc883885317208`

**Approved Day 1 PR head:**
`3c8ef41e1112436775eaee9b9815ef6630a51f53`

**Production mutation:** none

## Outcome

Day 2 adds a read-only shared projection from a validated `CommonRecord` to
the exact metadata the frozen resolver may consume:

- canonical names from the record's published title;
- explicit identifiers from the reviewed Day 1 producer contract;
- reviewed source aliases, if a future approved contract supplies them;
- source authority copied from the existing registry;
- source-present year, date and aware-datetime values; and
- deterministic collision and duplicate reports that do not rank, merge or
  resolve records.

The projection does not change stable IDs, content, hashes or serialized
records. It does not create conversational state or retrieval behaviour.

## Exact lookup-term semantics

Normalization is identical for every domain:

1. Unicode NFC normalization.
2. Whitespace collapse and edge trimming.
3. Unicode case folding.
4. Punctuation, word order and wording remain unchanged.

The original value and its source path remain alongside the normalized form.
Identifiers are lookup terms, not aliases and not replacements for stable
identity. The current reviewed producer contract has zero `source_alias`
paths, so Day 2 generates zero synonyms.

| Record shape | Canonical name | Explicit identifier | Generated alias |
|---|---|---|---|
| Course | exact source title | course code | none |
| Program | exact source title | program code | none |
| Scholarship | exact source title | none | none |
| Job | exact source title | requisition ID | none |
| Residence | exact source title | none | none |
| Support service | exact source title | none | none |
| Event | exact source title | source event ID | none |

The existing COMP1100 title discrepancy remains visible: the fixture/parser
produces `COMP1100 Programming as Problem Solving`, while the representative
schema example omits the code. Day 2 preserves the actual record title and
does not invent a stripped-title alias pending Qasim/Carmen review.

## Temporal resolver semantics

| Record shape | Resolver values | Missing-value rule |
|---|---|---|
| Course / Program | `academic_year`, precision `year` | required by frozen record contract; never inferred |
| Scholarship | `opening_date` -> `opens_on`; `closing_date` -> `closes_on`, precision `date` | absent date produces no entry; never record validity |
| Job | `closing_date` -> `closes_on`; `closing_at` -> `closes_at` | date-only never gains a time; undated remains absent |
| Residence / Support | none | no temporal source field is invented |
| Event | `start_at` -> `starts_at`; `end_at` -> `ends_at`, precision `datetime` | no missing end inference; explicit event timezone retained |

ISO dates are validated and emitted canonically. Datetimes must be
timezone-aware and are emitted using `datetime.isoformat()`. The projection
never attaches a timezone to a naive value. Jobs retain the offset already in
`closing_at`; Events also retain the explicit `Australia/Canberra` field.

## Collision and duplicate semantics

- A normalized term attached to multiple stable record IDs is reported as a
  collision with every record/source/kind reference.
- A repeated stable record ID is reported separately as a duplicate.
- Repeating the same record does not manufacture a term collision.
- Same-code Courses in different academic years correctly collide on code and
  title while retaining distinct year-qualified `entity_id`/`record_id`.
- The scraper does not choose a winner, use authority as ranking, infer the
  intended year, merge official/Rubric Events, or emit `EMPTY`/`NO_MATCH`.

Those decisions belong to Carmen's frozen resolver and reasoning contracts.

## Unsupported aliases and filters

Unsupported aliases:

- course/program paraphrases, acronyms or code-stripped titles not explicitly
  published as separate source facts;
- residence nicknames or location-derived names;
- scholarship, job, support-service or event shorthand;
- typo expansions, stemming, punctuation removal and generated synonyms; and
- treating URL slugs or inferred concepts as user-facing names.

Unsupported deterministic filters:

- numeric salary, scholarship-value or accommodation-rate ranges derived from
  source wording;
- personal course admission, scholarship eligibility, job suitability or
  support-service outcome;
- inferred residence vacancy;
- event modality inferred from venue/location;
- Rubric ticket availability inferred from status or ticket windows; and
- any content-only fact treated as a complete structured population.

Missing or prose-only evidence must remain visible as unknown/content-only; it
must not become false, a hard-filter exclusion or `NO_MATCH`.

## Carmen fixture handoff

`fixtures/v7/day2/resolver-search-metadata.json` contains eight offline cases
covering Course, Program, Scholarship, Job, Residence, Support, official Event
and Rubric Event records. Every case points to a checked-in parser fixture and
freezes:

- stable `record_id`;
- original/normalized lookup terms, kind and source path; and
- temporal kind, canonical value, precision, source path and explicit timezone.

The fixture permits no network calls. Carmen may reproduce the projection but
must not interpret normalized terms as synonyms, term collisions as rankings,
or absent temporal entries as false/no-match.

## Risks and dependencies

- Day 1 PR #36 is merged at
  `b1aa0b9b96f34dd393ac3fdd99bc883885317208`. Day 2 is rebased onto that
  frozen producer-capability baseline and no longer depends on an open branch.
- Qasim/Carmen must resolve or explicitly accept the COMP1100 title-example
  discrepancy before adding a stripped-title alias.
- Normalized collisions are expected across academic years and may occur for
  duplicate titles across all domains. Downstream resolution must use typed
  entity/domain/context and clarify genuine ambiguity.
- Rubric remains rank 3 `APPROVED_BOUNDED_UNSUPPORTED`, ingestion-only and
  source-distinct. This work does not make it an official ANU source or a live
  RAG dependency.
- New aliases, identity fields, temporal semantics, filters or source authority
  require the existing shared review/change workflow.

## Exact Day 2 gate evidence

- Latest reviewed `origin/main` verified after fetch:
  `b1aa0b9b96f34dd393ac3fdd99bc883885317208` (merged PR #36).
- Approved Day 1 source head:
  `3c8ef41e1112436775eaee9b9815ef6630a51f53`.
- New Day 2 files:
  `src/askanu_scraper/common/search_metadata.py`,
  `fixtures/v7/day2/resolver-search-metadata.json`,
  `tests/test_v7_day2_search_metadata.py`, and this handoff.
- Focused command:
  `py -m pytest tests/test_v7_day2_search_metadata.py -q`.
- Focused result: **16 passed**.
- Full command: `py -m pytest`.
- Full result: **413 passed** (clean merged Day 1 baseline **397 passed** + 16 Day 2
  tests).
- Handoff parser cases: **8/8 passed**.
- Source registry changes: **0**.
- Serialized schema/parser/collector changes: **0**.
- Stable ID/content-hash mutations caused by projection: **0**.
- Live institutional source requests: **0**.
- DB writes, cloud executions, deployments and scheduler changes: **0**.
- Pre-existing uncommitted Day 17/detail-coverage files were not modified or
  included.

The Day 2 implementation is ready for review directly against merged `main`.
Carmen still needs to confirm the fixture semantics before the Day 2 gate.
