# DEPLOYMENT.md

V3 target:
```text
Browser
 -> Firebase Hosting
 -> App Cloud Run
 -> authenticated RAG Cloud Run
 -> Cloud SQL PostgreSQL + pgvector
 -> Gemini / Vertex AI

Cloud Scheduler
 -> Scraper Cloud Run Job
 -> safe DB/index update
```

Initial working region assumption: `australia-southeast1` (Sydney), unless availability/credits require a documented change.

Use separate App/RAG/Scraper service identities, Secret Manager and least privilege.

## Confirmed Day 7 scraper foundation

| Resource | Confirmed value |
|---|---|
| Project | `askanu-dev-gdg` |
| Region | `australia-southeast1` |
| Cloud Run Job | `askanu-scraper` |
| Runtime service account | `askanu-scraper-runtime@askanu-dev-gdg.iam.gserviceaccount.com` |
| Cloud SQL instance | `askanu-postgres-dev` |
| Instance connection name | `askanu-dev-gdg:australia-southeast1:askanu-postgres-dev` |
| Database | `askanu` |
| Database user | `askanu_backend` |
| Password secret | `askanu-db-password:2` (active; version 1 disabled) |

The deployed job is verified to use the dedicated scraper runtime identity and
the merged Day 6 image. The runtime identity has the intended Cloud SQL Client
role and access to the database-password secret. Bind secret version 2 to the
runtime `DB_PASSWORD` environment variable; never place its payload in files,
image layers, command arguments or documentation.

The scraper-side implementation follows Qasim's approved ownership boundary:
NEW/CHANGED records become `PENDING` with no embedding version; UNCHANGED
records preserve their index status and embedding version. Day 7 requires a
durable `ingestion_runs` row, with structured Cloud Run JSON as supplementary
evidence. Carmen owns the minimal table in the shared migration; Will owns
writing/updating it. RAG PR #16 has merged that schema contract. The shared
migration is confirmed at Alembic revision `20260911_0001` (`head`) and was
verified in Cloud SQL Studio. The scraper adapter/image still requires Qasim's
deployment and release review before real writes.

Do not wait until final week. V3 requires an early real vertical slice:
`Firebase -> App -> RAG -> Cloud SQL -> one real course answer -> real source card`.

## Scraper Cloud Run Job readiness (Day 6)

The scraper is a terminating process, not an HTTP server. The container
entrypoint runs exactly one bounded collector invocation, writes one structured
JSON summary to standard output, and exits `0` only for `SUCCESS`. `FAILED` and
`SUSPICIOUS_ZERO` exit `1`; invalid configuration exits `2`.

The implemented job targets are:

```text
source_id = courses_programs_and_courses
domain    = courses

source_id = scholarships_anu_finder
domain    = scholarships

source_id = jobs_anu_search
domain    = jobs

source_id = accommodation_anu_study
domain    = accommodation

source_id = support_anusa_student_assistance
domain    = support
```

All selections pass through the machine-readable approved-source registry.
Official ANU Events is supported for bounded local/dry-run collection. Rubric
is approved only for bounded unsupported ingestion and remains blocked on its
exact search-endpoint capture plus an independent PostgreSQL release gate.
Accommodation is bounded
to its frozen 19-page public registry; Support is bounded to its frozen six-page
ANUSA registry.

### Environment contract

