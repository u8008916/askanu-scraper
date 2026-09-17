# Day 13 V6 source completeness, recovery and demo candidate handoff

Captured 17 September 2026 (Australia/Sydney). This is **demo candidate
evidence, not a production data lock**. No production record was written, no
Cloud Run Job was triggered, and no Scheduler, IAM, deployment, shared schema,
source registry or runtime configuration was changed.

Implementation commit: `75e4304c1a261b5896b46269f80c07e0d4cf9d12`,
based on merged PR #26 commit
`93def34b0e53a6d8951987ba52281457fd9d28cc`. The matching RAG capability
evidence was read at `ccd93b37510b585f734e8dd38f23f52ae8042c61`, which
contains merged migration `20260916_0008`.

## Coverage matrix

The RAG repository has frozen capability matrices, but no single centralized
six-domain golden-question file. This audit uses the Day 11 retrieval audit and
Day 12 Accommodation/Support capability matrices verbatim; it does not invent
new questions. Events is explicitly unavailable.

| Domain | Frozen/current entity evidence | Required source-present facts | Affected capability set | Gap | Severity / disposition |
|---|---|---|---|---|---|
| Courses | Day 11: Course 500/500, Program 393/393, Major 109/109, Minor 126/126, Specialisation 128/128 | A fresh post-fix full-detail denominator is not in merged evidence | Exact lookup; prerequisites/incompatibilities/assumed knowledge; offerings; subplan requirements | stale data/evidence | P1: keep denominators, do not re-claim 99% field coverage |
| Scholarships | Day 11: 379/379 approved Finder entities; Day 13 headline remains 405 | Day 13 intentionally sampled one detail and did not reconcile all pages | Exact/filter; eligibility/status; dates; value/selection/application | stale data/evidence | P1: full-detail refresh after freeze |
| Jobs | Day 11 snapshot 55; Day 13 advertised total 50, one detail sampled | Representative fields passed; current 50-detail denominator not traversed | Current/exact; employment/location/classification/salary; closing/status | stale data drift | P1: reconcile read-only; never treat the five-record delta as deletion proof |
| Accommodation | Day 12 19/19; Day 13 listing still 19 | 1,086/1,086 (100%) | Lookup/comparison; room/rate/contract/features; application/contact; explicit unknown vacancy | none | Freeze |
| Support | Day 12 6/6; Day 13 listing still 6 | 163/163 (100%) | Service/purpose/category; contact/cost/topic/referral; missing hours/access; high-stakes abstention | none | Freeze |
| Events | No denominator and no runnable collector | unavailable | Discovery; temporal filtering; provenance | parser/source-target blocker | BLOCKED: Day 15, official source only; Rubric disabled |

Majors, Minors and Specialisations remain discovery-only on the scraper side;
they are not silently counted as persisted Programs. Source-absent nullable
Accommodation/Support fields are not parser misses.

## Failure and recovery report

The new cross-collector matrix ran 17 focused cases and the complete repository
suite now reports **308 passed** (the 291-test baseline plus 17 Day 13 cases).

| Scenario | Domains | Expected / observed | Last-known-good | Recovery evidence |
|---|---|---|---|---|
| HTTP 503 | All five runnable collectors | `FAILED` / `FAILED` | ID, hash, content, timestamps and index state preserved | Healthy rerun `SUCCESS`, one `UNCHANGED` |
| Timeout | All five runnable collectors | `FAILED` / `FAILED` | Preserved | Healthy rerun `SUCCESS`, one `UNCHANGED` |
| Malformed/parser failure | All five runnable collectors | `FAILED` / `FAILED` | Preserved | Healthy rerun `SUCCESS`, one `UNCHANGED` |
| Atomic run-row/DB failure | Shared storage boundary, Courses representative | `FAILED` / `FAILED` | Rolled back to the prior logical record | Healthy rerun `SUCCESS`, one `UNCHANGED` |
| Many-to-zero | All five runnable collectors | `SUSPICIOUS_ZERO` / `SUSPICIOUS_ZERO` | Existing collector proofs retain records and perform no destructive write | Healthy/idempotent paths remain green |
| Secret-bearing failure | One-shot job boundary | Redacted `FAILED` summary | No write | Credential and query values absent from output |

