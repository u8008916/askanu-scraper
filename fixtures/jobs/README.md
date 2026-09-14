# Jobs fixture provenance

`anu_jobs_listing_sample.html` and `anu_job_open_dated_sample.html` are reduced
source evidence from the approved public ANU Jobs listing/detail pages. The
dated record was rechecked on 2026-09-14, including its numeric requisition ID,
Fixed Term employment type, classification, closing time and salary wording.
`normalized_job_record_sample.json` is the frozen Jobs v1 normalized output for
that source-backed snapshot. It supplies the current dated, fixed-term and exact
numeric-ID lookup cases.

The following files are deliberately synthetic test inputs and must not be
presented as captured or currently published ANU jobs:

- `anu_job_open_undated_sample.html`: explicit-current/null-deadline behavior;
- `anu_job_closed_sample.html`: closed/past-date exclusion behavior; and
- `anu_job_malformed_sample.html`: required-identity/parser failure behavior.

The two synthetic detail paths returned HTTP 404 when checked on 2026-09-14.
Same-closing-date ordering and unknown-status exclusion are RAG repository
behaviors; consumers should construct clearly labelled synthetic model objects
from the frozen normalized fixture rather than inventing additional production
source evidence.

`synthetic_jobs_v1_edge_records.json` contains complete normalized open-undated,
closed, same-closing-date tie-break and unknown-state objects for Carmen's
contract/model tests. Its wrapper warning must remain with the records. These
are repository test objects, not source claims. Pair the source-backed record
`563693` with synthetic record `563694` to test numeric identity tie-breaking.
