# Source-Selection Golden

`source_selection_golden.py` is a focused live-eval runner for source grounding.
It checks whether the query pipeline surfaces the canonical evidence sources,
not only whether the final answer text looks plausible.

This runner is separate from the full answer-quality golden set because v1
failures were mostly retrieval/source-selection failures. A model can write a
good-looking answer while the top evidence is adjacent, broad, or wrong.

## Run

Full source-selection golden:

```powershell
python source_selection_golden.py
```

Run one or more cases:

```powershell
$env:SOURCE_GOLDEN_CASE_IDS="q9_cuba_protests_source,q22_narva_visuals_top_source"
python source_selection_golden.py
```

Limit a run while debugging:

```powershell
$env:SOURCE_GOLDEN_CASE_LIMIT="3"
python source_selection_golden.py
```

Override artifact paths:

```powershell
$env:SOURCE_GOLDEN_RESULTS_FILE="artifacts/my_source_results.md"
$env:SOURCE_GOLDEN_SCORES_FILE="artifacts/my_source_scores.json"
python source_selection_golden.py
```

Useful controls:

```text
SOURCE_GOLDEN_CASE_IDS
SOURCE_GOLDEN_CASE_LIMIT
SOURCE_GOLDEN_SOURCE_LIMIT
SOURCE_GOLDEN_QUERY_DELAY_SECONDS
SOURCE_GOLDEN_RESULTS_FILE
SOURCE_GOLDEN_SCORES_FILE
```

If `SOURCE_GOLDEN_QUERY_DELAY_SECONDS` is not set, the runner falls back to
`GOLDEN_QUERY_DELAY_SECONDS`.

## What It Checks

Each case can define:

- required answer markers;
- one or more acceptable canonical source ids, URLs, or normalized file ids;
- a maximum acceptable source rank;
- optional forbidden near-miss sources in the top N results;
- a note explaining why the source is canonical.

Current case families:

- Trump/Orban source selection;
- Cuba talks, protests, and pressure-vs-deal source selection;
- Narva planning and Narva visual/media source selection;
- AfD / Ukraine / Russia source grounding;
- AfD nepotism source grounding;
- ultra-left/right similarity source grounding;
- North Korea troops source-control.

## Current Baseline

Phase 2 baseline on `deepseek-v4-flash`:

```text
Source-selection golden: 9/10 passed, average score 90.0
```

The single failing case is `q22_narva_visuals_top_source`.

Observed issue:

- direct Narva/Estonia visual source `3889026624/2` is present at rank 3;
- broad Baltic visual sources `3889026624/9` and `3889026624/6` occupy ranks 1-2;
- the answer-quality golden can still pass, so this runner keeps the retrieval
  weakness visible.

Artifacts:

```text
artifacts/v1_1_phase2_source_selection_results.md
artifacts/v1_1_phase2_source_selection_scores.json
```

Phase 3 retrieval work should use this failure as the first red case.
