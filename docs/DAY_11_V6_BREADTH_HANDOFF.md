# Day 11 V6 breadth handoff

Captured on 2026-09-15 (Australia/Sydney). This is a read-only discovery
handoff. No detail-page breadth run, PostgreSQL write, shared migration, or
production deployment was performed.

## Frozen acceptance denominators

| Entity class | Denominator | 99% gate |
|---|---:|---:|
| Courses | 500 | 495 |
| Programs | 393 | 390 |
| Majors | 109 | 108 |
| Minors | 126 | 125 |
| Specialisations | 128 | 127 |
| Scholarships (approved ANU Finder records) | 379 | 376 |
| Jobs (timestamped snapshot) | 55 | 55 |

The five Programs & Courses classes are independent acceptance denominators;
they must not be pooled into one 1,256-record gate.

## Read-only live census evidence

### Programs & Courses 2026

| Entity class | Raw rows | Unique | Duplicates | Rejected | Denominator | Coverage | Gate | Result |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Courses | 500 | 500 | 0 | 0 | 500 | 100.00% | 495 | PASS |
| Programs | 393 | 393 | 0 | 0 | 393 | 100.00% | 390 | PASS |
| Majors | 109 | 109 | 0 | 0 | 109 | 100.00% | 108 | PASS (discovery only) |
| Minors | 126 | 126 | 0 | 0 | 126 | 100.00% | 125 | PASS (discovery only) |
| Specialisations | 129 | 128 | 1 | 0 | 128 | 100.00% | 127 | PASS (discovery only) |

All four Program feeds were enumerated and unioned by Program identity. No
cross-feed overlap appeared in this snapshot. The one duplicate above is a
Specialisation identity, not a Program overlap.

Source-reported totals remain anomalous and are retained as evidence:

| Feed | Source `TotalCount` | Accessible rows | Unique |
|---|---:|---:|---:|
| Majors | 132 | 109 | 109 |
| Minors | 144 | 126 | 126 |
| Specialisations | 153 | 129 | 128 |

The live census used 19 approved API requests with request spacing. It did not
fetch detail pages or create an ingestion run. Major/Minor/Specialisation are
still excluded from `persisted_candidates`; their shared contract STOP remains
in force.

### Scholarships

| Measure | Count |
|---|---:|
| Finder headline/raw cards | 405 |
| External-scholarship exclusions | 26 |
| Approved unique detail URLs | 379 |
| Duplicate URLs | 0 |
| Other rejection reasons | 0 |

The collector traversed 41 listing pages. Raw cards reconciled exactly to the
405 Finder headline, and 405 - 26 = 379 approved records. Entity discovery is
379/379 (100.00%, gate 376): PASS. Detail parsing, required source-present field
coverage, and persistence were not exercised by this listing-only census.

### Jobs

The healthy-source retry at `2026-09-15T12:28:26.084740+10:00` reconciled:

| Measure | Count |
|---|---:|
| Advertised current vacancies | 55 |
| Approved unique URLs | 55 |
| Base/`?page=1` overlap duplicates | 30 |
| Rejected | 0 |

Entity discovery is 55/55 (100.00%, gate 55): PASS. The live advertised count
is split across nested DOM elements and contains non-ASCII separators; the
updated selector and fixture test cover that structure. The run used three
listing requests and performed no detail fetch/write.

## Representative live detail-field audit

One approved live detail record per domain was parsed through the normal
collector boundary using a dry-run store. All three runs succeeded, produced
non-empty deterministic content, retained canonical source URLs, and wrote no
records or ingestion runs.

- Course `COMP1100_2026`: required identity fields plus source-backed career,
  units, delivery mode, assumed knowledge and offerings were captured.
- Scholarship `anu-international-achievement-award`: all frozen metadata keys
  were present; source-backed status, application, audience/filter, value,
  selection and eligibility evidence was captured.
- Job `563258`: all frozen metadata keys were present and source-backed category,
  employment type, location, classification, salary, closing, status and summary
  evidence was captured.

This representative audit is not the >=99% full-detail field-coverage result.
That denominator still requires the controlled detail traversal/review stage.

## Implemented safety and evidence behavior

- Courses: all eight approved APIs, deterministic pagination, stable identities,
  Program cross-feed dedupe, source totals, raw/unique counts, duplicate/reject
  counts, anomaly reporting, repeated/empty-page termination, and discovery-only
  subplans.
- Scholarships: multi-page traversal, headline census, canonical URL dedupe,
  external/off-boundary rejection reasons, raw-to-approved reconciliation, and
  failure before detail fetch/write on mismatch.
- Jobs: dynamic advertised count, base/page-one overlap detection, continuation
  traversal, canonical URL dedupe, rejection reasons, timestamped read-only
  reporting, and failure before detail fetch/write on mismatch.
- Existing preflight, atomic batch persistence, suspicious-zero, source boundary,
  unchanged/hash, and last-known-good behavior remain intact.

Run a fresh read-only census with:

```powershell
python -m askanu_scraper.breadth --domain all
```

The command uses a dry-run store, fetches listing/search APIs only, and writes
the JSON report to stdout. It does not fetch details or write records/runs.

## Remaining approval gates

- Do not persist Major/Minor/Specialisation until the shared metadata/identity/
  canonical-URL contract and RAG migration are approved.
- Do not broad-write any domain until detail parser/field coverage review,
  staged write, unchanged rerun, and last-known-good failure drill pass.
- Position Description documents remain out of scope.

## Staged-write checklist

- [ ] Qasim reviews the listing census and parser-field evidence.
- [ ] Confirm the approved shared migration/runtime state and PostgreSQL gates.
- [ ] Run a bounded PostgreSQL dry-run and inspect the summary.
- [ ] Run the first staged write and inspect added/changed/rejected counts.
- [ ] Inspect representative `source_records` and `ingestion_runs` rows.
- [ ] Repeat the identical run and require `UNCHANGED` evidence.
- [ ] Exercise fetch/parser/drastic-count failure and confirm last-known-good.
- [ ] Recompute entity and required source-present field coverage.
- [ ] Approve broader production execution only after every prior check passes.
