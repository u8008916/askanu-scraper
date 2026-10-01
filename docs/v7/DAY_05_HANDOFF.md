# V7 Day 5 — Courses and Scholarships cross-repository checkpoint

Owner: Will
Lane: scraper/data
Verified: 2026-09-29 (Australia/Sydney)

## Outcome

The producer checkpoint remains sound, but the real cross-repository gate
against Carmen RAG Day 5 `75c017ba7db3551e74a4326afd514bd26d898573`
**FAILS**. The audit found one consumer shape defect and four consumer semantic
defects. No scraper feature, parser, schema, source, canonical content,
persistence path, or production data was changed to compensate for them.

The scraper D5 evidence commit was first replayed conflict-free onto squash-
merged Day 4 `79f939a7dfbd36e7321d4b20e31b3255eb9d6c46`. That pure replay had the
same tree as old D5 `9e50fa0996d1110524da678675f97e1ff8a4378c`.
This handoff and its existing evidence/test artifact were then updated with the
actual consumer result.

## Courses

- The 2026 read-only source audit accounts for 500 Course records and 1,256
  records across the supported Course-family entity classes, with zero
  unexplained loss.
- The 500-Course identity manifest has no duplicate record IDs, entity IDs,
  canonical URLs, or Course codes.
- Academic year remains part of canonical identity. A 2025 and 2026 version of
  the same Course code are not collapsed.
- COMP2120 preserves `successfully completed or be currently studying
  COMP2100` and incompatibilities `COMP2130, COMP6120 and COMP6311`.
- Description, learning outcomes, and corequisites remain content-only under
  the frozen producer contract. Personal eligibility, guaranteed enrolment,
  and structured teaching staff remain unsupported.

The exact producer COMP2120 record does not validate in Carmen's consumer
because its source-preserved canonical URL ends in `/COMP2120` and the consumer
requires the path to be lowercased. After changing only that URL in a disposable
diagnostic object, the prerequisite and incompatibility values pass exactly.
The shared contract forbids lowercasing source URL paths, so COMP2120 is **FAIL**
at this gate and the fix belongs in RAG.

The consumer also labels the entire canonical Course content as `Description`
when the producer's content-only description has no metadata field, and it
looks for content-only corequisites in a non-contract metadata field. The latter
causes published producer evidence to be reported as `not_published`.

## Scholarships

The producer exposes source-backed structured fields for status, application
requirement, study stage, student type, study level, area of study, value,
selection basis, opening date, closing date, and eligibility wording.
Description and application-period/source wording remain content-only.

The four filter dimensions are arrays by contract. An empty array means that
the approved source did not establish the dimension; it is not a universal
match. Missing dates remain null and are not converted to closed, zero, or an
invented timestamp. Matching published dimensions establish candidate
relevance, not personal eligibility or award probability.

The personal-eligibility boundary passes: the consumer says that it cannot
determine personal eligibility and does not turn missing criteria into
ineligibility. Missing award value also remains missing rather than `$0`.

Two filtering semantics do not align with the producer. The consumer's status
filter expects synthetic `open`/`closed` values, but the producer preserves the
exact approved wording `Open for applications`/`Application closed`. Its study-
level aliases also fail to apply a Bachelor/undergraduate constraint to the
producer value `Undergraduate/Bachelor`, silently dropping that dimension.

## Cross-repository result

- Course paths checked: **17**
- Scholarship paths checked: **21**
- Structured matches: **31**
- Content-only approved matches: **2**
- Shape mismatches: **1**
- Semantic mismatches: **4**
- Material producer paths unconsumed: **1** (`content.Corequisites`)
- Consumer claims without producer evidence: **0**
- Identity/provenance: **FAIL**
- Course year identity: **PASS**
- COMP2120: **FAIL** (consumer URL-shape rejection; prerequisite and incompatibility wording otherwise exact)
- Scholarship missing-date semantics: **PASS**
- Scholarship eligibility boundary: **PASS**

## Change and cost impact

- Canonical retrieval content changed: **NO**
- Content hashes changed: **0**
- Retrieval units changed: **0**
- Reindex required: **NO**
- Re-embedding required: **NO**
- Production mutation: **NO**
- Production backfill initiated: **NO**
- Production writes, migrations, or crawls: **0**

## External acceptance gate

Carmen must correct or formally reconcile the five consumer mismatches above
against the frozen producer contract, then the exact replacement RAG SHA must
be re-audited. No scraper workaround, synthetic status rewrite, URL
lowercasing, or metadata expansion is approved.

Status: **D5 PRODUCER DATA/EVIDENCE READY; CROSS-REPO ACCEPTANCE FAIL; MERGE HOLD**.