The Day 13 proof is in `tests/test_day13_failure_recovery.py`. Existing
PostgreSQL fake-transaction tests continue to prove run-row failures roll record
changes back without contacting a database.

## Read-only operational snapshot

The existing `askanu-scraper` Cloud Run Job is Ready at generation 5. It is a
Courses-only bounded dry-run (`1` Course + `1` Program), uses the dedicated
runtime identity, a 30-second HTTP timeout, one-second request spacing, a
600-second task timeout and zero task retries.

The latest execution was `askanu-scraper-ddvgg`, created by the Scheduler
caller at `2026-09-17 03:15` Canberra time. It succeeded in 14.34 seconds. Its
structured dry-run summary was `run_ce642261c16b`: two records seen, two NEW
comparisons, zero changed/unchanged, four requests and no persistence. The ten
most recent listed executions all succeeded.

Two limitations remain visible:

- `gcloud run jobs describe` reports configured digest
  `sha256:f52a4c9cc3e1bc05598ddb8d23093dae50ad7753de5c478424964ea29150512f`,
  while recent execution snapshots report
  `sha256:1cdfae38e1f31f588e0448fcecfe52fdf919d9e52fcfbdbc30f560efe7c0a890`.
  Qasim must reconcile the immutable revision/digest before a deployment
  decision; nothing was changed here.
- Scheduler description returned `PERMISSION_DENIED` for
  `cloudscheduler.jobs.get`. Execution ownership/timing indicates a scheduler
  caller but does not prove schedule, retry or backoff configuration.

No raw source content, credential value, or query string is included in the
operational evidence.

## Demo candidate record

Final bounded live dry-runs were non-persistent:

| Domain | Run ID | Seen / requests | Source signal |
|---|---|---:|---|
| Courses | `run_dc7a12ea9431` | 2 / 4 | one Course + one Program |
| Scholarships | `run_417fa17bae54` | 1 / 2 | headline 405; one page intentionally unreconciled |
| Jobs | `run_d90a630b31d1` | 1 / 2 | advertised total 50; one page intentionally unreconciled |
| Accommodation | `run_51d1c7f07088` | 1 / 2 | listing reconciled to frozen 19 |
| Support | `run_98201f5aaaf6` | 1 / 2 | listing reconciled to frozen 6 |

Every run returned `SUCCESS`, with zero duplicate record IDs and canonical
URLs. Representative approved URLs were fetched successfully. Representative
record IDs, hashes, exact run summaries and supporting-artifact checksums are
in `day13-evidence.json` (SHA-256
`8fe250ac5ac624e9dc83f53e8cd3cf598c1b7280f844d92a5b0981f2e470d9d7`).
Events has no representative record; none was fabricated.

The current production dataset and durable `ingestion_runs` were not read, so
these dry-run IDs must never be presented as persisted ingestion IDs. Source
and parser changes are frozen after this capture.

## Prioritized issues

1. **P1 — Events blocker:** resolve the exact official Events target and build
   the collector on Day 15; Rubric remains disabled.
2. **P1 — first-three-domain evidence:** merge a reviewed current full-detail
   field audit after the demo freeze. One-record samples do not prove 99%.
3. **P1 — Jobs drift:** reconcile the timestamped 55-to-50 change read-only;
   never turn it directly into missing/deleted records.
4. **P1 — cloud digest discrepancy:** Qasim reconciles job revision and
   execution image evidence before any deployment.
5. **P1 — persisted demo data:** Qasim confirms actual dataset/run IDs through
   separately approved read-only access. Until then this is candidate evidence.
6. **P2 — Scheduler visibility:** provide read-only configuration evidence;
   do not alter cadence/retries during freeze.

The locally present untracked `detail-coverage-evidence.json` was preserved and
excluded from this change. It predates later parser fixes and is not treated as
the current merged coverage result.
