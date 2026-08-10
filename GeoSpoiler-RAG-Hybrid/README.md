# GeoSpoiler-RAG

Telegram-to-RAG pipeline for collecting posts, normalizing linked content, and loading a LightRAG knowledge base you can query locally.

## What It Does

The pipeline can:

- fetch new messages from Telegram channels in a chosen Telegram folder
- normalize plain text, web pages, YouTube links, Instagram links, and reviewed manual-queue items
- build enriched v2 cards and refresh local card/source/semantic indexes automatically
- explicitly load enriched v2 graph text into LightRAG when needed
- answer questions over the resulting knowledge graph

## Project Layout

- `main.py` — thin CLI entry point
- `cli_app.py`, `cli_pipeline.py`, `cli_query.py`, `cli_tools.py` — command routing and CLI command groups
- `loader/` — focused LightRAG factory, ingest, storage, query, and card-context modules
- `run_pipeline.ps1` — Windows-friendly runner with UTF-8 and Python resolution
- `run_pipeline.cmd` — wrapper that bypasses restrictive PowerShell execution policies
- `auth.py` — one-time Telegram authorization
- `output/normalized/` — immutable normalized `.txt` source archive for enrichment
- `output/review_queue/` — manual review queue for AI chat shares, external links that need human triage, long Instagram Reels, and low-information posts
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
python main.py search "связь и управление" --mode recall
```

## Text LLM Profiles

The default `LLM_PROFILE=luna` routes text generation through the authenticated
Codex CLI and the Codex subscription, without a text-LLM API key. The selected
model must be available to the local Codex installation:

```env
LLM_PROFILE=luna
CODEX_LUNA_MODEL=gpt-5.6-luna
CODEX_LUNA_REASONING_EFFORT=xhigh
```

The Luna profile covers enrichment, LightRAG build/query, answer synthesis,
translation, and the Instagram text summary. It does not
replace transcription, Vision, embeddings, or reranking. The profile can also
be selected for one command without changing `.env`:

```powershell
python main.py enrich --llm-profile luna
python main.py query --llm-profile luna "What is the source saying about Taiwan?"
```

Codex calls run through an isolated read-only CLI process with concurrency 1.
The configured reasoning effort is passed explicitly even though the isolated
process ignores the user's global Codex configuration. The model identity
stored in generated metadata includes the effort, for example
`codex-cli:gpt-5.6-luna@xhigh`.
API fallback is disabled by default (`CODEX_FALLBACK_TO_API=false`). Gemini
transcription/Vision and Qwen embeddings remain separate OpenRouter-backed
services. Switching between `current` and `luna` does not by itself force card regeneration;
`REGENERATE_ON_PROFILE_CHANGE=true` enables that behavior.

The selected profile is also passed to the separate Streamlit Reviewer process,
including when Reviewer is opened automatically after `run`. A live Luna check
is deliberately opt-in and makes only two calls:

```powershell
python scripts/luna_smoke.py --confirm-live
```

The command requires `LLM_PROFILE=luna`, an exact `CODEX_LUNA_MODEL`, and the
explicit confirmation flag. It writes only to a temporary runtime directory
and does not run enrichment or LightRAG.

## Search & Retrieval

By default (`LATE_FUSION_ENABLED=false`) normal `query` preserves the existing
hybrid path: it asks LightRAG first, then adds strong matches from enriched
memory cards as additional context. The minimal Late-Fusion V1 path can be
enabled only after its acceptance run: it retrieves LightRAG data, Enriched FTS
cards and YouTube segments in parallel, hydrates selected evidence, then makes
one final cited Luna synthesis call. It preserves Enriched-first ingest and
excludes Wiki from this new path.

The system also features a multi-index **Retrieval Composer** that supports different search modes depending on your analytical needs:

- **recall**: Broadest search. Combines LightRAG's hybrid retrieval with a BM25 shadow search. Good for general queries.
- **thesis**: Focuses on high-level analytical claims and theses extracted during the enrichment phase.
- **entity**: Strict search for specific actors, organizations, or locations.
- **shadow**: Fast cards-only keyword search over enriched cards. Does not call LightRAG or an LLM.

## Recommended Workflow

### Full automatic flow

```powershell
.\run_pipeline.cmd run
```

This will:

1. fetch new Telegram messages
2. normalize them into `output/normalized/`
3. **enrich** them into structured memory cards `output/enriched/`
4. rebuild card FTS and the source registry
5. leave the dormant Wiki untouched while `WIKI_ENABLED=false`
6. open the browser reviewer only when the content queue needs a decision

LightRAG is not changed by the automatic run; use `load` as a separate explicit
command.

### Approved-concept Wiki

Wiki is a reviewed navigation layer over Enriched cards, not an automatically
expanding encyclopedia:

It is preserved but disabled by default. Set `WIKI_ENABLED=true` to restore
Wiki ingest, review, projections, FTS, CLI commands, and optional query context.
Existing Wiki SQLite state is not deleted while the feature is disabled.

- only user-approved entities/topics receive hubs;
- identity-equivalent aliases such as `КНДР`, `Северная Корея`, and `DPRK`
  resolve to one concept;
- with the Luna profile active, inflected forms such as `Европа`, `Европе`, and
  `Европы` are proposed as one reviewable identity group with claim/event
  context; a lone form such as `Украиной` can be proposed as `Украина`, and
  nothing is normalized or merged before approval;
- a registry proposal requires two independent substantive content clusters;
- claim occurrences remain immutable; exact duplicates share a reversible
  claim group instead of being physically merged;
- one card may contribute to several hubs with `subject`, `actor`, `object`,
  `context`, or `mentioned` roles;
- contextual metonyms are resolved per claim and never become aliases;
- Luna may propose identity/hierarchy/ambiguity decisions, but only the user
  changes authoritative state;
- SQLite is system state, Enriched cards are source material, generated
  Markdown hubs are disposable, and `wiki_sidecars/` is authoritative manual
  Markdown.

Useful commands:

```powershell
python main.py wiki run
python main.py wiki run --llm-profile luna
python main.py wiki run --no-luna
python main.py wiki rebuild
python main.py wiki search "Китай ракетная программа"
python main.py wiki status
python main.py wiki review
```

### Enriched Memory Layer

During the **enrich** stage, the system uses an LLM to extract a compact semantic payload: summaries, key points, entities, topics, quotes, theses, and events. These are saved as strict `enriched_v2` `*.enriched.json` files.

Enriched cards are the working memory/retrieval layer. `python main.py load`
explicitly loads only `enriched_v2` `graph_text` into LightRAG; it never falls
back to normalized source text.

Before a full v2 regeneration, use the isolated pilot harness. The default is a
read-only dry-run that prints a deterministic representative sample and an LLM
call estimate. The sample contains exactly one YouTube transcript; every other
YouTube candidate is excluded even when it also looks like a forward or an
Instagram post:

```powershell
python scripts/enriched_v2_pilot.py
python scripts/enriched_v2_pilot.py --run --limit 12 --run-id pilot-v2-001
# Require the selected YouTube sample to exercise real segmentation:
python scripts/enriched_v2_pilot.py --run --limit 12 --require-long-youtube --run-id pilot-youtube-long-001
```

The live form requires the explicit `--run` flag and writes only under
`artifacts/enriched_v2_pilot/<run-id>/`. It rebuilds temporary FTS and source
indexes, validates every card against its exact selected source,
runs required self-recall at `top_k=10`, and writes `report.json` plus
`report.md`. The self-derived check is labeled `self_recall`; it is never
reported as a golden test. With `--require-long-youtube`, the report also checks
that the episode manifest is complete, all child segments exist, and the segment
FTS index contains them. The harness does not call LightRAG.

Long YouTube enrichment checkpoints are kept under `state/youtube_checkpoints`
until the episode generation is committed. Completed-card freshness remains
profile-independent when configured that way, but resumable checkpoints include
the active enrichment model, so `current` and `luna` can never share an
in-progress segment generation.

Pilot output is rejected when it equals, contains, or is inside live output,
normalized, enriched, state, RAG, or SQLite paths. The check happens
before any pilot directory is created. The default artifacts location is
allowed.

For a real retrieval gate, provide a curated JSON manifest. Each expectation
must refer to source IDs in the selected pilot or to selected normalized files:

```json
{
  "queries": [
    {
      "query": "North Korea intercontinental ballistic missile program",
      "must_find_source_ids": ["telegram:123:456"]
    },
    {
      "query": "UK SAFE accession fee dispute",
      "must_find_normalized_files": ["channel/000000789.txt"]
    }
  ]
}
```

Run it with a configurable cutoff (default `20`):

```powershell
python scripts/enriched_v2_pilot.py --run --limit 12 --run-id pilot-v2-001 `
  --golden-manifest .\pilot_golden.json --golden-top-k 20
```

