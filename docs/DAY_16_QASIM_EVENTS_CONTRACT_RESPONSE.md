# Events producer contract response to Qasim

Day 15 scraper PR #32 remains unchanged at
`7b9d463ba1f35bc87b9573bbf743b3b17caf3e83`. The Day 16 operational-freeze
work is a separate stacked branch. This response documents producer truth; it
does not change Event identity or metadata.

## Complete deterministic producer examples

Both records below were serialized from the checked-in sanitized fixtures with
the parser clock fixed to `2026-09-20T12:00:00+10:00`.

### Official ANU Event

```json
{
  "canonical_url": "https://www.anu.edu.au/events/window-opening",
  "collected_at": "2026-09-20T12:00:00+10:00",
  "content": "Title: Window-opening symposium\nDate and times: Fri 18 Sep 2026, 9:00 am - Sat 19 Sep 2026, 5:00 pm\nLocation: Kambri Cultural Centre\nCategories: Conference\nTags: Indonesia\nPresented by: Presented by ANU College of Asia and the Pacific\nDescription: Official event description. Register in person Online registration: Register for Zoom\nRegistration: Register in person; Register for Zoom",
  "content_hash": "aa365c41255ee2f768bbaca3925263564046cf58db971d6666546bca4dbf7922",
  "domain": "events",
  "effective_from": "2026-09-18T09:00:00+10:00",
  "effective_to": "2026-09-19T17:00:00+10:00",
  "embedding_version": null,
  "entity_id": "1001",
  "index_status": "PENDING",
  "last_seen_at": "2026-09-20T12:00:00+10:00",
  "metadata_json": {
    "cancellation_text": null,
    "categories": ["Conference"],
    "description": "Official event description. Register in person Online registration: Register for Zoom",
    "end_at": "2026-09-19T17:00:00+10:00",
    "end_date": "2026-09-19",
    "entity_type": "event",
    "event_id": "1001",
    "format": null,
    "location": "Kambri Cultural Centre",
    "organiser": "Presented by ANU College of Asia and the Pacific",
    "registration_links": [
      {"label": "Register in person", "url": "https://tickets.example/register/in-person"},
      {"label": "Register for Zoom", "url": "https://zoom.example/register"}
    ],
    "start_at": "2026-09-18T09:00:00+10:00",
    "start_date": "2026-09-18",
    "status": null,
    "tags": ["Indonesia"],
    "timezone": "Australia/Canberra"
  },
  "record_id": "events:event:1001",
  "source_id": "events_anu_official",
  "status": "NEW",
  "title": "Window-opening symposium"
}
```

### Rubric Event 78459

```json
{
  "canonical_url": "https://campus.hellorubric.com/?eid=78459",
  "collected_at": "2026-09-20T12:00:00+10:00",
  "content": "Title: ANU Community Bonfire Night\nStart: 2026-09-20T18:00:00+10:00\nEnd: 2026-09-20T21:00:00+10:00\nLocation: ANU Acton campus\nPresented by: ANU International Students Association\nDescription: A community event for ANU students.\nRegistration: https://example.org/anuisa/bonfire-registration\nSource: Rubric ANU community events",
  "content_hash": "3e103cb9abcb83dc6c5138083b4837a3b9b6fd00fcfafd489faf430dda78b9bf",
  "domain": "events",
  "effective_from": "2026-09-20T18:00:00+10:00",
  "effective_to": "2026-09-20T21:00:00+10:00",
  "embedding_version": null,
  "entity_id": "rubric:78459",
  "index_status": "PENDING",
  "last_seen_at": "2026-09-20T12:00:00+10:00",
  "metadata_json": {
    "cancellation_text": null,
    "categories": [],
    "description": "A community event for ANU students.",
    "end_at": "2026-09-20T21:00:00+10:00",
    "end_date": "2026-09-20",
    "entity_type": "event",
    "event_id": "78459",
    "format": null,
    "location": "ANU Acton campus",
    "organiser": "ANU International Students Association",
    "registration_links": [
      {"label": "Event link", "url": "https://example.org/anuisa/bonfire-registration"}
    ],
    "start_at": "2026-09-20T18:00:00+10:00",
    "start_date": "2026-09-20",
    "status": null,
    "tags": [],
    "timezone": "Australia/Canberra"
  },
  "record_id": "events:event:rubric:78459",
  "source_id": "rubric_unified_search",
  "status": "NEW",
  "title": "ANU Community Bonfire Night"
}
```

