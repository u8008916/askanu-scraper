# AskANU V6 - Will day-by-day tasks

**Ownership:** Scraper/data
**Primary repo:** askanu-scraper

## V6 execution rule

A day is not complete because code exists. Use the acceptance criteria/evidence from the V6 PDF. Domain Complete requires >=99% entity + required source-present information + capability coverage and 100% critical provenance/safety.

## Day 11 - Tue 15 Sep 2026 - 14h

**Focus:** Scraper/data - freeze three source universes + expand Courses/Scholarships/Jobs to 99%

**Primary outcome:** Turn the first three domains from bounded proof datasets into measured, source-faithful broad datasets with >=99% entity and required-field coverage targets.

**Work map:**
- **0-3h - Universe + field inventory:** Freeze current Programs & Courses entity counts by type, scholarship finder/detail snapshot and current Jobs snapshot. Sample source pages to confirm required source-present fields.
- **3-7h - Courses breadth:** Progress discovery-only -> 20 -> 100 -> larger bounded batches across courses/programs/majors/minors/specialisations. Inspect IDs, URLs, duplicates and field capture before broad write.
- **7-10.5h - Scholarships breadth:** Expand approved scholarship discovery/detail ingestion toward frozen universe. Prove status/date/filter/value/eligibility field capture and idempotency.
- **10.5-14h - Jobs breadth + report:** Expand current Jobs through pagination/detail pages toward frozen timestamped snapshot. Validate current/closed/date semantics, links and source health; publish three-domain coverage report.

**Acceptance criteria:**
- Frozen denominators and approved exclusions recorded for all three domains.
- Each domain reaches >=99% entity coverage or has an exact quantified blocker.
- Required source-present fact capture reaches >=99% or quantified blocker.
- Idempotent rerun and failure/last-known-good behavior remain green.
- Canonical URLs and stable identities pass representative audits.

**Evidence:**
- PR/SHA(s) + test counts.
- Frozen denominator/count report by entity class/source.
- Cloud execution IDs + added/changed/unchanged/rejected/duplicate counts.
- Representative normalized records + field coverage results.
- Quantified gaps with source examples.

**Do not / escalate:**
- Do not mass-ingest before sanity review.
- Do not invent fields from prose or third-party sources.
- Do not enable Rubric or StarRez.
- Do not bypass suspicious-count/failure guards to hit a percentage.

**Copy-paste AI kickoff:**

> You are Will in askanu-scraper on V6 Day 11. Read source registry, current collectors, common storage, DATA_SCHEMA and V6 99% domain specs first. Today is not a sample demo: first freeze the approved source universe and required-field denominator for Courses, Scholarships and Jobs with Qasim. Then expand progressively using existing safety primitives. Courses must cover courses, programs, majors, minors and specialisations. Scholarships must cover the approved finder/detail universe. Jobs must cover the frozen current public vacancy snapshot. At every gate report discovered/parsed/persisted/rejected/duplicate counts and stop on suspicious drops. Preserve stable IDs, canonical URLs, source-present wording, nulls, content_hash/idempotency and last-known-good. Do not loosen guards simply to reach 99%.

## Day 12 - Wed 16 Sep 2026 - 14h

**Focus:** Scraper/data - Accommodation + Support source inventory, safe broad ingestion and 99% coverage

**Primary outcome:** Build two independently testable approved collectors and expand each from sample safety proof to >=99% of its frozen entity universe.

**Work map:**
- **0-3h - Universe + field inventory:** Freeze Accommodation entity classes/counts and Support approved service registry. Sample page variants; confirm required source-present fields and canonical identity.
- **3-7h - Accommodation collector:** Fixtures -> dry-run -> small write -> unchanged/failure guard -> progressive broad ingestion. Preserve fees/period wording, features, application/eligibility and explicit unknown vacancy.
- **7-11h - Support collector:** Build source-specific fixtures/parsers; preserve purpose/category/audience/contact/location/hours only when published; progressive broad ingestion with untrusted-content sanitization.
- **11-14h - Cloud + coverage proof:** Run bounded production writes/reruns/failure drills; inspect Cloud SQL counts/representative rows/ingestion_runs; compute entity + field coverage and source health.

**Acceptance criteria:**
- Each domain has frozen entity denominator/source registry.
- >=99% entity coverage and >=99% required source-present fact capture or quantified blocker.
- Repeated run idempotent; failure/drastic-count guard preserves current data.
- Representative rows have approved canonical URLs and stable IDs.
- No authenticated or unapproved source introduced.

