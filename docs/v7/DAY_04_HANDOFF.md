# V7 Day 4 — Accommodation evidence handoff

**Owner:** Will

**Reviewer:** Qasim

**Lane:** Scraper/data

**Evidence refreshed:** 2026-09-27 (Australia/Sydney)

## Producer evidence gate outcome

PASS. The approved Accommodation source still reconciles to the frozen 19-residence universe, all 19 public detail pages parsed with stable identities, and all 273 source-present audited facts were captured. The refreshed source exposes Accessibility content for 18/19 records, an advertised rate for 18/19, an application link for 14/19, and an explicit vacancy fact for 0/19.

The Accommodation parser, schema, registry, API, source boundary, and persistence behaviour are unchanged. The audit-only source-presence detector was corrected to recognise the live ANU two-column Accessibility layout, and the fresh artifact explicitly records zero production writes, zero migrations, and zero StarRez requests.

The Carmen/Will numeric-price evidence rule remains frozen exactly as recorded below. PR #39 is reconciled onto the accepted Day 3 scraper base. The final producer/consumer cross-check against Carmen's reconciled RAG head passed with zero shape and zero semantic mismatches. Day 4 scraper/data is ready for final cross-repository PM acceptance, but the PR must not be merged until Qasim closes the remaining release gate.

## Reviewed base and files

PR #39 was rebased without dropping its Day 4 commits from the original Day 2 base onto accepted scraper main commit `301c3a2cf0f00f7c0d09ea9fc45a72ce446de2d4` (merged Day 3). The historical 2026-09-25 audit remains unchanged.

Day 4 files:

- `fixtures/v7/day4/accommodation-evidence-contract.json` — offline capability/field matrix, representative present/missing cases, and unsupported operations.
- `tests/test_v7_day4_accommodation_evidence.py` — contract, parser, registry, identity, comparison, and StarRez boundary proof.
- `day4-accommodation-source-health.json` — immutable 2026-09-25 bounded live dry-run snapshot.
- `day4-accommodation-source-health-2026-09-27.json` — refreshed bounded live dry-run acceptance evidence.
- `docs/v7/DAY_04_HANDOFF.md` — this review record.

- `docs/DECISION_LOG.md` records the Carmen/Will cross-repository price-evidence decision.

## Behavioural impact

- The producer still stores exact price text; the agreed consumer capability permits only the named-room numeric weekly maximum rule below, not advertised-rate filtering, totals, ranges, sorting, or cheapest ranking.
- Catering and audience filters are supported only by exact source-backed membership values.
- Advertised and room rates remain exact text. The implementation does not create numeric prices, totals, ranges, or “cheapest” rankings.
- Room name, rate, contract term, inclusions, and other fees remain paired in each room object; the published cost-period wording stays separate and must qualify comparisons.
- Published StarRez URLs are navigation evidence only. The collector does not fetch StarRez, and link presence does not imply vacancy or application status.
- Missing facts remain unknown. In particular, `vacancy_status: null` is neither `false` nor an available/unavailable claim.
- Accommodation resolver metadata continues to contain the canonical residence name and no invented temporal value or alias.

## Agreed Carmen/Will price decision

Current effective rule: `advertised_rate` remains display/exact-comparison evidence only. Numeric maximum-price filtering is supported only against an explicit named room with an unambiguous published AUD weekly rate and exact cost period.

Agreed rule:

- a residence may match a numeric budget only when at least one named room has an unambiguous published AUD weekly rate satisfying the threshold;
- the qualifying room must retain its exact `cost_period`, contract, inclusions, and other fees;
- `advertised_rate` wording such as `Rates from A$380.00 /wk` remains display/comparison-only and does not establish a particular available room below the threshold;
- `under`, `below`, and `less than` are strict `<`;
- `up to`, `maximum`, `max`, and `no more than` are `<=`;
- `MATCH` requires at least one qualifying named room;
- `NO_MATCH` requires every published named room rate to be evaluable and outside the threshold;
- if no room proves `MATCH` and any room rate is missing or ambiguous, the residence is `UNKNOWN`, making the result set `INCOMPLETE` rather than globally `EMPTY`; and
- no price evidence supports vacancy, eligibility, residence-wide affordability, cheapest ranking, or total contract cost.

