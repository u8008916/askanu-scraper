# Day 14 V6 pre-demo source health and provenance handoff

Captured 18 September 2026 (Australia/Sydney). This is read-only source and
demo-support evidence, **not a production data lock**. No production write,
Cloud Run execution, deployment, Scheduler change, schema change, registry
change, Rubric request or StarRez request was made.

Repository baseline: `bdf7a0f1e4a05a18deadcc0dc14eef74c4389ffb` on
`main`. The full suite passed **315 tests** and the focused Day 13 recovery
matrix passed **17 tests**. The pre-existing untracked
`detail-coverage-evidence.json` remained unchanged at SHA-256
`d711219fc96aa6b8152048bd582a99fe3840ec4c62583f10ab8c1b0aca353cdd`;
it is stale and is not cited as current coverage evidence.

**Release recommendation: `GO WITH CARRY-OVER`, not a six-domain data PASS.**
Five domains have current source-health or explicit last-known-good evidence.
Events has no runnable collector, denominator, representative record or run ID
in this repository. Qasim must accept the explicit unavailable/no-evidence
Events fallback or supply independently verified Events evidence before calling
the demo a six-domain PASS.

## Pre-demo decision

| Domain | Status | Current evidence | Demo action |
|---|---|---|---|
| Courses | `GREEN` | Full census exactly matches 500 Courses, 393 Programs, 109 Majors, 126 Minors and 128 Specialisations; bounded dry-run and live COMP1100 provenance passed | Use the current candidate/source evidence; do not re-claim full-detail field coverage |
| Scholarships | `GREEN` | 405 raw cards reconcile to 379 approved records after rejecting 26 external scholarships; representative detail passed | Keep the frozen approved denominator at 379 |
| Jobs | `FALLBACK_LAST_KNOWN_GOOD` | Full census reconciled 57 unique current roles and the first bounded dry-run passed, but a later listing recheck returned an empty body after retries | Stop retries and writes; use last-known-good and disclose the transient source failure |
| Accommodation | `GREEN` | Listing remains exactly 19; representative Yukeembruk record passed | Freeze |
| Support | `GREEN` | Listing remains exactly 6; representative Academic Support record passed | Freeze |
| Events | `BLOCKED` | No official-source collector, frozen count, record or run ID exists; Rubric remains inactive | Demo only an explicit unavailable/no-evidence state unless Qasim supplies verified external evidence |

The Jobs sequence is intentionally conservative. The prior snapshots of 55,
50 and today's 57 are timestamped source states, not deletion or missing-record
instructions. The successful census does not override the later failure, and
the failure must not wipe current data.

### Known-good run and count sheet

| Domain | Day 13 run | Day 14 run | Count/source state | Persistence claim |
|---|---|---|---|---|
| Courses | `run_dc7a12ea9431` | `run_f345711ef53a` | 500 Courses, 393 Programs, 109 Majors, 126 Minors, 128 Specialisations | Local dry-run only |
| Scholarships | `run_417fa17bae54` | `run_fcfe35ce8de4` | 379 approved from 405 raw cards; 26 external rejected | Local dry-run only |
| Jobs | `run_d90a630b31d1` | `run_af705fde6d83` | Successful census: 57; later recheck failed | Last-known-good/local dry-run only |
| Accommodation | `run_51d1c7f07088` | `run_3c98637bf635` | 19/19 | Local dry-run only |
| Support | `run_98201f5aaaf6` | `run_09ffd0a1b6f3` | 6/6 | Local dry-run only |
| Events | none | none | Unavailable; no collector record exists | None; no data fabricated |

## Provenance pack

| Domain | Representative record | Canonical URL | Day 14 hash state |
|---|---|---|---|
| Courses | `courses:course:COMP1100_2026` | `https://programsandcourses.anu.edu.au/2026/course/comp1100` | Live hash captured |
| Scholarships | `scholarships:scholarship:anu-international-achievement-award` | `https://study.anu.edu.au/scholarships/find-scholarship/anu-international-achievement-award` | Live hash captured |
| Jobs | `jobs:job:563693` | `https://jobs.anu.edu.au/jobs/senior-consultant-user-experience-hr-systems-projects-canberra-act-act-australia` | Day 13 last-known-good only; no fresh representative hash claimed |
| Accommodation | `accommodation:residence:yukeembruk` | `https://study.anu.edu.au/accommodation/our-residences/yukeembruk` | Live hash captured and unchanged from Day 13 |
| Support | `support:support_service:academic` | `https://anusa.com.au/student-assistance/academic/` | Live hash captured and unchanged from Day 13 |

