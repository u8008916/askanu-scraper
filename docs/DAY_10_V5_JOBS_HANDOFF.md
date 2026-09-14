# V5 Day 10 Jobs Handoff

Owner: Will
Date: 2026-09-14
Source: `jobs_anu_search`
Status: **LOCAL SLICE COMPLETE — CLOUD/CONTRACT GATES OPEN**

## Implemented

- Bounded one-page discovery with at most ten same-origin public job details.
- Current PageUp listing/detail selectors validated against the approved public
  ANU Jobs source.
- Stable numeric requisition identity and exact public canonical detail URLs.
- Source title, category, employment type, location, classification, closing
  wording, summary and explicit/derived current-or-closed state.
- `Australia/Canberra` normalization for exact close times; date-only closes do
  not invent a time and remain current through that local calendar day.
- Complete preflight before atomic persistence, duplicate checks,
  suspicious-zero/drastic-count handling, dry-run support and last-known-good
  preservation.
- URL validation before every direct or discovered fetch; invalid, mismatched,
  account/application and off-origin canonical URLs fail before persistence.
- One-shot Jobs selection and an explicit PostgreSQL approval gate.

The proposed cross-repo identity/metadata contract is recorded in
`docs/DAY_10_JOBS_CONTRACT_PROPOSAL.md`. It is not yet a frozen shared-contract
change.

## Verification

Local suite:

```text
204 passed
40 focused Jobs/storage tests passed
83% repository coverage
Jobs collector / discovery / parser coverage: 77% / 90% / 91%
compileall: passed
git diff --check: passed
```

Bounded live dry-run:

```text
run_id: run_f404164cb37a
status: SUCCESS
requests: 2 (1 listing + 1 detail)
discovered / accepted / over limit: 30 / 1 / 29
records_seen / NEW: 1 / 1 (dry-run comparison only)
duplicate records / URLs: 0 / 0
duration: 1.545 seconds
```

The live run used `--dry-run`, local comparison, and no PostgreSQL connection;
it wrote no records or ingestion-run files.

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

1. Carmen/Qasim approve or revise Jobs identity, metadata keys, current/closed
   semantics and whether any temporal value belongs in top-level `effective_to`.
2. Synchronize the approved decision into `docs/DATA_SCHEMA.md`, the decision
   log, and affected RAG/App contracts.
3. Qasim approves the one-page/ten-detail fetch bound and daily cadence.
4. Qasim verifies the shared migration/runtime grants and deploys the reviewed
   image; this account cannot inspect the Cloud SQL instance.
5. Enable `SCRAPER_JOBS_POSTGRES_APPROVED=true` only for the approved job
   revision, then prove dry-run, first `NEW`, repeated `UNCHANGED`, stored rows,
   ingestion run and failure-safe preservation in staging.

No Cloud Run Job, Scheduler, IAM, shared schema or Cloud SQL data was changed.
