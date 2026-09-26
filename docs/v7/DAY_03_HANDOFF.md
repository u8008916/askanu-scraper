# AskANU V7 Day 3 scraper/data handoff

**Gate:** Final data/evidence closure against Carmen's frozen retrieval benchmark

**Owner:** Will

**Status:** READY FOR QASIM REVIEW

**Reviewed base:** `93b94ef102ab22df08c01e5ef4245ad6653d98e9`
(merged Scraper PR #37)

**Branch:** `will/v7-day3-evidence-benchmark`

**RAG evidence source:** merged RAG PR #37 at
`54d75f470c2f26b96bce9d5fafe70da8f9b7a6d6`

**Production mutation:** none

## Outcome

Day 3 now closes both evidence obligations without changing retrieval,
reasoning, production schemas, source authority, ingestion, scheduling or
database behavior:

1. the original 14-requirement representative harness remains unchanged and
   demonstrates the shared evidence primitives; and
2. Carmen's exact 24-query holdout/result evidence has a separate, exhaustive
   scraper reconciliation that preserves every frozen expectation while
   exposing synthetic/canonical mismatches.

The added helper only verifies artifact bytes, exact query joins, unchanged
expected IDs/sources/constraints/result expectations, classifications,
ownership and separate provenance denominators. It cannot retrieve, rank,
reason, rewrite an expectation or manufacture institutional provenance.

## Frozen Carmen artifacts

The following files are copied into `fixtures/v7/day3/carmen/` and protected
from line-ending conversion by a path-specific `.gitattributes` rule:

| Artifact | SHA-256 |
|---|---|
| `holdout.json` | `13b061af57a6c2730dc7434f325996f0e2ce536ceddf00281545a89f58bf65b6` |
| `v7_day3_final_retrieval_baseline.json` | `e703b4a49f0dcf7202d8b024fa2fcdba453f11d826857a098d509b60ff4e3534` |
| `v7_day3_final_retrieval_baseline.md` | `9444ae98bb2312f2ff7e640c9dd1a538fe91e7f260e72a1fd647638e21cdc412` |

The holdout is the merged LF blob. The two result copies preserve the reviewed
Windows CRLF bytes whose hashes were recorded in RAG PR #37. Their merged Git
blobs use LF and therefore have different byte hashes; content is unchanged.
This distinction is recorded rather than silently normalised.

Integrity checks establish 24 unique queries, four per domain, and exact
coverage by both the result and reconciliation. Query IDs, expected relevant
record IDs, allowed source IDs, hard constraints, expected answer states,
expected result statuses, population flags and expected failure classes are
retained without revision.

## Two scoreboards, deliberately separate

Carmen's frozen retrieval result:

- 24/24 measured queries;
- failure classes: 20 `NONE`, 4 `DATA`;
- recall@1 92.36%, recall@3 100%, recall@5 100%;
- pre-rerank recall@10, hard-constraint pass, selected-evidence completeness
  and RAG provenance preservation: 100%; and
- no provider errors.

Scraper institutional-evidence reconciliation:

| Classification | Count |
|---|---:|
| `IDENTITY_DEFECT` | 17 |
| `AMBIGUOUS_SOURCE` | 2 |
| `MISSING_SOURCE` | 2 |
| `INCOMPLETE_POPULATION` | 1 |
| `NOT_DATA_FAILURE` | 2 |

Mapping status is 4 exact, 1 partial and 19 unmapped benchmark identities.
Ownership is 18 `CROSS_REPO_CONTRACT`, 4 `SOURCE_PRODUCT_LIMITATION` and 2
`NO_FAILURE`. RAG provenance is preserved for 24/24 benchmark results, while
scraper-complete institutional provenance is only 4/24. These denominators are
not conflated.

The low institutional denominator does not invalidate Carmen's synthetic
retrieval benchmark. It prevents benchmark-only identities or facts from being
presented as verified ANU records. In particular:

- `accommodation:residence:bruce-hall` and `...:ursula-hall` collapse distinct
  approved wing identities; only Burgmann maps exactly in the catering query;
- benchmark-only Scholarship, Job and Event IDs receive no invented entity ID,
  canonical URL or source authority; and
- Carmen's Yukeembruk fixture states $340, while the approved scraper fixture
  records $380. The benchmark value remains benchmark evidence and is not
  adopted as institutional fact.

The four frozen `DATA` cases retain Carmen's failure class and are assigned as
requested:

| Query | Scraper classification | Owner | Reason |
|---|---|---|---|
| `holdout-scholarship-eligibility` | `AMBIGUOUS_SOURCE` | `SOURCE_PRODUCT_LIMITATION` | The approved source cannot guarantee a person's eligibility. |
| `holdout-accommodation-vacancy` | `MISSING_SOURCE` | `SOURCE_PRODUCT_LIMITATION` | The approved accommodation source does not publish current vacancy. |
| `holdout-jobs-incomplete` | `INCOMPLETE_POPULATION` | `SOURCE_PRODUCT_LIMITATION` | The supported current Jobs population is not established as complete. |
| `holdout-events-rubric-organiser` | `MISSING_SOURCE` | `SOURCE_PRODUCT_LIMITATION` | The approved Rubric evidence does not publish the organiser. |

## Representative 14-requirement harness

`fixtures/v7/day3/representative-evidence-audit.json` is unchanged, including
its historical `BLOCKED_PENDING_CARMEN_BENCHMARK` label. It remains a separate
harness artifact and is not rewritten after Carmen's benchmark arrived.

| Domain | Requirements | Structured | Content only | Source missing | Ambiguous source | Incomplete population | Provenance |
|---|---:|---:|---:|---:|---:|---:|---:|
| Courses | 3 | 3 | 0 | 0 | 0 | 0 | 3/3 |
| Scholarships | 2 | 1 | 0 | 0 | 1 | 0 | 2/2 |
| Jobs | 2 | 1 | 0 | 0 | 0 | 1 | 2/2 |
| Accommodation | 2 | 1 | 0 | 1 | 0 | 0 | 2/2 |
| Support | 1 | 1 | 0 | 0 | 0 | 0 | 1/1 |
| Events | 4 | 2 | 1 | 1 | 0 | 0 | 4/4 |
| **Total** | **14** | **9** | **1** | **2** | **1** | **1** | **14/14** |

This baseline remains 10/14 questions with all required evidence, including 9
fully structured and 1 content-only, with 14/14 provenance complete. It is
harness proof, not a claim about Carmen's synthetic identities or the live
institutional corpus.

## Fresh 2026 Programs & Courses audit

On 2026-09-26 the approved collector and detail-coverage path ran once with
`dry_run=true`, a minimum one-second request interval and no detail limit.

Whole domain result:

- approved discovery reconciled;
- 1,256/1,256 course, program, major, minor and specialisation details covered;
- 14,840/14,840 source-present facts captured;
- full detail traversal `true`, status `SUCCESS`; and
- production writes, migrations and persisted subplans: 0.

Course-only accounting:

| Measure | Count |
|---|---:|
| Discovered | 500 |
| Detail pages attempted/fetched | 500/500 |
| Parsed/accepted | 500/500 |
| Explicit rejects | 0 |
| Fetch failures | 0 |
| Parse failures | 0 |
| Validation failures | 0 |
| Unexplained losses | 0 |

Accounting equation: `500 discovered = 500 accepted + 0 explicitly accounted
failures/rejects + 0 unexplained`.

All 500 identity-manifest rows carry a course code, record ID, entity ID,
canonical URL and approved source ID. Duplicate course codes, record IDs,
entity IDs and canonical URLs are all zero; missing/invalid identity lists are
empty. The observed academic year is 2026. The fresh count equals the frozen
Day 16 count (drift 0), but the fresh audit—not the old denominator—is the
current evidence.

Raw evidence is in `courses-population-audit-2026.json`; the compact,
hash-linked accounting is in `courses-population-reconciliation-2026.json`.

## COMP2120 compatibility

The existing generic parser correction remains unchanged. Tests explicitly
establish that:

- simple `successfully completed COMP2100` normalises to the established
  simple form `COMP2100`;
- the concurrent alternative remains
  `successfully completed or be currently studying COMP2100`;
- it never becomes leading `or be currently studying COMP2100`; and
- incompatibilities remain `COMP2130, COMP6120 and COMP6311`.

No course-code-specific parser branch was introduced.

## Exact review commands

All commands are run from the isolated Day 3 worktree with `PYTHONPATH` set to
that worktree's `src` so they cannot import Day 4 code:

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
py -m pytest tests/test_v7_day3_benchmark_evidence.py -q
py -m pytest tests/test_courses_parser.py -q
py -m pytest tests/test_v7_day3_course_population.py tests/test_detail_coverage.py tests/test_v6_detail_gap_fixes.py -q
py -m pytest tests/test_v7_day1_contract.py tests/test_v7_day2_search_metadata.py tests/test_v7_day3_benchmark_evidence.py tests/test_v7_day3_course_population.py -q
py -m pytest -q
git diff --check
```

Results:

- Day 3 focused: 17 passed;
- Courses parser: 16 passed;
- detail/population reconciliation: 43 passed;
- combined Day 1/2/3: 46 passed;
- full suite: 430 passed; and
- `git diff --check`: exit 0.

The final commit identifier is recorded in the PR closure message because a
commit cannot contain its own hash.

## Scope confirmation and residual risk

- Production source, registry or authority changes: 0.
- Serialized schema/API changes: 0.
- Retrieval, ranking or reasoning changes: 0.
- Scheduler, persistence, ingestion or database changes: 0.
- Production writes/migrations: 0.
- Authenticated StarRez or undocumented Rubric requests: 0.
- Day 4 PR #39 changes included or advanced: 0.

Residual risk is explicit: Carmen's benchmark is synthetic and mostly does not
map to scraper canonical identities. It is valid retrieval evidence but cannot
serve as institutional truth. Live population evidence is a point-in-time
2026 audit and may drift after capture; future runs must reconcile rather than
assume 500 remains current.
