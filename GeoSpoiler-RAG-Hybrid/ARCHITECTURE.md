# Architecture

GeoSpoiler RAG is a local OSINT memory system built around Telegram sources,
normalized text, enriched evidence cards, local indexes, and
LightRAG query execution.

The project is not trying to make LightRAG the only source of truth. The stable
source chain is:

```text
Telegram / web / media
  -> output/normalized
  -> output/enriched
  -> local indexes
  -> optional LightRAG commands
  -> query/search/eval
```

## Main Layers

```text
fetcher/
  Telegram discovery, message fetch, media capture, source state.

normalizer/
  TelegramMessage -> normalized .txt + .meta.json.
  Expands text, images, YouTube, Instagram, web links, unified review
  placeholders, and native audio/video transcripts.

enricher/
  normalized .txt + .meta.json -> enriched evidence cards.
  Extracts summaries, key points, entities, topics, quotes, theses, and events;
  deterministic builders produce graph/search text.

retrieval/
  Local retrieval/index layers:
  - card FTS;
  - source registry;
  - composer search.

loader/
  Focused LightRAG modules for factory setup, ingestion, storage, extraction,
  entity merge policy, query orchestration, and card fallback context.
  `loader/lightrag_loader.py` is a compatibility facade.

cli_tools.py
  Secondary command helpers for experiment-registry, enriched-validation,
  source-registry, FTS, and transcription-backfill printers.

cli.py
  Compatibility wrapper that re-exports `cli_tools` for older imports.

cli_app.py / cli_pipeline.py / cli_query.py / cli_runtime.py
  Argparse command routing, pipeline commands, query/source display helpers,
  and shared CLI runtime utilities.

experiment_registry.py
  Read-only score-artifact registry for golden/probe/smoke run summaries.

main.py
  Thin entry point that calls `cli_app.main()`.
```

## Source Of Truth

`output/normalized/` is the immutable source archive. `output/enriched/` is the
working card layer used by local retrieval and explicit LightRAG graph loading.
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
  -> full card FTS rebuild
  -> full source registry rebuild

cmd_load
  -> cli_pipeline.cmd_load
  -> loader.factory.create_rag
  -> loader.ingest.load_from_enriched
  -> enriched_v2 graph_text only
  -> rag_storage/
