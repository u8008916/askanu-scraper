# Will's AskANU V3 Day-by-Day Tasks

**Primary lane:** Scraper / data / freshness

This is a role-filtered copy of the V3 schedule. The shared objective is included so you can see what the rest of the team needs from you.

**Daily rule:** finish the listed deliverable, run the listed verification, surface blockers immediately, and do not invent new scope when blocked.

## Day 1 — Saturday, 05 September 2026 — 5h/person
**Phase:** BOOTSTRAP + CONTRACT FREEZE
**Shared objective:** Make all three repos usable, aligned, and safe for AI-assisted development.

### Will - Scraper repo
**Goal:** Create a safe scraper framework and source registry.
**Do:**
- Create Python source modules for courses, scholarships, jobs, accommodation, support, events.
- Add common fetch/parse/normalise interfaces and ingestion-run model placeholders.
- Add approved source registry from V3; mark Rubric as `PENDING_APPROVAL` and non-production.
- Save initial public HTML fixtures for one course/program and one scholarship page; no mass crawling.
**Verify:** Parser framework tests run; no collector can target a source missing from registry.
**Deliverable:** PR: Scraper bootstrap + source registry + representative fixtures.
**Dependency / fallback:** Uses V3 source list. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: All three repos run locally, contract docs match, and each owner has a mergeable Day 1 PR.

## Day 2 — Sunday, 06 September 2026 — 5h/person
**Phase:** COURSES DATA FOUNDATION
**Shared objective:** Prove the course/program source can become structured records that RAG and UI can consume.

### Will - Scraper repo
**Goal:** Parse ANU Programs & Courses into the first real normalized records.
**Do:**
- Inspect Programs & Courses page structure for course and program entities.
- Implement parser for core identifiers, academic year, title, career/units/delivery and canonical URL.
- Extend course parsing for sessions/prerequisites/assumed knowledge where present.
- Create deterministic `content_hash` and stable IDs; add BACCT + one computing-course fixtures/tests.
**Verify:** Re-parsing the same fixture produces the same IDs/hash and no invented fields.
**Deliverable:** PR: first courses/programs parser + normalized fixtures.
**Dependency / fallback:** Source: programsandcourses.anu.edu.au only. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: One real ANU course/program page can be normalized into a shared record shape and rendered as a mocked grounded answer.

## Day 3 — Monday, 07 September 2026 — 5h/person
**Phase:** FIRST LOCAL VERTICAL SLICE
**Shared objective:** Make a real ANU course question travel from collected data to the browser with a real source link.

### Will - Scraper repo
**Goal:** Perform a live single-record fetch and safe normalization.
**Do:**
- Fetch one approved course/program page through common fetcher.
- Parse and validate required identity/year/URL fields.
- Write normalized record + ingestion-run output to local development storage/DB handoff.
- Add fetch failure and changed-content tests.
**Verify:** Live fetch result matches fixture expectations; repeated run is idempotent.
**Deliverable:** PR: first live approved-source collector.
**Dependency / fallback:** Needs local DB handoff agreed with Qasim/Carmen. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: A student can ask one real course question locally and get a grounded answer with an official ANU source link.

## Day 4 — Tuesday, 08 September 2026 — 5h/person
**Phase:** GROUNDED GEMINI + ABSTENTION
**Shared objective:** Add model synthesis without allowing the model to outrun evidence.

### Will - Scraper repo
**Goal:** Expand course parsing to fields needed for natural questions.
**Do:**
- Capture prerequisites/corequisites/incompatibilities/assumed knowledge when present.
- Capture sessions/offerings and relevant enrolment/census dates when exposed.
- Preserve academic year and canonical URL for every record.
- Add malformed/missing-field fixtures and ensure missing fields stay null/empty, not invented.
**Verify:** Fixtures cover normal + missing-field pages and pass normalization tests.
**Deliverable:** PR: richer course schema parsing.
**Dependency / fallback:** Coordinate field names with DATA_SCHEMA. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: AskANU can use Gemini for a real course answer while preserving evidence, source provenance and abstention.

## Day 5 — Wednesday, 09 September 2026 — 5h/person
**Phase:** COURSE BREADTH + HYBRID RETRIEVAL
**Shared objective:** Turn the single course demo into a reusable course/program retrieval pattern.