Carmen's final reconciled RAG head implements this boundary. This scraper change updates the capability matrix, supported/unsupported operation lists, tests, and handoff together; it does not implement consumer filtering in the scraper.

Ownership remains explicit: Will freezes and tests producer evidence, Carmen applies only the agreed interpretation in RAG, and Ben's App displays the structured result without parsing price strings itself.

## Final reconciled producer/consumer cross-check

The exact RAG consumer reviewed was
`d349e8870715709fa034d57d902da4bec6dd5d34`. GitHub's compare result proves
that its merge-base with accepted Day 3
`68d5aa367ce7adc1051c714c88a2e7b63751dd90` is exactly that accepted Day 3
SHA; the reconciled head is nine commits ahead and zero behind.

All 15 frozen Accommodation metadata paths are present in the strict RAG
record model and are consumed without adding a stronger institutional fact:

| Producer path | Consumer use | Evidence classification / qualifier |
|---|---|---|
| `metadata_json.category` | discovery, result cards, comparison | Structured source-backed text; missing remains unpublished. |
| `metadata_json.location` | factual answers, cards, comparison | Structured source-backed text; no inferred location. |
| `metadata_json.catering_options` | discovery/filtering, cards, comparison | Structured source-backed membership values; empty remains unknown. |
| `metadata_json.audiences` | audience/student-type evidence, cards | Structured source-backed membership values; not personal eligibility. |
| `metadata_json.advertised_rate` | display and exact-text comparison | Structured source-backed text; explicitly excluded from numeric proof. |
| `metadata_json.cost_period` | rate qualification, cards, comparison | Structured source-backed qualifier; missing makes numeric room evidence incomplete. |
| `metadata_json.rooms` | named-room budget filtering and qualifying evidence | Structured nested/paired evidence retaining room name, rate, contract, inclusions and other fees. |
| `metadata_json.features` | discovery, factual answers, comparison | Structured source-backed membership values. |
| `metadata_json.overview` | factual answers | Structured source-backed text; no consumer inference. |
| `metadata_json.accessibility` | factual answers | Structured source-backed wording; no inferred accessibility boolean. |
| `metadata_json.application_text` | application explanation | Structured source-backed text; not application-open evidence. |
| `metadata_json.application_url` | application action | Structured validated stored URL only; navigation evidence only. |
| `metadata_json.eligibility` | published eligibility wording | Structured source-backed wording; not a personal eligibility decision. |
| `metadata_json.contact` | email, phone, location and hours facts | Structured nested source-backed evidence; missing subfields stay unpublished. |
| `metadata_json.vacancy_status` | current-vacancy response | Structured explicit-only field; 0/19 source-present means `UNKNOWN`, never false. |

Accommodation has no approved content-only fact path under the frozen producer
contract. Individual nullable values remain missing/unknown where the source
does not publish them. Rates and cost periods are point-in-time source evidence
and must retain their exact period/context rather than being treated as
timeless current prices.

The reconciled consumer applies strict `<` for `under`, `below`, and `less
than`, and inclusive `<=` for `up to`, `maximum`, `max`, and `no more than`.
Its numeric path iterates `rooms`, requires a non-null `cost_period`, excludes
`advertised_rate`, and returns paired `qualifying_evidence`. Tests at the exact
RAG SHA cover advertised-rate exclusion, missing/ambiguous room evidence,
complete room context, source-order preservation without cheapest ranking,
and both operator classes.

Vacancy requests return `UNKNOWN` / insufficient evidence when any selected
record lacks explicit `vacancy_status`; room rows, rates, page existence and
application links are not treated as vacancy proof. Application actions are
built only from model-validated stored `application_url` values and retain the
record/source identity. URL presence does not establish vacancy, application
opening, eligibility, or likely acceptance.

