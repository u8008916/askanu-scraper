# AskANU V7 — Day 8: Production release + post-deploy acceptance

**Date:** 2026-09-28  
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

Perform only explicitly authorized release data actions and verify post-release source health.

## Start / stop contract

**Start from:** latest reviewed main + all prior-day accepted contracts/evidence. On Day 8, use the Day 7 frozen RC manifest rather than arbitrary newer main.

**STOP and escalate** if the work requires silently changing shared API/schema/source authority, moving institutional reasoning to the wrong repo, or violating a frozen invariant.

## Work map

- 0–2h — Confirm approved producer changes and gates.
- 2–4h — Run only bounded authorized ingestion/write steps if required.
- 4–6h — Verify DB/source identity/provenance/temporal health.
- 6–8h — Prove idempotency/LKG where release path requires it.
- 8–10h — Do not alter Scheduler unless explicitly required.
- 10–12h — Publish six-domain source-health snapshot.

## Acceptance / do-not-cross lines

- No broad surprise production write.
- Rubric/live census only if its separate gate has been satisfied.
- Preserve LKG/failure safety.

## Evidence to hand off

PR/SHA if changed; capability/field matrix; representative fixtures; parser/registry tests; source limitations; exact authorized production-action evidence.

## Copy-paste AI kickoff prompt

You are Will working on AskANU V7 in the Scraper/data lane. Start from latest reviewed main and the frozen V7 behavioural contract. Implement only Day 8's scope through shared primitives. Do not invent unsupported institutional facts, silent source/schema/API changes, domain-specific state engines, or magic-wording shortcuts. Show planned files, behavioural impact, tests, risks and dependencies before implementation. Finish with exact evidence that Qasim can review against today's gate.

---

## Cross-repo handoff rule

If today's work exposes a requirement owned by another repository, record the exact contract/evidence gap and hand it to Qasim. Do not silently implement the other repository's responsibility here.
