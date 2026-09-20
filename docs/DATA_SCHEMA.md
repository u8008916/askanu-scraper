# DATA_SCHEMA.md

Shared Scraper -> storage/DB -> RAG normalized record contract.

## Schema version

**Shared schema v1 with frozen Courses/Programs, Scholarships and Jobs domain contracts**

Courses/Programs were frozen on 2026-09-06, Scholarships on 2026-09-13 and Jobs
on 2026-09-14.

This document defines the serialized boundary between:

```text
askanu-scraper
    -> normalized record
    -> local storage / DB
    -> askanu-rag
```

The scraper and RAG repositories may use different internal Python classes,
but the serialized record crossing this boundary MUST follow this contract.

Do not copy scraper implementation into the RAG repository.

---

# 1. Common normalized record

A normalized record contains these top-level fields:

| Field | Serialized type | Nullable | Meaning |
|---|---|---:|---|
| `record_id` | string | no | Stable globally unique AskANU record identifier |
| `source_id` | string | no | Stable ID of the approved source registry entry |
| `entity_id` | string | no | Stable logical entity identity for this academic-year record |
| `domain` | string | no | AskANU domain |
| `title` | string | no | Source-derived normalized title |
| `content` | string | no | Canonical normalized text used for retrieval/embedding and hashing |
| `canonical_url` | URL string | no | Official source URL for this record |
| `status` | string enum | no | Scraper ingestion/change state |
| `effective_from` | ISO-8601 datetime | yes | Source-supported effective start, when available |
| `effective_to` | ISO-8601 datetime | yes | Source-supported effective end, when available |
| `collected_at` | ISO-8601 datetime | no | Time this source record was collected |
| `last_seen_at` | ISO-8601 datetime | no | Most recent successful observation of this record |
| `content_hash` | string | no | Lowercase SHA-256 hex digest of `content` |
| `embedding_version` | string | yes | Embedding version if/when embedding has occurred |
| `index_status` | string enum | no | Indexing state |
| `metadata_json` | JSON object | no | Domain-specific normalized metadata |

Unknown top-level fields are not part of schema v1.

RAG models MAY use strict validation such as `extra="forbid"` provided they
declare every schema-v1 top-level field above.

---

# 2. Required vs optional fields

The following top-level fields are REQUIRED and MUST NOT be null:

```text
record_id
source_id
entity_id
domain
title
content
canonical_url
status
collected_at
last_seen_at
content_hash
index_status
metadata_json
```

The following top-level fields MAY be null when no supported value exists:

```text
effective_from
effective_to
embedding_version
```

A missing required identity/provenance field makes the normalized record invalid.

Do not invent a replacement value for a missing required source identity field.
Reject/flag the record instead.

---

# 3. Domain values

Current schema-v1 domain values remain:

```text
courses
scholarships
jobs
accommodation
support
events
```

ANU Courses and ANU Programs both use:

```text
domain = "courses"
```

Their entity type is distinguished inside `metadata_json` and in `record_id`.

---

# 4. Record status

Allowed `status` values:

```text
NEW
CHANGED
UNCHANGED
MISSING
```

Meanings:

- `NEW`: no previous logical record exists.
- `CHANGED`: same logical record exists but `content_hash` changed.
- `UNCHANGED`: same logical record and same `content_hash`.
- `MISSING`: previously known record was not observed; this does not mean immediate deletion or cancellation.

Fetch/parser failures preserve last-known-good data.

A suspicious many-to-zero result MUST fail/review the run rather than mark all
records missing or delete them.

---

# 5. Index status

Allowed `index_status` values:

```text
PENDING
INDEXED
FAILED
```

Meanings:

- `PENDING`: DB/record exists but indexing/embedding is not complete.
- `INDEXED`: required indexing/embedding completed successfully.
- `FAILED`: indexing/embedding failed.

DB success plus embedding failure MUST NOT appear as `INDEXED`.

Day 2 deterministic exact retrieval does not need to use this field for lookup
yet, but it MUST be able to accept/preserve it.

---

# 6. ID semantics

## `source_id`

