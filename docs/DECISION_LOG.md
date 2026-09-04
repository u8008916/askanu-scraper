# DECISION_LOG.md

Record only decisions that change V3 contracts, architecture, source policy, scope, security/privacy rules, or schedule.

| Date | Decision | Why | Affected repos/docs | Owner | Approved by |
|---|---|---|---|---|---|
| | | | | | |

If a decision changes a shared contract, update every affected repo in the same work cycle.

## Documentation-only bootstrap record — 2026-09-05

This separate record captures the requested bootstrap clarification and outstanding gaps, not a change to locked V3 decisions. The three-repo architecture, roles, dates/schedule, six domains, sources, GCP region assumption and source policy remain unchanged.

- Scope: documentation/bootstrap scaffold only. Will's Day 1 implementation is outstanding; this cleanup adds no Python package, dependencies, source modules, registry enforcement, machine-readable registry, HTML fixtures or parser tests, and performs no live requests or mass crawling.
- Repository hygiene: remove README trailing whitespace and align credential/private-key ignore patterns with the RAG repo while keeping `.env.example` trackable.
- Source gaps: Will's machine-readable registry needs stable `source_id`, parser mapping and approval/active state. A bounded fetch/rate policy and exact additional Support targets remain unresolved. Document an exact production Events target if different from the approved official ANU Events/calendar fallback. Qasim coordinates source approvals; no values or targets are invented here.
- Contract gaps: precise field types/nullability, status values and ID/hash rules remain for the Qasim/Carmen/Will schema coordination before implementation. Authoritative API/conversation contracts remain in `askanu-rag/docs/API_CONTRACT.md` and `askanu-rag/docs/CONVERSATION_CONTRACT.md`; no API contract is copied here.
- Preserved safeguards: Rubric is `PENDING_APPROVAL`, non-production pending documented approved access; no undocumented/internal API integration. Official ANU Events/calendar is the release-safe fallback/primary source unless Rubric approval is obtained and remains the release source regardless of the response. No authenticated StarRez scraping; no collector targets outside the eventual approved registry; failed or suspicious collection preserves last-known-good data.

Affected documentation: `README.md`, `.gitignore`, `docs/SOURCE_REGISTRY.md`, `docs/DATA_SCHEMA.md` and this log. These entries record the user-authorized documentation cleanup, not approval of unresolved implementation choices.
