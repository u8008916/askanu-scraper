# AGENTS.md — askanu-scraper

Primary owner: **Will**. Contracts/integration/release: **Qasim**.

This repo owns approved-source collection, fetch/parse/normalise, stable IDs, canonical URLs, dedupe, hashes, freshness, ingestion runs, safe DB writes, scheduled polling and parser fixtures/tests.

Read `docs/SOURCE_REGISTRY.md` before every collector.

Do not:
- add a production source because an AI found it
- bypass login/auth/paywall/technical controls
- scrape authenticated StarRez
- use Rubric's undocumented/internal API without approved access

Pipeline:
FETCH -> PARSE -> VALIDATE -> SANITY CHECK -> COMPARE -> DB UPDATE -> EMBED CHANGED -> MARK INDEXED -> PUBLISH CURRENT

Failure must preserve last-known-good.

Before coding read root `my_day_by_day_tasks.md` as the current execution plan,
then `docs/DATA_SCHEMA.md`, `docs/SOURCE_REGISTRY.md` and
`docs/SECURITY_BASELINE.md`. `docs/MY_DAY_BY_DAY_TASKS.md` is the older V3 plan.
