# Development Return Log

This file tracks blocked checks, deferred decisions, and implementation errors that should be revisited later.
Use `LLM_VERIFICATION_QUEUE.md` for model/live-endpoint checks; use this log for broader development breadcrumbs.

## Pending

- A-lite local ruff report is deferred because `ruff` is not installed in the active Python 3.11 environment.
  CI installs `ruff` explicitly and runs `python -m ruff check . --config pyproject.toml --exit-zero`.
- B2 data cleanup follow-up:
  `python main.py validate enriched` on 2026-05-31 parsed all current enriched cards (`218/218`) with `0` errors and
  `16` warnings. The warnings are non-blocking but should be cleaned later: `11` kept cards have neither `summary` nor
  `key_facts`, and `5` key facts use legacy claim types outside `fact|source_claim|hypothesis` (`claim`, `quote`,
  `thesis`). Report: `artifacts/enriched_validation_20260531_143553.md`.
- Run I3 transcription backfill on real downloaded native media when candidates exist.
  `python main.py transcribe backfill --limit 3 --dry-run` on 2026-05-28 found `0` downloaded
  `video/audio/voice` candidates in current `output/normalized/*.meta.json`, so no old media was modified.
  Rechecked on 2026-05-31 with `python main.py transcribe backfill --limit 5 --dry-run`: still `0` candidates.
  `media_cache/` currently has image files but no local audio/video extensions suitable for transcription.
  Report: `artifacts/transcription_live_check_20260531.md`.
- Re-test paid model candidates only if current DeepSeek V4 Flash quality or latency becomes insufficient.
- Local shell still does not have `git` on PATH, so diff/status checks cannot be run from this session.
  Revisit when commits or repository hygiene become part of the workflow.

## Completed / Notes

- 2026-05-31 B-lite data contracts:
  Added read-only Pydantic contracts in `models.py` for enriched cards, normalized metadata, provenance, key facts,
  references, source ids, wiki page refs, query profiles, and experiment runs. Added soft enriched-card validation in
  `data_validation.py` plus `python main.py validate enriched [--fail-on-error]`; default mode writes a Markdown report
  and does not block on warnings. Added `DATA_CONTRACTS.md` and unit coverage.
  Initial real-corpus validation: `218/218` cards valid, `0` errors, `16` warnings.
  Tests:
  `python -m unittest test_data_contracts test_main.MainQueryTests.test_main_validate_enriched_cli_parses_fail_flag`
  -> 6 tests OK.
- 2026-05-31 A-lite tooling:
  Added `pyproject.toml` with project metadata, dependencies, dev extras, setuptools package/module declarations,
  unittest discovery notes, and ruff report configuration. Added `.pre-commit-config.yaml`, GitHub Actions
  `.github/workflows/unit-tests.yml`, opt-in no-network guard (`GEOSPOILER_NO_NETWORK=1`) via `sitecustomize.py` and
  `testing/no_network.py`, plus README testing/tooling notes.
  Tests:
  `python -m unittest test_no_network` -> 1 test OK.
  `python -m unittest` -> 125 tests OK.
  `GEOSPOILER_NO_NETWORK=1 python -m unittest` -> 125 tests OK.
- 2026-05-31 F4 reranker evaluation:
  Full golden with `RERANKER_ENABLED=true` on `deepseek-v4-flash` scored `20/23`, avg `96.7`, versus the rebuilt
  no-reranker baseline `23/23`, avg `100.0`. Comparison showed `avg_delta=-3.3`, `3` regressions, `0` improvements.
  Regressions were Q1 ultra-left/ultra-right source selection, Q10 US/Cuba pressure-vs-deal wording, and Q21 AfD
  absence wording. `.env` was returned to `RERANKER_ENABLED=false` because reranker is not beneficial for the trusted
  default path.
  Artifacts:
  `artifacts/deepseek_v4_flash_reranker_clearcache_golden_set_scores.json`,
  `artifacts/deepseek_v4_flash_reranker_clearcache_golden_set_results.md`,
  `artifacts/deepseek_v4_flash_reranker_vs_rebuilt_baseline_compare.md`.
- 2026-05-31 K-lite experiment registry/report:
  Added `experiment_registry.py` and `python main.py experiments index` to index local score artifacts into a JSON
  manifest plus compact Markdown report without making any live LLM calls. After retired-model archive cleanup, the
  active registry indexes `8` current score summaries.
  Artifacts:
  `artifacts/experiment_registry.json`,
  `artifacts/experiment_registry.md`.
  Tests:
  `python -m unittest test_experiment_registry test_main.MainQueryTests.test_main_experiments_index_cli_dispatches`
  -> 3 tests OK.
