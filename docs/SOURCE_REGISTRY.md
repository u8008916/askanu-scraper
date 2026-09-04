# SOURCE_REGISTRY.md

Only approved sources may enter production.

| Domain | Approved V3 source | Rule | Initial poll |
|---|---|---|---|
| Courses | https://programsandcourses.anu.edu.au/ | Courses + programs + majors/minors/specialisations; preserve year/session/prerequisites/requirements/URL. | Daily |
| Scholarships | https://study.anu.edu.au/scholarships and find-scholarship | Structured eligibility/status/application/deadline data. | Daily |
| Jobs | https://jobs.anu.edu.au/jobs/search | Current/open roles; closing-date data; canonical URL. | Daily |
| Accommodation | https://study.anu.edu.au/accommodation and /our-residences | Residence/catering/resident type/advertised rate/application info. | Daily |
| Support | https://anusa.com.au/student-assistance/ + approved ANU support pages | Academic, financial, accommodation, disciplinary, physical/mental health, SASH, advocacy. | Daily |
| Events | Official ANU Events/calendar | Release-safe fallback/primary source unless Rubric approval is obtained; remains the release source regardless of Rubric response. | Daily |
| Rubric | `PENDING_APPROVAL`, non-production | No production use of undocumented/internal API without approved access. | Disabled unless approved |

StarRez authenticated/application portal is an external destination, not a scraping target.

Daily polling means fetch/parse/hash compare. Only new/changed content is re-embedded.
Failure/suspicious-zero keeps last-known-good.

## Unresolved implementation tasks

This document records source policy; the machine-readable registry and enforcement are still outstanding as part of Will's implementation work.

- Define the machine-readable approved registry with stable `source_id`, parser mapping, and approval/active state. No collector may target a source absent from the eventual approved registry; registry presence alone does not grant production approval.
- Agree a bounded source-fetch/rate policy before live requests. Request bounds and rate limits remain unresolved; daily poll cadence does not define those limits.
- Record the exact additional approved ANU Support source targets before collecting them. The general reference to ANU support pages does not approve arbitrary pages.
- Document the exact production Events target if different from the already approved official ANU Events/calendar fallback. Do not infer a new target or approval. Official ANU Events/calendar remains the release-safe baseline, and Rubric approval is non-blocking.

Will owns registry/collector implementation; Qasim owns source-approval decisions and coordinates unresolved targets and policy. Rubric remains `PENDING_APPROVAL` and non-production until approved access is documented. No authenticated StarRez scraping is permitted. Failed or suspicious collection must preserve last-known-good data.