### Will - Scraper repo
**Goal:** Broaden Programs & Courses collection pattern.
**Do:**
- Handle catalogue/search result discovery for courses, programs, majors, minors and specialisations.
- Preserve academic year and entity type in IDs/metadata.
- Add sanity counts and duplicate detection before any bulk DB update.
- Run a bounded sample across multiple entity types; do not mass-ingest until sanity checks pass.
**Verify:** Sample contains multiple entity types with stable IDs and no duplicate canonical entities.
**Deliverable:** PR: catalogue discovery + bounded multi-entity tests.
**Dependency / fallback:** Must obey source load/rate policy. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: Courses are no longer a one-record demo: the team has a tested reusable discovery, storage, retrieval and UI pattern.

## Day 6 — Thursday, 10 September 2026 — 5h/person
**Phase:** EARLY GCP FOUNDATION
**Shared objective:** Get the real system onto GCP early enough that cloud problems cannot surprise the team later.

### Will - Scraper repo
**Goal:** Make scraper runnable as a job rather than a continuously running web server.
**Do:**
- Create one-shot job entrypoint with source selection/dry-run mode.
- Return non-zero exit on ingestion failure and structured run summary on success.
- Use environment config for DB/cloud values; no secret files.
- Run local job against bounded course sample.
**Verify:** Job exits cleanly on success and safely on simulated fetch failure.
**Deliverable:** PR: Cloud Run Job-ready scraper entrypoint.
**Dependency / fallback:** Needs deployment/env contract. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: At least a health-level App -> RAG deployment exists in the real GCP environment.

## Day 7 — Friday, 11 September 2026 — 5h/person
**Phase:** DEPLOYED REAL COURSE SLICE
**Shared objective:** Connect cloud services, Cloud SQL and one real course query end-to-end.

### Will - Scraper repo
**Goal:** Load first safe course ingestion run into shared cloud DB.
**Do:**
- Run bounded collector job against approved course source.
- Write ingestion_run counts and normalized record with canonical URL/hash.
- Verify rerun is idempotent and unchanged record is not unnecessarily re-embedded.
- Record any source-rate/parser issues before expanding scope.
**Verify:** Two runs show stable record ID/hash and safe ingestion counts.
**Deliverable:** Cloud ingestion evidence + test logs.
**Dependency / fallback:** Needs Qasim DB/job identity. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: A real student-facing deployed URL completes the first source-to-answer vertical slice.

## Day 8 — Saturday, 12 September 2026 — 5h/person
**Phase:** SCHEDULED FRESHNESS PROOF
**Shared objective:** Prove AskANU can update safely after source content changes.

### Will - Scraper repo
**Goal:** Deploy the first daily scheduled collector with last-known-good protection.
**Do:**
- Create Cloud Run Job deployment for courses and Cloud Scheduler daily trigger.
- Implement compare-by-content_hash and `last_seen_at`.
- Add suspicious many-records-to-zero sanity guard and parser-failure rollback/keep-current behaviour.
- Trigger job manually once and collect ingestion-run evidence.
**Verify:** Scheduled job exists; unchanged rerun does not re-embed; simulated zero/failure does not wipe data.
**Deliverable:** Scheduled update proof + run logs.
**Dependency / fallback:** Needs Qasim Scheduler/job IAM. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: AskANU has a proven scheduled, change-aware update path rather than a one-time index.

## Day 9 — Sunday, 13 September 2026 — 5h/person
**Phase:** SCHOLARSHIPS DOMAIN
**Shared objective:** Add structured scholarship ingestion, filtering and the 9-card Featured resource page.

### Will - Scraper repo
**Goal:** Build ANU scholarship listing + detail collector.
**Do:**
- Discover scholarship listing/detail URLs from approved ANU finder.
- Collect featured flag, status, application requirement, study stage/type/level/area, value, selection basis, dates, eligibility and URL.
- Preserve missing deadline as unknown; never invent date.
- Add fixtures for open Featured, open non-Featured and closed scholarship.
**Verify:** Parser tests cover Featured/open/closed and produce stable canonical records.
**Deliverable:** PR: scholarship collector + fixtures/tests.
**Dependency / fallback:** Source: study.anu.edu.au scholarships only. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: Students can browse current Featured scholarships and ask filtered scholarship questions without persistent profiling.

## Day 10 — Monday, 14 September 2026 — 5h/person
**Phase:** JOBS DOMAIN
**Shared objective:** Add current ANU jobs with deterministic closing-date logic and chat retrieval.

### Will - Scraper repo
**Goal:** Build ANU jobs search/list/detail collector.
**Do:**
- Collect title, category, employment type, location, classification, closing date, summary and canonical URL.
- Normalize closing date in Canberra-aware representation.
- Mark current/closed based on explicit source data/date rules; do not invent status.
- Add fixtures/tests for open dated, open undated and expired/closed cases.
**Verify:** Collector produces records that deterministic endpoint can sort correctly.
**Deliverable:** PR: jobs collector + fixtures/tests.
**Dependency / fallback:** Source: jobs.anu.edu.au/jobs/search. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: AskANU can deterministically surface current jobs and answer job questions using fresh official data.

