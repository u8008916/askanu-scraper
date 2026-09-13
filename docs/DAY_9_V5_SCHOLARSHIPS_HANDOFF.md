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

The full local suite passes: **171 tests passed** (including 42 focused
Scholarship/PostgreSQL tests). A live dry-run against one
finder page and the configured maximum of ten same-site detail candidates also
succeeded:

```text
run_id: run_d1f05fbe3093
status: SUCCESS
requests: 9 (1 listing + 8 accepted same-site details)
records_seen / NEW: 8 / 8 (dry-run comparison only)
rejected listing cards: 2 external scholarships
duplicate records / URLs: 0 / 0
duration: 11.654 seconds
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

No approved Day 9 scraper image is deployed. The cloud job was not changed or
executed for Scholarships. This account cannot inspect the private RAG service,
so deployment of the merged shared migration is not asserted here.

## Record and safety contract

- Identity is the canonical lowercase detail slug: `entity_id=<slug>` and
  `record_id=scholarships:scholarship:<slug>`.
- `metadata_json` matches Qasim's shared v1 names: `entity_type`, `featured`,
  `status`, `application_required`, the four filter arrays, `value`,
  `selection_basis`, ISO `opening_date`/`closing_date`, and `eligibility`.
- Unpublished or placeholder deadlines remain `null`. Application dates remain
  in Scholarship metadata/content; top-level `effective_from`/`effective_to`
  stay `null` because an application window is not general record validity.
- Discovery is fixed to one finder page and at most ten details, with a minimum
  one-second interval for live HTTP. External, off-origin, application/auth,
  malformed, duplicate and over-limit links are rejected before persistence.
- All accepted details are fetched, parsed and validated before one atomic batch
  write. Fetch/parser failure or suspicious zero preserves last-known-good.
- A RUNNING audit is persisted before collection. The accepted batch and final
  SUCCESS/count update share one transaction; a failure rolls back that batch
  before a separate FAILED recovery update.
- Because the run is a bounded sample rather than a complete source snapshot,
  unseen records remain last-known-good and are not marked `MISSING`.

## Navigation links versus evidence links

The persisted identity rule applies only to individual Scholarship detail
records. The App's official navigation links remain valid as static resources:

```text
https://study.anu.edu.au/scholarships
https://study.anu.edu.au/scholarships/find-scholarship
```

They create no `entity_id` or `record_id` and must not be passed through the
persisted-detail validator. By contrast, a source link supporting an answer
about a specific Scholarship must be the exact stored detail `canonical_url`;
the App and model must not construct it.

## Cloud SQL release gate

RAG PR #19 merged the approved shared contract at head
`8006e900c5b9be82ab01066ca46d08da7daa28ee` (merge commit
`6e5bd0b91bc66ff9a007d6ac36853dbeed595185`). The canonical writable table is
now `source_records`; `course_program_records` is the read-only compatibility
view. This scraper branch targets `source_records` and tests that it never
writes through the compatibility view.

The deployed migration, PostgreSQL 18 behavior, runtime grants, COMP1110
regression and Scholarship live read must still be verified by the integration
owner. The job enforces the write hold with:

```text
SCRAPER_SCHOLARSHIP_POSTGRES_APPROVED=false
```

After those live gates pass and the reviewed image is deployed, set the gate to
`true` and capture, in order:

1. bounded PostgreSQL dry-run;
2. first real run showing `NEW`;
3. identical second run showing `UNCHANGED`;
4. representative stored scholarship plus `ingestion_runs` row;
5. simulated fetch failure showing the stored record remains unchanged.

Do not enable the daily Scheduler until Qasim separately approves the fetch/rate
policy and the resulting source-health evidence.
