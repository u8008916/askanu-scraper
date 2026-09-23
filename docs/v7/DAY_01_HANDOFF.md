# AskANU V7 Day 1 scraper/data handoff

**Gate:** Freeze shared V7 contracts

**Owner:** Will

**Reviewed base:** `main` / `origin/main` at
`98e10cd6a3fc7979749bf03ea3e7e885fe961a93`

**Production mutation:** none

## Outcome

The six-domain producer inventory is now executable and fixture-backed without
changing the serialized record contract. `common/v7_contract.py` classifies
stable identity, structured facts, content-only facts, known absent facts and
producer evidence support through one shared primitive. It also projects safe
lookup terms from validated records.

The current reviewed sources publish no separate alias field. The safe Day 1
result is therefore deliberately narrow:

- canonical source title is a `canonical_name`;
- an explicit source code/ID is an `identifier` where the frozen contract has
  one; and
- there are currently zero `source_alias` paths.

Normalization performs only Unicode NFC normalization, whitespace collapse and
case folding. It does not remove punctuation, expand abbreviations, stem words
or add synonyms. Adding an alias later requires explicit source evidence and a
reviewed producer-contract change.

## Stable identity and fact inventory

| Record shape | Stable identity | Structured source facts | Content-only source facts | Explicitly unsupported / unknown |
|---|---|---|---|---|
| Course | source + type + course code + academic year; canonical URL | career, units, delivery mode, prerequisites, incompatibilities, assumed knowledge, offerings | description, learning outcomes, corequisites | personal eligibility, guaranteed enrolment |
| Program | source + type + program code + academic year; canonical URL | career, units, duration, delivery mode, learning outcomes | overview, requirements, admission requirements, prerequisites, minors, elective/study options | personal admission outcome, guaranteed entry |
| Scholarship | source + canonical URL slug; canonical URL | featured/status/application-required, four filter arrays, value, selection basis, dates, eligibility wording | description, application wording/period, scholarship/study type | personal eligibility decision, award probability |
| Job | source + numeric requisition ID; canonical URL | category, employment types, location, classification, salary wording, closing evidence/status, summary | none outside the frozen metadata shape | personal suitability, application outcome |
| Residence | source + canonical residence slug; canonical URL | category, location, catering, audiences, rate wording, rooms, features, overview, accessibility, application/contact facts, explicit vacancy only | none outside the frozen metadata shape | inferred vacancy, personal room offer |
| Support service | source + top-level category slug; canonical URL | category, purpose, audiences, contact, published hours/access/cost, topics, unfetched referrals | none outside the frozen metadata shape | case-specific advice, service outcome |
| Event | source + source event ID; canonical URL | start/end/timezone, organiser, venue/address/coordinates, category/tags, registration, source/cancellation status, audience | description, format, displayed date wording | inferred modality, inferred ticket availability |

Null still means no supported evidence. An empty list retains only the existing
frozen exceptions and semantics in `DATA_SCHEMA.md`; this work adds no new null
or empty-list interpretation.

## Source authority inventory

| Source ID | Domain | Rank | Approval classification | V7 boundary |
|---|---|---:|---|---|
| `courses_programs_and_courses` | Courses | 1 | `APPROVED` | Official Programs & Courses |
| `scholarships_anu_finder` | Scholarships | 1 | `APPROVED` | Official ANU scholarship finder/details |
| `jobs_anu_search` | Jobs | 1 | `APPROVED` | Official public ANU Jobs |
| `accommodation_anu_study` | Accommodation | 1 | `APPROVED` | Official public residence pages; StarRez link-only |
| `support_anusa_student_assistance` | Support | 2 | `APPROVED` | Frozen ANUSA Student Assistance categories |
| `events_anu_official` | Events | 1 | `APPROVED` | Official-only Upcoming Events source |
| `rubric_unified_search` | Events | 3 | `APPROVED_BOUNDED_UNSUPPORTED` | Ingestion-only community events; never reclassified as official |

The executable handoff reads these values from the existing machine-readable
registry. Approval permits only the registry's bounded collection mode; it is
not a production-write or deployment approval.

## Producer capability matrix

These labels describe the evidence the producer can hand to retrieval. They do
not claim that the RAG/app already implements or passes an end-to-end V7 intent.

| Record shape | Lookup | Discovery | Filter | Compare | Match |
|---|---|---|---|---|---|
| Course | reliable | reliable | reliable | reliable | content-only |
| Program | reliable | reliable | reliable | reliable | content-only |
| Scholarship | reliable | reliable | reliable | reliable | content-only |
| Job | reliable | reliable | reliable | reliable | absent |
| Residence | reliable | reliable | reliable | reliable | content-only |
| Support service | reliable | reliable | reliable | content-only | absent |
| Event | reliable | reliable | reliable | content-only | absent |