## Day 11 — Tuesday, 15 September 2026 — 5h/person
**Phase:** ACCOMMODATION + SUPPORT
**Shared objective:** Add two lower-volatility domains with strict claims boundaries.

### Will - Scraper repo
**Goal:** Build ANU Accommodation + ANUSA Student Assistance collectors.
**Do:**
- Collect residence name, catering/resident type, advertised rate text, description, application status/year and canonical page.
- Do not scrape authenticated StarRez application content.
- Collect ANUSA assistance categories, service descriptions, contact/action URLs and only explicit hours.
- Add fixtures/tests for missing rate/hours and link validation.
**Verify:** Collectors preserve source wording for sensitive fields and never infer vacancy/hours.
**Deliverable:** PR: accommodation + support collectors.
**Dependency / fallback:** Sources: study.anu.edu.au accommodation + anusa.com.au student-assistance. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: Accommodation and Support have real resource pages and grounded chat coverage without overclaiming.

## Day 12 — Wednesday, 16 September 2026 — 5h/person
**Phase:** EVENTS RELEASE SOURCE
**Shared objective:** Ship Events using an approved source while keeping Rubric optional and permission-gated.

### Will - Scraper repo
**Goal:** Implement official ANU Events collector and isolate Rubric work.
**Do:**
- Build approved ANU Events/calendar collector with event ID/title/start/end/venue/organiser/description/URL.
- Add temporal/status normalization and daily polling fixtures/tests.
- Create Rubric adapter interface/feature flag only; no calls to undocumented `getUnifiedSearch`.
- Document known Rubric schema discovery for future approved integration without storing tokens/cookies.
**Verify:** Events collector produces current/upcoming records; Rubric path is disabled by default.
**Deliverable:** PR: ANU Events collector + Rubric placeholder/documentation.
**Dependency / fallback:** Rubric use requires explicit approval. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: Upcoming Events works from an approved source; Rubric cannot block the stakeholder demo or release.

## Day 13 — Thursday, 17 September 2026 — 5h/person
**Phase:** CONVERSATION + MOBILE + DEMO STABILISATION
**Shared objective:** Make the six-domain baseline feel coherent as one assistant and freeze tomorrow’s demo scope.

### Will - Scraper repo
**Goal:** Run full daily poll and harden parser failures across all six domains.
**Do:**
- Execute bounded staging ingestion for Courses, Scholarships, Jobs, Accommodation, Support and Events.
- Verify run counts, canonical URLs, hashes and last-known-good behaviour.
- Fix only release-blocking parser/data issues today.
- Produce one source-health summary for demo morning refresh.
**Verify:** Every required domain has at least baseline approved records or a documented blocker/fallback.
**Deliverable:** Six-domain ingestion report + P0 data issues.
**Dependency / fallback:** All approved collectors must exist. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: One deployed, responsive six-domain AskANU baseline is stable enough to rehearse for stakeholders.

## Day 14 — Friday, 18 September 2026 — 5h/person
**Phase:** STAKEHOLDER PRESENTATION
**Shared objective:** Present a stable, real AskANU slice and convert feedback into actionable post-demo work.

### Will - Scraper repo
**Goal:** Refresh source data and verify provenance before demo.
**Do:**
- Run final approved-source daily ingestion with sanity checks.
- Validate representative source URLs for all six domains.
- Keep Rubric disabled unless explicit approval is already documented.
- After demo, classify data/source feedback and parser gaps.
**Verify:** Freshness/source-health report is green or documented; no suspicious ingestion overwrote current data.
**Deliverable:** Pre-demo source report + feedback issues.
**Dependency / fallback:** Needs staging/prod job access. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: A stable AskANU is demonstrated to ANU GDG and the remaining schedule is updated from real feedback.

## Day 15 — Saturday, 19 September 2026 — 1h/person
**Phase:** POST-DEMO TRIAGE
**Shared objective:** Convert stakeholder feedback into a realistic remaining plan without immediately expanding scope.

### Will - Scraper repo
**Goal:** Review source/data feedback and identify one highest-risk coverage gap.
**Do:**
- Check source health/counts since demo.
- Choose one parser/field gap that affects real answers.
**Verify:** Gap has affected query/source example.
**Deliverable:** One prioritised scraper issue.
**Dependency / fallback:** Uses source-health report. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: Every stakeholder comment is triaged; tomorrow starts from actual status, not the old assumption.

