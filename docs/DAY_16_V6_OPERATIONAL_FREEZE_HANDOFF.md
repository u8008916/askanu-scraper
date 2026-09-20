# Day 16 V6 six-domain operational freeze handoff

Date: 20 September 2026 (Canberra)

This handoff is read-only operational evidence. No Cloud Run execution,
PostgreSQL write, deployment, image change or Scheduler mutation was performed.
Official ANU Events remains the sixth-domain release source. Rubric remains a
separately approved, unsupported supplementary source and is blocked on the
exact sanitized `getUnifiedSearch` request-contract verification capture.
Endpoint discovery itself is complete.

## Contract state after the branch refresh

This branch is based on current scraper `main` after merged PR #32. Carmen's
corresponding RAG Events PR #31 is also merged. The Events producer contract,
consumer contract and cross-repository representation are therefore closed and
frozen. The active Rubric identity is `rubric-<source_event_id>` with record ID
`events:event:rubric-<source_event_id>`.

This closes the former producer/consumer reconciliation blocker only. Events
production migration/write authorization, Rubric request-contract review and
the source-health blockers below remain open.

## Release posture

The authoritative machine-readable snapshot is `day16-source-health.json`.
It distinguishes frozen denominators from current observations, source facts
from normalized values, and local read-only evidence from Cloud and persisted
runs. A source that fails or becomes suspicious retains last-known-good data.

| Domain | Frozen/reference denominator | Current observation | Classification |
|---|---:|---:|---|
| Courses | 500 courses; 393 programs; 109 majors; 126 minors; 128 specialisations | 1,256/1,256 entities; 14,840/14,840 source-present facts | `GREEN` |
| Scholarships | 379 previously approved | Headline 405; 379 approved candidates; 26 direct external rejections; 378 normalized; 1 external-canonical redirect | `BLOCKED` |
| Jobs | historical observations 55, 50 and 57 | Current advertised 56; full audit stopped after 7 details; drift +1/+6/-1 respectively is not deletion proof | `FALLBACK_LAST_KNOWN_GOOD` |
| Accommodation | 19 | 19/19 entities; 255/255 facts | `GREEN` |
| Support | 6 | 6/6 entities; 56/56 facts after the fixture-backed access-link fix | `GREEN` |
| Official Events | 30 in the frozen 2026-09-19 through 2026-10-31 Canberra window | 30 cards, 29 unique/eligible, 1 duplicate; 339/339 facts; complete five-page traversal | `BLOCKED` |
| Rubric Events | no frozen live denominator | Fixture-backed recovery only; request-contract capture and live census missing | `BLOCKED`, not zero coverage |

`GREEN` means reconciled traversal, at least 99% entity and source-present fact
coverage, and no identity/canonical conflict. `FALLBACK_LAST_KNOWN_GOOD` means a
temporary fetch failure with prior healthy evidence. `BLOCKED` means zero or
incomplete traversal, a parser/identity/canonical failure, or quantified
coverage below 99%.

## Cloud observation (read-only)

At the beginning of the Day 16 sweep, `askanu-scraper` in project
`askanu-dev-gdg`, region `australia-southeast1`, was generation 20 and Ready.
Its image digest was
`sha256:0b4b2da3ad6977b7b1aef556460e668e6ac637fb53f0eba7dd1df5d91169f8b5`.
The configured job was Courses-only, bounded to one course plus one program,
with `SCRAPER_DRY_RUN=true`. The latest observed scheduled execution was
`askanu-scraper-9cmf9`, created at `2026-09-19T17:15:03Z`, and it succeeded.
That Cloud execution is neither a six-domain refresh nor a persisted ingestion
run.

Scheduler configuration could not be listed because the active principal,
`dinosur451@gmail.com`, lacks `cloudscheduler.jobs.list`. No schedule is
inferred from the execution timestamp. Qasim owns Scheduler access and any
configuration change. The proposed separate Events schedule remains 03:45
Canberra and was not created.

The end-of-sweep read returned the same generation, image, configuration and
latest execution. Dormant Accommodation/Support approval environment values do
not change the effective job scope: the selected domain is Courses and the job
is dry-run. No Cloud execution was launched during Day 16.

## Local dry-run IDs

These are local, non-persisted run IDs. They are not Cloud execution IDs or
database ingestion-run IDs.

| Domain | Local run ID | Result | Bound |
|---|---|---|---|
| Courses | `run_d21d34b6214b` | `SUCCESS` | one course plus one program |
| Scholarships | `run_a6afa77accbe` | `SUCCESS` | one listing page; representative only, not the full census |
| Jobs | `run_014e76b4a159` | `FAILED`, zero writes | one listing page; empty detail response after seven requests |
| Accommodation | `run_7e224ff10bce` | `SUCCESS` | full frozen 19 |
| Support | `run_67cd3c342538` | `SUCCESS` | full frozen 6 |
| Official Events | `run_365f22c7708c` | `FAILED`, zero writes | full fixed window; 29 accepted versus frozen 30 |

There are no persisted ingestion-run IDs for Day 16.

## Verification

The historical pre-freeze branch recorded 93 focused and 377 full-suite
passes. After rebasing onto current main and adapting the Day 16 audit to the
merged Events contract, verification was rerun from the refreshed branch:

