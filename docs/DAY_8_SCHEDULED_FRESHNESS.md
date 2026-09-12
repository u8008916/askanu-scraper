# Day 8 Scheduled Freshness Evidence and Qasim Handoff

Owner: Will
Date: 2026-09-12
Current gate: **DRY RUN — shared Cloud SQL migration deployment not confirmed**

This is the evidence and review checklist for the first daily Programs &
Courses job. It does not authorize a production write, create IAM bindings, or
create a Scheduler job. Qasim coordinates those changes after confirming
Carmen's existing shared migration is applied.

## Implemented safety boundary

- A fully fetched, parsed, schema-validated and duplicate-checked bounded batch
  is committed with its successful `ingestion_runs` row in one PostgreSQL
  transaction.
- Any record or run-row write error rolls the transaction back. The collector
  emits a redacted `FAILED` summary and attempts a separate durable failure-run
  audit without changing current records.
- Identical hashes preserve the existing content, `collected_at`, index status
  and embedding version; only status and `last_seen_at` change.
- Changed hashes preserve the stable IDs and original `collected_at`, replace
  source-supported content, set `index_status=PENDING`, and clear
  `embedding_version`.
- Fetch, parse, validation, duplicate and suspicious-zero outcomes never delete
  records or mark a bounded sample as `MISSING`.
- Job summary schema v2 adds a supplemental `sanity` object. It records request
  and detail-request counts, five discovery entity counts, rejected candidates,
  and identity/record-ID/canonical-URL duplicate counts. No new shared DB field
  is introduced.

## Bounded discovery policy

The scheduled proposal remains limited to the approved
`courses_programs_and_courses` source, first-page catalogue API requests, one to
four course/program detail records total, and at least one second between live
requests. There is no automatic pagination.

Courses and programs are the only schema-v1 persisted types. Majors, minors and
specialisations are fixture-discovered and included in sanity/duplicate counts,
but are not written until Carmen and Qasim approve their shared record shape.

## Reviewed Cloud Run Job proposal

Existing resource contract:

```text
project: askanu-dev-gdg
region: australia-southeast1
job: askanu-scraper
runtime service account: askanu-scraper-runtime@askanu-dev-gdg.iam.gserviceaccount.com
Cloud SQL attachment: askanu-dev-gdg:australia-southeast1:askanu-postgres-dev
database/user: askanu / askanu_backend
secret binding: DB_PASSWORD=askanu-db-password:1
```

Required non-secret job environment:

```text
SCRAPER_SOURCE_ID=courses_programs_and_courses
SCRAPER_DOMAIN=courses
SCRAPER_ACADEMIC_YEAR=2026
SCRAPER_MAX_COURSES=1
SCRAPER_MAX_PROGRAMS=1
SCRAPER_STORAGE_BACKEND=postgres
SCRAPER_DRY_RUN=true
SCRAPER_TIMEOUT_SECONDS=30
SCRAPER_MIN_REQUEST_INTERVAL_SECONDS=1
CLOUD_SQL_INSTANCE_CONNECTION_NAME=askanu-dev-gdg:australia-southeast1:askanu-postgres-dev
DB_NAME=askanu
DB_USER=askanu_backend
```

`DB_PASSWORD` must remain a Secret Manager reference. Do not put the secret
payload in environment files, CLI arguments, image layers, evidence or logs.
Record the reviewed immutable image digest and resulting Cloud Run revision
here after Qasim publishes/deploys them:

```text
source commit: <PR MERGE SHA>
image digest: <REVIEWED IMAGE DIGEST>
job generation/update time: <OBSERVED VALUE>
```

## Daily Scheduler proposal for Qasim

Proposed dedicated caller identity:

```text
askanu-scraper-scheduler@askanu-dev-gdg.iam.gserviceaccount.com
```

Grant that identity `roles/run.invoker` on the `askanu-scraper` job only. The
identity must belong to the Scheduler job's project and must not be the Google-
managed Cloud Scheduler service agent. The administrator creating/updating the
Scheduler job also needs the normal ability to act as the selected service
account. Do not grant the Scheduler caller database or secret access; the Cloud
Run runtime identity retains those responsibilities.

