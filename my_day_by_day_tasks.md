# askanu-scraper - my_day_by_day_tasks.md (V5)

**Primary owner:** Will - Scraper / data  
**Plan window:** 12-18 Sep 2026 accelerated phase; 19 Sep-3 Oct 1h/day hardening/release.  
**Rule:** code is not done until tests/evidence exist. Read repo instructions/contracts before editing.

## Cross-repo rules

- Preserve the frozen Browser -> App -> private RAG -> Cloud SQL/Gemini architecture.
- Do not silently change the `/api/v1/ask` response envelope/statuses.
- Official source URLs come from stored records.
- Session memory is current-chat only; no persistent account history.
- Events/Rubric is scheduled ingestion only, never a synchronous user-request dependency.
- Every day ends with a handoff: status, PR/SHA, tests, cloud evidence if relevant, known issues, contract/source changes.

## Sat 12 Sep - Busy-day light task: source registry/freshness contract review

**Capacity:** 3h (busy)  
**Outcome:** Spend a short busy-day block making Sunday/Monday heavy data work safer: verify source registry, current scraper semantics and the exact approved source boundaries for the five remaining domains.

**Starting state:** Courses collector and Cloud SQL safety behavior are proven, including NEW -> UNCHANGED and simulated fetch failure preserving last-known-good.

**Dependencies / stop:** Maximum 3h today. Do not start a large collector that cannot be completed/tested. Rubric exact endpoint is still TBC.

### Work blocks
- **0-1h - Registry audit:** Read source registry/contracts and list the exact approved URLs/source IDs for Scholarships, Jobs, Accommodation, Support and Events. Flag anything still ambiguous.
- **1-2h - Reuse plan:** Identify shared collector/storage primitives from Courses that should be reused: run records, hash/idempotency, last_seen_at, last-known-good, dry-run, bounded limits.
- **2-3h - Fixture prep:** Capture/update a small fixture or parsing sample for Scholarships and Jobs; write Sunday kickoff notes. If Rubric endpoint details are available, document only - do not call or enable it yet.

### Understand before coding
- Today is preparation, not a half-built production collector.
- External source HTML/endpoints are untrusted and may change.
- Every stored record needs canonical provenance and deterministic identity.

### Acceptance criteria
- [ ] Source/claim-boundary checklist exists for five remaining domains.
- [ ] Scholarships/Jobs next-step fixtures or parsing notes exist.
- [ ] No production config or source enablement changed.

### Evidence to hand off
- Short markdown handoff or issue comment.
- Fixture paths/URLs and known ambiguities.

### Do not / escalate
- Do not exceed the light-day scope.
- Do not enable Rubric or live request-time integrations.
- Do not weaken Courses safety guards.

### Copy-paste AI kickoff

> Use this as a 3-hour preparation block only. Audit approved source registry and shared scraper/storage primitives, prepare Scholarships/Jobs fixtures, and document unresolved source questions. Do not build or deploy a new collector today and do not enable Rubric.

### Qasim integration checkpoint

Before this day is considered closed, coordinate with Qasim on: **V5 reset, contract freeze and integration gates**. Shared contract/source/schema/cloud changes must be explicitly approved and evidenced.

## Sun 13 Sep - Scholarships approved collector + safe cloud ingestion

**Capacity:** 12h  
**Outcome:** Implement and prove the Scholarships collector end-to-end using approved ANU scholarship pages, normalized records, deterministic identity, idempotency and last-known-good behavior.

**Starting state:** Saturday source audit/fixtures plus proven Courses ingestion primitives.

**Dependencies / stop:** Coordinate normalized field names with Carmen/Qasim before shared DB migration if new generic storage shape is needed.