- Focused detail-coverage, recovery, Support, Events and Rubric isolation
  suites: 90 passed.
- Complete regression suite: 380 passed.
- Registry suite: 13 passed.
- JSON validation and `git diff --check`: passed.
- Tracked/staged secret-pattern scan: passed.

The focused count is the exact collection from the documented refreshed test
command, not an attempt to preserve the historical 93-test number.

## Refresh matrix

| Domain | Intended cadence | Day 16 operating mode | Production state |
|---|---|---|---|
| Courses | Daily | Full read-only census plus bounded local dry-run | Existing generation-20 Cloud job is a 1+1 dry-run only |
| Scholarships | Daily | Full read-only census plus bounded local dry-run | PostgreSQL and schedule remain release-gated |
| Jobs | Daily | Full read-only census plus bounded local dry-run | PostgreSQL and schedule remain release-gated |
| Accommodation | Daily | Full 19-record read-only census/dry-run | PostgreSQL and schedule remain release-gated |
| Support | Daily | Full 6-record read-only census/dry-run | PostgreSQL and schedule remain release-gated |
| Official Events | Daily proposal at 03:45 Canberra | Full fixed-window read-only census/dry-run | Separate job/schedule and PostgreSQL remain release-gated |
| Rubric Events | Daily proposal only | Fixture recovery proof; no live request without reviewed capture | `BLOCKED`; supplementary and never a chat-time dependency |

## Bounded manual dry-run commands

These commands fetch only approved public sources and write no records:

```powershell
# Courses representative smoke
.\.venv\Scripts\python.exe -m askanu_scraper.job `
  --source-id courses_programs_and_courses --domain courses `
  --academic-year 2026 --max-courses 1 --max-programs 1 --dry-run

# Scholarships representative detail after listing reconciliation
.\.venv\Scripts\python.exe -m askanu_scraper.job `
  --source-id scholarships_anu_finder --domain scholarships `
  --max-scholarship-listing-pages 1 --max-scholarship-details 1 --dry-run

# Jobs representative detail after listing reconciliation
.\.venv\Scripts\python.exe -m askanu_scraper.job `
  --source-id jobs_anu_search --domain jobs `
  --max-jobs-listing-pages 1 --max-job-details 1 --dry-run

# Full frozen Accommodation and Support registries
.\.venv\Scripts\python.exe -m askanu_scraper.job `
  --source-id accommodation_anu_study --domain accommodation `
  --max-accommodation-details 19 --dry-run
.\.venv\Scripts\python.exe -m askanu_scraper.job `
  --source-id support_anusa_student_assistance --domain support `
  --max-support-details 6 --dry-run

# Official Events, fixed Canberra window
.\.venv\Scripts\python.exe -m askanu_scraper.job `
  --source-id events_anu_official --domain events `
  --max-events-listing-pages 6 --max-event-details 100 `
  --events-window-start 2026-09-19 --events-window-days 43 `
  --expected-event-count 30 --dry-run
```

The complete non-persistent audit command is:

```powershell
.\.venv\Scripts\python.exe -m askanu_scraper.detail_coverage `
  --domain all --academic-year 2026 --max-listing-pages 100 `
  --events-window-start 2026-09-19 --events-window-days 43 `
  --output day16-source-health.json
```

Do not use the old untracked `detail-coverage-evidence.json`: the CLI now
refuses that output name so it cannot be overwritten and cited as current.

## Recovery procedure

1. Stop before persistence when discovery is zero, pagination is incomplete,
   a canonical/identity conflict exists, parsing fails, or the count drops
   sharply without reconciliation.
2. Retain the last-known-good rows and record the exact source, error,
   timestamp, local/Cloud/persisted execution type and observed counts.
3. Re-run a bounded read-only audit after the external source recovers. Do not
   rewrite a parser for a transient source failure and do not patch the database
   manually as normal operation.
4. Proceed to a production write only after migration alignment, independent
   count/provenance review and a new explicit Qasim GO.

The fixture-backed recovery matrix covers HTTP failure, timeout, malformed
detail, suspicious zero, incomplete pagination, drastic count, atomic
persistence failure and successful `UNCHANGED` recovery. Source-isolation
tests prove official Events failure does not modify stored Rubric records and
Rubric failure does not modify official records.

## Known gates and one-hour backlog

- Qasim: attach the exact sanitized reviewed Rubric request/response capture.
- Will: run and freeze the bounded Rubric window census after that capture is
  available; the previously observed 119 is not a denominator.
- Qasim/Carmen: review the approved Events migration execution evidence and
  issue an explicit production-write GO or HOLD; the shared contract itself is
  already frozen and merged.
- Will/Qasim: after explicit write GO, perform first-write and unchanged-run
  verification and independently check persisted counts, provenance and URLs.
- Qasim: grant read-only Scheduler Viewer access or provide a timestamped
  Scheduler configuration export.
- Qasim/Ben: independently verify database counts and the deployed six-domain
  path after the release gates pass.

No Friday feedback fix was included because no accepted issue with approved
source evidence was supplied. No new source, schema, normalized contract,
registry membership or release gate was introduced.
