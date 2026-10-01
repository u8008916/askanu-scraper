# V7 Day 7 — six-domain producer-consumer release audit

Owner: Will  
Lane: scraper/data  
Verified: 2026-09-30 (Australia/Sydney)

## Outcome

The Day 7 scraper packet was replayed cleanly onto audited Day 6 and inspected
against Carmen’s exact current RAG RC
`e88a0d7e6bde2f6135ef152dc1b90d211a56a83e` (parent
`971e837c141908a147a4bf5a0bdedb5f0dccb730`). The six-domain producer-consumer
result is **FAIL**. Accommodation and Support align; Courses, Scholarships,
Jobs, and Events retain exact release-blocking mismatches listed below.

No producer field, source value, canonical content, hash, retrieval unit,
source scope, database, index, or production environment was changed to make a
consumer test pass.

## Restack proof

- Old Day 7 head: `2714bccdf0c319dddeaa58db2e0111938244c2ee`
- Old parent: `e9c6ce2817f12d190a07dbe85a297bab6e4c6deb`
- New parent: `8bbe5c13ca406a745f12a0af71a966f79757f8b4`
- Pure replay: `c65814549059a22d86fb07ca69eb7ad361974810`
- Conflicts: **0**
- Manual resolutions: **0**
- Stable Day 7 patch ID before/after: identical,
  `63f4d94642fd41b4c53d5ca35d1f875e45a0e638`

The old and replay trees differ only through the finalized Day 5 ledger and
audited Day 6 packet inherited from the new parent. The genuine Day 7 delta is
byte-equivalent.

## Six-domain result

| Domain | Contract | Identity/provenance | Missing-field semantics | Source-health semantics |
|---|---|---|---|---|
| Courses | FAIL | FAIL | FAIL | PASS |
| Scholarships | FAIL | PASS | FAIL | FAIL |
| Accommodation | PASS | PASS | PASS | PASS |
| Jobs | FAIL | PASS for known records | FAIL | PASS with `INCOMPLETE_POPULATION` caveat |
| Events | FAIL | PASS | PASS | FAIL |
| Support | PASS | PASS | PASS | PASS |

Source health remains truthful: Courses, Accommodation, and Support are
`GREEN`; Scholarships is `BLOCKED` by the external-canonical redirect; Jobs is
`FALLBACK_LAST_KNOWN_GOOD` and `INCOMPLETE_POPULATION`; Events is `BLOCKED` by
the official 30-versus-29 reconciliation and Rubric request-contract/live-
denominator gates.

## Unresolved mismatch ledger

1. Course URL path case — **CONSUMER FIX REQUIRED**. The source-preserved
   `/COMP2120` path is rejected by a lowercase-only RAG validator.
2. Course Description — **CONSUMER FIX REQUIRED**. RAG labels the whole
   canonical record as Description when no structured producer field exists.
3. Course Corequisites — **CONSUMER FIX REQUIRED**. RAG reads a non-contract
   metadata field and reports real content-only evidence as not published.
4. Scholarship status — **CONSUMER FIX REQUIRED**. RAG expects synthetic
   `open`/`closed`, while the producer preserves `Open for applications` and
   `Application closed`.
5. Scholarship study level — **CONSUMER FIX REQUIRED**. The RC normalizes only
   exact `undergraduate` or `bachelor`, not the producer value
   `Undergraduate/Bachelor`.
6. Jobs `role_requirements` — **SHARED CONTRACT DECISION REQUIRED**. RAG
   requires a v2 key and tests populated values; scraper Jobs v1 rejects that
   extra key and the latest audit found no source evidence in 7 records.
7. Jobs remote/work arrangement — **CONSUMER FIX REQUIRED**. No producer field
   exists. The RC must report that it cannot reliably apply the filter, not
   treat `remote` as an employment type with a genuine evaluated zero.
8. Jobs location applicability — **CONSUMER FIX REQUIRED**. Location is a
   valid optional field and Canberra exists in a representative captured
   fixture, but the latest partial audit found it source-present for 0/7.
   Population-wide hard filtering is therefore not reliable.
9. Events population completeness — **CONSUMER FIX REQUIRED**. RAG still marks
   Event discovery ResultSets population-complete while both source gates are
   open.
10. Jobs classification shorthand — **CONSUMER FIX REQUIRED**. The producer
    value is shaped like `ANU Officer 8 (Administration)` and does not produce
    `ANU08`; the RC’s exact comparison does not map the shorthand to that real
    value.

Carmen’s R6-B fix correctly stops `at ANU in Canberra` from becoming
`anu in canberra`, and R6-C correctly stops ordinary words such as `any` and
`about` becoming employment types. Those interpretation fixes pass, but they
do not resolve producer capability: location is not reliably populated and
remote/work arrangement is unsupported.

## Jobs source-backed value audit

- Canberra: source-backed in the representative captured record, but not
  reliable across the latest population evidence.
- Fixed Term: source-backed and stored as source wording.
- Casual and Full-time: not established by the committed source-capture
  evidence. Casual appears only in a fixture explicitly labelled synthetic.
- Classification: source-backed example is `ANU Officer 8 (Administration)`;
  no `ANU08` alias is produced.
- Remote/work arrangement: no producer field and no normalization.

Employment type, category, and classification were each source-present for 7/7
successfully audited records before the Jobs source failure. A zero result for
an exact source-backed value may mean “no supported matching result” only while
retaining the incomplete-population caveat. Location, remote/work arrangement,
and unverified aliases must instead use “cannot reliably apply/verify.”

## Producer fields materially unconsumed

- `content.Corequisites`
- `metadata_json.registration_url`
- `metadata_json.latitude`
- `metadata_json.longitude`

`content.Description` is not listed as unconsumed because RAG does project a
value, but it projects the wrong boundary (the whole canonical record), which
is already recorded as a semantic defect.

## Safety and impact

- Canonical data mutation: **NONE**
- Content-hash changes: **0**
- Retrieval-unit changes: **0**
- Reindex/re-embedding required: **NO**
- Crawls, DB writes, migrations, backfills, secret/IAM changes: **0**
- Merge state: **MERGE HOLD / DAY 8 HOLD**

Status: **SCRAPER DATA RC AUDITED; PRODUCER-CONSUMER ALIGNMENT FAIL; MERGE HOLD**.
