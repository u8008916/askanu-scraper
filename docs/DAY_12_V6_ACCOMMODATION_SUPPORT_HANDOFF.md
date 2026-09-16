# Day 12 V6 Accommodation and Support handoff

Captured on 2026-09-16 (Australia/Sydney). The two collectors are independent,
their approved public universes are frozen, fixture and live safety gates pass,
and both live universes exceed the 99% entity and required source-present fact
targets. Cloud SQL writes were not performed because the shared Accommodation
and Support contracts still require Qasim/Carmen cross-repo approval and this
workspace has no database runtime configuration.

## Frozen source universes

| Domain | Approved registry | Frozen denominator | 99% gate | Approved exclusions |
|---|---|---:|---:|---|
| Accommodation | `https://study.anu.edu.au/accommodation/our-residences` | 19 public residence detail pages | 19 | StarRez/login/application portal; other living-option pages |
| Support | `https://anusa.com.au/student-assistance/` | 6 top-level category detail pages | 6 | Additional ANU pages without exact registry approval; nested ANUSA topics are facts of their parent category, not separate entities |

The Support entities are Academic, Accommodation, Financial, Disciplinary,
Physical and Mental Health, and Sexual Assault and Sexual Harassment. No
additional ANU Support URL is active in this freeze.

## Proposed shared contracts for Qasim/Carmen review

These are **proposed scraper-side Accommodation v1 and Support v1 shared
metadata contracts**. They are not yet approved cross-repo contracts. Both
PostgreSQL approval flags remain off until Qasim and Carmen confirm an exact
match or approve the smallest required alignment change.

Both domains use the common normalized-record envelope in `DATA_SCHEMA.md`.
Missing scalar evidence is `null`; required identity fields are never replaced
with placeholders.

### Proposed Accommodation v1

| Rule | Exact proposal |
|---|---|
| `domain` | `accommodation` |
| `source_id` | `accommodation_anu_study` |
| `metadata_json.entity_type` | `residence` |
| `entity_id` | Lowercase canonical residence URL slug matching `[a-z0-9]+(?:-[a-z0-9]+)*` |
| `record_id` | `accommodation:residence:<entity_id>` |
| Canonical URL | Exactly `https://study.anu.edu.au/accommodation/our-residences/<entity_id>`; no credentials, port, query, fragment, or trailing slash |

`metadata_json` has exactly these keys and shapes:

| Key | Type | Missing-source representation |
|---|---|---|
| `entity_type` | literal `"residence"` | not nullable |
| `category` | string or null | `null` |
| `location` | string or null | `null` |
| `catering_options` | array of non-empty strings | `[]` |
| `audiences` | array of non-empty strings | `[]` |
| `advertised_rate` | string or null | `null` |
| `cost_period` | string or null | `null` |
| `rooms` | array of room objects | `[]` |
| `features` | array of non-empty strings | `[]` |
| `overview` | string or null | `null` |
| `accessibility` | string or null | `null` |
| `application_text` | string or null | `null` |
| `application_url` | HTTPS StarRez subdomain URL or null | `null` |
| `eligibility` | string or null | `null` |
| `contact` | exact contact object | object with nullable values |
| `vacancy_status` | string or null | `null` |

Each room object has exactly `name`, `rate`, `contract`, `inclusions`, and
`other_fees`. `name` is a required non-empty string; the other four values are
strings or null and preserve published wording. `contact` has exactly `email`,
`phone`, `location`, and `hours`, each a string or null.

Published residence/category/location/catering/audience/rate/room/features/
application/contact wording may be stored. Location is populated only from a
discrete published field; location prose remains in `overview`. Eligibility is
null when not published. Vacancy is never derived from application status,
rates, dates, room lists, or an application link; it remains null unless an
approved live public source explicitly publishes it.

