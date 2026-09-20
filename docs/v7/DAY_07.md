# AskANU V7 — Day 7: Cross-domain torture + integration

**Date:** 2026-09-27  
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

Support torture testing with frozen fixtures and investigate only evidence/data-rooted failures.

## Start / stop contract

**Start from:** latest reviewed main + all prior-day accepted contracts/evidence. On Day 8, use the Day 7 frozen RC manifest rather than arbitrary newer main.

**STOP and escalate** if the work requires silently changing shared API/schema/source authority, moving institutional reasoning to the wrong repo, or violating a frozen invariant.

## Work map

- 0–2h — Confirm failing cases are or are not caused by missing/incorrect normalized evidence.
- 2–4h — Run identity/collision/provenance/temporal regression across six domains.
- 4–6h — Verify representative source records for failing comparisons/filters.
- 6–8h — Do not mutate production to make tests green.
- 8–10h — Provide exact data limitation classification.
- 10–12h — Freeze scraper changes except release-critical fixes.

## Acceptance / do-not-cross lines

- Do not manufacture facts for acceptance.
- No broad crawl unless explicitly authorized.
- No schema churn.

## Evidence to hand off

PR/SHA if changed; capability/field matrix; representative fixtures; parser/registry tests; source limitations; no unauthorized production mutation.

## Copy-paste AI kickoff prompt

You are Will working on AskANU V7 in the Scraper/data lane. Start from latest reviewed main and the frozen V7 behavioural contract. Implement only Day 7's scope through shared primitives. Do not invent unsupported institutional facts, silent source/schema/API changes, domain-specific state engines, or magic-wording shortcuts. Show planned files, behavioural impact, tests, risks and dependencies before implementation. Finish with exact evidence that Qasim can review against today's gate.

---

## Cross-repo handoff rule

If today's work exposes a requirement owned by another repository, record the exact contract/evidence gap and hand it to Qasim. Do not silently implement the other repository's responsibility here.
