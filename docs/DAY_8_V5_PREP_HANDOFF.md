# V5 Day 8 Source and Freshness Preparation Handoff

Owner: Will
Date: 2026-09-12
Scope: three-hour preparation block only

## Status

The five remaining domains were audited against the policy and machine-readable
registry. Courses freshness primitives were reviewed for reuse. One reduced,
source-supported public-page sample now exists for Scholarships and Jobs. No
collector, schema, credential, production source, cloud job or schedule was
enabled or changed by this preparation work.

Verification: **135 tests passed**, including three focused V5 preparation
checks for registry state, fixture provenance and exclusion of Jobs application
flows.

## Approved boundaries and claim limits

| Domain | Registry source ID | Approved starting boundary | Allowed claims from explicit source evidence | Stop/escalate |
|---|---|---|---|---|
| Scholarships | `scholarships_anu_finder` | `https://study.anu.edu.au/scholarships` and public `/scholarships/find-scholarship` listing/detail pages | Status, application requirement, Featured, study filters, value, selection basis, dates and eligibility | Do not infer deadlines/status; confirm whether external-scholarship detail targets may be followed before collecting them |
| Jobs | `jobs_anu_search` | `https://jobs.anu.edu.au/jobs/search` and its public ANU job detail links | Title, category, employment type, location, classification, closing date and source summary | Do not follow application/candidate-account flows or infer work eligibility/status |
| Accommodation | `accommodation_anu_study` | `https://study.anu.edu.au/accommodation`; policy also names public `/accommodation/our-residences` | Published residence type, catering, rate wording and application information | Never scrape authenticated StarRez; Qasim should confirm exact residence-detail traversal and request bound |
| Support | `support_anusa_student_assistance` | `https://anusa.com.au/student-assistance/` | Published categories, descriptions, contact/action URLs and explicit hours | Exact supplementary ANU support-page targets remain unresolved and must be registered/approved first |
| Events | `events_anu_official` | `https://www.anu.edu.au/events` | Public event identity, title, dates, venue/format, organiser, description and canonical URL | Exact pagination/window policy remains to be agreed; Rubric is not a fallback unless separately approved |

Rubric remains `rubric_unified_search`, `active=False`, cadence `DISABLED` and
`PENDING_APPROVAL`. Its root entry does not approve an endpoint. Do not call an
undocumented/internal API or store cookies/tokens.

## Reusable Courses primitives

The next collectors should reuse these behaviours rather than reproduce source-
specific versions:

- `CommonRecord` and `IngestionRun` validation for provenance, timezone-aware
  observations and controlled statuses.
- Registry enforcement before every fetch; same-origin/detail-boundary checks
  remain collector-specific.
- Bounded request counts, explicit timeouts and minimum request spacing.
- Fetch-all/parse-all/validate-all/duplicate-check before the first batch write.
- Stable domain-scoped IDs and SHA-256 of deterministic normalized `content`.
- Atomic `save_records_and_run`: NEW/CHANGED become PENDING; UNCHANGED preserves
  index state and only advances observation state.
- FAILED/SUSPICIOUS_ZERO preserves last-known-good and never mass-marks a
  bounded or failed sample missing.
- Dry-run performs comparison and summaries without record/run writes.
- Summary schema v2 reports comparison counts plus non-secret request,
  discovery, rejection and duplicate sanity counts.

## Fixture preparation evidence

- Scholarships listing sample:
  `fixtures/scholarships/anu_scholarship_listing_sample.html`
- Existing Scholarships detail sample:
  `fixtures/scholarships/anu_humanitarian_scholarship_sample.html`
- Jobs listing/detail-field sample:
  `fixtures/jobs/anu_jobs_listing_sample.html`

The two new files are deliberately reduced evidence samples. They record their
approved source and capture date and do not claim to be durable copies of the
complete live DOM. Parser implementation must validate current selectors with a
fresh bounded request and add malformed/missing/closed examples.

## Sunday Scholarships kickoff

1. Confirm with Carmen/Qasim whether Scholarships fits the existing generic
   record table through `metadata_json`; do not create a competing table or new
   top-level fields.
2. Inspect one bounded finder response and one registered same-site detail page;
   set explicit listing/detail/request limits before coding.
3. Implement listing discovery separately from detail parsing so one malformed
   card/detail fails preflight without partial writes.
4. Define deterministic scholarship identity from source-supported identity or
   canonical path, then canonical content ordering and SHA-256 hashing.
5. Add open/closed, automatic/requires-application, Featured/non-Featured,
   missing-deadline, duplicate, suspicious-zero, idempotency, controlled-change
   and failed-fetch fixtures/tests.
6. Stay local/dry-run until the schema and source bounds are reviewed; only then
   prepare a bounded Cloud SQL proof.

## Monday Jobs kickoff notes

- Treat the public search page as discovery and public `/jobs/<slug>` pages as
  detail evidence; application and candidate-account destinations are excluded.
- Prefer source job ID `563693` when present for stable identity; do not derive
  current/open state from missing source evidence.
- Preserve the displayed closing text and separately normalize its Canberra-
  aware value only after date/time semantics are tested.
- Add open, expired/closed and missing-optional fixtures before any cloud write.
- A zero/drastically reduced parse must fail sanity review, not mark current jobs
  missing.

## Qasim checkpoint

Please confirm before Sunday shared-cloud work:

1. Scholarships external-detail policy and maximum listing/detail requests.
2. Whether the existing generic record schema accepts scholarship metadata keys.
3. Accommodation residence-detail boundary and request limit.
4. Exact supplementary ANU Support URLs, if any.
5. Events pagination/window limit; Rubric remains disabled pending exact approval.

Freshness hardening branch/commit: `day8-safe-freshness` /
`794f41a2053772623ba3396860ae42395768fcfd` (132 tests passed before this V5
preparation commit).