| Variable | Required/default | Purpose |
|---|---|---|
| `SCRAPER_ACADEMIC_YEAR` | required for Courses | Four-digit catalogue year; unused by Scholarships. |
| `SCRAPER_COURSE_CODE` | unset | Optional single-course smoke target, for example `COMP1110`; bypasses catalogue discovery but still enforces the approved source root. |
| `SCRAPER_SOURCE_ID` | `courses_programs_and_courses` | Approved registry ID. |
| `SCRAPER_DOMAIN` | `courses` | Must match the selected registry entry. |
| `SCRAPER_MAX_COURSES` | `2` | Bounded course count; minimum 1. |
| `SCRAPER_MAX_PROGRAMS` | `2` | Bounded program count; minimum 1. |
| `SCRAPER_MAX_SCHOLARSHIP_LISTING_PAGES` | `1` | Fixed one-page scholarship discovery bound; other values are rejected. |
| `SCRAPER_MAX_SCHOLARSHIP_DETAILS` | `10` | Scholarship detail bound; valid range 1–10. |
| `SCRAPER_SCHOLARSHIP_POSTGRES_APPROVED` | `false` | Set true only after migration `20260913_0002`, runtime grants, Courses regression and Scholarship live read are verified and Qasim approves writes. |
| `SCRAPER_MAX_JOBS_LISTING_PAGES` | `1` | Fixed one-page Jobs discovery bound; other values are rejected. |
| `SCRAPER_MAX_JOB_DETAILS` | `10` | Public Jobs detail bound; valid range 1-10. |
| `SCRAPER_JOBS_POSTGRES_APPROVED` | `false` | Set true only after frozen Jobs v1 alignment and the migration/runtime grants and bounded live-read gate are approved. |
| `SCRAPER_MAX_ACCOMMODATION_DETAILS` | `10` | Approved public residence detail bound; valid range 1-19. |
| `SCRAPER_ACCOMMODATION_POSTGRES_APPROVED` | `false` | Keep false until Qasim's final review and a separately approved migration `20260916_0008` runtime/write gate. |
| `SCRAPER_MAX_SUPPORT_DETAILS` | `6` | Approved ANUSA category detail bound; valid range 1-6. |
| `SCRAPER_SUPPORT_POSTGRES_APPROVED` | `false` | Keep false until Qasim's final review and a separately approved migration `20260916_0008` runtime/write gate. |
| `SCRAPER_MAX_EVENTS_LISTING_PAGES` | `10` | Hard cap; the 2026-09-18 source snapshot advertises six pages (`page=0` through `page=5`). |
| `SCRAPER_MAX_EVENT_DETAILS` | `100` | Bound applied after same-origin link deduplication. |
| `SCRAPER_EVENTS_WINDOW_START` | current Canberra date | Frozen release runs set `2026-09-19`. |
| `SCRAPER_EVENTS_WINDOW_DAYS` | `43` | Frozen release interval ends `2026-10-31` inclusive. |
| `SCRAPER_EXPECTED_EVENT_COUNT` | unset | Frozen release runs set the recomputed denominator `30`; below 99% fails before persistence. |
| `SCRAPER_EVENTS_POSTGRES_APPROVED` | `false` | Keep false until the Events migration and Qasim/Carmen approval reference are verified. |
| `SCRAPER_RUBRIC_SEARCH_ENDPOINT` | unset | Exact reviewed Rubric search capture; no guessed default. |
| `SCRAPER_MAX_RUBRIC_LISTING_PAGES` | `20` | Hard pagination cap for unsupported Rubric discovery. |
| `SCRAPER_MAX_RUBRIC_DETAILS` | `250` | Deduplicated per-run detail cap. |
| `SCRAPER_RUBRIC_POSTGRES_APPROVED` | `false` | Keep false until Qasim reviews the migration, complete dry-run and release GO. |
| `SCRAPER_DRY_RUN` | `true` in the Day 6 container (`false` application default) | Compare normally but suppress all local writes. |
| `SCRAPER_STORAGE_PATH` | `local-data` (`/data` in container) | Existing local JSON handoff. |
| `SCRAPER_STORAGE_BACKEND` | `local` | Set to `postgres` only for the reviewed shared Cloud SQL adapter. |
| `SCRAPER_TIMEOUT_SECONDS` | `30` | Per-request timeout, 1–300 seconds. |
| `SCRAPER_MIN_REQUEST_INTERVAL_SECONDS` | `1` | Live request spacing, 1–60 seconds. |
| `SCRAPER_SIMULATE_FETCH_FAILURE` | `false` | Deterministic no-network failure drill. |
| `DATABASE_URL` | unset unless the approved interface selects a DSN | Protected optional Cloud SQL handoff; never logged. |
| `DB_NAME` | `askanu` | Confirmed Cloud SQL database name. |
| `DB_USER` | `askanu_backend` | Confirmed Cloud SQL database user. |
| `DB_PASSWORD` | required for durable writes; Secret Manager only | Bind from `askanu-db-password:2`; never log it. |
| `CLOUD_SQL_INSTANCE_CONNECTION_NAME` | `askanu-dev-gdg:australia-southeast1:askanu-postgres-dev` | Confirmed Cloud SQL attachment/socket name. |
| `GOOGLE_CLOUD_PROJECT` | `askanu-dev-gdg` | GCP project selection. |
| `GOOGLE_CLOUD_LOCATION` | `australia-southeast1` | Initial region assumption. |
| `SCRAPER_USER_AGENT` | `AskANU/0.1` | Production HTTP user agent. |

CLI flags use the lowercase, hyphenated form of the job variables and override
environment values. `--dry-run` and `--simulate-fetch-failure` are boolean
flags. A combined course/program bound above four is rejected before fetching.
When `SCRAPER_COURSE_CODE` is set, the job fetches exactly that course detail
page for the configured academic year and does not call catalogue APIs.
Scholarship runs reject `SCRAPER_COURSE_CODE`, external-scholarship cards,
off-origin links and application/authentication paths.

