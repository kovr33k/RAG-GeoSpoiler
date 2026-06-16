# Testchina Enrichment Bakeoff Manual Review

Run: `artifacts/enrichment_bakeoff/testchina_20260616_enrichment_bakeoff`

Inputs: 10 Telegram posts from `testchina`, message IDs `2, 3, 4, 5, 6, 7, 9, 11, 12, 13`.

Gold: `gold_codex.json`, written before reviewing model outputs.

## Technical Summary

| Model | Cards | LLM calls | Empty summaries | Prompt tokens | Completion tokens | Est. cost | Avg latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| `mistralai/mistral-small-2603` | 10 | 18 | 0 | 21116 | 22019 | $0.01637880 | 8481.7 ms |
| `openai/gpt-5.4-nano` | 10 | 18 | 0 | 20906 | 25974 | $0.03664870 | 11658.4 ms |
| `google/gemini-3.1-flash-lite` | 10 | 18 | 2 | 18665 | 13163 | $0.02441075 | 4877.7 ms |
| `deepseek-v4-flash` | 10 | 18 | 0 | 22342 | 15857 | $0.00756784 | 7749.2 ms |

Gemini had two parse failures that produced empty cards: posts `5` and `9`.

## Per-Post Winners

| Post | Best | Second | Third | Fourth | Notes |
|---:|---|---|---|---|---|
| 2 | GPT nano | DeepSeek | Mistral | Gemini | GPT kept source-claim framing and nearly all gold points. Mistral added an unsupported year to the March 18 event and called the text a video. Gemini was too compressed. |
| 3 | GPT nano | DeepSeek | Mistral | Gemini | GPT best preserved Taiwan, blockade, arms packages, Trump quotes, and Taiwan MFA response. DeepSeek was concise but accurate. |
| 4 | GPT nano | Mistral | Gemini | DeepSeek | GPT was the cleanest. Mistral preserved details but left `openly` in English. DeepSeek was accurate but too sparse. |
| 5 | GPT nano | Mistral | DeepSeek | Gemini | Gemini produced an empty card. GPT captured the full Africa/neocolonialism structure. Mistral was strong but less disciplined. |
| 6 | GPT nano | Mistral | Gemini | DeepSeek | GPT captured TEE-01B, Emposat, IRGC, Russia, and Chang Guang. DeepSeek was accurate but left too much in summary rather than facts. |
| 7 | GPT nano | Mistral | DeepSeek | Gemini | GPT best preserved the Foreign Affairs logic, energy/export numbers, Taiwan transfer, and Europe/Japan market risk. |
| 9 | GPT nano | Mistral | DeepSeek | Gemini | Gemini produced an empty card. GPT captured Paracels, 6 sq km, military infrastructure, disputes, and Taiwan-route logic. |
| 11 | GPT nano | Mistral | DeepSeek | Gemini | GPT best preserved all port/resource numbers and the final logistics/political/data-control conclusion. Gemini mixed Russian/Ukrainian and lost details. |
| 12 | GPT nano | Mistral | DeepSeek | Gemini | GPT was most complete and in Russian. Mistral preserved many facts but answered in Ukrainian, which is bad for this project. |
| 13 | GPT nano | DeepSeek | Mistral | Gemini | GPT best preserved the Thailand re-export chain, sanctions, company names, and amounts. DeepSeek was very good. Mistral had one risky wording: Autel EVO Max 4T was described as used in combat “in Russia”. |

## Model Findings

### 1. `openai/gpt-5.4-nano`

Best quality overall.

Strengths:
- Most complete extraction against the Codex gold.
- Best source-fidelity discipline: often writes “в посте утверждается” / `source_claim`.
- Best on long posts with many numbers and actors.
- Best Russian output consistency.
- Best fit if enrichment quality is the priority.

Weaknesses:
- Most expensive in this run: about 2.24x Mistral and 4.84x DeepSeek.
- Sometimes verbose: more facts than strictly necessary.
- Occasionally returns entities as structured objects that project normalization stringifies.

### 2. `mistralai/mistral-small-2603`

Good, but not the quality winner.

Strengths:
- High recall on most posts.
- Strong on Africa, satellite, port, and Belarus production posts.
- Better than DeepSeek when many details must be preserved in facts.
- Much cheaper than GPT nano.

Weaknesses:
- Repeatedly called text posts “Видео”.
- Post 12 came back mostly in Ukrainian, despite the project expecting Russian enrichment fields.
- Sometimes produced odd mixed language (`openly`) or object-like entity strings.
- Needs code/prompt hardening before being fully safe as a mass default.

### 3. `deepseek-v4-flash`

Surprisingly viable and very cheap, but more compressed.

Strengths:
- No empty cards.
- No visible China-party propaganda, censorship, or softening on these 10 posts.
- Strong on the most sensitive China/Russia/Belarus/Thailand posts.
- Cheapest by a large margin.
- Clean Russian more often than Mistral on Ukrainian inputs.

Weaknesses:
- Often too short: fewer key facts, weaker search surface.
- Some important details remain only in summary or are omitted from facts.
- Less ideal for building rich memory cards where recall matters.
- Still has production trust concerns for China-sensitive input because it is a Chinese model, even though this sample did not show manipulation.

### 4. `google/gemini-3.1-flash-lite`

Not recommended for enrichment.

Strengths:
- Fastest average latency.
- Usually writes clean summaries when it does not fail.

Weaknesses:
- Two empty cards out of ten due JSON parse failures.
- Too compressed on complex posts.
- Loses many numbers, company names, and source-chain details.
- Mixed language in at least one card.
- Better suited to translation than enrichment in this project.

## Final Ranking

Quality ranking:

1. `openai/gpt-5.4-nano`
2. `mistralai/mistral-small-2603`
3. `deepseek-v4-flash`
4. `google/gemini-3.1-flash-lite`

Price/value ranking:

1. `deepseek-v4-flash`
2. `mistralai/mistral-small-2603`
3. `openai/gpt-5.4-nano`
4. `google/gemini-3.1-flash-lite`

Recommended `ENRICHMENT_MODEL` after this real-post test:

```env
ENRICHMENT_MODEL=openai/gpt-5.4-nano
```

If cost matters more than maximum quality:

```env
ENRICHMENT_MODEL=mistralai/mistral-small-2603
```

DeepSeek Flash is good enough to keep as a cheap experimental/budget option, but I would not make it the default for a China-sensitive corpus unless price is the overriding constraint.
