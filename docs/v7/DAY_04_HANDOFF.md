# V7 Day 4 — Accommodation evidence handoff

**Owner:** Will

**Reviewer:** Qasim

**Lane:** Scraper/data

**Evidence captured:** 2026-09-25 (Australia/Sydney)

## Producer evidence gate outcome

PASS. The approved Accommodation source still reconciles to the frozen 19-residence universe, all 19 public detail pages parsed with stable identities, and all source-present audited facts were captured. This does **not** claim that every comparison fact exists: the live source exposed an advertised rate for 18/19 records, an application link for 14/19, and an explicit vacancy fact for 0/19.

No production parser, schema, registry, API, source boundary, or persistence behaviour changed. Day 4 adds reviewable evidence and regression tests around the existing shared `CommonRecord`, V7 producer contract, resolver metadata projection, source registry, and bounded collector.

The Carmen/Will numeric-price evidence rule is now agreed and recorded below. The cross-repository Day 4 integration gate remains **pending** until Carmen lands matching RAG implementation/tests and Qasim supplies the exact final Day 3 scraper base SHA. PR #39 must not be merged before those gates close.

## Reviewed base and files

Implementation branch started from reviewed `origin/main` commit `93b94ef102ab22df08c01e5ef4245ad6653d98e9` (merged Day 2). The open/unreviewed Day 3 branch was not included.

Day 4 files:

- `fixtures/v7/day4/accommodation-evidence-contract.json` — offline capability/field matrix, representative present/missing cases, and unsupported operations.
- `tests/test_v7_day4_accommodation_evidence.py` — contract, parser, registry, identity, comparison, and StarRez boundary proof.
- `day4-accommodation-source-health.json` — bounded live dry-run audit evidence.
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

Carmen confirmed this boundary for the RAG side on 2026-09-26 and will update the Day 4 RAG implementation/tests to match it. This scraper change updates the capability matrix, supported/unsupported operation lists, tests, and handoff together; it does not implement consumer filtering in the scraper.

Ownership remains explicit: Will freezes and tests producer evidence, Carmen applies only the agreed interpretation in RAG, and Ben's App displays the structured result without parsing price strings itself.

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
- source-present fact capture: 255/255 facts captured;
- `advertised_rate`: 18/19 present;
- `application_url`: 14/19 present; and
- `vacancy_status`: 0/19 present.

The zero vacancy count is a faithful source-presence result, not a scraper failure and not evidence that zero rooms are available.

## Frozen universe and refresh safety

The approved universe is discovered only from `https://study.anu.edu.au/accommodation/our-residences`. Accepted details must be exact HTTPS `study.anu.edu.au/accommodation/our-residences/<slug>` pages. The canonical slug is `entity_id`; `record_id` is `accommodation:residence:<entity_id>`.

The expected population remains 19. A future observation of 18 is an unexplained/suspicious disappearance: retain last-known-good, alert/recheck, and investigate. It is not immediate deletion evidence. This identity and provenance model remains compatible with later `NEW`, `CHANGED`, `UNCHANGED`, `MISSING`, and reviewed removal reconciliation.

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

## Evidence-type separation

- Fixture tests prove parser behavior for frozen inputs; they are not claims about the current ANU website.
- `day4-accommodation-source-health.json` is the immutable bounded live audit for the timestamp recorded above.
- The interim price-pattern review is a read-only semantic check and does not replace or rewrite the bounded audit.
- Any final live rerun must create a new timestamped artifact while preserving this historical artifact unchanged.

### Post-artifact source-drift observation

The 2026-09-25 artifact records `accessibility` as 0/19 source-present. A read-only 2026-09-26 spot-check found explicit Accessibility sections on multiple approved residence pages, including [Bruce Hall Packard Wing](https://study.anu.edu.au/accommodation/our-residences/bruce-hall-packard-wing), [Warrumbul Lodge](https://study.anu.edu.au/accommodation/our-residences/warrumbul-lodge), [Lena Karmel Lodge](https://study.anu.edu.au/accommodation/our-residences/lena-karmel-lodge), and [Davey Lodge](https://study.anu.edu.au/accommodation/our-residences/davey-lodge). This is a source-drift signal, not permission to rewrite the historical artifact or silently change its denominator.

The final bounded audit after the Day 3 rebase must recalculate accessibility and the overall source-present fact denominator. Until then, `0/19` and `255/255` must be described as the 2026-09-25 snapshot, not guaranteed current values. Existing parser behavior already preserves an explicit Accessibility section as source text; no structured accessibility boolean or universal accessibility claim is authorized.

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
| `accessibility` | Content only when present | 0 / 0 | No universal accessibility boolean |
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
20 passed in 0.22s
```

Broader Accommodation/shared-contract gate:

```text
py -m pytest tests/test_accommodation_parser.py tests/test_day12_collectors.py tests/test_v7_day1_contract.py tests/test_v7_day2_search_metadata.py tests/test_v7_day4_accommodation_evidence.py -q
68 passed in 0.43s
```

Current local repository gate:

```text
py -m pytest -q
434 passed in 5.00s
py -m pip check
No broken requirements found.
py -m compileall -q src tests
PASS
```

These current results include pre-existing uncommitted Day 17 detail-coverage work in the shared worktree, which this correction did not modify. They are interim regression evidence, not the final clean-head gate. The full suite and checks must be rerun after Qasim supplies the final Day 3 base and PR #39 is refreshed onto it.

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

## Current producer-side contract summary (pre-rebase)

Accommodation entity universe:
19 approved public ANU residence detail pages discovered from the frozen listing boundary; stable identity is `accommodation:residence:<canonical-slug>`. The 2026-09-25 audit parsed 19/19 with zero duplicate IDs, canonical URLs, or normalized identities.

Source-present fact capture:
2026-09-25 historical snapshot: 255/255; `advertised_rate` 18/19, `application_url` 14/19, `vacancy_status` 0/19. A post-artifact accessibility drift signal requires recalculation on the final head.

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
git diff origin/main...HEAD -- fixtures/v7/day4/accommodation-evidence-contract.json tests/test_v7_day4_accommodation_evidence.py day4-accommodation-source-health.json docs/v7/DAY_04_HANDOFF.md docs/DECISION_LOG.md
py -m pytest tests/test_v7_day4_accommodation_evidence.py -q
py -m pytest -q
```