`source_id` identifies the approved source definition.

It does NOT identify:

- the course,
- the program,
- an academic year,
- or an individual webpage.

For ANU Programs & Courses schema v1:

```text
source_id = "courses_programs_and_courses"
```

The source registry remains owned by the scraper/data side.

---

## `entity_id`

`entity_id` identifies one normalized course/program entity for one academic
year.

### Course

Format:

```text
<COURSE_CODE>_<ACADEMIC_YEAR>
```

Example:

```text
COMP1100_2026
```

### Program

Format:

```text
<PROGRAM_CODE>_<ACADEMIC_YEAR>
```

Example:

```text
BACCT_2026
```

Academic year is part of `entity_id` because multiple years of the same
course/program MUST be able to coexist.

The same `entity_id` remains stable when source content changes during that
academic year. Content changes are represented by `content_hash`, not by
creating a new entity ID.

### Scholarship

For the approved ANU Scholarship Finder, `entity_id` is the lowercase slug from
the persisted canonical detail URL path:

```text
https://study.anu.edu.au/scholarships/find-scholarship/<slug>
```

It is not derived from the title and contains no deadline, status, year or
value. This persisted-record rule does not apply to the Scholarship home or
Finder listing pages used as frontend navigation links; those pages create no
`entity_id` or `record_id`.

Example:

```text
national-university-scholarship
```

### Job

For the approved public ANU Jobs source, `entity_id` is the numeric public
requisition/job identifier represented as a string. It is not derived from the
title or canonical URL slug and remains stable when mutable job fields change.

Example:

```text
563693
```

---

## `record_id`

`record_id` is the stable persisted AskANU record key.

### Course format

```text
courses:course:<ENTITY_ID>
```

Example:

```text
courses:course:COMP1100_2026
```

### Program format

```text
courses:program:<ENTITY_ID>
```

Example:

```text
courses:program:BACCT_2026
```

### Scholarship format

```text
scholarships:scholarship:<ENTITY_ID>
```

Example:

```text
scholarships:scholarship:national-university-scholarship
```

### Job format

```text
jobs:job:<ENTITY_ID>
```

Example:

```text
jobs:job:563693
```

`record_id` remains stable when the normalized source content changes.
`content_hash` is used to detect those changes.

---

# 7. Course/program code normalization

## Course code

Normalize for deterministic lookup by:

1. removing whitespace,
2. converting to uppercase.

Schema-v1 course-code validation:

```regex
^[A-Z]{4}\d{4}[A-Z]?$
```

Examples:

```text
COMP 1100 -> COMP1100
comp1100  -> COMP1100
BIOL9001P -> BIOL9001P
```

The normalized source-supported value is stored in:

```text
metadata_json["course_code"]
```

---

## Program code

For schema v1:

1. trim surrounding whitespace,
2. convert to uppercase.

Do not introduce a stricter program-code regex until supported by actual ANU
program source evidence.

The normalized source-supported value is stored in:

```text
metadata_json["program_code"]
```

---

# 8. Academic year

For Courses/Programs schema v1, academic year is REQUIRED.

Serialized type:

```text
string
```

Format:

```regex
^\d{4}$
```

Example:

```text
"2026"
```

It is stored explicitly in:

```text
metadata_json["academic_year"]
```

RAG MUST NOT infer academic year from:

- current system date,
- `record_id`,
- `entity_id`,
- or `canonical_url`.

The scraper may derive academic year from approved source evidence during
parsing, including the page's explicit Academic Year control or the approved
page URL when necessary.

After normalization, the explicit `metadata_json["academic_year"]` value is
the cross-repo value consumed by RAG.

---

# 9. Multi-year retrieval rule

RAG storage/repository indexing MUST permit multiple records with the same
course/program code across different academic years.

Do not index only by code.

Conceptually the deterministic key is:

```text
(entity_type, normalized_code, academic_year)
```

Examples:

```text
("course", "COMP1100", "2026")
("course", "COMP1100", "2027")
("program", "BACCT", "2026")
```

Code-only lookup may return:

- zero matching years,
- one matching year,
- multiple matching years.