**Evidence:**
- PR/SHA(s), fixture/full test counts.
- Cloud execution IDs + run summaries.
- DB counts/samples + coverage numerators/denominators.
- Source-health report and known page variants/missing fields.

**Do not / escalate:**
- Do not scrape StarRez/login/application portals.
- Do not infer vacancy or hours.
- Do not tightly couple parsers.
- Do not mass-write until sample/failure proof is green.

**Copy-paste AI kickoff:**

> You are Will in askanu-scraper on V6 Day 12. Build Accommodation and Support only from the reviewed approved source registry. First freeze the entity universe and required source-present field denominator with Qasim/Carmen. For each domain, prove fixtures, dry-run, first write, unchanged rerun and fetch/parser/drastic-count failure before widening. Then expand in bounded batches toward >=99%. Accommodation preserves residence/category/location/catering/audience/room/rate wording/features/application/eligibility/contract/contact where published and never scrapes StarRez or invents vacancy. Support preserves service purpose/category/audience/contact/location/published hours/access/cost/referral where published. Keep parsers independent so one source failure cannot block the other. Publish raw counts and gaps.

## Day 13 - Thu 17 Sep 2026 - 14h

**Focus:** Scraper/data - five-domain freshness, completeness and recovery freeze

**Primary outcome:** Prove the five completed domains remain >=99% against current frozen snapshots and can refresh/fail/recover safely before Friday.

**Work map:**
- **0-4h - Coverage + freshness rerun:** Recompute entity/field counts for Courses, Scholarships, Jobs, Accommodation, Support; inspect representative canonical URLs and suspicious deltas.
- **4-8h - Failure/recovery drill:** Representative fetch/parser/drastic-count failures across collectors; confirm independent failure and last-known-good; fix only release-critical data defects.
- **8-11h - Schedule/manual refresh state:** Verify safe cadence/manual-run pattern, runtime identity/config and source-health reporting without overlapping dangerous jobs.
- **11-14h - Freeze + provenance pack:** Final bounded refresh with recovery margin; capture counts/execution IDs/source examples; pin scraper/job versions and parser-known-issues.

**Acceptance criteria:**
- Five-domain coverage remains >=99% or exact drift/blocker recorded.
- Representative failure drills preserve last-known-good.
- No suspicious run overwrites current data.
- Source-health/refresh state is known and repeatable.
- Scraper/job versions pinned.

**Evidence:**
- Execution IDs/counts/source-health report.
- Coverage rerun numerators/denominators.
- Failure/recovery evidence.
- Pinned scraper/job config + canonical URL samples.

**Do not / escalate:**
- Do not run risky mass ingestion late.
- Do not add Rubric/new sources.
- Do not manually overwrite DB to hide parser problems.
- Do not relax sanity guards for demo convenience.

**Copy-paste AI kickoff:**

> You are Will in askanu-scraper on V6 Day 13. Today is source/data stabilization for Friday. Recompute coverage for the five completed domains from their frozen source snapshots, inspect any delta and rerun only safe bounded refreshes with last-known-good guards. Exercise representative fetch/parser/drastic-count failures and prove one source cannot wipe another. Fix only P0/P1 coverage/parser defects. Do not add Rubric or a new source today. Freeze parser changes after the evidence block and provide Qasim exact execution IDs, counts, canonical URL samples, job/runtime config and known source risks.

## Day 14 - Fri 18 Sep 2026 - 14h

**Focus:** Scraper/data - pre-demo source health + provenance support + feedback triage

**Primary outcome:** Refresh/verify safely, keep the five completed datasets stable through the presentation and convert data/source feedback into reproducible issues.

**Work map:**
- **0-3h - Pre-demo source health:** Check/refresh approved five-domain data early, inspect counts/suspicious deltas and representative canonical URLs.
- **3-6h - Recovery margin:** If any source fails, prove last-known-good/fallback and stop before risky parser changes; provide provenance evidence to Qasim.
- **6-10h - Presentation stability:** Monitor run/source state, answer source/provenance questions, do not alter source registry/parser unless P0.
- **10-14h - Feedback triage:** Reproduce claimed missing/wrong data against approved source pages; capture fixtures/issues and prepare Saturday Events/source work.