- 2026-05-31 J-final documentation closure:
  Audited and updated `README.md`, `EVAL.md`, `OPERATIONS.md`, and `ARCHITECTURE.md` for the current DeepSeek trusted
  state, local experiment registry, runtime env-var table, and rebuild/recovery runbook. Existing J docs now cover all
  roadmap documents: `ARCHITECTURE.md`, `DATA_CONTRACTS.md`, `OPERATIONS.md`, `EVAL.md`, and `WIKI_MEMORY.md`.
  Tests/checks:
  `python main.py experiments index` -> 18 records before retired-model archive cleanup.
  `python -m unittest test_experiment_registry` -> 2 tests OK.
- 2026-05-31 retired model cleanup:
  Removed retired model references from active documentation and verification queues, and moved its historical artifacts
  out of the top-level experiment registry scan into `artifacts/retired_model_archive/`.
  `python main.py experiments index` -> 8 active records.
- 2026-05-31 provider cleanup before commit:
  Removed retired Google/Vertex runtime hooks from active code: static API-key auth is now the only `llm_auth.py` path,
  `VERTEX_THINKING_LEVEL` and custom provider thinking config were removed from the query option builder, and retired
  Gemini share-link detection was removed from active AI-chat URL patterns. `.env` was removed from Git tracking and
  `.gitignore` now excludes local secrets, logs, state, generated output, and provider setup helpers.
- 2026-05-31 L-lite refactor step 1:
  Added `cli.py` as the first small CLI extraction boundary and moved the `experiments index` command printer out of
  `main.py` while keeping `main.py` as the dispatcher. Added `test_cli.py` and updated packaging metadata for `cli` and
  `experiment_registry` modules.
  Tests/checks:
  `python -m unittest test_cli test_main.MainQueryTests.test_main_experiments_index_cli_dispatches test_experiment_registry`
  -> 4 tests OK.
  `python main.py experiments index` -> 8 active records.
  `python -m unittest` -> 129 tests OK.
- 2026-05-31 L-lite refactor step 2:
  Moved the `validate enriched` CLI helper into `cli.py` while keeping `main.py` as the dispatcher. Added focused CLI
  tests for validation summary output and `--fail-on-error` behavior.
  Tests/checks:
  `python -m unittest test_cli test_main.MainQueryTests.test_main_validate_enriched_cli_parses_fail_flag`
  -> 4 tests OK.
  `python main.py validate enriched` -> 218/218 valid, 0 errors, 16 warnings; report
  `artifacts/enriched_validation_20260531_171300.md`.
  `python -m unittest` -> 131 tests OK.
- 2026-05-31 L-lite refactor step 3:
  Moved `registry rebuild` and `registry resolve` CLI helpers into `cli.py` while keeping `main.py` as the dispatcher.
  Added focused CLI tests for registry rebuild output, source passport output, missing-source output, and `registry
  rebuild` dispatch.
  Tests/checks:
  `python -m unittest test_cli test_main.MainQueryTests.test_main_registry_resolve_cli_passes_source_id
  test_main.MainQueryTests.test_main_registry_rebuild_cli_dispatches`
  -> 8 tests OK.
  `python main.py registry resolve telegram:3328128766:148` -> resolved expected source passport.
  `python -m unittest` -> 135 tests OK.
- 2026-05-31 L-lite refactor step 4:
  Moved `fts rebuild` and `fts search` CLI helpers into `cli.py` while keeping `main.py` as the dispatcher. Added
  focused CLI tests for FTS rebuild output, FTS search output, empty-result hints, shadow comparison output, and `fts
  rebuild` dispatch.
  Tests/checks:
  `python -m unittest test_cli test_main.MainQueryTests.test_main_fts_search_cli_parses_flags
  test_main.MainQueryTests.test_main_fts_rebuild_cli_dispatches`
  -> 11 tests OK.
  `python main.py fts search "Trump Orban" --top-k 2` -> returned expected local FTS matches.
  `python -m unittest` -> 139 tests OK.
- 2026-05-31 L-lite refactor step 5:
  Moved `transcribe backfill` CLI printer into `cli.py` while keeping `main.py` as the dispatcher. The transcription
  backend was not changed. Added focused CLI tests for summary output, item `updated` display, and item error display.
  Tests/checks:
  `python -m unittest test_cli test_main.MainQueryTests.test_main_transcribe_backfill_cli_parses_flags`
  -> 12 tests OK.
  `python main.py transcribe backfill --limit 5 --dry-run` -> 0 attempts, 0 updates, no live transcription call.
  `python -m unittest` -> 141 tests OK.