If multiple years exist and the retrieval/planner layer has not resolved an
academic year, the repository MUST NOT:

- overwrite one record with another,
- silently choose an arbitrary year,
- or infer the current year from system time.

The ambiguity must remain visible to the retrieval/planner layer so it can
resolve or clarify it.

---

# 10. Canonical URL

`canonical_url` is REQUIRED.

The scraper owns canonical-URL extraction.

Priority:

1. use an official canonical URL explicitly supplied by the approved source;
2. otherwise use the approved fetched page URL.

Allowed normalization:

- trim surrounding whitespace,
- remove an unnecessary trailing slash where safe.
- for approved ANU Scholarship Finder detail URLs, strip query strings and
  fragments before deriving identity or storing the canonical URL.
- for approved ANU Jobs detail URLs, require `https://jobs.anu.edu.au/jobs/<slug>`,
  strip query strings/fragments, remove the trailing slash and require any page
  canonical URL to match the fetched detail URL. The slug is provenance, not
  job identity.

Do NOT:

- synthesize an ANU URL inside RAG,
- reconstruct it from course/program code,
- lowercase source URL paths,
- or ask the LLM to produce it.

RAG consumes the stored `canonical_url` directly.

For source/evidence responses, URLs come from stored records, never Gemini.

Scholarship navigation/resource links are separate from persisted evidence
URLs. The App may statically link to the official Scholarship home and Finder:

```text
https://study.anu.edu.au/scholarships
https://study.anu.edu.au/scholarships/find-scholarship
```

These are not individual Scholarship records and must not be forced through
the detail-slug identity validator. A source link supporting an answer about a
specific Scholarship must instead come from that stored record's exact
`canonical_url`.

---

# 11. Content

`content` is REQUIRED and non-empty.

It is the canonical normalized textual representation of the source fields
that are useful for retrieval/answering.

Examples may include:

```text
Title
Course/Program Code
Academic Year
Career
Units
Mode of Delivery
Description/Overview
Prerequisites/Requisites
Incompatibilities
Assumed Knowledge
Offerings
Learning Outcomes
```

Only source-supported values may appear.

Do not add placeholder claims for missing fields.

---

# 12. `content_hash`

`content_hash` is REQUIRED.

Schema-v1 rule:

```text
content_hash =
    SHA-256(content encoded as UTF-8)
    represented as a lowercase hexadecimal string
```

Equivalent Python:

```python
hashlib.sha256(content.encode("utf-8")).hexdigest()
```

Expected format:

```regex
^[0-9a-f]{64}$
```

The scraper owns calculation of `content_hash`.

RAG:

- accepts it,
- preserves it,
- does not recalculate it during retrieval,
- and does not use an LLM to generate it.

Change-detection behaviour:

```text
no previous record -> NEW
same record_id + different content_hash -> CHANGED
same record_id + same content_hash -> UNCHANGED
```

`record_id` and `entity_id` do not change merely because source content
changes.

---

# 13. Courses metadata v1

For a course record, these keys are REQUIRED inside `metadata_json`:

| Key | Type | Nullable |
|---|---|---:|
| `entity_type` | string literal `"course"` | no |
| `course_code` | string | no |
| `academic_year` | four-digit string | no |

Schema-v1 currently recognises these optional course metadata keys:

| Key | Type when present | Nullable |
|---|---|---:|
| `career` | string | yes |
| `units` | string | yes |
| `delivery_mode` | string | yes |
| `prerequisites` | string | yes |
| `incompatibilities` | string | yes |
| `assumed_knowledge` | string | yes |
| `offerings` | array of JSON objects | yes |

Representative structure:

```json
{
  "entity_type": "course",
  "course_code": "COMP1100",
  "academic_year": "2026",
  "career": "UGRD",
  "units": "6",
  "delivery_mode": "In Person",
  "prerequisites": null,
  "incompatibilities": "COMP1130",
  "assumed_knowledge": null,
  "offerings": null
}
```

Optional metadata MUST NOT be fabricated.

If the source does not provide an optional value, use `null` for the documented
schema-v1 key.

In particular:

```text
missing prerequisites != "no prerequisites"
missing offerings != "no offerings"
```

An empty list MUST only mean the source was successfully interpreted as
explicitly containing zero items.

It MUST NOT be used as a substitute for unknown/missing evidence.

Additional source-supported course metadata may be added inside `metadata_json`
in later schema versions without adding arbitrary new top-level fields.

---

# 14. Programs metadata v1

For a program record, these keys are REQUIRED inside `metadata_json`:

| Key | Type | Nullable |
|---|---|---:|
| `entity_type` | string literal `"program"` | no |
| `program_code` | string | no |
| `academic_year` | four-digit string | no |

Schema-v1 currently recognises these optional program metadata keys:

| Key | Type when present | Nullable |
|---|---|---:|
| `career` | string | yes |
| `units` | string | yes |
| `duration` | string | yes |
| `delivery_mode` | string | yes |
| `learning_outcomes` | array of strings | yes |

Representative structure:

```json
{
  "entity_type": "program",
  "program_code": "BACCT",
  "academic_year": "2026",
  "career": null,
  "units": null,
  "duration": null,
  "delivery_mode": null,
  "learning_outcomes": null
}
```

Optional metadata follows the same missing-value rule as course metadata.

Unknown/missing source evidence is represented as `null`, never as an invented
answer.

---

# 15. Scholarships metadata v1

Scholarship records use:

```text
domain = "scholarships"
source_id = "scholarships_anu_finder"
entity_id = <canonical ANU scholarship URL slug>
record_id = "scholarships:scholarship:<entity_id>"
```

These keys are required inside `metadata_json`; nullable values remain present
using the types below:

| Key | Type | Nullable |
|---|---|---:|
| `entity_type` | string literal `"scholarship"` | no |
| `featured` | boolean | yes |
| `status` | string | yes |
| `application_required` | boolean | yes |
| `study_stage` | array of strings | no |
| `student_type` | array of strings | no |
| `study_level` | array of strings | no |
| `area_of_study` | array of strings | no |
| `value` | string | yes |
| `selection_basis` | string | yes |
| `opening_date` | ISO calendar date string (`YYYY-MM-DD`) | yes |
| `closing_date` | ISO calendar date string (`YYYY-MM-DD`) | yes |
| `eligibility` | string | yes |

`application_required` is normalized only from explicit source wording:
required -> `true`, automatic/no application required -> `false`, and missing
or ambiguous evidence -> `null`. The parser preserves the original source
wording in canonical `content`.

Scholarship application periods do not define general record validity.
`opening_date` and `closing_date` remain in `metadata_json`, displayed wording
remains in canonical `content`, and top-level `effective_from`/`effective_to`
remain `null` for Scholarships.

The four filter fields are always arrays. Explicit source values become array
members; missing source evidence becomes `[]`. All other missing scholarship
metadata remains `null`. User-specific eligibility reasoning does not belong in
scraper metadata.

---

# 16. Jobs metadata v1

Jobs records use:

```text
domain = "jobs"
source_id = "jobs_anu_search"
entity_id = <numeric public requisition ID as a string>
record_id = "jobs:job:<entity_id>"
metadata_json.job_id = entity_id
```

These exact keys are required inside `metadata_json`; unknown additional keys
are invalid for Jobs v1:

| Key | Type | Nullable |
|---|---|---:|
| `entity_type` | string literal `"job"` | no |
| `job_id` | digits-only string | no |
| `category` | string | yes |
| `employment_types` | array of strings | no |
| `location` | string | yes |
| `classification` | string | yes |
| `salary` | string | yes |
| `closing_text` | string | yes |
| `closing_date` | ISO calendar date string (`YYYY-MM-DD`) | yes |
| `closing_at` | timezone-aware ISO-8601 datetime string | yes |
| `status` | `"current"`, `"closed"`, or null | yes |
| `summary` | string | yes |

Missing scalar evidence is `null`; missing `employment_types` evidence is `[]`.
Employment-type values and salary preserve normalized official source wording.
Salary remains text in v1 and is not converted into numeric ranges. Fixed term
is an employment-type value and never implies that a role is closed.