Definitions:

- `reliable`: a deterministic path is backed by frozen structured producer
  fields, subject to record-level nulls and source freshness.
- `content-only`: the relevant source wording is retained, but not represented
  as a complete deterministic structure. Retrieval/reasoning must expose
  missingness and provenance.
- `absent`: the approved producer record does not carry enough evidence to
  support the operation safely.

## Representative handoff fixtures

`fixtures/v7/day1/producer-capabilities.json` contains eight offline cases:

1. Course and program records, covering both frozen Courses record shapes.
2. Scholarship, Job, Accommodation and Support records.
3. One official ANU Event and one source-distinct Rubric Event.

Each case points to an existing checked-in source fixture and freezes the
expected domain, entity type, source, record ID and exact lookup terms. Parser
tests build the records; the handoff does not carry invented normalized rows.
Rubric remains ingestion-only, separately sourced by `source_id`, and creates
no RAG/frontend live dependency.

## Producer gaps versus other-repository gaps

Producer/data gaps:

- Majors, minors and specialisations are discovered for census purposes but
  are not serialized record shapes under the frozen v1 contract. Persisting
  them would require an explicit shared schema decision; Day 1 does not do so.
- The checked-in COMP1100 fixture and existing parser assertion produce title
  `COMP1100 Programming as Problem Solving`, while the representative identity
  in `DATA_SCHEMA.md` shows `Programming as Problem Solving`. Day 1 preserves
  the tested parser output and flags this exact pre-existing contract/example
  discrepancy for Qasim/Carmen; it does not silently strip the code or rewrite
  the frozen schema example.
- There is no reviewed source-backed alias field for any current record shape.
  Only canonical titles and explicit codes/IDs are handed off.
- Source-present prose classified as content-only is not promoted into a new
  deterministic field merely to improve matching.
- Rubric still carries unsupported-endpoint/change risk and remains bounded,
  cached ingestion data rather than an official ANU classification or live
  request-path dependency.

RAG/app/orchestration gaps to hand to Qasim and Carmen:

- Natural-language paraphrases, typo handling and intent/entity separation are
  retrieval/understanding responsibilities; the scraper must not create
  magic-word aliases.
- ResultSet state (`RESULTS` / `EMPTY` / `INCOMPLETE`) and answer epistemic
  state (`CONFIRMED` / `DERIVED` / `PARTIAL` / `UNKNOWN`) are not producer
  fields or scraper state machines.
- Personal matching, ranking, comparison explanations and constraint handling
  must use the evidence levels above without converting missing evidence into
  false or no-match.
- Official-only Upcoming Events versus stored official+Rubric chat retrieval
  must continue to use `source_id`; source approval is not institutional
  equivalence.

## Risks and dependencies

- Qasim must review the capability labels before they become a cross-repo V7
  claim. They are conservative producer-evidence labels, not V7=YES results.
- Carmen owns consuming the fixture/contract in retrieval tests and must not
  treat `content_only` as an exact filter or `absent` as false.
- Any new alias, metadata field, entity type, identity rule or source authority
  remains a shared contract change under `DATA_SCHEMA.md` and the decision log.
- Existing production write, crawl, migration, deployment and scheduler gates
  remain unchanged.

## Exact Day 1 gate evidence

- Reviewed base verified after `git fetch origin main --prune`:
  `HEAD == origin/main == 98e10cd6a3fc7979749bf03ea3e7e885fe961a93`.
- New implementation files:
  `src/askanu_scraper/common/v7_contract.py`,
  `fixtures/v7/day1/producer-capabilities.json`,
  `tests/test_v7_day1_contract.py`, and this handoff.
- Focused command: `py -m pytest tests/test_v7_day1_contract.py -q`.
- Focused result: **12 passed**.
- Full command: `py -m pytest`.
- Full result: **397 passed** (baseline **385 passed** + 12 Day 1 tests).
- All eight handoff cases parse checked-in fixtures; test network access is
  disabled by contract.
- Source registry changes: **0**.
- Serialized schema/parser/collector changes: **0**.
- Live institutional source requests: **0**.
- DB writes, cloud executions, deployments and scheduler changes: **0**.
- Pre-existing uncommitted Day 17/detail-coverage files were not modified by
  this Day 1 work.

The gate is ready for Qasim's contract/capability review. It is not evidence of
production release approval or end-to-end V7 intent completion.