**Acceptance criteria:**
- Pre-demo source health green or explicit safe fallback.
- Representative canonical URLs valid for five completed domains.
- No suspicious run overwrites current data.
- Source/data feedback has actual source example/fixture.

**Evidence:**
- Execution IDs/counts/source-health report.
- Representative URL validation.
- Any P0 data fix PR/test.
- Post-demo source/data issue list.

**Do not / escalate:**
- Do not run risky mass ingestion near demo.
- Do not enable Rubric before approval.
- Do not manually edit DB to hide parser failure.

**Copy-paste AI kickoff:**

> You are Will on V6 Day 14. Run approved-source checks early enough to recover before the GDG ANU presentation. Verify coverage/counts and representative canonical URLs for Courses, Scholarships, Jobs, Accommodation and Support. If a source is unhealthy, rely on last-known-good and report it rather than forcing a risky parser rewrite. During the presentation, do not expand sources or enable Rubric. Afterward, reproduce data feedback against the actual approved source and capture a fixture for real parser defects. Prepare factual source notes for Saturday Events/Rubric work.

## Day 15 - Sat 19 Sep 2026 - 14h

**Focus:** Scraper/data - Events/Rubric source decision, 99% event ingestion + feedback data fixes

**Primary outcome:** Deliver the sixth domain data path with >=99% coverage of the frozen release window and safe freshness, using Rubric only if verified/approved.

**Work map:**
- **0-3h - Source/window freeze:** Inspect/verify official Events and any approved Rubric public-search endpoint. Freeze source, 42-day window (or approved natural window), IDs, pagination, fields and rate behavior.
- **3-6h - Sample safety proof:** Fixtures, dry-run, small real write, unchanged rerun, duplicate/date/timezone/cancellation cases and fetch/parser failure last-known-good.
- **6-10h - Broad window ingestion:** Traverse all approved pagination in window; progressively ingest toward >=99% entity + required-field coverage; inspect counts/source health.
- **10-14h - Freshness + feedback:** Configure safe daily schedule or approved manual fallback only after source-health passes; fix accepted source/data feedback; publish six-domain source-health/coverage report.

**Acceptance criteria:**
- Events entity coverage >=99% or exact quantified blocker.
- Required source-present fact capture >=99% or quantified blocker.
- Unchanged/failure/duplicate/temporal cases pass.
- Safe schedule exists or explicit approved manual fallback.
- Rubric remains disabled unless approved with evidence.

**Evidence:**
- PR/SHA, image/job execution IDs.
- Source/window/denominator record.
- DB counts + field coverage + source-health report.
- Scheduler/manual fallback config.
- Accepted feedback data-fix evidence.

**Do not / escalate:**
- Do not guess Rubric endpoint/permission.
- Do not call Events/Rubric from chat request path.
- Do not run risky unbounded ingestion.
- Do not store cookies/auth tokens.

**Copy-paste AI kickoff:**

> You are Will in askanu-scraper on V6 Day 15. First verify the Events source contract. Rubric may be used only if endpoint/permission/pagination/identity are understood and Qasim explicitly approves it; otherwise use official ANU Events and keep Rubric disabled. Freeze a bounded release window, recommended current Canberra date through 42 days unless the source has a better natural boundary. Build fixtures and prove dry-run/first write/unchanged/failure before broadening. Capture stable event ID, title, start/end/timezone, location/format, category/tags, organiser, description, registration, status/cancellation and canonical URL where published. Traverse all pagination in the window toward >=99%, then prove safe freshness and source health. Apply only accepted Friday data feedback.

## Day 16 - Sun 20 Sep 2026 - 15h

**Focus:** Scraper/data - final six-domain coverage, freshness, recovery and scheduler sweep

**Primary outcome:** Close any remaining approved-source data gap, prove six-domain freshness/recovery and leave collectors boring to operate.

**Work map:**
- **0-3h - Six-domain coverage audit:** Recompute latest entity/field coverage, inspect excluded/rejected/duplicate reasons and rank gaps that are still safely fixable.
- **3-7h - Close data gaps:** Fix highest-value approved parser/discovery/pagination gaps, rerun bounded ingestion and prove changed/unchanged behavior.
- **7-11h - Failure + freshness:** Source fetch/parser/drastic-count/partial-source drills, schedule/manual refresh review, independent-source failure and recovery evidence.
- **11-15h - Operational freeze:** Final safe refresh, source-health snapshot, canonical URL audit, runbook/docs, job/runtime config and one-hour backlog.

