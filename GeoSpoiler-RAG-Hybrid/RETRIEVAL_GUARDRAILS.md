# Retrieval Guardrails

This document tracks deterministic source/answer guardrails that still exist
around the retrieval pipeline. The goal is to keep them visible, avoid confusing
them with model quality, and remove them only after retrieval itself is strong
enough.

## Phase 3 Retrieval Changes

Phase 3 improved card-context retrieval instead of adding a Q22-specific hint:

- `shadow_search._matches_term()` now matches short Slavic inflection variants
  such as `Нарвы` / `Нарву`, while avoiding broad long-prefix collisions such
  as `протесты` / `против`.
- `_shadow_fallback_result()` now separates content/entity terms from generic
  task wording such as `какие`, `можно`, `использовать`, `визуалы`, `ролик`,
  `база`, and `описывает`.
- Card-context candidates are ranked by content-term coverage first, then
  lexical score, with specificity only as a tie-breaker.
- Visual questions keep only the most focused card-context source before graph
  references, so broad visual neighbors do not outrank direct evidence.

This fixed the Phase 2 red case without hardcoding Narva:

```text
q22_narva_visuals_top_source
before: direct Narva source 3889026624/2 at rank 3, broad 3889026624/9 and 3889026624/6 in top 2
after:  direct Narva source 3889026624/2 at rank 1
```

## Active Safety Nets

| Guardrail | Location | Protected failure | Status |
|---|---|---|---|
| Ultra-left/right similarity source hint | `loader/reference_hints.py` | The direct similarity source `3299898370/11` can rank behind adjacent Ursula/ultra-left/right posts. | Active safety net. A no-hint check on 2026-06-01 put `11.txt` at rank 4, so retrieval is not ready to remove it. |
| AfD / АдГ alias wording | `loader/answer_postprocess.py` | The answer may use only the Russian alias `АдГ`, while golden/user questions often say `AfD`. | Active wording safety net. |
| AfD problematic-party Ukraine marker | `loader/answer_postprocess.py` | Broad AfD/Russia answers can omit the Ukraine-support context that exists in the corpus. | Active answer safety net until retrieval and synthesis reliably include the Ukraine evidence. |
| AfD funding absence wording | `loader/answer_postprocess.py` | Correct absence answers may omit explicit `отсутствует` / `нельзя определить` wording. | Active evaluator/user clarity safety net. |
| Ultra-right overview country markers and weak-region cleanup | `loader/answer_postprocess.py` | Overview answers can omit Germany/Russia or over-emphasize weak side mentions like Moldova/Sweden. | Active overview safety net. |
| Card references before graph references | `loader/lightrag_loader.py` | LightRAG graph references can be broad while enriched cards point at direct local evidence. | Downgraded by Phase 3: card context is now content-ranked, and visual questions attach only the most focused card before graph references. |

## Removal Policy

Remove one guardrail at a time only after the relevant source-selection case
passes without it.

Required checks for removal:

```powershell
python -m unittest
python source_selection_golden.py
python test_golden_set.py
```

For ultra-left/right similarity specifically, first make this no-hint check pass:

```text
SOURCE_GOLDEN_CASE_IDS=ultra_left_right_similarity_source
expected: source 3299898370/11 at rank 1 without loader/reference_hints.py
```
