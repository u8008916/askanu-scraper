# V7 Day 4 — Accommodation evidence handoff

**Owner:** Will

**Reviewer:** Qasim

**Lane:** Scraper/data

**Evidence captured:** 2026-09-25 (Australia/Sydney)

## Gate outcome

PASS. The approved Accommodation source still reconciles to the frozen 19-residence universe, all 19 public detail pages parsed with stable identities, and all source-present audited facts were captured. This does **not** claim that every comparison fact exists: the live source exposed an advertised rate for 18/19 records, an application link for 14/19, and an explicit vacancy fact for 0/19.

No production parser, schema, registry, API, source boundary, or persistence behaviour changed. Day 4 adds reviewable evidence and regression tests around the existing shared `CommonRecord`, V7 producer contract, resolver metadata projection, source registry, and bounded collector.

## Reviewed base and files

Implementation branch started from reviewed `origin/main` commit `93b94ef102ab22df08c01e5ef4245ad6653d98e9` (merged Day 2). The open/unreviewed Day 3 branch was not included.

Day 4 files:

- `fixtures/v7/day4/accommodation-evidence-contract.json` — offline capability/field matrix, representative present/missing cases, and unsupported operations.
- `tests/test_v7_day4_accommodation_evidence.py` — contract, parser, registry, identity, comparison, and StarRez boundary proof.
- `day4-accommodation-source-health.json` — bounded live dry-run audit evidence.
- `docs/v7/DAY_04_HANDOFF.md` — this review record.

## Behavioural impact

- Catering and audience filters are supported only by exact source-backed membership values.
- Advertised and room rates remain exact text. The implementation does not create numeric prices, totals, ranges, or “cheapest” rankings.
- Room name, rate, contract term, inclusions, and other fees remain paired in each room object; the published cost-period wording stays separate and must qualify comparisons.
- Published StarRez URLs are navigation evidence only. The collector does not fetch StarRez, and link presence does not imply vacancy or application status.
- Missing facts remain unknown. In particular, `vacancy_status: null` is neither `false` nor an available/unavailable claim.
- Accommodation resolver metadata continues to contain the canonical residence name and no invented temporal value or alias.

## Live bounded audit

Command run from a clean detached worktree at the reviewed base:

```text
py -m askanu_scraper.detail_coverage --domain accommodation --min-request-interval-seconds 1 --output day4-accommodation-source-health.json
```

Artifact: `day4-accommodation-source-health.json`

LF-normalized SHA-256: `3e958e9ae0dfb0bf0700c51eb4dda8445db9f803ec39fc53530a0d4e50a186b8`

Captured at: `2026-09-25T12:59:11.798607+10:00`

Exact audit results:

| Check | Result |
|---|---:|
| Dry run | `true` |
| Production records written | `0` |
| Migrations applied | `0` |
| Advertised / discovered / approved / frozen | `19 / 19 / 19 / 19` |
| Detail pages attempted / fetched | `19 / 19` |
| Parsed records | `19` |
| Parser exceptions / malformed / rejected | `0 / 0 / 0` |
| Canonical mismatches | `0` |
| Duplicate record IDs / canonical URLs / normalized identities | `0 / 0 / 0` |
| Source-shape anomalies | `[]` |
| Source-present facts captured | `255 / 255` |
| Domain health | `GREEN` |

`255 / 255` measures capture of facts the audited source actually presented. It is not a completeness claim for absent fields.

## Capability and field matrix

The checked-in JSON matrix covers exactly all 15 Accommodation `structured_fact_paths` in the frozen Day 1 producer contract.