**Acceptance criteria:**
- No domain remains below 99% due to a fixable approved parser gap, or exact blocker recorded.
- Changed/unchanged/failure/recovery behavior remains green.
- Canonical URL/source-health audit passes.
- Refresh/schedule/manual fallback state is explicit for every domain.
- Remaining data work fits one-hour slices.

**Evidence:**
- Final scraper SHA/jobs/execution IDs.
- Six-domain coverage/source-health report.
- Failure/recovery evidence + runbook.
- Known source gaps + one-hour backlog.

**Do not / escalate:**
- Do not add new sources casually.
- Do not relax sanity guards.
- Do not manually patch DB as normal operation.
- Do not store auth tokens/cookies.

**Copy-paste AI kickoff:**

> You are Will in askanu-scraper on V6 Day 16, the final planned heavy data day. Recompute six-domain entity and required-field coverage against frozen denominators, then close only approved-source gaps that are still material and safe. Verify pagination/discovery/identity/canonical URLs, changed/unchanged hashes, many-to-zero guards and last-known-good. Exercise representative failures across sources and prove independent recovery. Review safe scheduler/manual refresh cadence; no broad IAM or unapproved sources. Finish with one clean source-health snapshot, exact execution IDs/counts/runbooks and a one-hour-sized data backlog.

## 21 Sep - 3 Oct: one-hour hardening phase

### Day 17 - Mon 21 Sep - SECURITY + PRIVACY AUDIT
- **~45 min:** Secret/source-policy/malicious-source fixture check across collectors; no new source.
- **~15 min proof:** Scraper security PASS/PR.

### Day 18 - Tue 22 Sep - ACCESSIBILITY + MOBILE PASS
- **~45 min:** Validate long titles/special chars/URLs/data display compatibility; fix normalization only if source-faithful.
- **~15 min proof:** Data display-compatibility PASS/PR.

### Day 19 - Wed 23 Sep - FAILURE + RECOVERY PASS
- **~45 min:** Timeout/parser/drastic-count drill on one source; verify last-known-good and recovery rerun.
- **~15 min proof:** Scraper recovery report.

### Day 20 - Thu 24 Sep - PERFORMANCE + COST PASS
- **~45 min:** Inspect scraper request counts/cadence/runtime for one expensive collector; bound if needed.
- **~15 min proof:** Scraper cost/cadence note.

### Day 21 - Fri 25 Sep - SIX-DOMAIN REGRESSION
- **~45 min:** Inspect latest six-domain source-health/counts/URLs/hash/last_seen; no broad refresh if unnecessary.
- **~15 min proof:** Source-health report.

### Day 22 - Sat 26 Sep - DOCS + RUNBOOKS
- **~45 min:** Update source registry, collector/run/failure/freshness notes and approved-source boundaries.
- **~15 min proof:** Scraper runbook PR/PASS.

### Day 23 - Sun 27 Sep - FREEZE READINESS
- **~45 min:** Close top source/parser P0/P1; latest healthy source snapshot.
- **~15 min proof:** Scraper freeze-readiness note.

### Day 24 - Mon 28 Sep - FEATURE FREEZE
- **~45 min:** Check source-registry diff/latest ingestion; no new source without release blocker.
- **~15 min proof:** Scraper freeze note.

### Day 25 - Tue 29 Sep - FROZEN REGRESSION
- **~45 min:** Run frozen source-health/collector subset; no schema/source expansion.
- **~15 min proof:** Scraper frozen-regression PASS/PR.

### Day 26 - Wed 30 Sep - RELEASE-CANDIDATE DRILL
- **~45 min:** Check safe scheduled/manual refresh + recovery; inspect counts.
- **~15 min proof:** Scraper RC drill evidence.

### Day 27 - Thu 1 Oct - FINAL SECURITY + SOURCE AUDIT
- **~45 min:** Dependency/secret/source-policy scan; Rubric only if approved in final registry.
- **~15 min proof:** Scraper final security/source report.

### Day 28 - Fri 2 Oct - RELEASE EVE
- **~45 min:** Final safe source-health check + representative canonical URL validation.
- **~15 min proof:** Final source report.

### Day 29 - Sat 3 Oct - FINAL RELEASE
- **~45 min:** Confirm latest healthy source runs and no suspicious ingestion.
- **~15 min proof:** Data final health.
