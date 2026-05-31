# Architecture

GeoSpoiler RAG is a local OSINT memory system built around Telegram sources,
normalized text, enriched evidence cards, wiki memory, local indexes, and
LightRAG query execution.

The project is not trying to make LightRAG the only source of truth. The stable
source chain is:

```text
Telegram / web / media
  -> output/normalized
  -> output/enriched
  -> output/wiki + local indexes
  -> query/search/eval
```

## Main Layers

```text
fetcher/
  Telegram discovery, message fetch, media capture, source state.

normalizer/
  TelegramMessage -> normalized .txt + .meta.json.
  Expands text, images, YouTube, Instagram, web links, AI-chat review
  placeholders, and native audio/video transcripts.

enricher/
  normalized .txt + .meta.json -> enriched evidence cards.
  Extracts summaries, key facts, entities, topics, quotes, theses, events,
  graph text, and visual notes.

retrieval/
  Local retrieval/index layers:
  - card FTS;
  - source registry;
  - wiki indexes/resolver/health/update;
  - composer search.

loader/
  LightRAG creation, loading, query prompt setup, wiki/card context attachment,
  fallback synthesis, source extraction support.

cli.py
  Small CLI command helpers extracted from main.py as the first L-lite refactor
  boundary. Currently owns experiment-registry, enriched-validation,
  source-registry, FTS, and transcription-backfill command printers.

experiment_registry.py
  Read-only score-artifact registry for golden/probe/smoke run summaries.

main.py
  CLI orchestration.
```

## Source Of Truth

`output/normalized/` is the source-of-truth text layer for the default graph.
Each normalized text has a sidecar metadata file:

```text
output/normalized/{channel}/{message_id}.txt
output/normalized/{channel}/{message_id}.meta.json
```

The sidecar contains channel, message, post URL, media metadata, and link
metadata. Source ids are derived from Telegram provenance:

```text
telegram:{channel_id}:{message_id}
```

## Ingestion Flow

The normal pipeline is:

```text
cmd_fetch
  -> TelegramFetcher.fetch_all_channels
  -> list[TelegramMessage]

cmd_normalize
  -> normalizer.pipeline.normalize_batch
  -> output/normalized/*.txt
  -> output/normalized/*.meta.json
  -> state/progress.json update

cmd_enrich
  -> enricher.pipeline.enrich_all
  -> output/enriched/*.enriched.json
  -> state/enrichment_progress.json update

cmd_load
  -> loader.lightrag_loader.create_rag
  -> loader.lightrag_loader.load_from_directory
  -> rag_storage/
```

`python main.py run` executes fetch, normalize, enrich, and load in one pass.

## Normalization

The normalizer assembles a single text document from:

- Telegram text;
- image descriptions from the vision handler;
- native media placeholders and optional transcripts;
- YouTube subtitles/description;
- Instagram caption/subtitles;
- queued AI-chat review placeholders;
- extracted web article text.

The first line is a metadata header for source parsing. Loader code strips
headers and placeholder-only lines before LightRAG insertion, but preserves
meaningful transcript/body text.

## Native Media

Telegram native `video`, `audio`, and `voice` attachments are captured as
structured media metadata by `fetcher.telegram_client`.

Transcription is optional:

```text
normalizer.transcription_handler
  -> OpenAI-compatible /audio/transcriptions
  -> output/transcripts/*.json
  -> normalized text transcript section
  -> sidecar transcription metadata
```

Backfill is deliberately controlled:

```text
normalizer.transcription_backfill
  -> scan existing normalized sidecars
  -> transcribe small limited batches
  -> append transcript to existing normalized .txt
```

## Enrichment

`enricher.pipeline` scans normalized files and creates structured cards under
`output/enriched/`.

Cards include:

- provenance;
- content type and triage;
- summary;
- key facts;
- entities and topics;
- quotes;
- events;
- theses;
- visual/B-roll notes;
- graph/search text.

The default LightRAG graph is still loaded from normalized source text, not from
enriched cards. Loading enriched cards into LightRAG is retained only as an
explicit experimental mode:

```powershell
python main.py load --from-enriched
python main.py rebuild --from-enriched
```

## LightRAG Storage

The active LightRAG working directory is:

