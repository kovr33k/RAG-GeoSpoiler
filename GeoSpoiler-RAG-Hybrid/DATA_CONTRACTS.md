# Data Contracts

This document records the read-only data contracts introduced for local
GeoSpoiler artifacts. The contracts are intentionally soft: they describe the
current shape of generated files, preserve unknown fields, and report quality
issues without stopping the RAG pipeline.

## Modules

- `models.py` contains Pydantic models for normalized metadata, enriched cards,
  source identifiers, wiki references, query profiles, and experiment runs.
- `data_validation.py` contains soft validators and Markdown report generation.

## Enriched Cards

Primary model: `EnrichedCard`.

Important fields:

- `version`
- `enriched_at`
- `provenance`
- `content_type`
- `triage`
- `language`
- `summary`
- `key_facts`
- `entities`
- `topics`
- `quotes`
- `events`
- `source_chain`
- `graph_text`
- `search_text`

The model keeps extra fields so older and future cards can still be scanned.

## Provenance

Primary model: `Provenance`.

Stable source ids are derived in this order:

1. Existing `source_id`, if present.
2. `telegram:{channel_id}:{message_id}`.
3. `telegram:{channel_name}:{message_id}`.

If no stable source id can be derived, validation reports a warning.

## Claim Types

Allowed `key_facts[].claim_type` values:

- `fact`
- `source_claim`
- `hypothesis`

Unknown values are warnings, not hard errors, because older cards may contain
legacy labels such as `quote`, `claim`, or `thesis`. Claim-building logic should
continue to treat only source-grounded facts as evidence.

## Normalized Metadata

Primary model: `NormalizedMeta`.

Important fields:

- `channel_name`
- `channel_id`
- `channel_username`
- `message_id`
- `date`
- `post_url`
- media flags such as `has_text`, `has_images`, `has_video`, `has_voice`
- URL lists such as `youtube_urls`, `instagram_urls`, `ai_chat_urls`, `web_urls`
- optional `media`

URL list fields accept missing or null values and normalize them to empty lists.

## Validation Command

Run:

```powershell
python main.py validate enriched
```

The command scans `output/enriched`, writes a Markdown report under
`artifacts/`, and exits successfully even when warnings are found.

For future CI or release checks:

```powershell
python main.py validate enriched --fail-on-error
```

`--fail-on-error` exits non-zero only when hard schema errors are present.
Warnings remain non-blocking until the corpus is intentionally cleaned.

## Current Baseline

Latest B-lite validation baseline:

- cards seen: 218
- cards valid: 218
- cards invalid: 0
- errors: 0
- warnings: 16
- report: `artifacts/enriched_validation_20260531_143553.md`

The warnings are data-cleanup candidates, not runtime blockers.
