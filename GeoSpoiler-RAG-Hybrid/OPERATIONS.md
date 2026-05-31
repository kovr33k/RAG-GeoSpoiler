# Operations

This document is the operational runbook for the local GeoSpoiler RAG project.
It focuses on safe day-to-day commands, rebuilds, generated artifacts, and
recovery checks.

## Python And Encoding

Preferred interpreter:

```powershell
C:\Users\artem\AppData\Local\Programs\Python\Python311\python.exe
```

For PowerShell sessions that print Cyrillic paths or answers:

```powershell
$env:PYTHONIOENCODING="utf-8"
$env:PYTHONUTF8="1"
```

On Windows, `.\run_pipeline.cmd ...` is useful for common pipeline commands
because it resolves a real Python interpreter and sets UTF-8 environment
variables.

Use direct Python for newer subcommands that are not exposed through
`run_pipeline.ps1`:

```powershell
python main.py wiki health
python main.py fts rebuild
python main.py registry rebuild
python main.py transcribe backfill --dry-run
python main.py experiments index
```

## Runtime Configuration

Keep secrets in `.env`; use `.env.example` only as a template. These are the
operationally important flags to check before runs:

| Variable | Purpose | Current trusted note |
|---|---|---|
| `LLM_BASE_URL`, `LLM_MODEL` | Default OpenAI-compatible chat endpoint/model | Current trusted model family is DeepSeek V4 Flash. |
| `RAG_BUILD_*` | Build-time chat endpoint/model override | Empty values fall back to `LLM_*`. |
| `QUERY_*` | Query-time chat endpoint/model override | Use for live query/golden runs. |
| `FALLBACK_SYNTH_*` | Hybrid synthesis endpoint/model override | Keep aligned with trusted query model unless testing. |
| `ENRICHMENT_*` | Enriched-card generation endpoint/model override | Use the same provider family unless testing. |
| `TRANSLATION_*` | Translation endpoint/model override | Empty values fall back to `LLM_*`. |
| `LLM_MAX_ASYNC` | Chat request concurrency | Higher values are useful only with a paid/stable provider. |
| `LLM_DELAY_SECONDS`, `RAG_BUILD_DELAY_SECONDS` | Artificial pacing between LLM calls | Use `0.0` only when the provider quota can handle it. |
| `QUERY_MAX_TOKENS`, `FALLBACK_SYNTH_MAX_TOKENS` | Query/synthesis output budgets | Tune for long source-grounded answers. |
| `LLM_REASONING_EFFORT` | Generic OpenAI-style reasoning effort | Leave empty for DeepSeek V4 Flash trusted runs. |
| `HYBRID_QUERY_CARDS_ENABLED` | Attach enriched-card context to query | Keep `true` for trusted query runs. |
| `HYBRID_SYNTH_ENABLED` | Synthesize final answer from graph/cards/wiki | Keep `true` for trusted DeepSeek runs. |
| `WIKI_ENABLED`, `WIKI_TOP_K` | Attach wiki-memory context | Keep `true` and small `top_k` for trusted runs. |
| `RERANKER_ENABLED` | Enable reranker hook | Keep `false`; latest DeepSeek golden regressed with reranker. |
| `TRANSCRIPTION_ENABLED` | Enable native media transcription | Keep `false` unless testing real downloaded media. |

## Normal Daily Flow

Check current state:

```powershell
python main.py status
```

Fetch and normalize new Telegram messages without loading LightRAG:

```powershell
python main.py normalize
```

Enrich normalized posts into evidence cards:

```powershell
python main.py enrich
```

Load normalized text into the active LightRAG storage:

```powershell
python main.py load
```

Full fetch -> normalize -> enrich -> load:

```powershell
python main.py run
```

Use `run` only when you are comfortable doing all steps in one pass.

## Generated Artifacts

Important local paths:

```text
output/normalized/        source-of-truth normalized text and .meta.json files
output/enriched/          structured evidence cards
output/wiki/              wiki-memory markdown and JSON indexes
output/review_queue/      manual AI-chat review queue
output/transcripts/       native media transcript artifacts
artifacts/card_fts.sqlite local FTS index for enriched cards
artifacts/source_registry.sqlite source registry
rag_storage/              active LightRAG storage
rag_storage_backups/      rebuild backups
logs/                     pipeline and LightRAG logs
state/                    Telegram/progress state
media_cache/              downloaded images and native media
```

Do not delete generated data casually. If a rebuild or backfill needs to touch
these paths, prefer commands that make the operation explicit.

## Wiki Memory

Initialize wiki files and directories:

```powershell
python main.py wiki init
```

Seed source-grounded claims:

```powershell
python main.py wiki build --claims-only
```

Seed entities/topics:

```powershell
python main.py wiki build --entities-topics
```

Run local health checks:

```powershell
python main.py wiki health
```

Run incremental update from enriched-card hashes:

```powershell
python main.py wiki update
```

After manual wiki edits, run `python main.py wiki health` to rebuild indexes and
catch source/evidence issues.

## FTS Index

Rebuild the local card FTS index:

```powershell
python main.py fts rebuild
```

Search it:

```powershell
python main.py fts search "Trump Orban" --top-k 5
```

Compare with legacy shadow search:

```powershell
python main.py fts search "Trump Orban" --top-k 5 --compare-shadow
```

FTS rebuild is local and does not call an LLM.

