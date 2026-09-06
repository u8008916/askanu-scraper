# DECISION_LOG.md

Record only decisions that change V3 contracts, architecture, source policy, scope, security/privacy rules, or schedule.

| Date | Decision | Why | Affected repos/docs | Owner | Approved by |
|---|---|---|---|---|---|
| 2026-09-06 | Freeze Courses/Programs schema v1: full 16-field normalized Scraper -> DB -> RAG record; year-scoped `entity_id`; namespaced stable `record_id`; explicit four-digit academic year; SHA-256 `content_hash` of canonical `content`; stored canonical URLs; strict no-invented-value/null policy; multi-year-safe RAG lookup; and first DB/migration ownership. | Unblock Will -> Carmen integration using one implementation-ready shared boundary based on the verified scraper output and Carmen's Day 2 exact-retrieval requirements. | RAG `docs/DATA_SCHEMA.md` and `docs/DECISION_LOG.md`; Scraper `docs/DATA_SCHEMA.md` and implementation require synchronisation before PR #5 merge. | Qasim (contracts/integration) | Qasim after Will/Carmen implementation review |

If a decision changes a shared contract, update every affected repo in the same work cycle.

## Documentation-only bootstrap record — 2026-09-05

This separate record captures the requested bootstrap clarification and outstanding gaps, not a change to locked V3 decisions. The three-repo architecture, roles, dates/schedule, six domains, sources, GCP region assumption and source policy remain unchanged.

- Scope: documentation/bootstrap scaffold only. Will's Day 1 implementation is outstanding; this cleanup adds no Python package, dependencies, source modules, registry enforcement, machine-readable registry, HTML fixtures or parser tests, and performs no live requests or mass crawling.
- Repository hygiene: remove README trailing whitespace and align credential/private-key ignore patterns with the RAG repo while keeping `.env.example` trackable.
- Source gaps: Will's machine-readable registry needs stable `source_id`, parser mapping and approval/active state. A bounded fetch/rate policy and exact additional Support targets remain unresolved. Document an exact production Events target if different from the approved official ANU Events/calendar fallback. Qasim coordinates source approvals; no values or targets are invented here.
- Contract gaps: precise field types/nullability, status values and ID/hash rules remain for the Qasim/Carmen/Will schema coordination before implementation. Authoritative API/conversation contracts remain in `askanu-rag/docs/API_CONTRACT.md` and `askanu-rag/docs/CONVERSATION_CONTRACT.md`; no API contract is copied here.
- Preserved safeguards: Rubric is `PENDING_APPROVAL`, non-production pending documented approved access; no undocumented/internal API integration. Official ANU Events/calendar is the release-safe fallback/primary source unless Rubric approval is obtained and remains the release source regardless of the response. No authenticated StarRez scraping; no collector targets outside the eventual approved registry; failed or suspicious collection preserves last-known-good data.

Affected documentation: `README.md`, `.gitignore`, `docs/SOURCE_REGISTRY.md`, `docs/DATA_SCHEMA.md` and this log. These entries record the user-authorized documentation cleanup, not approval of unresolved implementation choices.
