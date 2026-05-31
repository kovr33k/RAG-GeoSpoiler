# Wiki Memory

This document describes the local wiki-memory layer used by GeoSpoiler RAG.
It is a source-grounded markdown layer over normalized Telegram/web/media
sources and enriched evidence cards.

## Purpose

Wiki memory is not a replacement for `output/normalized`, `output/enriched`, or
LightRAG. Its job is to stabilize high-risk claims, entities, and topics so
query flows can retrieve source-grounded context before synthesis.

The layer is intentionally local and inspectable:

- no vector database;
- no wiki-specific LightRAG graph;
- no LLM calls during index, health, or incremental update commands;
- markdown pages plus JSON indexes.

## Layout

The active wiki lives under `output/wiki/`:

```text
output/wiki/
  _master_index.md
  _schema.md
  _health.md
  _change_log.md
  _log.md
  _pending_updates.json
  entities/
  topics/
  claims/
  indexes/
    source_to_pages.json
    page_to_sources.json
    claim_to_sources.json
    source_hashes.json
```

The important page types are:

- `claims/`: source-grounded statements with status, evidence, and guardrails.
- `entities/`: named actors such as people, organizations, countries, parties.
- `topics/`: recurring narratives, events, and research areas.

## Source Chain

Wiki pages cite stable source ids in the form:

```text
telegram:{channel_id}:{message_id}
```

The expected resolution chain is:

```text
wiki page
  -> output/wiki/indexes/page_to_sources.json
  -> source_id
  -> artifacts/source_registry.sqlite
  -> post_url / normalized_file / enriched_card
```

If the source registry is unavailable, `retrieval/wiki_resolver.py` falls back
to enriched card metadata.

## Claim Rules

Claim pages must keep source claims separate from interpretation. Evidence is
trusted in this order:

1. Direct quotes.
2. `key_facts` with `claim_type=source_claim`.
3. Events.
4. Provenance, `post_url`, and date.
5. Summary as supporting context only.

Do not use summaries, theses, or hypotheses as the only direct evidence for a
claim. Do not label a claim fake, false, or deepfake unless a cited evidence
item explicitly says that.

Supported claim statuses:

```text
supported_by_corpus
contradicted_by_corpus
disputed_in_corpus
unclear_in_corpus
```

Automatically generated pages keep `review_status: auto` until reviewed.

## Commands

Initialize the scaffold without overwriting existing files:

```powershell
python main.py wiki init
```

Seed claim pages:

```powershell
python main.py wiki build --claims-only
```

Seed entity/topic pages:

```powershell
python main.py wiki build --entities-topics
```

Run health checks and rewrite `output/wiki/_health.md`:

```powershell
python main.py wiki health
```

Run incremental update from enriched-card content hashes:

```powershell
python main.py wiki update
```

## Incremental Updates

`python main.py wiki update` compares current enriched-card content hashes with
`output/wiki/indexes/source_hashes.json`.

Linked changed sources update only the affected wiki pages. New or changed
sources that are not linked from any wiki page are written to:

```text
output/wiki/_pending_updates.json
```

This keeps the update path reviewable instead of silently expanding the wiki.

## Health Checks

`python main.py wiki health` checks for:

- claim pages without supported status values;
- claims without source ids;
- claims without quote or `source_claim` evidence;
- supported claims with `source_count < 1`;
- fake/deepfake labels outside direct evidence;
- broken page/source indexes;
- overly large pages.

Health checks are deterministic and local. They do not call Telegram, LightRAG,
or any LLM endpoint.

## Query Integration

Wiki context is read by:

- `retrieval/wiki_index.py` for lightweight page ranking;
- `retrieval/wiki_resolver.py` for source resolution;
- `retrieval/composer.py` for search/report context;
- `loader/lightrag_loader.py` for query prompt/context assembly.

The wiki should help select and constrain sources, but final answers should
still cite original posts, normalized files, or enriched cards.

## Operational Notes

- Rebuild indexes after manual wiki page edits with `python main.py wiki health`
  or `python main.py wiki update`.
- Do not run a LightRAG rebuild just because wiki pages changed.
- Do not overwrite manually edited pages from scaffold/build commands.
- Review `_pending_updates.json` before broadening claim coverage.
- Keep source-grounded claims small; split pages when they become difficult to
  inspect.
