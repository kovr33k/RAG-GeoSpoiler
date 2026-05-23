# GeoSpoiler-RAG

Telegram-to-RAG pipeline for collecting posts, normalizing linked content, and loading a LightRAG knowledge base you can query locally.

## What It Does

The pipeline can:

- fetch new messages from Telegram channels in a chosen Telegram folder
- normalize plain text, web pages, YouTube links, Instagram links, and reviewed AI chat shares
- load normalized texts into LightRAG with stable source-based document IDs
- rebuild the RAG index from current normalized files when you need a clean corpus
- answer questions over the resulting knowledge graph

## Project Layout

- `main.py` — CLI entry point
- `run_pipeline.ps1` — Windows-friendly runner with UTF-8 and Python resolution
- `run_pipeline.cmd` — wrapper that bypasses restrictive PowerShell execution policies
- `auth.py` — one-time Telegram authorization
- `output/normalized/` — normalized `.txt` files used as source of truth for ingest
- `output/review_queue/` — manual review queue for AI chat share links
- `rag_storage/` — active LightRAG storage
- `rag_storage_backups/` — rebuild backups
- `state/telegram.session` — saved Telegram session

## Requirements

- Windows PowerShell
- Python 3.11+ with a real interpreter installed
- API credentials in `.env`

Recommended: use `.\run_pipeline.cmd ...` on Windows. It bypasses restrictive PowerShell execution policies, avoids the common `WindowsApps\python.exe` shim problem, and resolves a usable Python interpreter automatically.

## Setup

1. Create and activate a virtual environment if you use one.
2. Install dependencies with your real Python interpreter:

```powershell
python -m pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and fill in:
   - Telegram credentials
   - LLM endpoint and model
   - embedding endpoint and model
   - optional vision/reranker settings

4. Run first-time Telegram auth:

```powershell
.\run_pipeline.cmd auth
```

## Daily Commands

```powershell
.\run_pipeline.cmd status
.\run_pipeline.cmd fetch
.\run_pipeline.cmd normalize
.\run_pipeline.cmd enrich
.\run_pipeline.cmd load
.\run_pipeline.cmd run
.\run_pipeline.cmd search "What changed in Cuba coverage?" --mode thesis
.\run_pipeline.cmd search "Трамп Орбан Венгрия" --mode shadow
.\run_pipeline.cmd quality
.\run_pipeline.cmd ui
```

Direct Python equivalents also work if your shell points to a real interpreter:

```powershell
python main.py status
python main.py run
python main.py search "связь и управление" --mode broll
```

## Search & Retrieval

Normal `query` is hybrid: it asks LightRAG first, then adds strong matches from enriched memory cards as additional context. If `HYBRID_SYNTH_ENABLED=true`, the final answer is synthesized from both the graph answer and the card facts.

The system also features a multi-index **Retrieval Composer** that supports different search modes depending on your analytical needs:

- **recall**: Broadest search. Combines LightRAG's hybrid retrieval with a BM25 shadow search. Good for general queries.
- **broll**: Visual-focused search. Scans enriched cards specifically for visual cues and B-roll notes to find footage.
- **thesis**: Focuses on high-level analytical claims and theses extracted during the enrichment phase.
- **entity**: Strict search for specific actors, organizations, or locations.
- **shadow**: Fast cards-only keyword search over enriched cards. Does not call LightRAG or an LLM.

Example:
`python main.py search "Нарва" --mode broll`

## Recommended Workflow

### Full automatic flow

```powershell
.\run_pipeline.cmd run
```

This will:

1. fetch new Telegram messages
2. normalize them into `output/normalized/`
3. **enrich** them into structured memory cards `output/enriched/`
4. load normalized text into LightRAG

### Enriched Memory Layer

During the **enrich** stage, the system uses an LLM to analyze the raw text and extract structured intelligence (summaries, key facts, entities, quotes, theses, visual b-roll notes). These are saved as `*.enriched.json` files.

Enriched cards are treated as a separate memory/retrieval layer. The default LightRAG graph is built from normalized source text. Experimental enriched-card graph loading is still available with `--from-enriched`, but it is not the default path.

Hybrid query controls:

```env
HYBRID_QUERY_CARDS_ENABLED=true
HYBRID_SYNTH_ENABLED=true
HYBRID_QUERY_CARDS_TOP_K=3
```

Set `HYBRID_SYNTH_ENABLED=false` to keep the LightRAG answer unchanged while still attaching matched card references.

## When To Use `rebuild`

`rebuild` is not for normal day-to-day runs. Use it only when you want to recreate the index from current source files.

Run:

```powershell
.\run_pipeline.cmd rebuild
```

What it does:

1. moves the current `rag_storage/` into `rag_storage_backups/`
2. creates a fresh empty `rag_storage/`
3. reloads all normalized source texts
4. reloads all reviewed AI-chat items with `status=processed`

Experimental enriched-card graph rebuild:

```powershell
.\run_pipeline.cmd rebuild --from-enriched
```

## Testing

```powershell
python test_golden_set.py
python -m unittest discover -p "test_*.py" -v
```

If `python` resolves to the Windows Store shim, either activate your environment first or use the real interpreter path.

## Current Readiness

The project is currently set up for:

- Hybrid Intelligence Pipeline (Fetch -> Normalize -> Enrich -> normalized Graph + enriched memory layer)
- Multi-index Retrieval Composer with specialized search modes
- stable path-based LightRAG document IDs
- safe index rebuilds with backup
- reviewed AI-chat ingest during `load` and `run`
- Windows-safe UTF-8 logging and console output
