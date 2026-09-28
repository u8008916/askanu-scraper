# V7 Day 7 — six-domain data/evidence release-candidate audit

Owner: Will  
Lane: scraper/data  
Prepared: 2026-09-28 (Australia/Sydney)

## Outcome

The scraper/data release-candidate packet is ready for final PM review, with
external gates called out rather than hidden. Day 7 adds only offline audit
fixtures, tests, and this handoff; it does not change producer behaviour or
canonical records.

The Day 4 consumer dependency is closed. Day 5 and Day 6 consumer SHAs and the
final Day 7 RAG release-candidate SHA/journey manifest remain pending. The
audit reuses the exact frozen 24-query Day 3 six-domain benchmark as fallback
evidence and does not create or tune a competing benchmark.

## Final Day 4 consumer cross-check

Carmen's final reconciled Day 4 head is
`d349e8870715709fa034d57d902da4bec6dd5d34`. Its exact merge-base with accepted
Day 3 `68d5aa367ce7adc1051c714c88a2e7b63751dd90` is that accepted SHA; it is nine
commits ahead and zero behind.

The consumer model and implementation use all 15 frozen Accommodation
metadata paths, including nested contact and paired room evidence. Final
result:

- paths checked: **15/15**;
- shape mismatches: **0**;
- semantic mismatches: **0**;
- material producer paths left unconsumed: **0**; and
- consumer paths lacking producer evidence: **0**.

The reconciled consumer excludes `advertised_rate` from numeric proof, keeps
named-room rate context intact, preserves missing vacancy as `UNKNOWN`, builds
actions only from validated stored `application_url`, and retains record,
source and canonical URL provenance. Day 4's producer/consumer dependency is
therefore closed for final PM acceptance.

## Cross-repository gates

- Day 4 RAG consumer: **CLOSED**, exact SHA
  `d349e8870715709fa034d57d902da4bec6dd5d34`.
- Day 5 RAG consumer SHA: **PENDING**.
- Day 6 RAG consumer SHA: **PENDING**.
- Day 7 RAG RC SHA and journey manifest: **PENDING**.

## Six-domain result

| Domain | Evidence state | Release interpretation |
|---|---|---|
| Courses | `GREEN` | 500 audited 2026 Courses and 1,256 Course-family records are fully accounted; year remains identity. |
| Scholarships | `BLOCKED` | Do not claim a complete current population while the external-canonical redirect remains unresolved. |
| Jobs | `FALLBACK_LAST_KNOWN_GOOD` | Known records remain usable, but exhaustive current-population queries are `INCOMPLETE_POPULATION`. |
| Accommodation | `GREEN` | 19/19 residences and 273/273 source-present facts; vacancy remains missing source evidence. |
| Support | `GREEN` | Last complete bounded audit is 6/6; service evidence does not adjudicate a student's case. |
| Events | `BLOCKED` | Official snapshot has an unresolved 30-card/29-eligible discrepancy; Rubric request-contract and live denominator remain gated. |

No broad live crawl was performed merely to refresh timestamps. The release
packet preserves the most recent bounded evidence and its limitations.

## Ownership table

| Query | Classification | Owner | Reason |
|---|---|---|---|
| `holdout-scholarship-eligibility` | `AMBIGUOUS_SOURCE` | Source/product limitation | Candidate dimensions do not prove personal eligibility. |
| `holdout-accommodation-vacancy` | `MISSING_SOURCE` | Source/product limitation | The approved source publishes no current vacancy fact. |
| `holdout-jobs-incomplete` | `INCOMPLETE_POPULATION` | Source/product limitation | Current Jobs population completeness is not established. |
| `holdout-events-rubric-organiser` | `MISSING_SOURCE` | Source/product limitation | Rubric does not publish the required organiser fact. |

Approved evidence that exists correctly remains a RAG responsibility if it is
not retrieved or used. An App rendering error remains Ben's responsibility.

## Torture checks

- Provenance and identity are traceable for all frozen offline representative
  records; official and Rubric Event identity/authority remain distinct.
- Missing vacancy, eligibility, modality, status, location, and application
  facts remain null/unknown rather than false.
- Jobs incomplete population and Accommodation missing vacancy evidence cannot
  collapse into empty/none claims.
- Prompt-like source text remains inert data; executable markup is removed.
- Unsupported cheapest, affordability, vacancy, eligibility, modality,
  application-outcome, and recommendation inferences were not added.

## Canonical-content and provider-cost impact

- Day 4–7 Course canonical content changed: **NO**
- Other canonical retrieval content changed: **NO**
- Content hashes changed by these checkpoints: **0**
- Retrieval units changed: **0**
- Reindex/re-embedding required: **NONE**
- Production embedding backfill initiated: **NO**

## Final scope confirmation

No new production source, source-authority change, scheduler change,
production ingestion, DB write, migration, live Rubric request path, StarRez
inventory access, weakened Jobs atomicity, frontend/RAG reasoning in scraper,
synthetic alias system, unrelated rewrite, or Course re-embedding was added.

All reported test results are local/isolated engineering evidence. No GitHub
Actions run is attached to the Day 4–7 scraper heads at this checkpoint.

Status: **SCRAPER/DATA RC PACKET READY; DAY 4 CROSS-REPO DEPENDENCY CLOSED;
DAY 5–7 CARMEN ARTIFACTS PENDING**.