Exact content hashes, local dry-run IDs, request counts and census results are
in `day14-evidence.json`. Every listed local run is non-persistent. In
particular, `records_added` in a dry-run is a comparison result and not a
database insert.

The exact frozen Qasim/Carmen demo-question list and RAG repository were not
available in this workspace. The source-side rehearsal candidates are COMP1100,
ANU International Achievement Award, Jobs last-known-good/unavailable handling,
Yukeembruk, ANUSA Academic Support, and explicit Events no-evidence behavior.
Qasim/Carmen must map their actual frozen questions to these record IDs or send
the missing IDs before claiming rehearsal PASS.

## Technical explanation notes

- **Approved sources:** every collector is constrained to an active registry
  entry and canonical boundary. Rubric is inactive; StarRez is link-only.
- **Stable IDs:** `record_id` and `entity_id` identify a logical source entity
  and remain stable when source wording changes.
- **`content_hash`:** SHA-256 of canonical normalized content. Same ID and hash
  is `UNCHANGED`; same ID with a new hash is `CHANGED`.
- **Idempotency:** an identical rerun updates freshness state without creating a
  duplicate or requesting unnecessary re-embedding.
- **Last-known-good:** fetch, parse, validation and suspicious-zero failures are
  recorded but cannot replace or delete the current approved records.

## Cloud and recovery margin

The existing `askanu-scraper` Cloud Run Job is Ready at generation 20. Its
current immutable image digest is
`sha256:0b4b2da3ad6977b7b1aef556460e668e6ac637fb53f0eba7dd1df5d91169f8b5`,
the runtime identity remains the dedicated scraper service account, and the
current job configuration selects PostgreSQL with `SCRAPER_DRY_RUN=true`, one
Course, one Program, zero task retries and a 600-second task timeout.

The latest execution is `askanu-scraper-d2m8q`, created by the Scheduler caller
at `2026-09-17T17:15:03.477523Z` (03:15 Canberra on 18 September), and it
succeeded. Of the ten most recent listed executions, nine succeeded and the
older `askanu-scraper-ptbpx` failed. Recent history also contains manual
non-dry-run executions, but their durable rows were not inspected here. Day 14
triggered no execution.

Scheduler description still returns `PERMISSION_DENIED`. The current persisted
`source_records` and `ingestion_runs` were not read, so Qasim must provide those
read-only counts and durable run IDs. Cloud execution IDs, local dry-run IDs
and persisted ingestion IDs must remain explicitly distinguished.
The principal also lacks `run.jobs.list`, so separate domain or Events jobs
cannot be inventoried from this session.

## Incident notes

`DAY14-JOBS-TRANSIENT-EMPTY` is an open P1 carry-over: after a successful
57-role census and bounded dry-run, the final Jobs listing recheck returned an
empty body after retries. Containment was to stop, perform no write or deletion,
and use last-known-good during the demo.

`DAY14-EVENTS-NO-SNAPSHOT` is a P1 demo/release blocker unless Qasim accepts the
explicit unavailable fallback. No official-source Events record or run exists,
and no Rubric data was substituted.

## Presentation freeze and feedback triage

During the presentation window, do not change the source registry, parsers,
schema, image, job configuration, Scheduler or Rubric state. Only a reproduced
P0 safety defect or materially incorrect demo fact may break the freeze; such a
fix needs an approved source example, minimal sanitized fixture, focused test,
full suite and last-known-good proof.

No presentation feedback item was supplied during this capture. For each new
item record the domain, expected and actual behavior, approved canonical source
URL, observation timestamp, reproduction, severity, owner and next action.
Classify it as source-absent, stale storage, parser defect or new/unapproved
source before accepting work. Never infer a missing fact or manually patch the
database.

## Saturday Events handoff

The official ANU Events/calendar remains the release-safe source. Day 15 must
freeze the exact target URL, pagination, release window, stable identity,
cancellation/update behavior, required field denominator and safe request
bounds before collection. A current-Canberra-date through 42-day window remains
the recommended starting proposal unless the approved source has a better
natural boundary.

Rubric remains `PENDING_APPROVAL`, inactive and non-production. It was not
requested or accessed. StarRez remains link-only and was not fetched.
