# GeoSpoiler RAG Development Roadmap v1.1

Status: Phase 1 completed; Phase 2 completed; Phase 3 completed; Phase 4 completed; v1.1.0 release checklist completed.

Purpose: harden the working v1 system without changing its product direction. v1.0.0 is already a usable release:
unit tests are green, GitHub Actions is green, the final DeepSeek V4 Flash golden run passed `23/23`, and the
normal normalized-source rebuild path has been validated. v1.1 focuses on maintainability, source-grounding quality,
retrieval robustness, and removal of experimental rebuild paths from the main workflow.

Do not start a later phase until the previous phase has been verified and accepted.

## Phase 1: Architecture Split Without Behavior Changes

Goal: make the code easier to develop while preserving current RAG behavior.

Completion note, 2026-06-01:
- Created `loader/clients.py` for OpenAI-compatible chat/embedding client helpers.
- Created `loader/answer_postprocess.py` for no-context/corrupt-answer detection, funding/visual question helpers,
  and deterministic answer wording guardrails.
- Created `loader/reference_hints.py` for reference merging, source path normalization, and deterministic source hints.
- Kept `loader/lightrag_loader.py` as the main LightRAG creation, insert, and query orchestration module.
- Verification:
  `python -m unittest` -> `145` tests OK;
  CI-like offline unit discovery without API keys -> `145` tests OK;
  full golden -> `23/23`, average `100.0`;
  `python main.py status` -> `220` normalized files and `0` pending reviews;
  `python main.py wiki health` -> `22` pages checked, `0` issues.

Rules:
- Treat this as refactor-only work.
- Do not change retrieval behavior, prompt policy, golden cases, or scoring logic in this phase.
- After each small extraction, run targeted tests.
- At the end, run the full unit suite and full golden set.

Baseline checks before editing:
- `python -m unittest`
- final full golden set
- `python main.py status`
- `python main.py wiki health`
- Git status check

Planned module split:
- Move OpenAI-compatible LLM and embedding client setup out of `loader/lightrag_loader.py`.
- Move answer postprocessing and wording guardrails out of `loader/lightrag_loader.py`.
- Move source/reference helper logic out of `loader/lightrag_loader.py`.
- Keep `loader/lightrag_loader.py` focused on LightRAG creation, insert orchestration, and query orchestration.

Suggested target modules:
- `loader/clients.py`
- `loader/answer_postprocess.py`
- `loader/reference_hints.py`
- Optional later split: `loader/query_pipeline.py`

Acceptance criteria:
- Public CLI behavior is unchanged.
- Full unit suite passes.
- Full golden set remains `23/23`.
- GitHub Actions passes.
- No manual data cleanup is required.

## Phase 2: Source-Selection Golden Expansion

Goal: test whether RAG retrieves the correct evidence, not only whether the final answer text looks correct.

Completion note, 2026-06-01:
- Added `source_selection_golden.py` as a dedicated live source-grounding runner.
- Added `test_source_selection_golden.py` with unit coverage for source scoring, forbidden top sources, slash/backslash
  source matching, selected-case mode, and case limits.
- Added `SOURCE_SELECTION_GOLDEN.md` with run commands, environment controls, scoring purpose, and current baseline.
- Current measured v1.1 baseline:
  focused selected run `q9_cuba_protests_source` -> `1/1`, average `100.0`;
  full source-selection golden -> `9/10`, average `90.0`.
- The suite catches the known Q22 Narva visuals retrieval weakness:
  direct Narva source `3889026624/2` appears at rank 3 while broad Baltic visual sources `3889026624/9` and
  `3889026624/6` occupy ranks 1-2.
- This is intentionally left as Phase 3 retrieval work; Phase 2 only expands measurement.
- Final Phase 2 verification:
  `python -m unittest` -> `151` tests OK;
  full golden -> `23/23`, average `100.0`;
  `python main.py status` -> `220` normalized files and `0` pending reviews;
  `python main.py wiki health` -> `22` pages checked, `0` issues;
  `python main.py experiments index` -> `19` active records.

Why this matters:
The main v1 quality failures were not general LLM failures. They were retrieval/source-grounding failures where the
answer could be plausible while the supporting source was weak, adjacent, or wrong.

Add a dedicated source-selection section to the golden set or a separate source-selection golden runner.

Each source-selection case should include:
- Question.
- Required answer markers.
- Required source path, source id, URL, or normalized file id.
- Optional forbidden sources for known near-miss documents.
- Short note explaining why this source is canonical.

Initial case families:
- Trump/Orban source selection.
- Cuba protests source selection.
- Narva visuals and media/visual evidence source selection.
- AfD / Ukraine / Russia source grounding.
- Ultra-left/right similarity source grounding.
- Questions where a nearby topic is semantically similar but not the correct source.

Suggested runner modes:
- Full golden: answer quality plus source validation.
- Source-only golden: fast source retrieval validation for iteration.
- Selected-case mode for debugging one failing source case.

Acceptance criteria:
- Source-selection golden exists and is documented.
- Current v1 behavior is measured before retrieval changes.
- The suite catches known historical source failures.
- Full golden still passes.

## Phase 3: Retrieval Improvements To Reduce Manual Guardrails

Goal: make correct source retrieval happen in the retrieval layer instead of relying on answer postprocessing.

Completion note, 2026-06-01:
- Added content-aware card-context ranking in `loader/lightrag_loader.py`.
- Improved short Russian/Slavic lexical matching in `retrieval/shadow_search.py` while preventing broad prefix
  collisions such as `протесты` vs `против`.
- Visual questions now attach only the most focused card-context source before graph references, preventing broad
  visual neighbors from outranking direct evidence.