## Day 16 — Sunday, 20 September 2026 — 1h/person
**Phase:** TOP DEFECT FIX
**Shared objective:** Use the one-hour window for one tested slice per person, not a new feature.

### Will - Scraper repo
**Goal:** Fix the highest-priority parser/data defect from Sep 19.
**Do:**
- Adjust one parser/normalizer rule.
- Add/repair fixture test.
**Verify:** Fixture reproduces old failure and now passes.
**Deliverable:** Small scraper PR.
**Dependency / fallback:** If blocked, capture new fixture + diagnosis. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: The most important post-demo defects have either a tested fix or a reproducible blocker.

## Day 17 — Monday, 21 September 2026 — 1h/person
**Phase:** SOURCE COMPLETENESS AUDIT
**Shared objective:** Find missing evidence before hardening the model around incomplete data.

### Will - Scraper repo
**Goal:** Audit collector coverage/counts and canonical URLs.
**Do:**
- Compare expected entity types/fields to actual records.
- Flag parsers producing suspicious missing fields.
**Verify:** Coverage gaps have source example + parser owner.
**Deliverable:** Scraper coverage report.
**Dependency / fallback:** Uses ingestion_runs. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: The team knows exactly which remaining failures are evidence gaps versus retrieval/UI defects.

## Day 18 — Tuesday, 22 September 2026 — 1h/person
**Phase:** MOBILE + ACCESSIBILITY
**Shared objective:** Make the confirmed responsive UI usable, not merely visually similar.

### Will - Scraper repo
**Goal:** Validate titles/URLs/text encoding for mobile resource cards.
**Do:**
- Check long titles and special characters from each source.
- Fix normalization only if source text breaks display/links.
**Verify:** Representative records render without broken text/URL.
**Deliverable:** Data display-compatibility test.
**Dependency / fallback:** Uses fixtures. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: AskANU works through the core chat/resource flow on common mobile widths with keyboard-accessible controls.

## Day 19 — Wednesday, 23 September 2026 — 1h/person
**Phase:** SECURITY + PRIVACY
**Shared objective:** Close concrete security/privacy gaps before feature freeze.

### Will - Scraper repo
**Goal:** Verify scraped content is treated as data, not instruction.
**Do:**
- Add malicious-source fixture if missing.
- Ensure sanitizer/normalizer retains evidence text safely without executing anything.
**Verify:** Fixture cannot alter scraper control flow.
**Deliverable:** Scraper security test.
**Dependency / fallback:** No unapproved source. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: Release security/privacy controls are tested and remaining governance questions are explicit.

## Day 20 — Thursday, 24 September 2026 — 1h/person
**Phase:** INGESTION FAILURE + RECOVERY
**Shared objective:** Prove source failures cannot silently corrupt the live index.

### Will - Scraper repo
**Goal:** Run failure drills: timeout, parser failure, suspicious zero.
**Do:**
- Execute or simulate each failure.
- Verify last-known-good survives and run status is failed/visible.
**Verify:** No failure wipes current approved data.
**Deliverable:** Scraper recovery report/PR.
**Dependency / fallback:** Primary owner today. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: One failed source run can be detected, contained and recovered without losing last-known-good data.

## Day 21 — Friday, 25 September 2026 — 1h/person
**Phase:** CONVERSATION EDGE CASES
**Shared objective:** Finish the core session-context behaviours before freeze.

### Will - Scraper repo
**Goal:** Provide multi-entity/course fixtures needed for ambiguity tests.
**Do:**
- Validate entity IDs/names remain distinct and stable.
- Fix data collision only if reproduced.
**Verify:** Ambiguity tests use realistic records.
**Deliverable:** Fixture/data PR or PASS.
**Dependency / fallback:** No new domain. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: Current-session follow-ups and clarification are reliable enough for release; optional batching cannot jeopardise them.

## Day 22 — Saturday, 26 September 2026 — 1h/person
**Phase:** SIX-DOMAIN REGRESSION
**Shared objective:** Run the whole product as a product, not as six separate demos.

### Will - Scraper repo
**Goal:** Run all six collectors in bounded staging mode and inspect counts.
**Do:**
- Check canonical URLs/hashes/last_seen.
- Investigate only suspicious counts/failures.
**Verify:** All required sources have healthy/latest run or documented blocker.
**Deliverable:** Source-health report.
**Dependency / fallback:** Approved sources only. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: The team has a single pre-freeze defect list based on a real six-domain regression run.

