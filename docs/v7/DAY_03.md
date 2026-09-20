# AskANU V7 — Day 3: Build retrieval + reasoning

**Date:** 2026-09-23  
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

Close only data-shape gaps required for trustworthy filtering/comparison/temporal discovery.

## Start / stop contract

**Start from:** latest reviewed main + all prior-day accepted contracts/evidence. On Day 8, use the Day 7 frozen RC manifest rather than arbitrary newer main.

**STOP and escalate** if the work requires silently changing shared API/schema/source authority, moving institutional reasoning to the wrong repo, or violating a frozen invariant.

## Work map

- 0–2h — Mark deterministic filter fields vs content-only evidence in each domain.
- 2–4h — Normalize only source-backed fields required by planner.
- 4–6h — Create comparison fixtures with asymmetric missing fields.
- 6–8h — Create Jobs/Events/Scholarship temporal boundary and missing-date fixtures.
- 8–10h — Preserve plural/nuanced facts in content where deterministic collapse would lose meaning.
- 10–12h — Run parser/registry/schema regressions and hand off deterministic corpus.

## Acceptance / do-not-cross lines

- Null = not established, not false.
- No invented values to satisfy a filter.
- No official-vs-Rubric regression.
- No source broadening.

## Evidence to hand off

PR/SHA if changed; capability/field matrix; representative fixtures; parser/registry tests; source limitations; no unauthorized production mutation.

## Copy-paste AI kickoff prompt

You are Will working on AskANU V7 in the Scraper/data lane. Start from latest reviewed main and the frozen V7 behavioural contract. Implement only Day 3's scope through shared primitives. Do not invent unsupported institutional facts, silent source/schema/API changes, domain-specific state engines, or magic-wording shortcuts. Show planned files, behavioural impact, tests, risks and dependencies before implementation. Finish with exact evidence that Qasim can review against today's gate.

---

## Cross-repo handoff rule

If today's work exposes a requirement owned by another repository, record the exact contract/evidence gap and hand it to Qasim. Do not silently implement the other repository's responsibility here.