### Work blocks
- **0-4h - Parser + fixtures:** Implement bounded fetch/parse for scholarship finder/detail data. Preserve canonical URL, title, open/closed, Featured, application requirement, filters, value, basis, deadlines and eligibility where present. Add HTML fixtures.
- **4-8h - Storage/idempotency:** Map to shared record contract; deterministic record_id/entity_id/content_hash. Add NEW/UNCHANGED/CHANGED/missing/fetch-failure tests. Dry-run locally then disposable DB if available.
- **8-12h - Shared cloud proof:** Deploy reviewed image/job config only after PR approval. Run bounded dry-run, first real run, second unchanged run, inspect Cloud SQL counts/fields and ingestion_runs, capture one failure-safe proof if time permits.

### Understand before coding
- Never infer scholarship facts not present in the official page.
- A parser failure must not wipe yesterday's valid scholarship data.
- Normalize dates/status but preserve original source wording where needed.

### Acceptance criteria
- [ ] Collector tests green; no duplicate logical records on repeated run.
- [ ] Stored sample has canonical official URL and required scholarship fields.
- [ ] Two-run cloud evidence shows NEW then UNCHANGED.
- [ ] Failed fetch preserves last-known-good or is explicitly blocked before unsafe write.

### Evidence to hand off
- PR/SHA, test counts, image digest if deployed.
- Cloud execution IDs + DB sample query/count.
- Source-health/field coverage note.

### Do not / escalate
- Do not scrape authenticated/private sources.
- Do not mass-ingest before bounded sample proves parser/storage safety.

### Copy-paste AI kickoff

> Build the approved ANU Scholarships collector using the existing safe Courses ingestion patterns. Preserve canonical provenance and scholarship status/deadline/eligibility fields. Add fixture, idempotency and failed-fetch tests. After review, prove dry-run -> first write -> unchanged second run in shared Cloud SQL and hand off sample records to RAG.

### Qasim integration checkpoint

Before this day is considered closed, coordinate with Qasim on: **Scholarships vertical-slice release gate**. Shared contract/source/schema/cloud changes must be explicitly approved and evidenced.

## Mon 14 Sep - Official ANU Jobs collector + temporal fields

**Capacity:** 12h  
**Outcome:** Implement and prove the official ANU Jobs collector with correct closing-date/source provenance and safe scheduled-refresh behavior.

**Starting state:** Reusable scraper/storage primitives plus Scholarships cloud evidence.

**Dependencies / stop:** Use jobs.anu.edu.au/jobs/search and detail pages within approved boundaries. Do not invent employment eligibility claims.

### Work blocks
- **0-4h - Fetch/parse:** Build bounded search/detail parser preserving title, type, location, classification, closing date, summary and canonical URL. Add fixtures for open, closed/expired and missing optional fields.
- **4-8h - Normalize/test:** Normalize dates carefully while retaining original value; deterministic identity/content hash; NEW/UNCHANGED/CHANGED/fetch failure tests; source page changes should fail visibly, not silently produce empty data.
- **8-12h - Cloud/schedule prep:** Run dry-run + bounded writes + repeat unchanged in Cloud SQL. Produce source-health counts and decide safe scheduler cadence with Qasim; do not create a high-frequency poll.

### Understand before coding
- Current jobs depend on correct date ingestion.
- Empty source/parser result is suspicious and must not mass-mark records missing without sanity thresholds.

### Acceptance criteria
- [ ] Sample jobs stored with canonical URL and closing date.
- [ ] Repeated ingestion idempotent.
- [ ] Parser/fetch failure preserves last-known-good.
- [ ] Run counts/source health suitable for scheduler.

### Evidence to hand off
- PR/SHA, execution IDs, DB sample/count, parser fixtures.

### Do not / escalate
- Do not scrape application/authenticated flows.
- Do not mark all jobs missing after suspicious zero-result parse.

### Copy-paste AI kickoff

> Build the official ANU Jobs collector with title/type/location/classification/closing date/summary/canonical URL. Reuse safe idempotent storage and last-known-good guards. Prove bounded Cloud SQL writes and unchanged rerun, then provide source-health/cadence evidence for Scheduler.

