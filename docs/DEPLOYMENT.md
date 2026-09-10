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
| `SCRAPER_SOURCE_ID` | `courses_programs_and_courses` | Approved registry ID. |
| `SCRAPER_DOMAIN` | `courses` | Must match the selected registry entry. |
| `SCRAPER_MAX_COURSES` | `2` | Bounded course count; minimum 1. |
| `SCRAPER_MAX_PROGRAMS` | `2` | Bounded program count; minimum 1. |
| `SCRAPER_DRY_RUN` | `true` in the Day 6 container (`false` application default) | Compare normally but suppress all local writes. |
| `SCRAPER_STORAGE_PATH` | `local-data` (`/data` in container) | Existing local JSON handoff. |
| `SCRAPER_TIMEOUT_SECONDS` | `30` | Per-request timeout, 1–300 seconds. |
| `SCRAPER_MIN_REQUEST_INTERVAL_SECONDS` | `1` | Live request spacing, 1–60 seconds. |
| `SCRAPER_SIMULATE_FETCH_FAILURE` | `false` | Deterministic no-network failure drill. |
| `DATABASE_URL` | pending Qasim/Carmen contract | Future Cloud SQL handoff; never logged. |
| `GOOGLE_CLOUD_PROJECT` | supplied at deployment | GCP project selection; never logged. |
| `GOOGLE_CLOUD_LOCATION` | `australia-southeast1` | Initial region assumption. |
| `SCRAPER_USER_AGENT` | `AskANU/0.1` | Production HTTP user agent. |

CLI flags use the lowercase, hyphenated form of the job variables and override
environment values. `--dry-run` and `--simulate-fetch-failure` are boolean
flags. A combined course/program bound above four is rejected before fetching.

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

Until Qasim supplies the concrete deployment/environment contract and Carmen's
Cloud SQL write boundary is ready, the job deliberately uses the existing
`LocalDataStore` adapter. It does not invent a second database contract.
Cloud SQL credentials and a durable cloud adapter are therefore a deployment
dependency, not silently simulated by this Day 6 package.

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