A configured golden miss makes the command fail. Self-recall is required even
without a manifest. Call estimates distinguish nominal model calls, the
theoretical maximum model calls with one repair per card, and the theoretical
maximum HTTP requests when every model call uses the HTTP 400 fallback.

Hybrid query controls:

```env
HYBRID_QUERY_CARDS_ENABLED=true
HYBRID_SYNTH_ENABLED=true
HYBRID_QUERY_CARDS_TOP_K=3
```

Set `HYBRID_SYNTH_ENABLED=false` to keep the LightRAG answer unchanged while still attaching matched card references.

Late-Fusion V1 controls and acceptance harness:

```env
LATE_FUSION_ENABLED=false
LATE_FUSION_CARD_TOP_K=30
LATE_FUSION_YOUTUBE_TOP_K=15
LATE_FUSION_MAX_SOURCES=20
LATE_FUSION_MAX_INPUT_TOKENS=120000
LATE_FUSION_FTS_TIMEOUT_SECONDS=120
WIKI_ENABLED=false
HYBRID_QUERY_WIKI_ENABLED=false
```

`LATE_FUSION_MAX_SOURCES` and its input budget are independent; increasing the
source count to 30–40 requires a separately verified input budget. The harness
records a content-based implementation/corpus/config/model/seed identity,
atomically checkpoints every frozen case, and writes blind answer pairs with
the citation URLs needed for review. Resume and scoring fail closed on identity
drift, incomplete cases, fallback, invalid citations/URLs or missing automatic
gates:

