# Role Fit Review: RAG Build and Fallback Synthesis

Дата: 2026-06-15

Проверенные модели:

- `mistralai/mistral-small-2603`
- `openai/gpt-5.4-nano`
- `google/gemini-3.1-flash-lite`

Проверенные роли:

- `RAG_BUILD_MODEL`
- `FALLBACK_SYNTH_MODEL`

## Артефакты

- Main role-fit run: `artifacts/model_bakeoff/role_fit_mistral_gpt_gemini_20260615_v2`
- LightRAG tuple smoke: `artifacts/model_bakeoff/role_rag_build_tuple_mistral_gpt_gemini_20260615_v3`

Ошибочный tuple-run `role_rag_build_tuple_mistral_gpt_gemini_20260615` не учитывать: там все вызовы получили `401 Unauthorized` из-за неверного ключа в команде запуска.

## Авто-результаты

### Main role-fit run

| Model | Role | Pass | Avg Score | Min Score | Cost |
|---|---|---:|---:|---:|---:|
| `openai/gpt-5.4-nano` | `rag_build` | 8/8 | 100.0 | 100 | `$0.00670340` |
| `mistralai/mistral-small-2603` | `rag_build` | 7/8 | 98.1 | 85 | `$0.00281280` |
| `google/gemini-3.1-flash-lite` | `rag_build` | 6/8 | 94.4 | 70 | `$0.00514400` |
| `openai/gpt-5.4-nano` | `fallback_synth` | 4/8 | 91.2 | 75 | included above |
| `mistralai/mistral-small-2603` | `fallback_synth` | 3/8 | 86.9 | 55 | included above |
| `google/gemini-3.1-flash-lite` | `fallback_synth` | 2/8 | 77.5 | 55 | included above |

### LightRAG tuple smoke

| Model | Pass | Avg Score | Cost |
|---|---:|---:|---:|
| `openai/gpt-5.4-nano` | 3/4 | 96.25 | `$0.00238070` |
| `mistralai/mistral-small-2603` | 0/4 | 77.5 | `$0.00061170` |
| `google/gemini-3.1-flash-lite` | 0/4 | 70.0 | `$0.00142500` |

Tuple postprocess parse counts also favored GPT Nano: it produced more parseable relations and fewer thin extraction records.

## Manual Notes

### RAG Build

`openai/gpt-5.4-nano` was the strongest candidate.

Why:

- Best deterministic scores on both JSON-like build extraction and LightRAG tuple smoke.
- Best preservation of uncertainty and source attribution.
- Better at producing machine-ingestible relation/entity structures.

Caveats:

- More verbose.
- More expensive and slower than Mistral Small.
- Tuple output is not perfect; it can produce extra delimiter fields, but the project postprocessor can still recover useful entities/relations.

`mistralai/mistral-small-2603` is a good budget candidate but not the max-confidence build model.

Main issues:

- In one JSON build case it added a questionable extra note about IRGC aerospace forces needing clarification.
- In tuple mode it used angle brackets around entity names and sometimes thin/empty descriptions.
- It is cheaper, but less clean for LightRAG graph extraction.

`google/gemini-3.1-flash-lite` is not the best fit for `RAG_BUILD_MODEL`.

Main issues:

- Missed exact quote preservation in build extraction.
- In one sanctions case turned "the post does not claim trade stopped" into "trade has not yet stopped".
- In tuple mode it added generic external descriptions like "capital of China" / "island state", which are not source-grounded extraction.

### Fallback Synthesis

`openai/gpt-5.4-nano` had the highest automatic fallback score and the best complex reasoning/grounding in most cases.

Manual caveat:

- In the noisy-context case it repeated an internal file path (`output/enriched/...json`) despite the instruction not to expose internal details. This is a real blemish, not just a scorer artifact.

`mistralai/mistral-small-2603` was surprisingly strong for fallback.

Why:

- Concise, grounded Russian answers.
- Did not expose internal technical paths in the noisy-context case.
- Preserved uncertainty well in the dual-use and direct-control questions.

Caveats:

- Sometimes less complete than GPT Nano.
- Can omit secondary attribution like `Financial Times` when it already names the local source id/file.

`google/gemini-3.1-flash-lite` is acceptable but weaker for fallback.

Main issues:

- More deterministic misses.
- In one direct-control case it phrased absence of proof too close to a negative factual claim.
- Less reliable at exact source-id/file preservation.

## Final Recommendation

If optimizing for maximum quality/confidence:

```env
RAG_BUILD_MODEL=openai/gpt-5.4-nano
FALLBACK_SYNTH_MODEL=openai/gpt-5.4-nano
```

If optimizing for cost while staying strong:

```env
RAG_BUILD_MODEL=mistralai/mistral-small-2603
FALLBACK_SYNTH_MODEL=mistralai/mistral-small-2603
```

My preferred production split after these tests:

```env
RAG_BUILD_MODEL=openai/gpt-5.4-nano
FALLBACK_SYNTH_MODEL=mistralai/mistral-small-2603
```

Reason: GPT Nano is clearly better for graph/build extraction, where bad extraction can poison memory. Mistral Small is strong enough and safer/cheaper for fallback synthesis, but GPT Nano remains the premium fallback option if cost is secondary.