```text
rag_storage/
```

Default load path:

```text
output/normalized/*.txt -> LightRAG
```

Document ids are stable and path-based. `load` also includes reviewed AI-chat
items from `output/review_queue/` when they have `status=processed`.

`rebuild` moves the current `rag_storage/` into `rag_storage_backups/`, clears
the active query cache, and reloads the chosen source layer.

## Wiki Memory

Wiki memory is a local markdown layer under:

```text
output/wiki/
```

It tracks:

- high-risk claims;
- entities;
- topics;
- source-grounding guardrails;
- page/source indexes.

Wiki search is implemented in `retrieval/wiki_index.py`. Source resolution is
implemented in `retrieval/wiki_resolver.py` and prefers
`artifacts/source_registry.sqlite` before falling back to enriched cards.

Query integration uses wiki context as read-only memory. It is not a primary
source; final answers should prefer Telegram/YouTube/normalized references.

## Local Retrieval Indexes

Card FTS:

```text
retrieval/card_fts.py
artifacts/card_fts.sqlite
```

This is the preferred local card search backend. It falls back to legacy
`retrieval/shadow_search.py` when FTS is empty or unavailable.

Source registry:

```text
retrieval/source_registry.py
artifacts/source_registry.sqlite
```

The registry maps source ids to post URLs, normalized files, enriched cards, and
reference URLs.

Retrieval composer:

```text
retrieval/composer.py
```

Composer combines wiki context, LightRAG query results, and card search for
search/report commands. Cards-only modes avoid LightRAG and live LLM calls.

## Query Flow

Normal query entry:

```text
main.py cmd_query
  -> loader.lightrag_loader.query_rag_result
```

Inside the loader query path:

```text
question
  -> optional wiki context lookup
  -> optional enriched-card context lookup
  -> LightRAG query with query profile prompt
  -> attach wiki/card references
  -> optional fallback synthesis when configured
  -> postprocess answer
  -> return llm_response + data.references
```

Query profiles:

```text
answer
source
overview
```

The source profile prioritizes concrete provenance. Overview allows broader
aggregation. Answer is the normal cautious response profile.

## Search Flow

Search entry:

```text
main.py search
  -> retrieval.composer.search
```

Modes:

```text
recall      broad LightRAG + card retrieval
broll       visual/B-roll focused search
thesis      claim/thesis focused search
entity      entity focused search
cards       local cards-only search
shadow      compatibility cards-only search
```

`cards`, `cards-only`, and `shadow` do not require a LightRAG/LLM query.

## Source Grounding

Source grounding is maintained by several cooperating layers:

- normalized `.meta.json` stores post URLs and media/link metadata;
- enriched cards preserve provenance and normalized file paths;
- source registry gives a single source passport;
- wiki indexes map pages to source ids;
- query results carry `data.references`;
- `main._extract_query_sources` resolves references for source display.

Known failure class: answer text can be plausible while source selection is
wrong. This is why golden and focused live probes check source-specific cases,
not only answer text.

## Evaluation Architecture

No-network checks:

```text
python -m unittest
python main.py wiki health
python main.py fts search "query"
python main.py registry resolve SOURCE_ID
```

Live model checks:

```text
python main.py baseline probe N
python test_golden_set.py
python llm_verification_probe.py
python main.py experiments index
```

See `EVAL.md` for run details and result recording rules.

## Configuration Boundary

Important runtime flags:

```text
HYBRID_QUERY_CARDS_ENABLED
HYBRID_SYNTH_ENABLED
WIKI_ENABLED
RERANKER_ENABLED
QUERY_MODEL
FALLBACK_SYNTH_MODEL
LLM_REASONING_EFFORT
TRANSCRIPTION_ENABLED
```

Reranker, synthesis, wiki, model, and retrieval changes should be evaluated
separately. Combining them in one run makes regressions hard to interpret.

## Design Principles

- Keep normalized sources as source of truth.
- Keep wiki as read-only memory during query, not as a replacement source.
- Prefer local deterministic indexes before adding new infrastructure.
- Do not rebuild LightRAG unless the active graph must be recreated.
- Keep source-grounding checks separate from answer-quality checks.
- Treat live LLM behavior as unstable and record artifacts for important runs.