### Qasim integration checkpoint

Before this day is considered closed, coordinate with Qasim on: **Jobs gate + scheduler/freshness decision**. Shared contract/source/schema/cloud changes must be explicitly approved and evidenced.

## Tue 15 Sep - Heavy data day: Accommodation + Support collectors

**Capacity:** 12h  
**Outcome:** Use the day when Ben/Carmen are unavailable to build and prove the data layer for two domains, so Wednesday is mainly retrieval/UI integration.

**Starting state:** Safe collector/storage/scheduler patterns proven for Courses/Scholarships/Jobs.

**Dependencies / stop:** Approved ANU accommodation/residence pages only; never authenticated StarRez. Support uses approved ANU + approved ANUSA Student Assistance pages. Escalate source ambiguity.

### Work blocks
- **0-4h - Accommodation collector:** Implement bounded approved-page parser. Preserve residence/entity title, category, location, cost/fee wording where published, application/how-to-apply info, features and canonical URL. Explicitly represent unknown live vacancy.
- **4-8h - Support collector:** Implement approved support-service parser preserving service/category, description, contact/location/hours only when published, audience/eligibility where present, canonical URL. Add source-specific fixtures and untrusted-content sanitization.
- **8-12h - Safety + shared DB proof:** Run local full tests, idempotency/change/failure cases for both domains, then bounded cloud dry-run/write/repeat. Inspect counts/representative rows and ingestion_runs. Update source-health registry.

### Understand before coding
- Two domains in one day is acceptable only because storage primitives already exist; keep each parser independently testable.
- Zero-result or drastic count drops should trip sanity guards, not erase current data.
- Live residence vacancy is out of scope.

### Acceptance criteria
- [ ] Both collector suites green with fixtures.
- [ ] Representative Cloud SQL rows have canonical approved URLs.
- [ ] Repeated run is idempotent.
- [ ] Failure/drastic-count guards preserve last-known-good.

### Evidence to hand off
- PR(s)/SHA(s), test counts, execution IDs.
- DB samples/counts for both domains.
- Source-health and known missing-field note for Carmen.

### Do not / escalate
- Do not scrape StarRez/login/application portals.
- Do not infer accommodation availability or support hours.
- Do not combine parsers so tightly that one source failure blocks the other.

### Copy-paste AI kickoff

> Make Tuesday a data-heavy day: implement separate approved Accommodation and Support collectors using the existing safe ingestion primitives. Prove fixtures, idempotency, last-known-good and bounded shared-cloud writes for each. Preserve provenance and never claim live vacancy or unsupported service hours.

### Qasim integration checkpoint

Before this day is considered closed, coordinate with Qasim on: **Data-first integration day + claims/source gate**. Shared contract/source/schema/cloud changes must be explicitly approved and evidenced.

## Wed 16 Sep - Six-domain source-health framework + Events baseline prep

**Capacity:** 12h  
**Outcome:** Stabilize scheduled ingestion/source-health across five active domains and prepare the approved Events/Rubric collector work for Thursday.

**Starting state:** Courses, Scholarships, Jobs, Accommodation and Support collectors exist or are merging.

**Dependencies / stop:** Rubric public-search integration direction is approved in principle but exact endpoint/fields remain TBC until verified. Official ANU Events remains fallback/release-safe source.

### Work blocks
- **0-4h - Source-health consolidation:** Create/complete per-source health summary: last success, record count, added/changed/unchanged/missing, suspicious change flag. Verify schedule/cadence does not overlap dangerously.
- **4-8h - Failure/coverage audit:** Run representative fetch/parser failure and suspicious-count tests across collectors; ensure independent sources fail independently and last-known-good remains.
- **8-12h - Events investigation:** Inspect actual public ANU Events and approved Rubric/public-search network endpoint if documented. Capture request/response shape, pagination, IDs, canonical event URL fields, rate behavior. Build fixtures only; no live user-time calls and no production enablement before Qasim review.