## Source Registry

Rebuild source registry from normalized metadata and enriched cards:

```powershell
python main.py registry rebuild
```

Resolve a source id:

```powershell
python main.py registry resolve telegram:3328128766:148
```

Run registry rebuild after major normalized/enriched changes if query source
resolution looks stale.

## Experiment Registry

Rebuild the local experiment registry after meaningful golden/probe/smoke
runs:

```powershell
python main.py experiments index
```

Outputs:

```text
artifacts/experiment_registry.json
artifacts/experiment_registry.md
```

This command reads existing `*_scores.json` artifacts only. It does not call a
live model and does not modify RAG storage.

## Native Media Transcription

Transcription is controlled by:

```text
TRANSCRIPTION_ENABLED
TRANSCRIPTION_API_KEY
TRANSCRIPTION_BASE_URL
TRANSCRIPTION_MODEL
TRANSCRIPTION_LANGUAGE
TRANSCRIPTION_TIMEOUT_SECONDS
```

New native media transcripts are attached during normalization when
`TRANSCRIPTION_ENABLED=true` and downloaded media is available.

For old downloaded media, use controlled backfill:

```powershell
python main.py transcribe backfill --limit 3 --dry-run
python main.py transcribe backfill --limit 3 --media-type voice
```

Backfill updates existing normalized `.txt` files only when a transcript is
available and also updates the `.meta.json` sidecar.

After backfilling transcripts, rerun:

```powershell
python main.py enrich
python main.py fts rebuild
python main.py registry rebuild
python main.py wiki update
```

Do not run a large transcription backfill without first doing a dry run.

## AI Chat Review Queue

Show pending review items:

```powershell
python main.py review
```

Review files live in:

```text
output/review_queue/
```

To process one item, edit its JSON:

```json
{
  "status": "processed",
  "extracted_text": "..."
}
```

Then run:

```powershell
python main.py load
```

The load step includes reviewed AI-chat items with `status=processed`.

## Query Modes

Common direct query:

```powershell
python main.py query "question" hybrid
```

Use `source` profile for provenance-style questions:

```powershell
python main.py query "Where is this claim from?" hybrid source
```

Search without live LLM:

```powershell
python main.py search "Narva Estonia" --mode cards
python main.py fts search "Narva Estonia" --top-k 5
```

Keep `RERANKER_ENABLED=false` until reranker comparisons have been explicitly
run and accepted.

## LightRAG Rebuild

Normal operations should not rebuild LightRAG.

Use rebuild only when the active graph must be recreated from current source
files:

```powershell
python main.py rebuild
```

This moves the existing `rag_storage/` into `rag_storage_backups/` and loads
from `output/normalized/`.

Experimental enriched-card graph rebuild:

```powershell
python main.py rebuild --from-enriched
```

Use the enriched rebuild only as an explicit experiment, not as the default
knowledge base.

## Rebuild And Recovery Runbook

Use this sequence when you intentionally need a clean graph from current
normalized files:

```powershell
python main.py fts rebuild
python main.py registry rebuild
python main.py wiki health
python main.py rebuild
python main.py fts rebuild
python main.py registry rebuild
python main.py wiki health
```

Then validate behavior:

```powershell
python -m unittest
python test_golden_set.py
python main.py experiments index
```

If rebuild quality regresses:

1. Stop further loads.
2. Keep the failed `rag_storage/` by moving or renaming it with a timestamp.
3. Restore the latest known-good directory from `rag_storage_backups/`.
4. Run `python main.py status`, `python main.py wiki health`, and a local FTS
   search before another live probe.
5. Record the failed attempt and artifact paths in `DEVELOPMENT_RETURN_LOG.md`.

Do not use `python main.py rebuild --from-enriched` as a recovery path. It is
experimental and previously proved slow/unstable on the full corpus.

## Evaluation After Operational Changes

After code changes:

```powershell
python -m unittest
```

After wiki/retrieval/source changes:

```powershell
python main.py wiki health
python main.py fts search "Trump Orban" --top-k 5
python main.py registry resolve telegram:3328128766:148
```

For live model quality checks, follow `EVAL.md`.

## Common Recovery Notes

If PowerShell corrupts Cyrillic inline strings, use UTF-8 files, Unicode
escapes, or set:

```powershell
$env:PYTHONIOENCODING="utf-8"
$env:PYTHONUTF8="1"
```

If query answers look stale after changing models, inspect LightRAG response
cache before trusting the run. Focused probes can back up and clear cache with:

```powershell
$env:LLM_PROBE_CLEAR_CACHE="true"
python llm_verification_probe.py
```

If source grounding is wrong, check retrieval/source layers before blaming the
LLM endpoint:

```powershell
python main.py fts search "query terms" --top-k 10 --compare-shadow
python main.py registry resolve SOURCE_ID
python main.py wiki health
```

If SQLite files are locked on Windows, make sure no long-running process still
has the DB open, then rerun the command. Unit tests should close SQLite
connections explicitly.

## Logs

Pipeline logs:

```text
logs/pipeline_YYYYMMDD.log
```

LightRAG/UI logs:

```text
logs/lightrag.log
logs/lightrag_ui.log
logs/lightrag_ui.err.log
```

Record unresolved operational issues in `DEVELOPMENT_RETURN_LOG.md`. Record
live model/provider checks in `LLM_VERIFICATION_QUEUE.md`.