The scraper maps explicit open/current wording to `current`, explicit
closed/expired wording to `closed`, and otherwise may derive status only from a
safely parsed source closing value. Insufficient evidence remains `null`.

`closing_date` is the Canberra-local calendar date used for deterministic
filtering and sorting. `closing_at` exists only when the source provides an
exact time; a date-only value never invents a time. Top-level `effective_from`
and `effective_to` remain `null` for Jobs v1.

Current Jobs includes only `status == "current"` where `closing_date` is null or
is on/after the current Canberra date. Closed, past-date and null-status records
are excluded. Dated records sort before undated records; dated records sort by
`closing_date` ascending, with numeric `entity_id` ascending as the stable
tie-breaker. Undated records sort by numeric `entity_id` ascending. Filtering
precedes ordering and limiting.

Exact lookup priority is numeric `job_id`/`entity_id`, then exact normalized
title, then general Jobs retrieval. Duplicate titles require disambiguation;
title is not identity.

---

# 17. Accommodation metadata v1

Status: **frozen by Qasim and Carmen on 2026-09-16**. The matching RAG migration
`20260916_0008` is merged and exact serialized-record validation passes.
PostgreSQL/runtime enablement remains blocked pending Qasim's final review.

Accommodation records use:

```text
domain = "accommodation"
source_id = "accommodation_anu_study"
entity_id = <canonical residence URL slug>
record_id = "accommodation:residence:<entity_id>"
```

`metadata_json` contains exactly: `entity_type` (`"residence"`), `category`,
`location`, `catering_options`, `audiences`, `advertised_rate`, `cost_period`,
`rooms`, `features`, `overview`, `accessibility`, `application_text`,
`application_url`, `eligibility`, `contact`, and `vacancy_status`.

`catering_options`, `audiences`, `rooms`, and `features` are arrays. Each room
preserves the source pairing of `name`, `rate`, `contract`, `inclusions`, and
`other_fees`; values remain text. `contact` contains `email`, `phone`,
`location`, and explicitly published `hours`. Missing scalar evidence is null.
Live vacancy is never inferred: `vacancy_status` stays null unless the approved
public residence page explicitly publishes it. A published StarRez application
URL may be retained as an outbound destination but is never fetched.

# 18. Support metadata v1

Status: **frozen by Qasim and Carmen on 2026-09-16**. The matching RAG migration
`20260916_0008` is merged and exact serialized-record validation passes.
PostgreSQL/runtime enablement remains blocked pending Qasim's final review.

Support records use:

```text
domain = "support"
source_id = "support_anusa_student_assistance"
entity_id = <canonical top-level Student Assistance category slug>
record_id = "support:support_service:<entity_id>"
```

`metadata_json` contains exactly: `entity_type` (`"support_service"`),
`category`, `purpose`, `audiences`, `contact`, `hours`, `access`, `cost`,
`topics`, and `referrals`. `contact` contains `email`, `phone`, and `location`.
Hours, access, cost, contact, and referrals are populated only from published
source facts. Missing scalar evidence is null. Source HTML is treated as
untrusted content; executable elements are removed and never enter canonical
content. Topic URLs must stay inside the approved internal ANUSA Student
Assistance topic boundary. Referral URLs must be credential-free external
HTTP(S) destinations; `anusa.com.au` and `www.anusa.com.au` are rejected
case-insensitively. Published valid referrals are never fetched by this
collector.

# 19. Events metadata v1

Status: **implemented locally; shared migration and production write approval
pending Qasim/Carmen**. Official ANU Events has complete source dry-run
evidence. Rubric is approved for bounded ingestion but its exact search
endpoint artifact and live frozen-window denominator remain blockers.

Events records use:

```text
domain = "events"
source_id = "events_anu_official"
entity_id = <numeric Drupal node ID>
record_id = "events:event:<entity_id>"
```

Rubric community-event records use:

```text
domain = "events"
source_id = "rubric_unified_search"
entity_id = "rubric-<numeric Rubric event ID>"
record_id = "events:event:rubric-<numeric Rubric event ID>"
```