The only approved external Accommodation URL shape is a published HTTPS
`*.starrezhousing.com` application destination stored in `application_url`.
It is link-only and is never fetched. A record is rejected for an invalid or
mismatched domain/source/entity type/ID, an off-boundary or non-canonical URL,
missing detail title, canonical-link mismatch, unaligned room-name/fee panels,
duplicate identity/URL, or a listing count that does not reconcile to the
frozen 19-entity universe. StarRez is always rejected as a collection target.

### Proposed Support v1

| Rule | Exact proposal |
|---|---|
| `domain` | `support` |
| `source_id` | `support_anusa_student_assistance` |
| `metadata_json.entity_type` | `support_service` |
| `entity_id` | Lowercase top-level category URL slug matching `[a-z0-9]+(?:-[a-z0-9]+)*` |
| `record_id` | `support:service:<entity_id>` |
| Canonical URL | Exactly `https://anusa.com.au/student-assistance/<entity_id>/`; no credentials, port, query, or fragment |

`metadata_json` has exactly these keys and shapes:

| Key | Type | Missing-source representation |
|---|---|---|
| `entity_type` | literal `"support_service"` | not nullable |
| `category` | string or null | `null` |
| `purpose` | string or null | `null` |
| `audiences` | array of non-empty strings | `[]` |
| `contact` | exact contact object | object with nullable values |
| `hours` | string or null | `null` |
| `access` | string or null | `null` |
| `cost` | string or null | `null` |
| `topics` | array of topic objects | `[]` |
| `referrals` | array of referral objects | `[]` |

`contact` has exactly `email`, `phone`, and `location`, each a string or null.
A topic object has exactly `title` (required non-empty string), `description`
(string or null), and `url` (HTTP(S) URL). A referral object has exactly
`label` (required non-empty string) and `url` (HTTP(S) URL). Topic cards remain
facts within their parent service and never become top-level Support entities.

Purpose/category/audience/contact/location/cost/topics/referrals are stored only
when published. Hours and access are service-level facts only when the category
contact content explicitly publishes them; hours or availability belonging to
a referred service are not attributed to ANUSA. The scraper never invents
service availability, emergency coverage, response times, guarantees,
diagnoses, or personal/medical/legal advice.

Published HTTP(S) external content links may be retained as referrals but are
never fetched by this collector. A record is rejected for an invalid or
mismatched domain/source/entity type/ID, a nested topic URL used as entity
identity, an off-boundary or non-canonical category URL, missing main content or
title, canonical-link mismatch, duplicate identity/URL, or a registry count
that does not reconcile to the frozen six-entity universe. Additional ANU
Support pages remain out of scope until their exact targets are approved.

## Live coverage and source health

The final full traversals used dry-run stores, so the comparison path ran but no
records or ingestion runs were persisted.

| Domain | Run ID | Requests | Parsed / denominator | Entity coverage | Required published facts | Rejected / duplicate |
|---|---|---:|---:|---:|---:|---:|
| Accommodation | `run_8648a3b2efc8` | 20 (1 listing + 19 details) | 19 / 19 | 100.00% | 1,086 / 1,086 (100.00%) | 0 / 0 |
| Support | `run_c63a11660ed9` | 7 (1 registry + 6 details) | 6 / 6 | 100.00% | 163 / 163 (100.00%) | 0 / 0 |

The fact denominator counts every required contract fact explicitly present in
the frozen pages. Source-absent nullable fields are excluded. Listing cards,
detail identities, room names/table cells, category cards, content links, and
canonical URLs were reconciled with independent source-specific selectors.
The machine-readable result, representative hashes, exact field presence, and
named gaps are in `day12-coverage-evidence.json`.

Accommodation captured 96 named room variants with each published rate,
contract, inclusion, and other-fee cell kept as text. All 19 records contain
category, catering, audience, overview, cost-period, room, feature, and contact
objects. Eighteen listing cards publish an advertised rate and 18 detail pages
publish an accessibility section. Fourteen pages publish the ANU application
footer/link. No page publishes a discrete residence-location or eligibility
field; location wording remains in the source overview. No page publishes live
vacancy, so all 19 `vacancy_status` values are null. John XXIII College is the
single source example without a listing rate or accessibility section.

