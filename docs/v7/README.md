# AskANU V7 — askanu-scraper Execution Plan

**Execution window:** 21–28 September 2026  
**Primary lane:** Scraper / approved-source data / normalization  
**Source of truth:** frozen AskANU V7 master execution plan.

## How to use this folder

Open the current day's file before starting work. The day is complete only when the required acceptance evidence exists; code alone is not completion.

Each day file contains only the work this repository/owner needs, plus cross-repo dependencies and gates necessary to avoid implementing another repository's responsibilities.

## Frozen repo boundaries

- Own approved-source collection, stable identity, normalization, source-backed aliases, temporal/source metadata, fixtures, and data-health evidence.
- Do not implement conversational state, ranking/reasoning, or frontend behaviour.
- Never invent fields or normalize uncertain prose into false deterministic facts.
- Rubric remains ingestion-only; no frontend/RAG live Rubric dependency.
- Production writes/crawls remain explicitly gated by Qasim.
- Day 8 performs only bounded, explicitly authorized production data actions.

## Shared V7 invariants

- AskANU should feel like talking to an ANU-aware assistant, not searching an ANU database.
- Never make the student learn how to prompt AskANU.
- Understand → Remember → Retrieve → Reason → Communicate.
- Session state is structured and bounded; conversation history alone is not state.
- DOMAIN, ENTITY, INTENT, and CONSTRAINTS are separate.
- Answer epistemic state is CONFIRMED / DERIVED / PARTIAL / UNKNOWN.
- ResultSet state is RESULTS / EMPTY / INCOMPLETE; UNKNOWN must never be converted into NO_MATCH.
- Hard constraints are never silently ignored.
- Missing evidence remains unknown rather than false.
- Every V7=YES intent must pass at least five materially different formulations.
- Feature expansion stops at the end of Day 6. Day 7 is torture/integration; Day 8 is release.
- Engineering readiness and experience readiness are reported separately.

## Files

- `DAY_01.md` … `DAY_08.md` — repo-specific daily execution briefs.
- `FINAL_RELEASE_ACCEPTANCE.md` — shared release gate relevant to all repos.