## Producer metadata contract

Every metadata key is emitted. "Optional" below means its value may be null or
an empty list when the approved source does not publish the fact.

| Field | Type | Producer | Requirement and derivation |
|---|---|---|---|
| `entity_type` | string | both | Required constant `event`; derived |
| `event_id` | numeric string | both | Required source identity |
| `start_date` | ISO date string | both | Required; derived from the published interval |
| `end_date` | ISO date string or null | both | Official required; Rubric optional |
| `start_at` | aware ISO datetime or null | both | Official nullable for date-only evidence; Rubric required |
| `end_at` | aware ISO datetime or null | both | Optional |
| `timezone` | string | both | Required normalized Canberra semantic |
| `location` | string or null | both | Optional source display text |
| `format` | string or null | official | Only explicit official evidence; Rubric deliberately null |
| `categories` | list of strings | both | Optional source values |
| `tags` | list of strings | both | Optional source values |
| `organiser` | string or null | both | Optional source value |
| `description` | string or null | both | Optional sanitized source text |
| `registration_links` | list of `{label,url}` | both | Optional credential-free HTTP(S) source links |
| `status` | `cancelled` or null | official | Only an explicit cancellation; Rubric deliberately null |
| `cancellation_text` | string or null | official | Exact explicit source wording only |

## Diff against Carmen migration 20260919_0009

| Producer | Consumer | Classification |
|---|---|---|
| `event_id` | `source_event_id` | Simple naming difference |
| `organiser` | `organiser_name` | Simple naming difference |
| `start_at`, `end_at`, `timezone`, `tags` | same | Direct mapping, subject to nullable date-only handling |
| `rubric:78459` | `rubric-78459` | Shared identity decision; both are stable and collision-safe |
| `location` | `venue_name`, `address`, coordinates | Not safely equivalent; producer has one source display string and will not invent structure |
| `registration_links` | `registration_url` | Consumer is lossy when a page publishes multiple labelled actions |
| `categories` | `category` | Potentially lossy plural-to-singular mapping |
| `status`, `cancellation_text` | `source_status`, `cancellation_status` | Generic status must not be conflated; normalized cancellation and exact wording are distinct |
| `start_date`, `end_date` | no direct keys | Needed to preserve date-only evidence without inventing midnight timestamps |
| `format` | no direct key | Useful only when explicitly published; current Rubric values do not establish it |
| `description` | common `content` plus no metadata key | Content already preserves it; metadata duplication is optional |
| none | `audience`, address, latitude, longitude | Leave absent/null unless explicitly sourced |

There is no producer-side technical requirement for a colon inside Rubric's
`entity_id`. The current colon form is a deliberate namespace, not a storage
constraint. If Qasim freezes the hyphenated convention, the producer preference
is `entity_id=rubric-78459` and `record_id=events:event:rubric-78459` because it
matches the shared consumer convention and avoids a nested record-ID delimiter.
No such change is made in this response.

The current consumer boundary would lose multiple registration actions and
labels, raw location text if it is forced into unsupported structure,
date-only boundaries, exact cancellation wording, an explicitly published
official format, and potentially multiple categories. These require a shared
decision; the producer will not silently collapse them.

## Deliberately unnormalized Rubric semantics

- `eventStatus: Online` is not format or generic normalized status.
- `ticketsPossiblyAvailable` is not exact availability or remaining tickets.
- A missing price does not mean free.
- A missing venue does not mean online.
- Missing registration data does not mean unavailable.
- Draft records remain excluded and are not normalized as accepted records.

## Operational confirmation

- No production database write occurred.
- No deployment, image update, Cloud execution or Scheduler change occurred.
- `SCRAPER_EVENTS_POSTGRES_APPROVED` and
  `SCRAPER_RUBRIC_POSTGRES_APPROVED` remain false/default-closed for Events.
- The bounded live Rubric census has not run.
- The observed Rubric `totalItemCount=119` is not the frozen denominator.
- Endpoint discovery is complete. The remaining gate is the exact sanitized
  request-contract verification/capture for `desiredType=events`, Australia,
  ACT, university ID 1 and bounded limit/offset pagination, followed by the
  bounded live census.
- No producer identity or metadata change will be committed until Qasim freezes
  the shared contract.