Support captured purpose, category, the source-wide `all ANU Students`
audience, free-service wording, email, phone, and location for all six records.
It captured 29 internal topics and eight external published referrals. The
category contact block publishes no service hours or access method, so those
fields remain null. Hours appearing inside descriptions of referred services
are not attributed to ANUSA. Disciplinary and SASH publish no internal topic
cards; Academic, Disciplinary, and Physical/Mental Health publish no external
referral link at the category-page level.

Gap-audit run IDs are `run_ce9846be297f` (Accommodation) and
`run_486460383810` (Support).

## Staged write and idempotency evidence

After fixture dry-runs and failure tests passed, one live record per domain was
written to a local durable store and the identical request was repeated.

| Domain | First local write | Result | Identical rerun | Result | Stable sample |
|---|---|---|---|---|---|
| Accommodation | `run_5d0d93c31832` | 1 NEW | `run_9fe3c41e8c82` | 1 UNCHANGED | `accommodation:residence:yukeembruk`, hash `bbc87d145a03e4cb20e076ea8bd531e00ca48a09e20a0d8c4907f0063abb57ed` |
| Support | `run_10f06e1e81c5` | 1 NEW | `run_3eb9aa062054` | 1 UNCHANGED | `support:service:academic`, hash `0abfa8db6ff6e50fbd61bd5799a264cb61c32f2432948f2bee4dcf25aab732a5` |

The Cloud-style one-shot CLI path also passed in dry-run mode:

- Accommodation: `run_344541a7afd7`, exit 0, 19-card census, one parsed detail.
- Support: `run_b83f64612e75`, exit 0, six-card census, one parsed detail.

## Failure and safety evidence

The focused Day 12 tests cover:

- listing and detail fixtures for both source-specific layouts;
- stable IDs, canonical URLs, deterministic content hashes, and exact metadata;
- first write and unchanged rerun;
- listing-fetch and detail-parser failure with last-known-good preservation;
- zero results as `SUSPICIOUS_ZERO` with no record write;
- frozen-count mismatch before any detail request;
- duplicate identity/URL checks and atomic batch persistence;
- strict approved detail URL boundaries;
- executable/untrusted source markup removal;
- StarRez retained only as an outbound application URL and never fetched;
- missing Support hours/access and Accommodation vacancy remaining null; and
- PostgreSQL approval gates rejecting both domains before fetch/connection.

Full test result: **273 passed**. Focused Day 12 result: **21 passed** (six
parser tests plus 15 collector/job tests).

## Cloud and DB gate

There is no Cloud execution ID or Cloud SQL row count for these two domains.
That is an explicit blocker, not omitted evidence:

- `docs/DECISION_LOG.md` records the v1 contracts as pending Qasim/Carmen
  cross-repo approval.
- The RAG/shared migration has not been shown to accept these exact metadata
  contracts.
- `DATABASE_URL`, `PGHOST`, `PGDATABASE`, `PGUSER`, and
  `GOOGLE_CLOUD_PROJECT` are unset in this workspace.
- The one-shot job defaults both
  `SCRAPER_ACCOMMODATION_POSTGRES_APPROVED` and
  `SCRAPER_SUPPORT_POSTGRES_APPROVED` to false and rejects PostgreSQL before
  collection unless the matching gate is explicitly approved.

After approval and migration deployment, run one bounded PostgreSQL dry-run,
one single-record write, inspect `source_records` and `ingestion_runs`, repeat
for `UNCHANGED`, run the failure drill, and only then set the full 19/6 bounds.

## Revision evidence

PR #26 is on branch `will/v6-day12-accommodation-support`. The branch contains
one Day 12 commit over squash-merged scraper main `5873826`; it does not carry
the superseded pre-squash Day 11 commit. Use the commit containing this handoff
as the implementation SHA.