- 2026-05-31 pre-commit RAG sanity:
  Local checks passed: `python main.py status` -> 220 normalized files and 0 pending reviews; `python main.py wiki health`
  -> 22 pages checked, 0 issues; `python main.py fts search "Trump Orban" --top-k 2` returned expected local FTS matches;
  `python main.py registry resolve telegram:3328128766:148` resolved the expected source passport.
  Unit tests passed: `python -m unittest` -> 140 tests OK after provider cleanup.
  Golden smoke passed: `GOLDEN_CASE_LIMIT=3`, `GOLDEN_QUERY_DELAY_SECONDS=0`, `python test_golden_set.py` -> 3/3,
  avg 100.0. Artifact paths: `artifacts/pre_commit_golden_smoke_results.md`,
  `artifacts/pre_commit_golden_smoke_scores.json`.
- 2026-05-28 I2 transcription MVP exists:
  `normalizer/transcription_handler.py` can call an OpenAI-compatible `/audio/transcriptions` endpoint when
  `TRANSCRIPTION_ENABLED=true`, writes transcript artifacts under `output/transcripts/`, and `normalizer/pipeline.py`
  appends successful native media transcripts into normalized text while preserving media placeholders and sidecar
  metadata. Unit coverage uses mocked transcription calls only; no live Whisper endpoint was verified in unit tests.
- 2026-05-28 I3 controlled transcription backfill exists:
  `normalizer/transcription_backfill.py` and `python main.py transcribe backfill [--limit N] [--channel NAME]
  [--media-type video|audio|voice] [--dry-run]` scan existing normalized sidecar metadata, process a small limited batch,
  append transcripts to existing normalized `.txt` files, and update sidecar transcription metadata. Local dry-run with
  `--limit 3` found no current downloaded native media candidates.
- 2026-05-28 query/synthesis OpenAI chat options are configurable:
  `QUERY_MAX_TOKENS`, `FALLBACK_SYNTH_MAX_TOKENS`, and `LLM_REASONING_EFFORT`.
- 2026-05-28 source-grounding reference priority fix:
  hybrid card/FTS references are merged ahead of LightRAG/wiki references whenever enriched-card context is attached.
  `_extract_query_sources` also falls back to adjacent normalized `.meta.json` sidecars when the persisted RAG metadata
  index contains stale absolute paths, so prioritized local card files resolve back to Telegram post URLs.
- 2026-05-29 controlled rebuild attempt:
  `python main.py fts rebuild` completed with 218/218 cards indexed.
  `python main.py registry rebuild` completed with 220 sources, 220 normalized docs, 218 enriched cards, and 21 references.
  `python main.py rebuild --from-enriched` did not complete in a practical time window. After roughly 50 minutes it had
  only 22/218 enriched cards in the new `rag_storage` (~10.1%), with doc statuses degrading to failed
  (`13 failed`, `2 processing`, `7 pending` at the last check). The live Python rebuild process was stopped, the partial
  storage was saved as `rag_storage_failed_rebuild_20260529_015124`, and the previous working storage was restored from
  `rag_storage_backups/rag_storage_20260529_005659`.
  Post-restore checks: `rag_storage` has 220 processed doc statuses, `python main.py status` reports 220 normalized files
  and 0 pending reviews, `python main.py wiki health` reports 22 pages and 0 issues, and `python main.py fts search
  "Trump Orban" --top-k 3` returns expected FTS results.
- 2026-05-30 DeepSeek V4 Flash switch:
  `.env` LLM role endpoints were moved onto the OpenAI-compatible DeepSeek endpoint with `deepseek-v4-flash` for base
  LLM, build, query, enrichment, fallback synthesis, and translation.
  `LLM_AUTH_PROVIDER` and `LLM_REASONING_EFFORT` are empty for this provider.
  DeepSeek V4 defaults to thinking mode and can return `reasoning_content` without visible `content`, so the chat
  option builders now send `thinking: disabled` for DeepSeek V4 when no reasoning effort is configured. This is covered
  for LightRAG/OpenAI SDK calls plus requests-based enrichment and translation calls.
  Smoke-test returned visible content (`working`) with no `reasoning_content`; unit tests passed (`python -m unittest`,
  117 tests OK).
