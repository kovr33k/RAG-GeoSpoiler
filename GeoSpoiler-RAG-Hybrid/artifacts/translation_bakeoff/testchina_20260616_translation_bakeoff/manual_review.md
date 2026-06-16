# Testchina Translation Bakeoff Manual Review

Run: `artifacts/translation_bakeoff/testchina_20260616_translation_bakeoff`

Inputs: the same 10 `testchina` posts used for enrichment bakeoff.

Models:
- `openai/gpt-5.4-nano`
- `google/gemini-3.1-flash-lite`
- `deepseek-v4-flash`

Prompt: project `normalizer.translator.TRANSLATOR_SYSTEM_PROMPT`.

## Technical Summary

| Model | Outputs | Errors | Empty | Prompt tokens | Completion tokens | Est. cost | Avg latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| `openai/gpt-5.4-nano` | 10 | 0 | 0 | 8840 | 6908 | $0.01040300 | 6387.6 ms |
| `google/gemini-3.1-flash-lite` | 10 | 0 | 0 | 8543 | 6740 | $0.01224575 | 3275.9 ms |
| `deepseek-v4-flash` | 10 | 0 | 0 | 10563 | 7714 | $0.00363874 | 6971.7 ms |

## Key Findings

### `openai/gpt-5.4-nano`

Good on most posts, but not reliable enough with the current project translation prompt.

Strong points:
- Preserved all Russian posts exactly.
- Good Russian style on Ukrainian posts 2, 3, 4, 12, and 13.
- Preserved sensitive Taiwan/China/Russia/Belarus claims where it translated.

Critical issue:
- Post `11` was left almost entirely in Ukrainian instead of being translated to Russian.

This is a practical failure for `TRANSLATION_MODEL`: if one Ukrainian post enters the normalized corpus untranslated, later enrichment/search becomes less consistent.

### `google/gemini-3.1-flash-lite`

Good and fast translation model.

Strong points:
- Translated all Ukrainian posts into Russian.
- Fastest model in this run.
- Preserved key names, amounts, dates, and politically sensitive claims.

Weak points:
- On Russian post `5`, it did not return the text exactly as-is; it reformatted bullet/list markup.
- On post `13`, it left the channel call-to-action title `"Ціну держави"` untranslated, which is minor because it is a brand/channel name.
- More expensive than GPT nano and much more expensive than DeepSeek in this run.

### `deepseek-v4-flash`

Best price/value result in this translation test.

Strong points:
- Translated all Ukrainian posts into Russian.
- Preserved all Russian posts exactly.
- Cheapest by a large margin.
- No visible softening, omission, or CCP-friendly rewrite on these China-sensitive posts.
- Preserved the main sensitive claims: Taiwan blockade, China-Belarus ammunition line, China/Thailand drone re-export, Chinese port control in Africa.

Weak points:
- Slightly slower than Gemini.
- Still carries provider/jurisdiction trust concerns for a China-sensitive corpus, even though this test did not show censorship or propaganda drift.

## Per-Post Result

| Post | Best | Second | Third | Notes |
|---:|---|---|---|---|
| 2 | DeepSeek | Gemini | GPT nano | All three good. DeepSeek/Gemini read most naturally; no sensitive omission. |
| 3 | Gemini | DeepSeek | GPT nano | All good. Gemini/DeepSeek slightly cleaner; nano left one Ukrainian CTA line. |
| 4 | GPT nano | DeepSeek | Gemini | All good; short post, no meaningful difference. |
| 5 | GPT nano / DeepSeek | Gemini | - | Russian identity test: GPT nano and DeepSeek exact; Gemini reformatted bullets. |
| 6 | Tie | Tie | Tie | Russian post preserved exactly by all three. |
| 7 | Tie | Tie | Tie | Russian post preserved exactly by all three. |
| 9 | Tie | Tie | Tie | Russian post preserved exactly by all three. |
| 11 | DeepSeek | Gemini | GPT nano | GPT nano failed: left post in Ukrainian. |
| 12 | DeepSeek | GPT nano | Gemini | All good; DeepSeek strongest balance of literalness and clean Russian. |
| 13 | DeepSeek | GPT nano | Gemini | All good; Gemini left one Ukrainian channel title in CTA, minor. |

## Final Ranking

For pure translation quality under the current project prompt:

1. `deepseek-v4-flash`
2. `google/gemini-3.1-flash-lite`
3. `openai/gpt-5.4-nano`

If using only Western models:

1. `google/gemini-3.1-flash-lite`
2. `openai/gpt-5.4-nano`

Recommended `TRANSLATION_MODEL`:

```env
TRANSLATION_MODEL=deepseek-v4-flash
```

If the project policy is "no Chinese model before enrichment" for trust reasons:

```env
TRANSLATION_MODEL=google/gemini-3.1-flash-lite
```

I do not recommend `openai/gpt-5.4-nano` as translation default unless the translation prompt is strengthened and retested, because it left post `11` untranslated.
