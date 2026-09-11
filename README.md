# AskANU Scraper

Approved-source collection, normalization, freshness, and safe ingestion.

**Primary owner:** Will

**Contracts/integration/release:** Qasim

The scraper owns approved-source fetch/parse/validate/compare behaviour,
stable IDs and canonical URLs, ingestion runs, and safe persistence handoff.
Shared record semantics are defined in `docs/DATA_SCHEMA.md`; production
source policy is defined in `docs/SOURCE_REGISTRY.md`.

## One-shot Courses job

Install the package, then run one bounded job:

```powershell
python -m pip install -e ".[dev]"
askanu-scraper-job --academic-year 2026 --max-courses 1 --max-programs 1 --dry-run
```

For the Day 7 COMP1110 smoke, select the one approved detail record directly:

```powershell
askanu-scraper-job --academic-year 2026 --course-code COMP1110 --dry-run
```

`--course-code` accepts only normalized ANU course-code shapes and constructs a
detail URL under the approved Programs & Courses registry root. When omitted,
the existing bounded catalogue sample remains the default.

The command performs one approved Courses catalogue run and exits. CLI options
override their matching environment variables. The current Day 6 safety bound
requires at least one course, at least one program, and no more than four total
records. Live requests retain a minimum one-second interval.

Success exits `0`. Collector failures and suspicious-zero runs exit `1`.
Invalid, inactive, mismatched, or unsupported source configuration exits `2`.
Every attempted run emits one compact JSON summary with status and record
counts. Secret-bearing DB/cloud configuration and credentials are never
included in that summary.

Dry-run mode fetches, parses, validates, and compares against existing local
records, but writes neither records nor ingestion-run files.

The Day 6 container image defaults `SCRAPER_DRY_RUN=true`: Cloud Run executions
must stay dry-run while `LocalDataStore` is the active persistence adapter,
because its `/data` filesystem is not durable. Enable
`SCRAPER_DRY_RUN=false` in Cloud Run only after the durable Cloud SQL
persistence path is connected. Local development can explicitly set it to
`false` when local JSON persistence is intended.

The reviewed Day 7 image can select the shared PostgreSQL boundary with
`SCRAPER_STORAGE_BACKEND=postgres`. Keep `SCRAPER_DRY_RUN=true` while reviewing
the connection and comparison path. Real writes require Carmen's migration to
contain `course_program_records`. Day 7 ingestion-run evidence remains the
structured JSON summary written to Cloud Run logs.

To verify the failure path without making a network request:

```powershell
askanu-scraper-job --academic-year 2026 --max-courses 1 `
  --max-programs 1 --dry-run --simulate-fetch-failure
$LASTEXITCODE
```

See `docs/DEPLOYMENT.md` for environment configuration, container usage, and
the current Cloud SQL handoff boundary.

## Development verification

```powershell
python -m pytest
git diff --check
```

No collector may target a source missing from the approved registry. Never
commit `.env` files, credentials, tokens, cookies, or service-account keys.