- 2026-05-30 DeepSeek absence-control wording fix:
  `_postprocess_answer_text` now treats DeepSeek-style "no direct answer" / "sources do not contain information"
  wording as an absence-control answer and appends the expected "absent / cannot determine" Russian markers.
  Unit coverage added for this wording.
  Tests:
  `python -m unittest test_loader.AnswerPostprocessTests` -> 4 tests OK.
  `python -m unittest` -> 118 tests OK.
  Focused clear-cache live probe with `deepseek-v4-flash`, `RERANKER_ENABLED=false`, `HYBRID_SYNTH_ENABLED=true`,
  and `WIKI_ENABLED=true` scored `6/6`, avg `100.0`, avg duration `11.487s`, with no `NoneType.content` failures.
  All source checks passed (`source_ok/source_any_ok=Y/Y`), including F1 Trump/Orban, Q9 Cuba protests,
  Q22 Narva visuals, North Korea source-control, and the AfD funding absence-control.
  Artifacts:
  `artifacts/llm_probe_deepseek_v4_flash_absence_fix_clearcache_scores.json`,
  `artifacts/llm_probe_deepseek_v4_flash_absence_fix_clearcache_results.md`.
- 2026-05-30 DeepSeek V4 Flash full golden check:
  - Pre-rebuild run: full golden set on `deepseek-v4-flash` with cleared LLM cache, `RERANKER_ENABLED=false`,
    `HYBRID_SYNTH_ENABLED=true`, and `WIKI_ENABLED=true`.
    Result: `23/23` passed, average score `100.0` (E2 baseline comparison showed `+1.3` average delta and `0` regressions).
    Artifacts: `artifacts/deepseek_v4_flash_clearcache_golden_set_scores.json`,
    `artifacts/deepseek_v4_flash_clearcache_golden_set_results.md`,
    `artifacts/deepseek_v4_flash_clearcache_vs_e2_compare.md`.
  - Post-rebuild validation run: full golden set on the newly rebuilt graph with zero delay and empty cache.
    Result: `23/23` passed, average score `100.0`, confirming `0` regressions and identical perfect results.
    Artifacts:
    `artifacts/deepseek_v4_flash_rebuilt_clearcache_golden_set_scores.json`,
    `artifacts/deepseek_v4_flash_rebuilt_clearcache_golden_set_results.md`,
    `artifacts/deepseek_v4_flash_rebuilt_clearcache_vs_e2_compare.md`,
    `artifacts/deepseek_v4_flash_rebuilt_vs_pre_rebuild_compare.md`.
- I1 media capture metadata exists:
  Telegram native `video`, `audio`, and `voice` attachments are captured into structured `media`
  metadata with `download_status`, `mime_type`, and `file_path` when downloaded.
  Normalized text still keeps non-transcribed placeholder lines only; transcription remains I2.
- F2 comparison tooling exists:
  `golden_compare.py`, `GOLDEN_RESULTS_FILE`, `GOLDEN_SCORES_FILE`, and `GOLDEN_CASE_LIMIT`.
- F3 synthesis prompt now receives compact wiki context when `HYBRID_SYNTH_ENABLED=true`.
- G1 SQLite FTS5 MVP exists:
  `retrieval/card_fts.py`, `python main.py fts rebuild`, and `python main.py fts search "query" [--top-k N] [--compare-shadow]`.
  Local sanity on 2026-05-27 indexed 218/218 enriched cards and returned relevant `Trump Orban` sources.
- G2 composer now uses SQLite FTS5 before `shadow_search` for `recall` and `shadow/cards/cards-only` modes.
  `shadow_search.py` remains a compatibility fallback when FTS is empty or unavailable.
- H1 source registry MVP exists:
  `retrieval/source_registry.py`, `python main.py registry rebuild`, and `python main.py registry resolve SOURCE_ID`.
  Local sanity on 2026-05-27 rebuilt `artifacts/source_registry.sqlite` with 220 sources, 220 normalized docs,
  218 enriched cards, and 21 references; `telegram:3328128766:148` resolved to post URL plus normalized/enriched paths.
- H2 wiki resolver now consults `source_registry.sqlite` before falling back to enriched JSON/files.

## Implementation Errors Fixed

- 2026-05-27: `test_golden_set.py` had an indentation error after adding golden output path overrides.
  Fixed and covered by `test_golden_set_unit`.
- 2026-05-27: first G1 FTS unit test left `card_fts.sqlite` locked on Windows because `sqlite3.Connection`
  context managers commit/rollback but do not close the connection.
  Fixed `retrieval/card_fts.py` to use explicit `contextlib.closing`.
- 2026-05-27: first H1 source registry test repeated the same Windows SQLite lock pattern in test code.
  Fixed `test_source_registry.py` to use explicit `contextlib.closing`.
- 2026-05-27: H2 manual registry sanity resolved the source correctly, then PowerShell/Python stdout failed on
  Cyrillic paths with `UnicodeEncodeError: cp1252`.
  Use `PYTHONIOENCODING=utf-8` for inline scripts that print Cyrillic paths.
