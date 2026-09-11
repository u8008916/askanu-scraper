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
| Password secret | `askanu-db-password:1` (enabled) |

The deployed job is verified to use the dedicated scraper runtime identity and
the merged Day 6 image. The runtime identity has the intended Cloud SQL Client
role and access to the database-password secret. Bind secret version 1 to the
runtime `DB_PASSWORD` environment variable; never place its payload in files,
image layers, command arguments or documentation.

The scraper-side implementation follows the shared ownership boundary:
NEW/CHANGED records become `PENDING` with no embedding version; UNCHANGED
records preserve their index status and embedding version. For Day 7,
ingestion-run evidence is the existing structured Cloud Run JSON summary, so no
unapproved database table is required. The adapter still requires review before
real writes.

Do not wait until final week. V3 requires an early real vertical slice:
`Firebase -> App -> RAG -> Cloud SQL -> one real course answer -> real source card`.

## Scraper Cloud Run Job readiness (Day 6)

The scraper is a terminating process, not an HTTP server. The container
entrypoint runs exactly one bounded collector invocation, writes one structured
JSON summary to standard output, and exits `0` only for `SUCCESS`. `FAILED` and
`SUSPICIOUS_ZERO` exit `1`; invalid configuration exits `2`.

The currently implemented job target is:

```text
source_id = courses_programs_and_courses
domain    = courses
```

All selections pass through the machine-readable approved-source registry.
Other approved domains remain unsupported until their collectors are
implemented. Rubric stays inactive and cannot be selected.

### Environment contract

| Variable | Required/default | Purpose |
|---|---|---|
| `SCRAPER_ACADEMIC_YEAR` | required | Four-digit catalogue year. |
| `SCRAPER_COURSE_CODE` | unset | Optional single-course smoke target, for example `COMP1110`; bypasses catalogue discovery but still enforces the approved source root. |
| `SCRAPER_SOURCE_ID` | `courses_programs_and_courses` | Approved registry ID. |
| `SCRAPER_DOMAIN` | `courses` | Must match the selected registry entry. |
| `SCRAPER_MAX_COURSES` | `2` | Bounded course count; minimum 1. |
| `SCRAPER_MAX_PROGRAMS` | `2` | Bounded program count; minimum 1. |
| `SCRAPER_DRY_RUN` | `true` in the Day 6 container (`false` application default) | Compare normally but suppress all local writes. |
| `SCRAPER_STORAGE_PATH` | `local-data` (`/data` in container) | Existing local JSON handoff. |
| `SCRAPER_STORAGE_BACKEND` | `local` | Set to `postgres` only for the reviewed shared Cloud SQL adapter. |
| `SCRAPER_TIMEOUT_SECONDS` | `30` | Per-request timeout, 1–300 seconds. |
| `SCRAPER_MIN_REQUEST_INTERVAL_SECONDS` | `1` | Live request spacing, 1–60 seconds. |
| `SCRAPER_SIMULATE_FETCH_FAILURE` | `false` | Deterministic no-network failure drill. |
| `DATABASE_URL` | unset unless the approved interface selects a DSN | Protected optional Cloud SQL handoff; never logged. |
| `DB_NAME` | `askanu` | Confirmed Cloud SQL database name. |
| `DB_USER` | `askanu_backend` | Confirmed Cloud SQL database user. |
| `DB_PASSWORD` | required for durable writes; Secret Manager only | Bind from `askanu-db-password:1`; never log it. |
| `CLOUD_SQL_INSTANCE_CONNECTION_NAME` | `askanu-dev-gdg:australia-southeast1:askanu-postgres-dev` | Confirmed Cloud SQL attachment/socket name. |
| `GOOGLE_CLOUD_PROJECT` | `askanu-dev-gdg` | GCP project selection. |
| `GOOGLE_CLOUD_LOCATION` | `australia-southeast1` | Initial region assumption. |
| `SCRAPER_USER_AGENT` | `AskANU/0.1` | Production HTTP user agent. |

CLI flags use the lowercase, hyphenated form of the job variables and override
environment values. `--dry-run` and `--simulate-fetch-failure` are boolean
flags. A combined course/program bound above four is rejected before fetching.
When `SCRAPER_COURSE_CODE` is set, the job fetches exactly that course detail
page for the configured academic year and does not call catalogue APIs.

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

The GCP deployment/environment values are confirmed, but Carmen's Cloud SQL
write boundary is still pending. Until it is ready, the job deliberately uses the existing
`LocalDataStore` adapter. It does not invent a second database contract.
The reviewed durable cloud adapter is therefore the remaining dependency, not
silently simulated by this package.

**Cloud Run executions must remain dry-run while `LocalDataStore` is the active
persistence adapter.** Cloud Run Job container filesystems, including `/data`,
are not durable after an execution completes. The Day 6 image consequently
sets `SCRAPER_DRY_RUN=true` so a job cannot report transient local writes as a
durable ingestion success. Set `SCRAPER_DRY_RUN=false` only after the durable
Cloud SQL persistence path is connected. Local development may explicitly set
`SCRAPER_DRY_RUN=false` when local JSON persistence is intended.

Failure or suspicious-zero outcomes do not delete or mark existing records
missing. Dry-run mode does not create or modify record/run files. Scheduler
creation and production scheduled runs remain Day 8 work and are not included.
