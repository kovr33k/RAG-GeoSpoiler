# GeoSpoiler RAG Development Roadmap v1.1

Status: Phase 1 completed; Phase 2 is next.

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

- `python -m unittest`
- Full golden set
- Source-selection golden
- `python main.py status`
- `python main.py wiki health`
- GitHub Actions success
- `DEVELOPMENT_RETURN_LOG.md` updated
- `LLM_VERIFICATION_QUEUE.md` updated if live LLM checks were run
- Release commit
- Optional tag: `v1.1.0`
