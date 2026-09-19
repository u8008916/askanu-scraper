# SOURCE_REGISTRY.md

Only approved sources may enter production.

| Domain | Approved V3 source | Rule | Initial poll |
|---|---|---|---|
| Courses | https://programsandcourses.anu.edu.au/ | Courses + programs + majors/minors/specialisations; preserve year/session/prerequisites/requirements/URL. | Daily |
| Scholarships | https://study.anu.edu.au/scholarships and find-scholarship | Structured eligibility/status/application/deadline data. | Daily |
| Jobs | https://jobs.anu.edu.au/jobs/search | Current/open roles; closing-date data; canonical URL. | Daily |
| Accommodation | https://study.anu.edu.au/accommodation/our-residences | Frozen 2026-09-16 public registry: 19 residence detail pages below this path. Preserve catering/resident type/rate and fee wording/features/application/contact; StarRez is link-only. | Daily |
| Support | https://anusa.com.au/student-assistance/ | Frozen 2026-09-16 registry: the 6 top-level category pages linked by this page (Academic, Accommodation, Financial, Disciplinary, Physical and Mental Health, Sexual Assault and Sexual Harassment). | Daily |
| Events | https://www.anu.edu.au/events | Official-only Upcoming Events source. Traverse advertised `?page=0` onward with a hard cap and >=1 second request spacing; accept exact same-origin `/events/<slug>` details only. Frozen 2026-09-19 through 2026-10-31 inclusive snapshot: 30 unique overlapping events from 34 cards/33 unique links. | Daily (manual fallback until schedule approval) |
| Rubric | https://campus.hellorubric.com | `APPROVED_BOUNDED_UNSUPPORTED`: written permission reported by Qasim for paced/cached AskANU ingestion. Community/society Events chat source, not an official-ANU classification. Exact search endpoint capture is required; no guessed endpoint, cookies, tokens, request-time RAG call, or production write without the separate release gate. | Daily proposal; manual dry-run until reviewed |

StarRez authenticated/application portal is an external destination, not a scraping target.

Daily polling means fetch/parse/hash compare. Only new/changed content is re-embedded.
Failure/suspicious-zero keeps last-known-good.

## Unresolved implementation tasks

This document records source policy; the machine-readable registry and enforcement are still outstanding as part of Will's implementation work.

- Define the machine-readable approved registry with stable `source_id`, parser mapping, and approval/active state. No collector may target a source absent from the eventual approved registry; registry presence alone does not grant production approval.
- Agree a bounded source-fetch/rate policy before live requests. Request bounds and rate limits remain unresolved; daily poll cadence does not define those limits.
- The Day 9 implementation uses a conservative pending-approval proof bound of one finder page, at most ten same-site detail pages and at least one second between live requests. This is not authorization for a broader crawl or Scheduler enablement.
- Record the exact additional approved ANU Support source targets before collecting them. The general reference to ANU support pages does not approve arbitrary pages. No additional ANU Support target is active in the Day 12 frozen universe.
- Official and Rubric PostgreSQL writes and any Cloud Run Job/Scheduler remain gated on the append-only migration plus Qasim/Carmen approval. Official collection has a complete dry-run; Rubric has fixture proof but its exact sanitized search-endpoint capture and live denominator are still missing.

Will owns registry/collector implementation; Qasim owns source approval, the missing exact Rubric endpoint artifact and production release. Rubric approval does not make its unsupported API stable or its records official ANU events. No authenticated StarRez scraping is permitted. Failed or suspicious collection must preserve last-known-good data.