| Field | Conservative capability | Live source-present / captured | Explicit boundary |
|---|---|---:|---|
| `category` | Exact membership | 19 / 19 | No guessed equivalence |
| `location` | Exact when present | 0 / 0 | No inference from name/contact |
| `catering_options` | Exact membership | 19 / 19 | No synonyms or feature inference |
| `audiences` | Exact membership | 19 / 19 | No personal eligibility |
| `advertised_rate` | Exact-text comparison | 18 / 18 | No numeric normalization/ranking/backfill |
| `cost_period` | Exact-text qualifier | 19 / 19 | No inferred currentness/equivalence |
| `rooms` | Paired exact-text comparison | 19 / 19 | No flattening or detached prices |
| `features` | Exact membership | 19 / 19 | Absence is not false |
| `overview` | Content only | 19 / 19 | No deterministic attribute extraction |
| `accessibility` | Content only when present | 0 / 0 | No universal accessibility boolean |
| `application_text` | Navigation text when present | 14 / 14 | No outcome/availability inference |
| `application_url` | Navigation only when present | 14 / 14 | Never fetch authenticated StarRez |
| `eligibility` | Content only when present | 0 / 0 | No personal decision |
| `contact` | Exact nested facts | 19 / 19 | Missing subfields stay missing |
| `vacancy_status` | Explicit only | 0 / 0 | No vacancy inference |

Unsupported filters/claims are enumerated in the fixture: numeric price range/sort, cheapest or total-cost ranking, vacancy or room availability, personal eligibility, inferred location/accessibility, application status/outcome, and magic wording/unreviewed synonyms.

## Representative evidence

- Yukeembruk fixture: exact listing rate, two independently paired room/cost records, cost period, full contact example, published application link, and null vacancy.
- Davey Lodge fixture: exact listing rate, one room/cost record, the same cost-period semantics, missing optional contact subfields, published application link, and null vacancy.
- Synthetic omission regression: removing only the listing `advertised_rate` keeps it `null`; the parser does not backfill it from the room tariff. This is a parser-boundary test, not an institutional claim about Davey Lodge.

## Test evidence

Focused gate:

```text
py -m pytest tests/test_accommodation_parser.py tests/test_day12_collectors.py tests/test_v7_day1_contract.py tests/test_v7_day2_search_metadata.py tests/test_v7_day4_accommodation_evidence.py -q
59 passed in 0.97s
```

Full repository gate:

```text
py -m pytest -q
424 passed (clean worktree at the Day 4 commit)
```

The 11 Day 4 tests specifically prove:

- exact composition with frozen Day 1 and Day 2 contracts;
- complete one-for-one field-matrix coverage;
- immutable dry-run artifact/hash and zero production mutation;
- live field asymmetry without absence claims;
- stable record IDs, canonical URLs, source authority, and lookup terms;
- exact catering/audience membership;
- exact-text rate/cost-period and room-field pairing;
- present/missing facts remain distinct and are not backfilled;
- published StarRez navigation is retained but never fetched;
- all 19 audited identities remain unique and inside the approved boundary;
- unsupported operations are explicit, with no magic-word shortcuts.

## Risks and dependencies

- Live public pages can drift after the captured timestamp; this artifact is a timestamped audit, not a perpetual guarantee.
- Published cost periods and rate wording can become stale; downstream consumers must show source context and freshness rather than infer currentness.
- A room tariff is not a total cost, and absent fees/inclusions are unknown.
- Application-link absence or presence says nothing about availability, vacancy, eligibility, or outcome.
- Deterministic filtering is limited to exact source-backed values; content-only fields need downstream evidence-aware handling.
- Depends on reviewed Day 1 producer capability and Day 2 resolver metadata contracts, the frozen 19-residence registry, and existing CommonRecord/collector/parser safeguards.
- Any future source, schema, or API change still requires explicit review. No production crawl/write or migration is authorized by this handoff.

## Qasim review commands

```text
git diff origin/main...HEAD -- fixtures/v7/day4/accommodation-evidence-contract.json tests/test_v7_day4_accommodation_evidence.py day4-accommodation-source-health.json docs/v7/DAY_04_HANDOFF.md
py -m pytest tests/test_v7_day4_accommodation_evidence.py -q
py -m pytest -q
```
