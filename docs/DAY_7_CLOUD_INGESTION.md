# Day 7 Cloud Ingestion Evidence

Owner: Will  
Date: 2026-09-11  
Current gate: **READY FOR PERSISTENCE REVIEW AND CLOUD EXECUTION**

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

## Shared handoff selected for Day 7

- The scraper owns parameterised upsert, hash comparison and
  NEW/CHANGED/UNCHANGED detection against `course_program_records`.
- `index_status=PENDING` is the durable Day 7 handoff for NEW/CHANGED records;
  their prior `embedding_version` is cleared.
- UNCHANGED updates observation/status only, preserves index state/version and
  emits no separate embedding signal.
- The structured job JSON summary is the Day 7 ingestion-run evidence. No
  additional database table is introduced.

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
canonical_url= https://programsandcourses.anu.edu.au/2026/course/COMP1110
content_hash= <observed lowercase SHA-256>
prerequisites= <observed source-derived value>
```

For run 2, record `SUCCESS`, `records_added=0`, `records_changed=0`,
`records_unchanged=1`, the same logical-record count and the same content hash.
Confirm through the agreed index boundary that no embedding/reprocessing was
requested for the unchanged record.

Finally run one safe fetch-failure drill and confirm the failed run is visible
while the previously persisted COMP1110 record remains current.

## Remaining blocker

- The local shell still has no `gcloud` CLI or Docker daemon access, but the
  deployed job and GCP runtime path have been independently verified.
- Carmen's RAG Day 7 branch supplies `course_program_records` and its reader.
  The scraper persistence diff must be reviewed before enabling real writes.

Local verification completed with the project test environment: **128 passed**.
The direct Windows Python launcher remains inaccessible, so use `uv` for local
verification in this environment.
