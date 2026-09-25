# AskANU V7 Day 3 scraper/data handoff

**Gate:** Data/evidence side of Carmen's retrieval benchmark

**Owner:** Will

**Status:** Implementation and representative offline audit complete; final
cross-repo benchmark audit blocked until Carmen supplies the frozen benchmark
version, query IDs, expected record IDs and required facts.

**Reviewed base:** `93b94ef102ab22df08c01e5ef4245ad6653d98e9`
(merged Scraper #37)

**Branch:** `will/v7-day3-evidence-benchmark`

**Production mutation:** none

## Outcome

Day 3 adds a read-only evidence audit over validated `CommonRecord` objects.
It separates source/data limitations from downstream retrieval failures without
retrieving, ranking, reasoning, changing expected answers or mutating records.

The shared primitives:

- project every reviewed structured fact with `ESTABLISHED` or
  `NOT_ESTABLISHED`; `false` remains established and null/empty placeholders do
  not become false facts;
- compare same-domain/entity-type records without filling asymmetric missing
  cells or ranking a winner;
- retain record, entity, source, canonical URL and authority on assessments and
  comparison values;
- classify fixed benchmark requirements as `PRESENT_STRUCTURED`,
  `PRESENT_CONTENT_ONLY`, `MISSING_SOURCE`, `MISSING_INGESTION`,
  `NORMALISATION_DEFECT`, `IDENTITY_DEFECT`, `STALE`,
  `INCOMPLETE_POPULATION` or `AMBIGUOUS_SOURCE`;
- mark correctly represented evidence as `NOT_DATA_FAILURE` for downstream
  ownership; and
- report requirement/question availability and provenance metrics overall and
  by domain.

Unsupported structured paths fail closed. The audit cannot silently create a
field, synonym, source, source-authority equivalence or domain state engine.

## Representative corpus, not Carmen's benchmark

`fixtures/v7/day3/representative-evidence-audit.json` is deliberately labelled
`BLOCKED_PENDING_CARMEN_BENCHMARK`. It proves the contract across Course,
Program, Scholarship, Job, Residence, Support, official Event and Rubric Event
fixtures, but it is not presented as Carmen's missing frozen benchmark.

Representative baseline:

| Domain | Requirements | Structured | Content only | Source missing | Ambiguous source | Incomplete population | Provenance |
|---|---:|---:|---:|---:|---:|---:|---:|
| Courses | 3 | 3 | 0 | 0 | 0 | 0 | 3/3 |
| Scholarships | 2 | 1 | 0 | 0 | 1 | 0 | 2/2 |
| Jobs | 2 | 1 | 0 | 0 | 0 | 1 | 2/2 |
| Accommodation | 2 | 1 | 0 | 1 | 0 | 0 | 2/2 |
| Support | 1 | 1 | 0 | 0 | 0 | 0 | 1/1 |
| Events | 4 | 2 | 1 | 1 | 0 | 0 | 4/4 |
| **Total** | **14** | **9** | **1** | **2** | **1** | **1** | **14/14** |

The representative requirement baseline therefore has 10/14 (71.43%)
questions with all required evidence, 9/14 (64.29%) fully structured, 1/14
(7.14%) requiring content, and 100% provenance completeness. Missing-ingestion,
normalisation-defect, identity-defect and stale-primary-classification counts
are zero in this representative set. These are harness proof numbers, not
claims about Carmen's benchmark or the live corpus.

## COMP2120 prerequisite trace and fix

On 2026-09-25 the approved 2026 COMP2120 detail page published a prerequisite
that preserves two alternatives: successful completion or current study of
COMP2100. The current parser regex consumed the completion phrase as generic
boilerplate, leaving a malformed value beginning with `or`.

Trace:

1. Approved source: `https://programsandcourses.anu.edu.au/2026/course/COMP2120`.
2. Parser defect: the live combined requisite-section regex consumed
   `successfully completed` before capturing the fact.
3. Normalised metadata before the fix would be
   `or be currently studying COMP2100`.
4. The same damaged wording would enter canonical content and retrieval-facing
   structured evidence.
5. The generic fix first captures the complete source clause, then strips a
   leading completed-prefix only when doing so does not leave a leading `or`.
6. After the fix, metadata/content preserve
   `successfully completed or be currently studying COMP2100`.

The fix is not keyed to COMP2120. Existing simple completed-course variants
still normalize to their course-code expressions, and the full parser suite is
green.

## Important domain findings represented by the harness

- Scholarships: published dimensions and exact dates can be structured;
  personal eligibility remains ambiguous when the source criteria and student
  facts cannot establish a decision.
- Accommodation: Yukeembruk's `2027 Indicative costs` remains attached to its
  rate period. Current vacancy is `MISSING_SOURCE`, never available/unavailable.
- Jobs: an exact record deadline can be audited independently, while a query
  over the complete current technical-jobs population is
  `INCOMPLETE_POPULATION` under the preserved V6 source/atomicity limitation.
  No atomic ingestion guard changed.
- Events: official and Rubric IDs, sources and authority ranks remain distinct.
  Rubric approval is not converted into official-ANU authority, and modality is
  not inferred.
- Support: the checked-in Academic Support record retains the source-backed
  Grade Appeal topic and problem wording without a synthetic synonym table.
- Temporal evidence: academic year, calendar dates and aware datetimes retain
  their Day 2 precision. Missing Job dates remain absent, and date-only values
  do not gain midnight.

## Carmen handoff contract

When Carmen supplies the frozen manifest, each requirement must include its
unchanged query ID, expected record/source/entity identity, required fact,
audited source status/reference, intended representation, freshness need and
population-completeness need. Running `audit_benchmark` then produces:

- present + provenance-correct -> `NOT_DATA_FAILURE`, returned to Carmen for
  resolver/retrieval/ranking/reasoning diagnosis;
- source-present but absent/damaged -> Will-owned ingestion, normalisation or
  identity defect;
- source-missing/ambiguous or incomplete supported population -> Qasim-owned
  product/source limitation; and
- stale for a current-only requirement -> not suitable as current evidence.

The benchmark expectation must not be revised after inspecting the corpus.

## Tests and exact evidence

- Day 3 focused: `py -m pytest tests/test_v7_day3_benchmark_evidence.py -q`
  -> **10 passed**.
- Parser + V7 Day 1/2/3 focused:
  `py -m pytest tests/test_courses_parser.py tests/test_v7_day1_contract.py tests/test_v7_day2_search_metadata.py tests/test_v7_day3_benchmark_evidence.py -q`
  -> **55 passed**.
- Full shared working tree: `py -m pytest` -> **424 passed**. This includes one
  pre-existing uncommitted Day 17 detail-coverage test; clean-branch evidence
  is recorded in the PR/final handoff after commit.
- `git diff --check` -> exit 0.
- Live institutional requests: one read-only approved COMP2120 detail request
  for defect tracing; no crawl.
- DB writes, cloud executions, deployments, scheduler changes and migrations:
  **0**.

## Scope confirmation

- New production sources: **0**.
- Source-registry or authority changes: **0**.
- Serialized schema/API changes: **0**.
- Generated aliases/synonyms: **0**.
- Scheduler or production ingestion changes: **0**.
- Production DB writes/migrations: **0**.
- Jobs atomicity changes: **0**.
- Live Rubric requests or App/RAG request paths: **0**.
- Pre-existing Day 17/detail-coverage changes included: **0**.

## Remaining gate dependency

Day 3 cannot honestly be called closed until Carmen's frozen benchmark is
available and the representative manifest is replaced or supplemented with its
exact version/query IDs/expected records/required facts. The harness is ready;
the missing cross-repo artifact is the only known blocker to the requested
benchmark-specific counts and ownership handoff.