Environment variables are injected by the Cloud Run Job configuration. Secret
values must come from Secret Manager references and must not be placed in image
layers, command arguments, `.env` files, or deployment documentation.

### Build and local container smoke

```powershell
docker build -t askanu-scraper:day6 .
docker run --rm `
  -e SCRAPER_ACADEMIC_YEAR=2026 `
  -e SCRAPER_MAX_COURSES=1 `
  -e SCRAPER_MAX_PROGRAMS=1 `
  -e SCRAPER_DRY_RUN=true `
  askanu-scraper:day6
```

Failure drill:

```powershell
docker run --rm `
  -e SCRAPER_ACADEMIC_YEAR=2026 `
  -e SCRAPER_MAX_COURSES=1 `
  -e SCRAPER_MAX_PROGRAMS=1 `
  -e SCRAPER_DRY_RUN=true `
  -e SCRAPER_SIMULATE_FETCH_FAILURE=true `
  askanu-scraper:day6
$LASTEXITCODE
```

### Persistence boundary

The GCP deployment/environment values, shared table contract and migration are
confirmed. Alembic is at `20260911_0001` (`head`) and the shared tables plus
COMP1110 data were verified in Cloud SQL Studio. The scraper image containing
the PostgreSQL adapter still needs to be reviewed, published and deployed by
Qasim.

For the Day 9 shared contract, RAG PR #19 defines `source_records` as the
canonical writable record table and retains `course_program_records` as a
read-only Courses/Programs compatibility view. The current scraper branch uses
only `source_records` for record reads/writes. Do not deploy that image ahead of
migration `20260913_0002`. Even after migration, keep
`SCRAPER_SCHOLARSHIP_POSTGRES_APPROVED=false` until production-equivalent grants,
the COMP1110 regression and a Scholarship live read have passed.
Until then, the deployed job deliberately uses the existing `LocalDataStore`
adapter. It does not simulate durable persistence.

**Cloud Run executions must remain dry-run while `LocalDataStore` is the active
persistence adapter.** Cloud Run Job container filesystems, including `/data`,
are not durable after an execution completes. The Day 6 image consequently
sets `SCRAPER_DRY_RUN=true` so a job cannot report transient local writes as a
durable ingestion success. Set `SCRAPER_DRY_RUN=false` only after the durable
Cloud SQL persistence path is connected. Local development may explicitly set
`SCRAPER_DRY_RUN=false` when local JSON persistence is intended.

Failure or suspicious-zero outcomes do not delete or mark existing records
missing. Dry-run mode does not create or modify record/run files. Scheduler
creation is not performed from this repository; the Day 8 review proposal is
below.

## Day 8 scheduled freshness gate

The scraper now supports an atomic PostgreSQL batch boundary: all preflighted
record changes and the successful `ingestion_runs` row commit together or roll
back together. Structured stdout summary schema v2 includes supplemental bounded
request, discovery, rejection and duplicate counts without changing the shared
database schema.

The proposed daily schedule is `03:15` in `Australia/Canberra`, using an OAuth-
authenticated POST to the Cloud Run Jobs v2 `askanu-scraper:run` endpoint. Qasim
must review/create the dedicated Scheduler caller and grant it only Cloud Run
Invoker on this job. The deployed job remains `SCRAPER_DRY_RUN=true` until
Qasim completes the adapter/image review, Scheduler IAM and release gate.

See `docs/DAY_8_SCHEDULED_FRESHNESS.md` for the exact proposal and evidence
checklist. It is a handoff document, not authorization to mutate GCP resources.

Jobs must deploy as a separate `askanu-scraper-jobs` Cloud Run Job rather than
overwriting the existing Courses or Scholarships job configuration. Its first
executions remain dry-run until the RAG migration after `20260914_0003`, runtime
grants and frozen-contract validation are verified. Scheduler activation is a
later Qasim-owned release decision after PostgreSQL `NEW` -> `UNCHANGED`,
failure-preservation and RAG live-read evidence passes.

Events likewise proposes a separate `askanu-scraper-events` Cloud Run Job and
a daily `03:45` `Australia/Canberra` schedule, offset from the existing 03:15
job. This is a proposal only: do not deploy, create the schedule, or enable
PostgreSQL until the Events migration, runtime grants and Qasim/Carmen approval
are evidenced. Until then the bounded command in the README is the manual
read-only fallback.

Rubric must not share or overwrite that job configuration until its exact
endpoint artifact, frozen denominator and migration are reviewed. Any future
Rubric job remains ingestion-only; no RAG request path may invoke it.