After Qasim reviews the identity and IAM scope, the proposed command is:

```powershell
gcloud scheduler jobs create http askanu-scraper-daily `
  --project askanu-dev-gdg `
  --location australia-southeast1 `
  --schedule "15 3 * * *" `
  --time-zone "Australia/Canberra" `
  --uri "https://run.googleapis.com/v2/projects/askanu-dev-gdg/locations/australia-southeast1/jobs/askanu-scraper:run" `
  --http-method POST `
  --oauth-service-account-email "askanu-scraper-scheduler@askanu-dev-gdg.iam.gserviceaccount.com" `
  --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform" `
  --max-retry-attempts 1 `
  --min-backoff 60s `
  --max-backoff 300s `
  --attempt-deadline 300s
```

The target is a `*.googleapis.com` endpoint, so Cloud Scheduler must use an
OAuth access token rather than OIDC. The first scheduled execution must remain
bounded and dry-run.

## Acceptance evidence checklist

- [ ] PR URL and merge SHA recorded.
- [ ] Full test count and command recorded.
- [ ] One first run shows stable record IDs/hashes and NEW counts.
- [ ] A second identical run shows the same IDs/hashes, zero logical duplicates,
      only UNCHANGED counts, and no new embedding signal.
- [ ] A controlled fixture change shows CHANGED while IDs and `collected_at`
      remain stable and index state becomes PENDING.
- [ ] Fetch/parser and transaction-failure proofs preserve byte-for-byte or
      row-for-row last-known-good state.
- [ ] Suspicious-zero proof exits non-zero and changes no record.
- [ ] Multi-entity fixture reports course/program/major/minor/specialisation and
      duplicate/rejected counts; only course/program records are persisted.
- [ ] Deployed image digest, job generation and runtime service account captured.
- [ ] Scheduler description shows `15 3 * * *`, `Australia/Canberra`, the Jobs
      v2 `:run` URI and the dedicated OAuth identity.
- [ ] Manual dry-run execution ID and schema-v2 JSON summary captured.
- [ ] Qasim confirms the shared migration gate before any later switch to
      `SCRAPER_DRY_RUN=false`.

## Local evidence captured

Verification command on 2026-09-12:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  --basetemp .test-tmp-day8-final -p no:cacheprovider
```

Result: **132 passed**.

The fixture-backed two-run proof produced one logical COMP1110 record:

```text
record_id: courses:course:COMP1110_2026
entity_id: COMP1110_2026
content_hash: 9a8c5671f65eafed4af46922f645690b23a16e6b8a2e53e80a1ad08e7b33c98c
run 1: seen=1 added=1 changed=0 unchanged=0
run 2: seen=1 added=0 changed=0 unchanged=1
logical records after run 2: 1
```

The controlled-change test preserves IDs and `collected_at`, changes the hash,
reports CHANGED, sets PENDING and clears the embedding version. Fetch failure
preserves the stored record bytes. The injected PostgreSQL run-row failure
rolls the record insert back, and the collector-level persistence failure emits
a safe FAILED summary with no record files.

The bounded multi-entity fixture evidence is:

```text
requests=5
detail_requests=4
course=2 program=2 major=1 minor=1 specialisation=1
duplicate_identities=1 rejected_candidates=2
persisted_records=4 (courses/programs only)
```

This is deterministic local/adapter evidence. It does not claim a shared Cloud
SQL write, deployed image, Scheduler resource or IAM change.

## Blocked handoff bundle

If the shared migration, image publication, logs or Scheduler IAM remain
blocked, send Qasim this document plus the PR/SHA, test output, schema-v2 run
summaries, two-run ID/hash comparison, discovery counts and exact missing IAM or
migration dependency. Do not create a competing production table or disable the
dry-run gate.

## Google Cloud references

- Cloud Run, "Execute jobs on a schedule":
  https://cloud.google.com/run/docs/execute/jobs-on-schedule
- Cloud Scheduler HTTP target authentication:
  https://cloud.google.com/scheduler/docs/http-target-auth
- `gcloud scheduler jobs create http` reference:
  https://cloud.google.com/sdk/gcloud/reference/scheduler/jobs/create/http
