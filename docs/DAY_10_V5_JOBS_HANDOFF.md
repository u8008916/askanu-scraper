# V5 Day 10 Jobs Handoff

Owner: Will
Date: 2026-09-14
Source: `jobs_anu_search`
Status: **FROZEN CONTRACT ALIGNED — CLOUD RELEASE GATES OPEN**

## Implemented

- Bounded one-page discovery with at most ten same-origin public job details.
- Current PageUp listing/detail selectors validated against the approved public
  ANU Jobs source.
- Stable numeric requisition identity and exact public canonical detail URLs.
- Source title, category, employment types, location, classification, raw
  salary wording, closing wording, summary and explicit/derived
  current-or-closed state.
- `Australia/Canberra` normalization for exact close times; date-only closes do
  not invent a time and remain current through that local calendar day.
- Complete preflight before atomic persistence, duplicate checks,
  suspicious-zero/drastic-count handling, dry-run support and last-known-good
  preservation.
- URL validation before every direct or discovered fetch; invalid, mismatched,
  account/application and off-origin canonical URLs fail before persistence.
- One-shot Jobs selection and an explicit PostgreSQL approval gate.
- Source-backed normalized fixture plus clearly labelled synthetic closed,
  undated, same-date tie-break and unknown-state repository/parser cases.

The cross-repo identity/metadata contract is frozen in
`docs/DAY_10_JOBS_CONTRACT_PROPOSAL.md`, synchronized into `docs/DATA_SCHEMA.md`
and recorded in `docs/DECISION_LOG.md` with Qasim's approval. The implementation
uses `employment_types` as an array and preserves salary as source text.

## Verification

Local suite:

```text
208 passed
44 focused Jobs/storage tests passed
83% repository coverage
Jobs collector / discovery / parser coverage: 77% / 90% / 89%
compileall: passed
git diff --check: passed
```

Bounded live dry-run:

```text
run_id: run_e6395b25c2bb
status: SUCCESS
requests: 2 (1 listing + 1 detail)
discovered / accepted / over limit: 30 / 1 / 29
records_seen / NEW: 1 / 1 (dry-run comparison only)
duplicate records / URLs: 0 / 0
duration: 1.583 seconds
```

The live run used the rebuilt Docker image, `--dry-run`, local comparison, and
no PostgreSQL connection; it wrote no records or ingestion-run files.

The local Docker image built successfully as `askanu-scraper:day10-local`. A
no-network `docker run --rm askanu-scraper:day10-local --help` smoke test also
passed and exposed the bounded Jobs command-line options.

## Read-only cloud preflight

A read-only audit on 2026-09-14 confirmed Cloud Run Job `askanu-scraper`
generation 5 still uses image digest:

```text
sha256:f52a4c9cc3e1bc05598ddb8d23093dae50ad7753de5c478424964ea29150512f
```

That is the same pre-Day-9 digest documented in the Day 9 handoff as the
reviewed Courses configuration, so it does not contain this Jobs change. The
latest execution, `askanu-scraper-n5ss2`, succeeded on 2026-09-13; nine of the
ten visible recent executions succeeded and one older execution failed with a
container exit code of 1.

The active account lacks `cloudscheduler.jobs.list`, so Scheduler existence,
configuration and cadence cannot be verified. It also cannot describe the
documented Cloud SQL instance, so the deployed migration/runtime grants remain
an integration-owner verification item. No deployment, execution, IAM,
Scheduler, schema or database mutation was attempted.

## Remaining release gates

1. Carmen synchronizes the frozen contract into RAG and creates the next
   migration after live revision `20260914_0003` (expected `20260914_0004`).
2. Qasim verifies the shared migration/runtime grants and deploys the reviewed
   image as a separate `askanu-scraper-jobs` Cloud Run Job.
3. Capture PostgreSQL dry-run, first `NEW`, repeated `UNCHANGED`, stored rows,
   ingestion run, failure-safe preservation and RAG live-read evidence.
4. Qasim separately approves Scheduler activation after the controlled evidence
   passes; daily cadence is intended but not yet a production release approval.

No Cloud Run Job, Scheduler, IAM, shared schema or Cloud SQL data was changed.