The canonical URL is an exact credential-free, query-free and fragment-free
`https://www.anu.edu.au/events/<slug>` URL. The article
`data-history-node-id` and page metadata `entityId` must both exist and agree.
The Rubric canonical URL is exactly
`https://campus.hellorubric.com/?eid=<numeric event ID>`.

`metadata_json` contains exactly: `entity_type` (`"event"`),
`source_event_id`, `start_at`, `end_at`, `timezone`, `organiser_name`,
`venue_name`, `address`, `latitude`, `longitude`, `category`, `tags`,
`registration_url`, `source_status`, `cancellation_status`, and `audience`.
The producer maps a raw source location only to `venue_name`; it leaves
`address`, `latitude`, and `longitude` null unless separately explicit. Exactly
one source category maps to `category`; zero or multiple categories map to
null, with every category retained in common record content. Exactly one
credential-free HTTP(S) registration destination maps to `registration_url`;
zero or multiple destinations map to null, with their labels and URLs retained
in content. Registration destinations are never fetched. `end_at` and
top-level `effective_to` may remain null when Rubric publishes a start but no
end. No end time is inferred.

Displayed HTML is authoritative for dates and times. Exact times use
`Australia/Canberra`, including daylight-saving transitions, and mirror into
top-level `effective_from` and `effective_to`. The current bounded census has
no date-only official records. Because this shared metadata contract contains
no date-only boundary fields, any future date-only official record blocks the
run before persistence for contract review rather than receiving invented
times. Multiple explicitly displayed occurrences use the earliest published
start and latest published end. Explicit cancellation maps only to
`cancellation_status = "cancelled"`; exact cancellation wording stays in
content, and `source_status` remains separate. Description and explicit
official format also remain in content rather than structured metadata.
Contact people are not inferred to be organisers, and format is not inferred
from location.

The release snapshot is Canberra-local 2026-09-19 through 2026-10-31
inclusive, evaluated by interval overlap. Its recomputed frozen denominator is
30 for the official source only. Rubric requires a separately reconciled live
denominator; the observed all-search count of 119 is not that denominator. The
official source `.ics` time disagreement observed on 2026-09-18 is recorded as
an anomaly; ICS values do not populate normalized times.

`source_id` is the authoritative provenance/classification field. Rubric being
an approved ingestion source does not make a Rubric society event an official
ANU event. Dedicated Upcoming Events retrieval filters to
`events_anu_official`; conversational Events retrieval may use both stored
sources. Rubric `eventStatus`, `ticketsPossiblyAvailable`, ticket-sale windows
and event end times are not interchangeable and must not be overinterpreted.

# 20. Missing/null value policy

Global rule:

```text
No source evidence -> no invented value.
```

For documented optional scalar/list metadata:

```text
missing / unknown -> null
```

Do not convert missing evidence into:

```text
"None"
"N/A"
"Unknown"
"Not applicable"
[]
{}
false
0
```

unless the source explicitly supports that value or the field's semantics
explicitly define it.

Scholarship filter arrays are the explicit exception: missing `study_stage`,
`student_type`, `study_level` or `area_of_study` evidence is represented by
`[]` under the approved Scholarships v1 contract.

Jobs `employment_types` is also always an array; missing evidence is `[]` under
the approved Jobs v1 contract.

Events `tags` is always an array; missing source evidence is `[]` under the
Events v1 contract. Singular `category` and `registration_url` are null when
the source publishes zero or multiple values; all source-backed values remain
available in common record content.

Required identity fields must not be silently replaced with placeholders.

If required identity cannot be established, the scraper must reject/flag the
record rather than publish a misleading normalized record.

---

# 21. Datetimes and timezone

Serialized datetimes MUST be timezone-aware ISO-8601 values.

Operational source collection uses:

```text
Australia/Canberra
```

`collected_at` and `last_seen_at` are required.

Lifecycle timestamp semantics are fixed across supported collectors:

- `NEW` sets both `collected_at` and `last_seen_at`;
- `CHANGED` preserves `collected_at` and advances `last_seen_at`; and
- `UNCHANGED` preserves `collected_at` and advances `last_seen_at`.

