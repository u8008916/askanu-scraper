# V5 Day 9 Scholarships Handoff

Owner: Will
Date: 2026-09-13
Source: `scholarships_anu_finder`

## Status

The approved public ANU Scholarship Finder now has a bounded listing/detail
collector, normalized scholarship records, deterministic slug-based identity,
atomic comparison/persistence, one-shot job selection and failure-safe tests.
No Scheduler, schema migration, production deployment or Cloud SQL write was
performed.

The full local suite passes: **169 tests passed**. A live dry-run against one
finder page and the configured maximum of ten same-site detail candidates also
succeeded:

```text
run_id: run_8691f33b7361
status: SUCCESS
requests: 9 (1 listing + 8 accepted same-site details)
records_seen / NEW: 8 / 8 (dry-run comparison only)
rejected listing cards: 2 external scholarships
duplicate records / URLs: 0 / 0
duration: 11.660 seconds
```

Because dry-run suppresses both record and ingestion-run writes, the live run
did not modify local or cloud data.

## Cloud preflight

A read-only `gcloud run jobs describe` on 2026-09-13 confirmed that generation
5 of `askanu-scraper` still runs the reviewed Day 8 Courses configuration:

```text
image: .../askanu-scraper@sha256:f52a4c9cc3e1bc05598ddb8d23093dae50ad7753de5c478424964ea29150512f
SCRAPER_SOURCE_ID=courses_programs_and_courses
SCRAPER_DOMAIN=courses
SCRAPER_STORAGE_BACKEND=postgres
SCRAPER_DRY_RUN=true
```

No approved Day 9 image or shared multi-domain table is deployed. The cloud job
was not changed or executed for Scholarships.

## Record and safety contract

- Identity is the canonical lowercase detail slug: `entity_id=<slug>` and
  `record_id=scholarships:scholarship:<slug>`.
- `metadata_json` matches Qasim's shared v1 names: `entity_type`, `featured`,
  `status`, `application_required`, the four filter arrays, `value`,
  `selection_basis`, ISO `opening_date`/`closing_date`, and `eligibility`.
- Unpublished or placeholder deadlines remain `null`. Unambiguous dates are
  also represented as Canberra-aware `effective_from`/`effective_to` values.
- Discovery is fixed to one finder page and at most ten details, with a minimum
  one-second interval for live HTTP. External, off-origin, application/auth,
  malformed, duplicate and over-limit links are rejected before persistence.
- All accepted details are fetched, parsed and validated before one atomic batch
  write. Fetch/parser failure or suspicious zero preserves last-known-good.
- Because the run is a bounded sample rather than a complete source snapshot,
  unseen records remain last-known-good and are not marked `MISSING`.

## Cloud SQL release gate

Qasim has confirmed that the existing `course_program_records` persistence and
RAG path is Courses/Programs-specific and must not receive Scholarship rows.
Carmen owns the smallest shared multi-domain persistence/RAG generalisation;
Qasim must review that deployed boundary before any Scholarships PostgreSQL
dry-run or write. The job enforces this with:

```text
SCRAPER_SCHOLARSHIP_POSTGRES_APPROVED=false
```

After that generalisation, approval and reviewed image deployment, set the gate
to `true` and capture, in order:

1. bounded PostgreSQL dry-run;
2. first real run showing `NEW`;
3. identical second run showing `UNCHANGED`;
4. representative stored scholarship plus `ingestion_runs` row;
5. simulated fetch failure showing the stored record remains unchanged.

Do not enable the daily Scheduler until Qasim separately approves the fetch/rate
policy and the resulting source-health evidence.
