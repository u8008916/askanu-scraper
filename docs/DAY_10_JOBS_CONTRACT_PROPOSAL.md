# Day 10 Jobs Contract v1

Owner: Will
Reviewers: Carmen and Qasim
Status: **FROZEN BY QASIM — PostgreSQL writes remain disabled**

Qasim froze this Scraper -> DB -> RAG contract on 2026-09-14 after Carmen/Will
review. Implementations may depend on this shape. Cloud SQL writes, production
release and Scheduler activation remain separate integration gates.

## Identity and provenance

- `domain = "jobs"`
- `source_id = "jobs_anu_search"`
- `entity_id = <numeric public requisition identifier>`
- `record_id = "jobs:job:<entity_id>"`
- `canonical_url` is the exact public `https://jobs.anu.edu.au/jobs/<slug>` URL.
- Search, `/me`, candidate-account, application, off-origin and malformed URLs
  are never persisted.

## Frozen metadata

`metadata_json` contains exactly:

```text
entity_type       "job"
job_id            numeric requisition ID string
category          string | null
employment_types array of source strings; [] when missing
location          string | null
classification    string | null
salary            source wording string | null
closing_text      original displayed wording | null
closing_date      YYYY-MM-DD | null
closing_at        timezone-aware ISO-8601 datetime | null
status            "current" | "closed" | null
summary           string | null
```

Unknown metadata keys are invalid. `salary` remains source text rather than a
calculated numeric range. Fixed term is an `employment_types` value and never
implies that a role is closed. No opening/start/posting date exists in v1
without a reliable, consistently available official source field.

An exact source time is interpreted in `Australia/Canberra`. A date-only close
remains current for that full Canberra calendar date and does not invent a
time. Explicit open/closed wording takes precedence; otherwise a parseable
closing value determines status. Missing status and deadline remain `null`.
Top-level `effective_from` and `effective_to` remain `null`.

## RAG query semantics

Current Jobs includes only records with `status == "current"` and either no
`closing_date` or a date on/after Canberra today. Closed, past-date and
null-status records are excluded. Dated current roles sort before undated roles.
Dated roles sort by `closing_date` ascending then numeric `entity_id` ascending;
undated roles sort by numeric `entity_id` ascending. Filtering occurs before
ordering and limiting.

Exact lookup uses numeric `job_id`/`entity_id` first, then exact normalized
title, then general Jobs retrieval. A duplicate title is ambiguous and must not
be selected arbitrarily.

## Persistence and ownership

Jobs use the shared `source_records` table rather than a Jobs-specific table.
Carmen owns the next RAG migration after live revision `20260914_0003` (expected
`20260914_0004`); Will owns normalized production and safe writes; Qasim owns
the cross-repo/cloud release gate. Cloud deployment uses a separate
`askanu-scraper-jobs` job rather than repurposing Courses or Scholarships.

## Safety and rollout gate

- One listing page and at most ten public same-origin detail pages.
- At least one second between live requests.
- Validate every direct/discovered URL before fetch and require any page
  canonical URL to match the fetched public detail URL.
- Parse/validate the complete bounded sample before the first batch write.
- Empty results, drastic advertised-card count mismatches, duplicate
  identity/URLs, failed fetches and parser drift fail visibly and preserve
  last-known-good.
- Bounded samples do not prove removal and do not mark unseen records missing.
- `SCRAPER_JOBS_POSTGRES_APPROVED` defaults to `false`; Cloud SQL writes and
  Scheduler changes require explicit cross-repo approval and evidence.