```powershell
python scripts/late_fusion_ab.py --output-dir .\artifacts\late_fusion_ab
# After blind review fills reviews.json:
python scripts/late_fusion_ab.py --output-dir .\artifacts\late_fusion_ab --score
```

## When To Use `rebuild`

`rebuild` is not for normal day-to-day runs. Use it only when you want to recreate LightRAG from current enriched v2 cards.

Run:

```powershell
.\run_pipeline.cmd rebuild
```

What it does:

1. moves the current `rag_storage/` into `rag_storage_backups/`
2. creates a fresh empty `rag_storage/`
3. reloads only non-empty `graph_text` from cards with `schema_version=enriched_v2`

Normalized texts and processed review-queue items are not loaded by `load` or `rebuild`.

## Testing

```powershell
python tests/test_golden_set.py
python -m unittest discover -s tests -p "test_*.py" -v
```

If `python` resolves to the Windows Store shim, either activate your environment first or use the real interpreter path.

Unit tests are intended to be no-network. To enforce that locally, run:

```powershell
$env:GEOSPOILER_NO_NETWORK = "1"
python -m unittest discover -s tests -p "test_*.py"
```

Live model checks such as `llm_verification_probe.py`, golden-set model runs, Telegram fetches, and transcription smoke
tests are integration checks, not unit tests.

Developer tooling:

```powershell
python -m pip install -e .[dev]
pre-commit install
python -m ruff check . --config pyproject.toml
python main.py validate enriched
```

Experiment/eval registry:

```powershell
python main.py experiments index
```

This writes `artifacts/experiment_registry.json` and
`artifacts/experiment_registry.md` from existing score artifacts.

## Current Readiness

The project is currently set up for:

- Hybrid Intelligence Pipeline (Fetch -> Normalize -> Enrich -> local indexes)
- Multi-index Retrieval Composer with specialized search modes
- stable path-based LightRAG document IDs
- safe index rebuilds with backup
- explicit enriched-v2-only LightRAG loading
- Windows-safe UTF-8 logging and console output
- read-only data contracts and enriched-card validation
- FTS, source registry, focused probe, golden comparison, and
  experiment registry workflows

Historical trusted live-eval baselines used `deepseek-v4-flash` with reranker;
that model is not part of the default runtime.
disabled. The latest recorded full golden validation passed `23/23` before and
after a clean graph rebuild.
