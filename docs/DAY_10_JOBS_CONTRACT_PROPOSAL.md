# Day 10 Jobs Contract Proposal

Owner: Will
Reviewers: Carmen and Qasim
Status: **PROPOSED — PostgreSQL writes remain disabled**

This proposal records the local scraper shape needed to unblock fixture and
parser work. It does not amend the frozen shared contract until Carmen and
Qasim approve it and synchronize affected repositories.

## Identity and provenance

- `domain = "jobs"`
- `source_id = "jobs_anu_search"`
- `entity_id = <numeric public requisition identifier>`
- `record_id = "jobs:job:<entity_id>"`
- `canonical_url` is the exact public `https://jobs.anu.edu.au/jobs/<slug>` URL.
- Search, `/me`, candidate-account, application, off-origin and malformed URLs
  are never persisted.

## Proposed metadata

`metadata_json` contains exactly:

```text
entity_type       "job"
job_id            numeric requisition ID string
category          string | null
employment_type   string | null
location          string | null
classification    string | null
closing_text      original displayed wording | null
closing_date      YYYY-MM-DD | null
closing_at        timezone-aware ISO-8601 datetime | null
status            "current" | "closed" | null
summary           string | null
```

An exact source time is interpreted in `Australia/Canberra`. A date-only close
remains current for that full Canberra calendar date and does not invent a
time. Explicit open/closed wording takes precedence; otherwise a parseable
closing value determines status. Missing status and deadline remain `null`.
Top-level `effective_from` and `effective_to` remain `null` pending review.

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