### Understand before coding
- Source health is operational metadata, not user-facing truth.
- Rubric is an ingestion source, never part of the synchronous question path.
- Exact endpoint/contract must come from observed/approved behavior, not memory.

### Acceptance criteria
- [ ] Five-domain source-health snapshot is available.
- [ ] Failure tests preserve valid data.
- [ ] Events/Rubric endpoint investigation has concrete fixture/schema evidence or explicit blocker.

### Evidence to hand off
- Source-health report + execution IDs.
- Events/Rubric fixture/request-shape note with sensitive tokens removed.

### Do not / escalate
- Do not store cookies/auth tokens.
- Do not hit unsupported endpoints at high volume.
- Do not enable a scraper from an undocumented guessed URL.

### Copy-paste AI kickoff

> Consolidate source health and failure safety for the five active domain collectors, then investigate the actual approved Events/Rubric public-search request. Capture schema/pagination/IDs/canonical URLs into fixtures with no secrets. Keep Rubric scheduled-ingestion-only and do not production-enable it until reviewed.

### Qasim integration checkpoint

Before this day is considered closed, coordinate with Qasim on: **Five-domain gate + conversation milestone + Events decision**. Shared contract/source/schema/cloud changes must be explicitly approved and evidenced.

## Thu 17 Sep - Events/Rubric scheduled collector + full freshness/failure pass

**Capacity:** 12h  
**Outcome:** Deliver the sixth domain data path using the approved Events source strategy and prove it is scheduled, bounded, provenance-safe and independent of user request traffic.

**Starting state:** Wednesday produced concrete endpoint/source evidence and Qasim selected Rubric scheduled ingestion or official Events fallback.

**Dependencies / stop:** If Rubric endpoint/permission remains unclear, implement official ANU Events fallback and leave Rubric disabled. Never block Friday on an unstable unverified endpoint.

### Work blocks
- **0-4h - Events collector:** Implement selected source parser with event ID/title/start/end/timezone/location-or-format/category/summary/canonical URL. Handle pagination/bounded window and duplicates.
- **4-8h - Cloud + schedule:** Fixture/idempotency/change/failure tests, bounded dry-run and real write, repeated unchanged run. Configure safe daily schedule/cadence only after source-health passes. No request-time external calls.
- **8-12h - Six-domain freshness drill:** Run/inspect scheduled or manual refresh for all domains early enough to recover. Capture source-health, record counts, failure fallback and representative canonical URLs. Freeze parser changes except P0 after this block.

### Understand before coding
- Daily scheduled ingestion is intentionally decoupled from chat requests.
- Events are highly time-sensitive; stored dates/timezone and refresh timestamp matter.
- Rubric endpoint instability should degrade freshness, not take AskANU chat down.

### Acceptance criteria
- [ ] Events sample stored with canonical official URL and temporal fields.
- [ ] Repeated run idempotent; failure preserves last-known-good.
- [ ] Safe daily schedule exists or explicit approved manual fallback.
- [ ] Six-domain source-health snapshot green/known-safe fallback.

### Evidence to hand off
- PR/SHA, image digest, execution IDs/scheduler config.
- DB sample/counts + six-domain source-health report.

### Do not / escalate
- Do not call Rubric from RAG/App at question time.
- Do not run risky broad ingestion immediately before Friday demo.

### Copy-paste AI kickoff

> Implement the selected Events source as a scheduled collector, never a synchronous chat dependency. Prove temporal fields, canonical provenance, idempotency and last-known-good in shared Cloud SQL, configure safe daily refresh if approved, then run a six-domain source-health/failure pass and freeze parser changes except P0.

### Qasim integration checkpoint

Before this day is considered closed, coordinate with Qasim on: **Six-domain release candidate + 72% gate**. Shared contract/source/schema/cloud changes must be explicitly approved and evidenced.

