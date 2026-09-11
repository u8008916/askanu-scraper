# Day 7 Cloud Ingestion Evidence

Owner: Will  
Date: 2026-09-11  
Current gate: **READY FOR PERSISTENCE REVIEW — awaiting migration deployment and image publish**

This file is the handoff and evidence location for the first bounded COMP1110
cloud ingestion. Do not mark the gate successful until the persisted cloud
record and both real run summaries have been inspected.

## Ready in this repository

- The job can target exactly `COMP1110` with `SCRAPER_COURSE_CODE=COMP1110`.
- The target URL remains under the approved Programs & Courses registry root.
- Schema-v1 identity, academic year, canonical URL, content and hash validation
  happen before persistence.
- Persistence is behind the `DataStore` interface, with an explicit PostgreSQL
  adapter for the shared Cloud SQL path.
- Fixture coverage proves COMP1110 prerequisite extraction, stable identity and
  hash, unchanged reruns, single logical-record persistence, and
  last-known-good preservation after a fetch failure.
- Error summaries redact known secret values and URL credentials/query strings.

## Confirmed GCP path

```text
Cloud Run Job: askanu-scraper
Project/region: askanu-dev-gdg / australia-southeast1
Runtime identity: askanu-scraper-runtime@askanu-dev-gdg.iam.gserviceaccount.com
Cloud SQL: askanu-dev-gdg:australia-southeast1:askanu-postgres-dev
Database/user: askanu / askanu_backend
Password binding: DB_PASSWORD=askanu-db-password:1
```

The deployed job is running as the scraper runtime identity on the merged Day 6
image. Its Cloud SQL Client and password-secret access are confirmed.

## Qasim-approved shared handoff

- The scraper owns parameterised upsert, hash comparison and
  NEW/CHANGED/UNCHANGED detection against `course_program_records`.
- `index_status=PENDING` is the durable Day 7 handoff for NEW/CHANGED records;
  their prior `embedding_version` is cleared.
- UNCHANGED updates observation/status only, preserves index state/version and
  emits no separate embedding signal.
- A durable `ingestion_runs` row is required for Day 7; structured job JSON
  remains supplementary evidence. Carmen owns its minimal shared migration and
  Will owns the upsert.
- The shared table contract was merged in RAG PR #16, including the exact
  11-field `ingestion_runs` table used by this adapter.

Do not add a second schema or write directly to guessed table names while these
items are unresolved. Cloud Run must remain in dry-run mode while
`LocalDataStore` is the active adapter.

## Execution settings after unblock

```text
SCRAPER_SOURCE_ID=courses_programs_and_courses
SCRAPER_DOMAIN=courses
SCRAPER_ACADEMIC_YEAR=2026
SCRAPER_COURSE_CODE=COMP1110
SCRAPER_STORAGE_BACKEND=postgres
SCRAPER_DRY_RUN=false
SCRAPER_TIMEOUT_SECONDS=30
SCRAPER_MIN_REQUEST_INTERVAL_SECONDS=1
```

Secrets must be injected by Secret Manager references and must not appear in
command arguments, this file, image layers or logs.

## Evidence to capture

For run 1, record the execution ID, timestamps, `SUCCESS` status and counts.
Inspect the persisted record and record only non-secret evidence for:

```text
record_id= courses:course:COMP1110_2026
entity_id= COMP1110_2026
academic_year= 2026
canonical_url= https://programsandcourses.anu.edu.au/2026/course/comp1110
content_hash= <observed lowercase SHA-256>
prerequisites= <observed source-derived value>
```

For run 2, record `SUCCESS`, `records_added=0`, `records_changed=0`,
`records_unchanged=1`, the same logical-record count and the same content hash.
Confirm through the agreed index boundary that no embedding/reprocessing was
requested for the unchanged record.

Finally run one safe fetch-failure drill and confirm the failed run is visible
while the previously persisted COMP1110 record remains current.

## Cloud fallback evidence captured

The currently deployed Day 6 image was executed without configuration changes
on 2026-09-11. Execution `askanu-scraper-64l5v` completed successfully in 12.5
seconds with one task succeeded. The execution used:

```text
project/region=askanu-dev-gdg/australia-southeast1
runtime identity=askanu-scraper-runtime@askanu-dev-gdg.iam.gserviceaccount.com
SCRAPER_DRY_RUN=true
approved source=courses_programs_and_courses
academic year=2026
bounded sample=1 course + 1 program
```

This proves the approved-source Cloud Run Job can execute under the intended
runtime identity. It is fallback evidence only: the deployed image predates the
PostgreSQL adapter and therefore cannot satisfy the durable-write or repeated
COMP1110 acceptance criteria.

Application-log retrieval using Will's account was denied because it lacks
`serviceusage.services.use` on `askanu-dev-gdg`. The execution-level success
status remains visible. No secret value was requested or exposed.

## Disposable cross-repository persistence verification

The Day 7 scraper image was built successfully from commit `6b53b73`. Carmen's
exact migration from merged RAG PR #16 was then applied to an isolated local
PostgreSQL 18 container. Two live, approved-source COMP1110 executions through
the real `PostgresDataStore` produced:

```text
run 1: run_aa8a9c8df565 | SUCCESS | seen=1 added=1 changed=0 unchanged=0
run 2: run_1a883d19d6ab | SUCCESS | seen=1 added=0 changed=0 unchanged=1
logical record count: 1
record_id: courses:course:COMP1110_2026
entity_id: COMP1110_2026
academic_year: 2026
canonical_url: https://programsandcourses.anu.edu.au/2026/course/comp1110
content_hash: 37356e7de031c3abc98fd3f4c1db2bde094f167c480320dfce162abf0e56d408
status: UNCHANGED
index_status: PENDING (preserved from NEW; no new signal)
embedding_version: NULL
prerequisites: COMP1100 OR COMP1130 OR COMP1730
```

The lowercase course code in `canonical_url` is the canonical link returned by
the live approved source; stable identity fields remain normalized uppercase.
A third deterministic failed execution persisted a `FAILED` ingestion run with
zero counts. A full-row snapshot before and after that failure was identical,
proving last-known-good preservation.

This verifies scraper-image/schema compatibility before deployment. It does not
replace the two required executions against the shared Cloud SQL destination.

## Remaining blocker

- RAG PR #16 merged the shared `course_program_records` and `ingestion_runs`
  migration, but its evidence explicitly states that no live GCP resource was
  changed. Qasim must confirm/apply the migration to the shared database.
- This scraper persistence branch still requires review/merge and its image must
  be published and deployed. Will currently has Artifact Registry Reader, not
  Writer, so Qasim must publish it or grant the narrowly scoped writer role.
- Will's account can describe and execute the job but cannot read application
  logs until Qasim grants `serviceusage.services.use` (normally via Service Usage
  Consumer) together with the intended logging access.
- Keep the deployed job on `SCRAPER_DRY_RUN=true` until those steps complete.

Local verification completed with the project test environment: **129 passed**.
Use `.venv\\Scripts\\python.exe -m pytest` for local verification in this
environment.