`effective_from` and `effective_to` remain nullable because many course/program
pages do not provide source-supported effective dates.

---

# 22. Representative normalized course identity

The verified live COMP1100 collection has this identity:

```text
domain        = courses
source_id     = courses_programs_and_courses
entity_id     = COMP1100_2026
record_id     = courses:course:COMP1100_2026
title         = Programming as Problem Solving
academic_year = 2026
course_code   = COMP1100
career        = UGRD
units         = 6
delivery_mode = In Person
```

The canonical URL is the URL stored from the official ANU Programs & Courses
source.

The exact `content_hash`, timestamps and optional metadata depend on the
normalized record instance and MUST NOT be invented in documentation.

---

# 23. Source registry

Source registry fields remain:

```text
source_id
canonical_root
domain
authority_rank
poll_cadence
parser_name
approval_status
active
notes
```

Rules:

- only approved/active production sources may be collected,
- bounded unsupported sources retain explicit risk classification,
- Rubric uses `APPROVED_BOUNDED_UNSUPPORTED` based on Qasim's permission handoff,
- source approval never bypasses migration/write/deployment release gates, and
- unsupported Rubric endpoints are ingestion-only and never called by RAG requests.

---

# 24. Ingestion run

Ingestion-run fields remain:

```text
run_id
source_id
started_at
completed_at
records_seen
records_added
records_changed
records_unchanged
records_missing
status
error
```

Allowed ingestion-run status values:

```text
RUNNING
SUCCESS
FAILED
SUSPICIOUS_ZERO
```

On fetch/parser failure:

```text
FAILED
preserve last-known-good data
```

On suspicious many-to-zero:

```text
SUSPICIOUS_ZERO
do not wipe current data
```

---

# 25. First DB / migration ownership

For the first Courses/Programs vertical slice:

**Carmen — RAG/backend**

- owns the RAG-side DB model/data-access implementation,
- owns the first migration code required by RAG retrieval,
- owns deterministic course/program read/query behaviour.

**Will — Scraper/data**

- owns normalized record production,
- owns scraper-side write/handoff integration against this contract,
- does not independently redefine shared field semantics.

**Qasim — PM/integration/contracts/GCP**

- owns cross-repo schema approval,
- coordinates the scraper -> DB -> RAG integration,
- coordinates Cloud SQL/GCP provisioning,
- reviews shared migration/contract changes,
- ensures affected contract documents remain synchronized.

No shared schema change should be made independently in one repo without
coordinating the affected repo(s).

---

# 26. RAG implementation boundary

The RAG repository MUST NOT copy scraper implementation such as:

```text
HTML parsers
HTTP fetchers
source registry implementation
LocalDataStore
scraper ingestion-run implementation
scraper change-detection implementation
```

RAG owns:

```text
its own validated record model
fixture loader
DB/data-access repository
exact/deterministic retrieval
planner/retrieval behaviour
```

The RAG record model may use strict validation (`extra="forbid"`) against the
schema-v1 top-level fields.

`metadata_json` remains the controlled domain-specific extension object.

---

# 27. Day 2 exact-retrieval expectations

For Courses/Programs exact retrieval:

- normalize course/program code deterministically,
- retrieve using entity type + code + academic year,
- support multiple academic years without collisions,
- do not infer missing year inside the repository,
- preserve the complete normalized record,
- preserve `canonical_url`,
- preserve `content_hash`,
- tolerate null optional metadata,
- return no-evidence behaviour for unknown codes,
- never invent missing course/program facts.

The exact-retrieval layer does not require Gemini or vector search.

---

# 28. Change workflow

Any future change to:

- common field names,
- top-level types,
- top-level nullability,
- ID formats,
- `content_hash` semantics,
- canonical URL semantics,
- academic-year semantics,
- required domain metadata,
- or DB ownership

is a shared contract change.

Such changes must:

1. be recorded in `docs/DECISION_LOG.md`,
2. be synchronized across affected repos,
3. be reviewed before dependent implementations silently diverge.
