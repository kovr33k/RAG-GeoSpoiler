# Wiki Memory

This document describes the local wiki-memory layer used by GeoSpoiler RAG.
It is a Karpathy-style, LLM-maintained markdown wiki over enriched evidence
cards. The enriched cards remain the source of truth; wiki pages are compiled
memory that make recurring claims, entities, and topics easier to retrieve.

## Purpose

Wiki memory is not a replacement for `output/normalized`, `output/enriched`, or
LightRAG. Its job is to stabilize high-risk claims, entities, and topics so
query flows can retrieve source-grounded context before synthesis.

The layer is intentionally local and inspectable:

- no Obsidian dependency;
- no wiki-specific LightRAG graph;
- LLM calls only during `python main.py wiki ingest`;
- deterministic index, health, overview, and FTS commands;
- markdown pages plus JSON/SQLite indexes.

## Layout

The active wiki lives under `output/wiki/`:

```text
output/wiki/
  _master_index.md
  _schema.md
  _overview.md
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

## Main Workflow

Grow and refresh wiki memory from enriched cards:

```powershell
python main.py wiki ingest
```

`wiki ingest` compares enriched-card content hashes against
`output/wiki/indexes/source_hashes.json`, sends new/changed cards to the wiki
LLM, validates that returned page operations cite only input `source_id` values,
writes wiki pages, rebuilds indexes, runs health, writes `_overview.md`, and
prints changed wiki files for git review.

Wiki LLM settings are separate but optional:

```text
WIKI_LLM_MODEL
WIKI_LLM_API_KEY
WIKI_LLM_BASE_URL
```

If a `WIKI_LLM_*` value is empty, the wiki client falls back to the matching
`ENRICHMENT_*` value.

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

LLM-generated pages must include:

```text
generated_by: wiki_ingest_v1
review_status: auto
source_count: N
updated_at: YYYY-MM-DD
```

## Pending Updates

`output/wiki/_pending_updates.json` is a fallback queue only. It is used when a
new/changed enriched source cannot be safely processed by `wiki ingest`, for
example because the LLM returned invalid JSON or cited a source outside the
input batch. It is not the primary wiki growth path.

## Legacy Bootstrap

The old hardcoded seed commands remain for bootstrap/regression use:

```powershell
python main.py wiki build --claims-only
python main.py wiki build --entities-topics
```

They should not be treated as the main way the wiki grows.

`python main.py wiki update` also remains available for metadata-only updates
to already-linked pages. It does not create new claim/entity/topic pages.

## Health And Overview

Run health checks and rewrite `output/wiki/_health.md`:

```powershell
python main.py wiki health
```

Generate deterministic counts, pending queue size, recent updates, and enriched
to wiki coverage gaps:

```powershell
python main.py wiki overview
```

Health checks are deterministic and local. They do not call Telegram, LightRAG,
or any LLM endpoint. They check claim grounding, indexes, pending queue size,
broken wiki references, overly broad claim pages, and frequent enriched
entities/topics that do not yet have wiki pages.

## Search Integration

Wiki context is read by:

- `retrieval/wiki_index.py` for FTS-first page ranking with keyword fallback;
- `retrieval/wiki_resolver.py` for source resolution;
- `retrieval/composer.py` for search/report context;
- `loader/query.py` and `loader/wiki_context.py` for query prompt/context assembly.

`retrieval/card_fts.py` keeps card FTS and wiki FTS in separate SQLite FTS5
tables: `cards_fts` and `wiki_fts`.

The wiki should help select and constrain sources, but final answers should
still cite original posts, normalized files, or enriched cards.

## Git Recovery Policy

LLM-generated wiki changes must be recoverable through git/GitHub history.
After `wiki ingest`, review changed wiki files, then preserve accepted changes:

```powershell
git status --short -- output/wiki
git add output/wiki
git commit -m "wiki: ingest enriched cards"
git push
```

This avoids a separate snapshot system and makes bad LLM edits reversible.

## Operational Notes

- Do not run a LightRAG rebuild just because wiki pages changed.
- Review `_pending_updates.json` after failed or unclear ingest batches.
- Keep source-grounded claims small; split pages when they become difficult to
  inspect.
- Run `python main.py fts rebuild` after substantial wiki changes to refresh
  both card and wiki FTS tables.