```

`python main.py run` executes fetch, normalize, enrich, card FTS rebuild, and
source-registry rebuild. LightRAG loading is a separate, explicit command.

## Normalization

The normalizer assembles a single text document from:

- Telegram text;
- image descriptions from the vision handler;
- native media placeholders and optional transcripts;
- YouTube subtitles/description;
- Instagram caption/subtitles;
- queued review placeholders for AI chats, external links, long Instagram Reels, and low-information posts;
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

Enriched v2 cards include:

- provenance;
- content type;
- summary;
- key points;
- entities and topics;
- quotes;
- events;
- theses;
- graph/search text.

LightRAG is not updated by `run` or `enrich`. `python main.py load` explicitly
loads `graph_text` from `schema_version=enriched_v2` cards. Cards without
`graph_text` are skipped; normalized text is never used as an implicit fallback.

## LightRAG Storage

The active LightRAG working directory is:

```text
rag_storage/
```

Explicit load path:

```text
output/enriched/*.enriched.json:graph_text -> LightRAG
```

Document ids are stable and path-based. The review queue remains a separate
manual workflow. `load` and `rebuild` do not read it; both commands ingest only
non-empty `graph_text` from `schema_version=enriched_v2` cards.

`rebuild` moves the current `rag_storage/` into `rag_storage_backups/`, clears
the active query cache, and reloads enriched v2 graph text.

## Wiki Status

The old file-first Wiki was removed. Its replacement is
`retrieval/wiki/`: a versioned SQLite state machine whose Markdown files are
only disposable projections.

```text
Enriched v2 + YouTube segment cards
  -> lineage/input revisions + immutable claim occurrences
  -> registry surface evidence
  -> user-approved concepts and identity aliases
  -> exact reversible claim groups
  -> role-aware occurrence -> concept links
  -> computed card relations
  -> approved hierarchy + authoritative manual sidecars
  -> card / claim / hub projections
  -> generated output/wiki/*.md + Wiki FTS
  -> Retrieval Composer and hybrid query context
```

The main ownership boundary is:

```text
Authoritative
  Enriched revisions, approvals/rejects/reopens, aliases,
  hierarchy decisions, pinned ambiguity resolutions, sidecars

Derived/rebuildable
  automatic groups and links, card relations, proposal candidates,
  projection artifacts, generated hubs, FTS
```

Stages use immutable input/dependency generations and processor-contract
activation history. Their final CAS checks every bound head, so a late worker
cannot apply an obsolete revision. Claim extraction is invalidated only by
claim inputs; summary, relation, eligibility, and display changes move their
own generations. Successful Luna identity/hierarchy analyses are cached by the
exact candidate/tree snapshot, prompt version, and model profile; unchanged
runs do not call the model again.

Lifecycle-active occurrences are distinct from eligible-active occurrences.
Grouping and concept resolution can be prepared from lifecycle state, while
eligibility only exposes or hides those results from review, hubs, and FTS.
Luna relation resolution runs only for unclear roles or plausible claim-local
metonyms; explicit structured `subject`/`actor`/`object` roles stay
deterministic.

Registry and resolver safety:

- two independent claim clusters are required before a surface proposal;
- reposts of the same content remain one cluster;
- concepts do not exist before explicit approval;
- aliases are identity equivalence only; metonyms are claim-local;
- exact claim grouping never destroys source occurrences;
- ambiguous candidates enter a separate review queue;
- hierarchy changes are proposals and approved branches never move
  automatically;
- hubs exist only for approved concepts with current eligible material;
- direct claims/cards are prominent, while context/mentions are preserved in
  collapsed sections.

Wiki is a dormant optional subsystem by default. With `WIKI_ENABLED=false`,
`cli_pipeline.refresh_enriched_retrieval()` skips it, `reviewer_app.py` hides
its tab, CLI commands are blocked, and query paths do not open its SQLite DB.
Setting `WIKI_ENABLED=true` restores those paths; approved hub context is then
included when `HYBRID_QUERY_WIKI_ENABLED=true`.

## Local Retrieval Indexes

Card FTS:

```text
retrieval/card_fts.py
artifacts/card_fts.sqlite
```

This is the preferred local card search backend. Composer also runs
`retrieval/shadow_search.py`, keeps FTS first for duplicates, and appends unique
shadow matches for extra recall. Direct FTS search supports bounded `--top-k`
and unbounded `--all` modes.

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

Composer combines LightRAG query results and card search for search/report
commands. Cards-only modes avoid LightRAG and live LLM calls.

## Query Flow

Normal query entry:

```text
main.py
  -> cli_app
  -> cli_query.cmd_query
  -> loader.query.query_rag_result
```

Inside the loader query path:

```text
LATE_FUSION_ENABLED=false
  -> preserved legacy LightRAG/card-context path

LATE_FUSION_ENABLED=true
  -> LightRAG aquery_data + Card FTS + YouTube segment FTS in parallel
  -> independent per-channel timeout/status/duration trace
  -> path/source normalization, deduplication and RRF
  -> best-ranked YouTube segment validation with backfill
  -> strict card/source identity, HTTP(S) URL validation and hydration backfill
  -> field-aware deterministic token packing
  -> one final Luna synthesis call with stable [S1]..[Sn] citations
  -> citation validation
  -> direct legacy fallback only for a Late-Fusion synthesis failure
```

Late Fusion remains Enriched-first: LightRAG ingestion still receives only
`EnrichedCardV2.graph_text`; normalized files are provenance identities, not
the answer evidence. Wiki is excluded from the V1 path. `data.late_fusion`
contains a compact retrieval trace, while `data.references` contains only the
source blocks actually passed to Luna.

Query-time Card/YouTube FTS and source-registry resolution open existing SQLite
databases read-only. Schema creation and migrations belong to explicit
rebuild/init paths, never to a user query.

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
main.py
  -> cli_app
  -> cli_query.cmd_search
  -> retrieval.composer.search
```

Modes:

```text
recall      broad LightRAG + card retrieval
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
- query results carry `data.references`;
- `cli_query._extract_query_sources` resolves references for source display.

Known failure class: answer text can be plausible while source selection is
wrong. This is why golden and focused live probes check source-specific cases,
not only answer text.

## Evaluation Architecture

No-network checks:

```text
python -m unittest
python main.py fts search "query"
python main.py registry resolve SOURCE_ID
```

Live model checks:

```text
python main.py baseline probe N
python tests/test_golden_set.py
python llm_verification_probe.py
python main.py experiments index
```

See `EVAL.md` for run details and result recording rules.

## Configuration Boundary

Important runtime flags:

```text
HYBRID_QUERY_CARDS_ENABLED
HYBRID_SYNTH_ENABLED
RERANKER_ENABLED
QUERY_MODEL
FALLBACK_SYNTH_MODEL
LLM_REASONING_EFFORT
TRANSCRIPTION_ENABLED
```

Reranker, synthesis, model, and retrieval changes should be evaluated
separately. Combining them in one run makes regressions hard to interpret.

## Design Principles

- Keep normalized sources as source of truth.
- Prefer local deterministic indexes before adding new infrastructure.
- Do not rebuild LightRAG unless the active graph must be recreated.
- Keep source-grounding checks separate from answer-quality checks.
- Treat live LLM behavior as unstable and record artifacts for important runs.