## Day 23 — Sunday, 27 September 2026 — 4h/person
**Phase:** 4-HOUR CATCH-UP + INTEGRATION
**Shared objective:** Use the only expanded late-phase day to close critical carry-over before feature freeze.

### Will - Scraper repo
**Goal:** Close highest-priority source/parser P0/P1 items and refresh staging data.
**Do:**
- First 2h: source coverage/parser blocker.
- Next 1h: full ingestion + failure sanity checks.
- Final 1h: source URL validation/report.
**Verify:** Required-domain data is healthy and no suspicious run is unresolved.
**Deliverable:** Scraper catch-up PRs + source report.
**Dependency / fallback:** Rubric only if approved and clearly non-blocking. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: Critical carry-over is closed or explicitly accepted before tomorrow’s feature freeze.

## Day 24 — Monday, 28 September 2026 — 1h/person
**Phase:** FEATURE FREEZE
**Shared objective:** Stop feature growth and lock the release candidate behaviour.

### Will - Scraper repo
**Goal:** Freeze production source registry/parser behaviour.
**Do:**
- Run source registry diff and latest ingestion health.
- No new source added without release-blocking reason.
**Verify:** Approved source set is explicit.
**Deliverable:** Scraper freeze note.
**Dependency / fallback:** Bug fixes only. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: AskANU enters bug-fix-only mode with a documented release candidate and known issues.

## Day 25 — Tuesday, 29 September 2026 — 1h/person
**Phase:** CLEAN CLONE + REPRODUCIBILITY
**Shared objective:** Prove the project works from repositories and docs, not only from current laptops.

### Will - Scraper repo
**Goal:** Run scraper install + one dry-run collector from clean clone.
**Do:**
- Use approved fixture/live bounded source.
- Verify no local-only file/secret required.
**Verify:** Scraper dry-run works from clean clone.
**Deliverable:** Clean-clone evidence/PR.
**Dependency / fallback:** No feature changes. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: The three repos can be reproduced from clean clones using documented configuration.

## Day 26 — Wednesday, 30 September 2026 — 1h/person
**Phase:** SECURITY + DEPENDENCY RELEASE SCAN
**Shared objective:** Run final automated/manual security checks before rehearsal.

### Will - Scraper repo
**Goal:** Run scraper dependency/secret/source-policy scan.
**Do:**
- Check no unapproved Rubric/internal endpoint code enabled.
- Verify credentials are environment/Secret Manager only.
**Verify:** Production source policy matches V3.
**Deliverable:** Scraper security report.
**Dependency / fallback:** Bug fixes only. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: Release candidate has a documented security/dependency/privacy status with no unknown critical blocker.

## Day 27 — Thursday, 01 October 2026 — 1h/person
**Phase:** DEPLOYMENT + RECOVERY REHEARSAL
**Shared objective:** Prove the team can deploy, smoke-test and recover before final day.

### Will - Scraper repo
**Goal:** Verify scheduled scraper job and manual recovery rerun.
**Do:**
- Check latest scheduled run.
- Trigger safe manual run and inspect counts/logs.
**Verify:** Job can be rerun without duplicates/corruption.
**Deliverable:** Scraper recovery evidence.
**Dependency / fallback:** Approved sources only. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: The team can deploy the release candidate and recover core services using documented steps.

## Day 28 — Friday, 02 October 2026 — 1h/person
**Phase:** FINAL REGRESSION + DEMO PREP
**Shared objective:** Finish only release blockers and prepare a boring, repeatable final demo.

### Will - Scraper repo
**Goal:** Run final source refresh + URL validation.
**Do:**
- Ingest approved sources with sanity guards.
- Validate representative canonical URLs and freeze source-health report.
**Verify:** No suspicious ingestion/source-link issue.
**Deliverable:** Final source report.
**Dependency / fallback:** No new source. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: Release candidate, data and demo are finalised; only emergency fixes remain for Oct 3.

## Day 29 — Saturday, 03 October 2026 — 1h/person
**Phase:** FINAL RELEASE
**Shared objective:** Release AskANU, run smoke tests, and leave a reproducible handover.

### Will - Scraper repo
**Goal:** Verify final ingestion/source health.
**Do:**
- Check latest scheduled/manual run status.
- Confirm all six required domains have approved baseline data.
**Verify:** No critical source failure at release.
**Deliverable:** Final scraper/source check.
**Dependency / fallback:** Emergency fixes only. If blocked: work only on the listed fallback or tests; do not invent new scope.

**Team integration check:** END-OF-DAY INTEGRATION CHECK: AskANU is released with traceable versions, healthy sources, passing core flows and a clear known-issues/handover record.
