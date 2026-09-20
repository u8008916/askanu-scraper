# AskANU V7 — Day 5: Complete Courses + Scholarships

**Date:** 2026-09-25  
**Repository:** `askanu-scraper`  
**Primary owner:** Will  

> **Completion rule:** Today is done only when the acceptance evidence exists — code alone is not completion.

## Repo boundary for today

- Own approved-source collection, stable identity, normalization, source-backed aliases, temporal/source metadata, fixtures, and data-health evidence.
- Do not implement conversational state, ranking/reasoning, or frontend behaviour.
- Never invent fields or normalize uncertain prose into false deterministic facts.
- Rubric remains ingestion-only; no frontend/RAG live Rubric dependency.
- Production writes/crawls remain explicitly gated by Qasim.
- Day 8 performs only bounded, explicitly authorized production data actions.

## Primary outcome

Verify course facts and scholarship matching/filter fields are source-backed.

## Start / stop contract

**Start from:** latest reviewed main + all prior-day accepted contracts/evidence. On Day 8, use the Day 7 frozen RC manifest rather than arbitrary newer main.

**STOP and escalate** if the work requires silently changing shared API/schema/source authority, moving institutional reasoning to the wrong repo, or violating a frozen invariant.

## Work map

- 0–2h — Map course code/title/prerequisites/units/offering facts and content-only boundaries.
- 2–4h — Map scholarship audience, degree/status/deadline/open-state/criteria fields: deterministic vs content-only.
- 4–6h — Create eligibility/missing-info fixtures and deadline boundary cases.
- 6–8h — Provide alias fixtures for course titles/codes and scholarship names.
- 8–10h — Run parser/identity/provenance regressions.
- 10–12h — Document unsupported matching dimensions.

## Acceptance / do-not-cross lines

- Do not invent eligibility from incomplete criteria.
- Do not turn prose-only criteria into false deterministic filters.
- No source widening to patch product gaps.

## Evidence to hand off

PR/SHA if changed; capability/field matrix; representative fixtures; parser/registry tests; source limitations; no unauthorized production mutation.

## Copy-paste AI kickoff prompt

You are Will working on AskANU V7 in the Scraper/data lane. Start from latest reviewed main and the frozen V7 behavioural contract. Implement only Day 5's scope through shared primitives. Do not invent unsupported institutional facts, silent source/schema/API changes, domain-specific state engines, or magic-wording shortcuts. Show planned files, behavioural impact, tests, risks and dependencies before implementation. Finish with exact evidence that Qasim can review against today's gate.

---

## Cross-repo handoff rule

If today's work exposes a requirement owned by another repository, record the exact contract/evidence gap and hand it to Qasim. Do not silently implement the other repository's responsibility here.