## Fri 18 Sep - Pre-demo freshness/provenance + source feedback triage

**Capacity:** 12h  
**Outcome:** Refresh early, prove six-domain provenance/source health, then freeze collectors through the presentation.

**Starting state:** Thursday collectors/schedules and last-known-good guards are proven.

**Dependencies / stop:** Refresh early enough to recover. Avoid risky mass ingestion or parser edits close to demo.

### Work blocks
- **0-4h - Early refresh:** Run/verify bounded scheduled ingestion, inspect counts/source health and representative canonical URLs for six domains. Confirm Events freshness/time window.
- **4-8h - Presentation stability:** Freeze source registry/parsers. Provide provenance/freshness evidence if asked. Monitor job health only.
- **8-12h - Feedback triage:** Reproduce claimed missing/wrong data against official source and exact parser fixture. Create P0/P1/P2 source issues; update source-health snapshot.

### Understand before coding
- Freshness is only useful if safe.
- A failed refresh should preserve known-good records.

### Acceptance criteria
- [ ] Pre-demo source health green or explicit safe fallback.
- [ ] Representative canonical URLs valid for six domains.
- [ ] No suspicious refresh overwrites good data.

### Evidence to hand off
- Execution IDs/counts/source-health report.
- Representative URLs and any parser issue fixtures.

### Do not / escalate
- Do not run a risky full crawl immediately before demo.
- Do not enable a new source on stakeholder day.

### Copy-paste AI kickoff

> Run early safe refresh/source-health for all six domains, validate representative canonical URLs and Events freshness, then freeze collectors for the presentation. Afterward reproduce source feedback against the actual page and create fixtures/issues rather than editing live.

### Qasim integration checkpoint

Before this day is considered closed, coordinate with Qasim on: **75% stakeholder milestone + V5 re-baseline**. Shared contract/source/schema/cloud changes must be explicitly approved and evidenced.

## 19 Sep - 3 Oct: 1-hour hardening/release rule

- **Sat 19 Sep:** Feedback reproduction + top P0/P1 only - Each owner gets 1h: reproduce highest-priority accepted feedback; smallest tested fix or evidence-only issue.
- **Sun 20 Sep:** Coverage gaps - One representative missing-data/retrieval/UI gap per owner; test before fix.
- **Mon 21 Sep:** Security/privacy pass - RAG logs/history privacy, App safe rendering, scraper secret/source hygiene, Qasim IAM/revision audit.
- **Tue 22 Sep:** Accessibility/mobile pass - Ben focuses a11y/mobile; others support only defects revealed by the pass.
- **Wed 23 Sep:** Failure/recovery pass - Embedding/API failure, app upstream failure, scraper fetch/parser failure, rollback evidence.
- **Thu 24 Sep:** Performance/cost pass - Bounded context/candidates, frontend network behavior, scraper cadence, cloud cost/limits.
- **Fri 25 Sep:** Six-domain regression - One clean + one negative scenario/domain; fix only P0/P1.
- **Sat 26 Sep:** Docs/runbooks - Update source registry, deployment/recovery, known issues and demo/release notes.
- **Sun 27 Sep:** Freeze readiness - Highest remaining P0/P1 or verification PASS; no new feature.
- **Mon 28 Sep:** FEATURE FREEZE - Snapshot exact versions/config/source health; bugs only.
- **Tue 29 Sep:** Frozen regression - Contract/golden/UI/source subset; smallest bug fixes only.
- **Wed 30 Sep:** Release-candidate drill - Rollback/fallback, scheduled freshness, public smoke.
- **Thu 1 Oct:** Final security/source audit - IAM/secrets/logging/source provenance/schedules.
- **Fri 2 Oct:** Release eve - Final regression, release notes, no optional changes.
- **Sat 3 Oct:** FINAL RELEASE - Deploy/verify pinned release, monitor, publish outcome and known issues.