The consumer evidence object retains `record_id`, `source_id`, domain and
`canonical_url`; selected results retain canonical identity and source-backed
actions. Final result: **15/15 paths checked, 0 shape mismatches, 0 semantic
mismatches, no consumer field lacking producer evidence, and no material
producer field left unconsumed for the Day 4 flows**.

No scraper production code, canonical content, content hash, retrieval unit,
source, schema or persistence behaviour changed as a result of this audit.

### Agreed price matrix

| Evidence field | Display | Exact comparison | Numeric filtering | Other boundaries |
|---|---:|---:|---:|---|
| `advertised_rate` | Yes | Yes | Not approved | Preserve `from`, currency, `/wk`, and cost period; no total, affordability, or cheapest claim |
| `rooms[].rate` | Yes, paired with room | Yes, paired with room | Named-room weekly maximum only | Require unambiguous AUD weekly evidence and exact cost period; never flatten or detach from contract/inclusions/fees |
| `cost_period` | Yes | Exact qualifier only | N/A | Must accompany any future price interpretation; cannot imply currentness or period equivalence |
| `rooms[].other_fees` | Yes, paired with room | Yes | Never a weekly-rate input | Cannot be silently folded into or ignored for a total-cost claim |

### Interim approved-source pattern review

A read-only review on 2026-09-26 found that the approved [residence listing](https://study.anu.edu.au/accommodation/our-residences) publishes `Rates from A$<amount>/wk` wording for 18 of 19 residences and exposes source-native room-rate filter bands. Representative approved detail pages publish room-specific values under the `Weekly Inclusive Tariff` label and separately publish dollar-bearing two-weeks-rent, refundable-deposit, registration-fee, committee-fee, and inclusion text.

This makes field context decisive: a dollar sign alone is not price authority. `Rates from A$380.00/wk` remains display/comparison-only evidence. `$380.00` is eligible for the agreed maximum filter only when it belongs to an explicit named room, was parsed from the room's `Weekly Inclusive Tariff` field, has unambiguous AUD context, and retains the exact cost period. A deposit or registration fee is never a room tariff. No range-style weekly-tariff wording has yet been established by this spot-check, so ranges remain unsupported pending the final bounded audit.

This spot-check supports the agreed field boundary but is not a replacement for the immutable bounded audit artifact or the required final-head rerun.

## Result completeness semantics

Source absence and source contradiction are different states. A record with no safely evaluable value is `UNKNOWN`; it is not a confirmed non-match. If any in-scope residence is unevaluable for a requested deterministic constraint, downstream results may be `INCOMPLETE` and must not be presented as globally `EMPTY` solely because the evaluable records did not match.

Entity completeness is reported separately from field presence:

- entity coverage: 19/19 approved residences parsed;
- source-present fact capture: 273/273 facts captured;
- `accessibility`: 18/19 present;
- `advertised_rate`: 18/19 present;
- `application_url`: 14/19 present; and
- `vacancy_status`: 0/19 present.

The zero vacancy count is a faithful source-presence result, not a scraper failure and not evidence that zero rooms are available.

## Frozen universe and refresh safety

The approved universe is discovered only from `https://study.anu.edu.au/accommodation/our-residences`. Accepted details must be exact HTTPS `study.anu.edu.au/accommodation/our-residences/<slug>` pages. The canonical slug is `entity_id`; `record_id` is `accommodation:residence:<entity_id>`.

The expected population remains 19. A future observation of 18 is an unexplained/suspicious disappearance: retain last-known-good, alert/recheck, and investigate. It is not immediate deletion evidence. This identity and provenance model remains compatible with later `NEW`, `CHANGED`, `UNCHANGED`, `MISSING`, and reviewed removal reconciliation.

## Live bounded audit

Command run from clean rebased head `15952f5c45b98a95cc5a3f1f8dce6636439a9300`:

```text
py -m askanu_scraper.detail_coverage --domain accommodation --min-request-interval-seconds 1 --output day4-accommodation-source-health-2026-09-27.json
```

Artifact: `day4-accommodation-source-health-2026-09-27.json`

LF-normalized SHA-256: `571326e676599f17191b9387c775531a75e5c5a5d8a607a9da799e972e2913a4`

Captured at: `2026-09-27T14:24:54.299110+10:00`

Exact audit results:

| Check | Result |
|---|---:|
| Dry run | `true` |
| Production records written | `0` |
| Migrations applied | `0` |
| StarRez requests | `0` |
| Advertised / discovered / approved / frozen | `19 / 19 / 19 / 19` |
| Detail pages attempted / fetched | `19 / 19` |
| Parsed records | `19` |
| Parser exceptions / malformed / rejected | `0 / 0 / 0` |
| Canonical mismatches | `0` |
| Duplicate record IDs / canonical URLs / normalized identities | `0 / 0 / 0` |
| Source-shape anomalies | `[]` |
| Source-present facts captured | `273 / 273` |
| Accessibility source-present / captured | `18 / 18` |
| Advertised-rate source-present / captured | `18 / 18` |
| Application-URL source-present / captured | `14 / 14` |
| Vacancy-status source-present / captured | `0 / 0` |
| Domain health | `GREEN` |

`273 / 273` measures capture of facts the audited source actually presented. It is not a completeness claim for absent fields.

Exact refreshed 19-residence census, in artifact order:

1. `bruce-hall-main-wing`
2. `bruce-hall-packard-wing`
3. `burgmann-college`
4. `burgmann-undergraduate-and-postgraduate-village`
5. `burton-garran-hall`
6. `davey-lodge`
7. `fenner-hall`
8. `graduate-house`
9. `john-xxiii-college`
10. `kinloch-lodge`
11. `lena-karmel-lodge`
12. `toad-hall`
13. `university-house`
14. `ursula-hall-laurus-wing`
15. `ursula-hall-main-wing`
16. `wamburun-hall`
17. `warrumbul-lodge`
18. `wright-hall`
19. `yukeembruk`

## Evidence-type separation

- Fixture tests prove parser behavior for frozen inputs; they are not claims about the current ANU website.
- `day4-accommodation-source-health.json` remains the immutable 2026-09-25 bounded snapshot at LF-normalized SHA-256 `3e958e9ae0dfb0bf0700c51eb4dda8445db9f803ec39fc53530a0d4e50a186b8`.
- `day4-accommodation-source-health-2026-09-27.json` is the refreshed acceptance artifact for the clean rebased audit head.
- The interim price-pattern review is a read-only semantic check and does not replace or rewrite the bounded audit.
- Future live reruns must create a new timestamped artifact while preserving both historical snapshots unchanged.

### Accessibility drift resolution

The 2026-09-25 artifact records `accessibility` as 0/19 source-present. A read-only 2026-09-26 spot-check found explicit Accessibility sections on multiple approved residence pages, including [Bruce Hall Packard Wing](https://study.anu.edu.au/accommodation/our-residences/bruce-hall-packard-wing), [Warrumbul Lodge](https://study.anu.edu.au/accommodation/our-residences/warrumbul-lodge), [Lena Karmel Lodge](https://study.anu.edu.au/accommodation/our-residences/lena-karmel-lodge), and [Davey Lodge](https://study.anu.edu.au/accommodation/our-residences/davey-lodge). This is a source-drift signal, not permission to rewrite the historical artifact or silently change its denominator.

The 2026-09-27 clean-head audit recalculated Accessibility as 18/19 source-present and captured, increasing the current source-present denominator from the historical 255 to 273. The old `0/19` and `255/255` values remain valid only for the immutable 2026-09-25 snapshot. Existing parser behavior already preserved Accessibility text; the correction was limited to the audit presence detector for the source's two-column row layout. No structured accessibility boolean or universal accessibility claim is authorized.

## Capability and field matrix

The checked-in JSON matrix covers exactly all 15 Accommodation `structured_fact_paths` in the frozen Day 1 producer contract.

| Field | Conservative capability | Live source-present / captured | Explicit boundary |
|---|---|---:|---|
| `category` | Exact membership | 19 / 19 | No guessed equivalence |
| `location` | Exact when present | 0 / 0 | No inference from name/contact |
| `catering_options` | Exact membership | 19 / 19 | No synonyms or feature inference |
| `audiences` | Exact membership | 19 / 19 | No personal eligibility |
| `advertised_rate` | Exact-text comparison | 18 / 18 | No numeric filtering, normalization, ranking, or backfill |
| `cost_period` | Exact-text qualifier | 19 / 19 | No inferred currentness/equivalence |
| `rooms` | Paired exact text plus named-room weekly maximum | 19 / 19 | Exact agreed semantics only; no flattening or detached prices |
| `features` | Exact membership | 19 / 19 | Absence is not false |
| `overview` | Content only | 19 / 19 | No deterministic attribute extraction |
| `accessibility` | Content only when present | 18 / 18 | No universal accessibility boolean |
| `application_text` | Navigation text when present | 14 / 14 | No outcome/availability inference |
| `application_url` | Navigation only when present | 14 / 14 | Never fetch authenticated StarRez |
| `eligibility` | Content only when present | 0 / 0 | No personal decision |
| `contact` | Exact nested facts | 19 / 19 | Missing subfields stay missing |
| `vacancy_status` | Explicit only | 0 / 0 | No vacancy inference |

Supported deterministic filters are exact category, catering, audience, and feature membership plus the agreed named-room AUD weekly maximum rule. Unsupported filters/claims include numeric filtering from `advertised_rate`, price sorting/cheapest ranking, minimum/range filtering beyond the agreed maximum rule, total-contract-cost calculation, residence-wide affordability, current-price claims without the cost period, numeric extraction from fees/deposits/free text, vacancy or room availability, personal eligibility, inferred location/accessibility, application status/outcome, and magic wording/unreviewed synonyms.

## Representative evidence

- Yukeembruk fixture: exact listing rate, two independently paired room/cost records, cost period, full contact example, published application link, and null vacancy.
- Davey Lodge fixture: exact listing rate, one room/cost record, the same cost-period semantics, missing optional contact subfields, published application link, and null vacancy.
- Synthetic omission regression: removing only the listing `advertised_rate` keeps it `null`; the parser does not backfill it from the room tariff. This is a parser-boundary test, not an institutional claim about Davey Lodge.

## Test evidence

Focused Day 4 gate:

```text
py -m pytest tests/test_v7_day4_accommodation_evidence.py -q
21 passed in 0.26s
```

Broader Accommodation/shared-contract gate:

```text
py -m pytest tests/test_accommodation_parser.py tests/test_day12_collectors.py tests/test_detail_coverage.py tests/test_v7_day1_contract.py tests/test_v7_day2_search_metadata.py tests/test_v7_day4_accommodation_evidence.py -q
92 passed in 0.68s
```

Current local repository gate:

```text
py -m pytest -q
451 passed in 5.76s
py -m pip check
No broken requirements found.
py -m compileall -q src tests
PASS
git diff --check
PASS
```

These gates were run after reconciliation onto exact base `301c3a2cf0f00f7c0d09ea9fc45a72ce446de2d4` and after the clean-head live audit. No Day 17 work was included in the commits or test state.

The Day 4 tests specifically prove:

- exact composition with frozen Day 1 and Day 2 contracts;
- complete one-for-one field-matrix coverage;
- immutable dry-run artifact/hash and zero production mutation;
- live field asymmetry without absence claims;
- stable record IDs, canonical URLs, source authority, and lookup terms;
- exact catering/audience membership;
- catering is not inferred from matching feature text and audience is not personal eligibility;
- exact-text rate/cost-period and room-field pairing;
- weekly room rates remain distinct from deposits and registration fees;
- present/missing facts remain distinct and are not backfilled;
- vacancy is not inferred from listing presence, rooms, rates, or an application link;
- missing location, accessibility, and eligibility remain unknown;
- published StarRez navigation is retained but never fetched;
- unsafe StarRez destinations are rejected, including HTTP, credentials, explicit/malformed ports, and arbitrary hosts;
- all 19 audited identities remain unique and inside the approved boundary;
- temporary disappearance preserves last-known-good rather than implying deletion;
- the agreed Carmen/Will price rule, comparison operators, and three-valued result semantics are explicit; and
- unsupported operations are explicit, with no magic-word shortcuts.

## Risks and dependencies

- Live public pages can drift after the captured timestamp; this artifact is a timestamped audit, not a perpetual guarantee.
- Published cost periods and rate wording can become stale; downstream consumers must show source context and freshness rather than infer currentness.
- A room tariff is not a total cost, and absent fees/inclusions are unknown.
- Application-link absence or presence says nothing about availability, vacancy, eligibility, or outcome.
- Deterministic filtering is limited to exact source-backed values; content-only fields need downstream evidence-aware handling.
- Depends on reviewed Day 1 producer capability and Day 2 resolver metadata contracts, the frozen 19-residence registry, and existing CommonRecord/collector/parser safeguards.
- Any future source, schema, or API change still requires explicit review. No production crawl/write or migration is authorized by this handoff.

## Current producer-side contract summary

Accommodation entity universe:
19 approved public ANU residence detail pages discovered from the frozen listing boundary; stable identity is `accommodation:residence:<canonical-slug>`. The 2026-09-27 audit parsed 19/19 with zero duplicate IDs, canonical URLs, or normalized identities.

Source-present fact capture:
2026-09-27 refreshed snapshot: 273/273; `accessibility` 18/19, `advertised_rate` 18/19, `application_url` 14/19, `vacancy_status` 0/19. The unchanged 2026-09-25 historical snapshot remains 255/255 with the then-audited Accessibility presence at 0/19.

Safe deterministic filters:
Exact category, catering, audience-as-description, and feature membership; named-room numeric maximum only when the room has unambiguous published AUD weekly evidence and an exact cost period. `under`/`below`/`less than` use `<`; `up to`/`maximum`/`max`/`no more than` use `<=`.

Display/comparison-only evidence:
`advertised_rate`; exact cost-period wording; non-qualifying or ambiguous room-price text; overview/accessibility/eligibility prose; room contract, inclusions, and other fees. Qualifiers such as `from` and `indicative` remain visible.

Explicit-only facts:
`vacancy_status`; missing means unknown and cannot be inferred from listing presence, rooms, rates, application links, page availability, or StarRez.

Navigation-only facts:
Validated source-published `application_url` and its text; StarRez is never fetched and link presence proves no application outcome, private inventory, or vacancy.

Unsupported conclusions:
Numeric filtering from `advertised_rate`; price sorting/cheapest ranking; minimum/range filtering beyond the agreed named-room maximum rule; total contract cost; residence-wide affordability; current-price wording without its period; numeric extraction from deposits, fees, inclusions, or free text; vacancy/availability; personal eligibility; inferred location/accessibility; and application status/outcome.

## Qasim review commands

```text
git diff 301c3a2cf0f00f7c0d09ea9fc45a72ce446de2d4...HEAD -- fixtures/v7/day4/accommodation-evidence-contract.json src/askanu_scraper/detail_coverage.py tests/test_detail_coverage.py tests/test_v7_day4_accommodation_evidence.py day4-accommodation-source-health.json day4-accommodation-source-health-2026-09-27.json docs/v7/DAY_04_HANDOFF.md docs/DECISION_LOG.md
py -m pytest tests/test_v7_day4_accommodation_evidence.py -q
py -m pytest -q
```
