# AskANU V7 — Day 6: Complete Jobs + Events + Support; feature freeze

**Date:** 2026-09-26  
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

Provide final trustworthy data fixtures/normalization for Jobs, Events, and Support.

## Start / stop contract

**Start from:** latest reviewed main + all prior-day accepted contracts/evidence. On Day 8, use the Day 7 frozen RC manifest rather than arbitrary newer main.

**STOP and escalate** if the work requires silently changing shared API/schema/source authority, moving institutional reasoning to the wrong repo, or violating a frozen invariant.

## Work map

- 0–2h — Jobs current/closing/requirements evidence and temporal boundaries.
- 2–4h — Events official + Rubric identities/provenance; Canberra timestamps; preserve source distinction.
- 4–6h — Support aliases/topic/contact/action facts from approved sources.
- 6–8h — Create missing-date/missing-field fixtures.
- 8–10h — Run source registry/identity/provenance regressions.
- 10–12h — Freeze producer-side V7 changes.

## Acceptance / do-not-cross lines

- Rubric remains ingestion-only.
- No modality inference from Rubric eventStatus.
- No exact ticket availability from ambiguous fields.
- No new sources.

## Evidence to hand off

PR/SHA if changed; capability/field matrix; representative fixtures; parser/registry tests; source limitations; no unauthorized production mutation.

## Copy-paste AI kickoff prompt

You are Will working on AskANU V7 in the Scraper/data lane. Start from latest reviewed main and the frozen V7 behavioural contract. Implement only Day 6's scope through shared primitives. Do not invent unsupported institutional facts, silent source/schema/API changes, domain-specific state engines, or magic-wording shortcuts. Show planned files, behavioural impact, tests, risks and dependencies before implementation. Finish with exact evidence that Qasim can review against today's gate.

---

## Cross-repo handoff rule

If today's work exposes a requirement owned by another repository, record the exact contract/evidence gap and hand it to Qasim. Do not silently implement the other repository's responsibility here.
