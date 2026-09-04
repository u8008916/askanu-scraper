# DATA_SCHEMA.md

Shared Scraper -> RAG contract.

## Cross-repo references and unresolved schema work

The authoritative shared contracts live in:

- `askanu-rag/docs/API_CONTRACT.md`
- `askanu-rag/docs/CONVERSATION_CONTRACT.md`

These are cross-repo references, not local contract copies. Shared schema changes must be coordinated with Qasim/Carmen before implementation.

The field lists below are the V3 bootstrap outline. Precise common/domain field types, nullability, status values, and deterministic ID/hash rules remain unresolved implementation tasks. Qasim coordinates the Day 2 schema freeze with Carmen/Will; do not invent values or independently implement incompatible mappings. This cleanup does not change existing field lists or status semantics.

## Common record
```text
record_id
source_id
entity_id
domain
title
content
canonical_url
status
effective_from
effective_to
collected_at
last_seen_at
content_hash
embedding_version
index_status
metadata_json
```

## Source registry
```text
source_id
canonical_root
domain
authority_rank
poll_cadence
parser_name
active
notes
```

## Ingestion run
```text
run_id
source_id
started_at
completed_at
records_seen
records_added
records_changed
records_unchanged
records_missing
status
error
```

Rules:
- stable IDs
- never invent missing fields
- timezone `Australia/Canberra`
- canonical URL comes from source
- preserve academic year/session
- DB success + embedding failure must not appear fully indexed
- NEW -> insert/embed
- CHANGED -> update/re-embed
- UNCHANGED -> update last_seen only
- MISSING -> review/expiry policy, not immediate delete
- fetch/parser failure -> keep last-known-good
- suspicious many->zero -> fail run; never wipe current