- Added regression coverage:
  `test_shadow_search.py`,
  `test_card_context_for_visual_query_keeps_focused_entity_source`,
  and `test_card_context_prioritizes_specific_entity_terms_over_generic_overlap`.
- Added `RETRIEVAL_GUARDRAILS.md` to document active answer/source guardrails, protected failures, and removal policy.
- Measured guardrail removal attempt:
  disabling the ultra-left/right reference hint still puts source `3299898370/11` at rank 4, so it remains an active
  documented safety net rather than being removed.
- Source-selection improvement:
  Phase 2 baseline -> `9/10`, average `90.0`;
  Phase 3 final -> `10/10`, average `100.0`.
- Q22 Narva visuals improvement:
  before -> direct source `3889026624/2` at rank 3, broad `3889026624/9` and `3889026624/6` in top 2;
  after -> direct source `3889026624/2` at rank 1, no forbidden top hits.
- Final Phase 3 verification:
  `python -m unittest` -> `155` tests OK;
  full golden -> `23/23`, average `100.0`;
  source-selection golden -> `10/10`, average `100.0`;
  `python main.py status` -> `220` normalized files and `0` pending reviews;
  `python main.py wiki health` -> `22` pages checked, `0` issues;
  `python main.py experiments index` -> `23` active records.

Current guardrails to analyze:
- AfD / AdG alias preservation.
- Ultra-left/right similarity source hint.
- Ultra-right overview weak side-country cleanup.
- AfD problematic-party Ukraine context stabilization.

Process:
1. Document each current guardrail and the exact failure it protects against.
2. For each guardrail, identify the root cause:
   - weak lexical match;
   - missing canonical source priority;
   - source registry lookup gap;
   - overly broad graph retrieval;
   - weak entity matching;
   - query profile mismatch;
   - hybrid merge/ranking problem.
3. Improve retrieval before removing guardrails:
   - add canonical source boosting where justified;
   - strengthen source registry lookup;
   - add or refine provenance/source-question query profile;
   - improve entity-aware filtering;
   - improve graph + FTS + wiki/card hybrid merge behavior;
   - keep weak adjacent documents from outranking direct evidence.
4. Test each improvement against:
   - source-selection golden;
   - full golden;
   - targeted unit tests.
5. Remove guardrails only when retrieval passes without them.

Guardrail removal policy:
- Remove one guardrail at a time.
- Run targeted tests and full golden after each removal.
- If removal causes regression, keep it as a documented safety net and continue improving retrieval.

Acceptance criteria:
- Source-selection golden is stronger than v1 and remains green.
- Full golden remains green.
- At least one manual source/answer guardrail is removed or downgraded to a documented safety net.
- Remaining guardrails are explicitly documented with reasons.

## Phase 4: Remove Enriched Rebuild From The Main Workflow

Goal: stop presenting `rebuild --from-enriched` as a supported release path.

Completion note, 2026-06-02:
- Removed `--from-enriched` from the supported main CLI flow for both `load` and `rebuild`.
- `python main.py load --from-enriched` and `python main.py rebuild --from-enriched` now print an unsupported
  experimental-path message and do not touch `rag_storage/`.
- Normal `python main.py load` and `python main.py rebuild` remain normalized-source workflows.
- Removed enriched rebuild commands from README, Operations, and Architecture docs.
- Added `experiments/enriched_rebuild/README.md` as a historical note for the retired experiment.
- Moved the old enriched rebuild investigation out of live-LLM pending work because it is no longer a supported
  release path.
- Final Phase 4 verification:
  targeted CLI tests -> `4` tests OK;
  `python -m unittest` -> `156` tests OK;
  full golden -> `23/23`, average `100.0`;
  source-selection golden -> `10/10`, average `100.0`;
  `python main.py status` -> `220` normalized files and `0` pending reviews;
  `python main.py wiki health` -> `22` pages checked, `0` issues;
  `python main.py experiments index` -> `25` active records.

Decision:
The official v1/v1.1 rebuild path is the normalized-source rebuild. Enriched cards remain useful as auxiliary retrieval
and context, but rebuilding the graph directly from enriched cards is experimental and not expected to improve answer
quality enough to justify mainline complexity.

Planned work:
- Remove or hide `rebuild --from-enriched` from normal CLI help.
- Move the implementation to an experimental area if worth preserving.
- Document the decision in `DEVELOPMENT_RETURN_LOG.md`.
- Make sure tests and CLI docs point users to normalized-source rebuild.

Possible experimental location:
- `experiments/enriched_rebuild/`

Recommended default:
- Preserve the code only if moving it is cheap and low-risk.
- Otherwise remove the main CLI path and keep the rationale in the development log.

Acceptance criteria:
- Main CLI exposes only supported rebuild paths.
- Normal rebuild still works.
- Unit tests pass.
- Full golden remains green.
- Development log explains that enriched rebuild was an experiment and is not part of the v1.1 release path.

## Final v1.1 Release Checklist

Completion note, 2026-06-02:
- Added `RELEASE_V1_1.md` with final release summary, accepted debt, supported rebuild path, and artifact links.
- `python -m unittest` -> `156` tests OK.
- Full golden set -> `23/23`, average `100.0`.
- Source-selection golden -> `10/10`, average `100.0`.
- `python main.py status` -> `220` normalized files and `0` pending reviews.
- `python main.py wiki health` -> `22` pages checked and `0` issues.
- `python main.py experiments index` -> `27` active records.
- `DEVELOPMENT_RETURN_LOG.md` and `LLM_VERIFICATION_QUEUE.md` updated.
- Release commit and `v1.1.0` tag are the final repository actions.
