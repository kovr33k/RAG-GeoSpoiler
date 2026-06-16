# Western Models Manual Review - 2026-06-15

Manual review of all western-model answers from:

- `artifacts/model_bakeoff/full_western_quality_20260614_final/model_outputs`
- 5 models x 18 cases = 90 answers

Models reviewed:

- `google/gemini-2.5-flash-lite`
- `google/gemini-3.1-flash-lite`
- `mistralai/mistral-large-2512`
- `mistralai/mistral-small-2603`
- `openai/gpt-5.4-nano`

Important caveat: the bakeoff enrichment prompt did not require Russian output, while the real project prompt in `enricher/llm_enricher.py` does. So English enrichment JSON is treated as a model-control caveat, not an automatic failure.

## Executive Ranking

Best by role:

| Role | Best quality | Best cost/quality | Avoid as default when |
|---|---|---|---|
| Translation | `google/gemini-3.1-flash-lite` | `mistralai/mistral-small-2603` | `google/gemini-2.5-flash-lite` if every nuance must survive |
| Enrichment JSON | `openai/gpt-5.4-nano` | `mistralai/mistral-small-2603` after schema hardening | `mistralai/mistral-large-2512` if cost/latency matters |
| Query answers | `mistralai/mistral-small-2603` / `openai/gpt-5.4-nano` | `mistralai/mistral-small-2603` | `google/gemini-2.5-flash-lite` for broad/multi-factor questions |
| Script/research packs | `openai/gpt-5.4-nano` / `mistralai/mistral-large-2512` | `google/gemini-3.1-flash-lite` | `google/gemini-2.5-flash-lite` when a real pack is needed |

Recommended project setup after manual review:

```env
ENRICHMENT_MODEL=mistralai/mistral-small-2603
TRANSLATION_MODEL=google/gemini-3.1-flash-lite
QUERY_MODEL=mistralai/mistral-small-2603
FALLBACK_SYNTH_MODEL=openai/gpt-5.4-nano
```

For a stricter high-risk setup:

```env
ENRICHMENT_MODEL=openai/gpt-5.4-nano
TRANSLATION_MODEL=google/gemini-3.1-flash-lite
QUERY_MODEL=mistralai/mistral-small-2603
FALLBACK_SYNTH_MODEL=mistralai/mistral-large-2512
```

## Cost, Length, Speed

Final run totals by model:

| Model | Avg output tokens | Avg chars | Avg latency | Cost for 18 cases |
|---|---:|---:|---:|---:|
| `google/gemini-2.5-flash-lite` | 152.9 | 615 | 1.65s | `$0.00138940` |
| `google/gemini-3.1-flash-lite` | 163.7 | 677 | 1.97s | `$0.00514400` |
| `mistralai/mistral-small-2603` | 315.6 | 1091 | 2.84s | `$0.00386055` |
| `openai/gpt-5.4-nano` | 314.1 | 1144 | 3.72s | `$0.00763430` |
| `mistralai/mistral-large-2512` | 259.4 | 1043 | 5.09s | `$0.00843950` |

Interpretation:

- `google/gemini-2.5-flash-lite` is extremely cheap and fast, but sometimes too compressed.
- `google/gemini-3.1-flash-lite` is the best pure translation model in this test.
- `mistralai/mistral-small-2603` is the best general-purpose default for project text work.
- `openai/gpt-5.4-nano` is the best cautious high-risk synthesizer/enricher.
- `mistralai/mistral-large-2512` is good but slow and not clearly better than cheaper alternatives.

## Translation Cases

### `quality_translation_ru_en_001`

All five models preserved:

- attribution: "author of the post"
- Russia full-scale invasion of Ukraine
- officials later denied responsibility for the strike

Best: `google/gemini-3.1-flash-lite`, `google/gemini-2.5-flash-lite`, `openai/gpt-5.4-nano`.

Notes:

- `mistralai/mistral-small-2603` moved attribution to the end: "according to the post's author". This is accurate, just slightly less direct.
- No meaningful failure.

### `quality_translation_uk_ru_001`

All five preserved:

- source attribution
- company linked to Xinjiang supply chains
- Chinese officials deny/refute accusations

Best: `google/gemini-2.5-flash-lite`, `openai/gpt-5.4-nano`.

Notes:

- `openai/gpt-5.4-nano` used "опровергают", which is a good natural Russian rendering.
- `mistralai/mistral-small-2603` used "должностные лица", acceptable but slightly bureaucratic.

### `quality_translation_ru_en_trade_001`

All five preserved:

- author claims/asserts
- China introduced/imposed extraterritorial control
- de minimis threshold 0.1%
- no direct evidence of mass mailings

Best: `google/gemini-3.1-flash-lite`, `mistralai/mistral-small-2603`.

Notes:

- `mistralai/mistral-large-2512` wrote "mass letter distributions", which is accurate but less natural.
- `openai/gpt-5.4-nano` wrote "mass mailing of letters", slightly clunky.

### `quality_translation_uk_en_tibet_001`

All five preserved:

- Beijing
- award to the Dalai Lama
- political manipulation against China
- Foreign Ministry attribution

Best: `openai/gpt-5.4-nano`, `google/gemini-3.1-flash-lite`.

Notes:

- `mistralai/mistral-small-2603` used "spokesman", which adds gender not present in the original "представник". Small issue.
- `openai/gpt-5.4-nano` was the most literal on "Ministry of Foreign Affairs' representative".

### `quality_translation_en_ru_scs_001`

All five preserved the core sense.

Best: `google/gemini-3.1-flash-lite`, `mistralai/mistral-large-2512`.

Notes:

- `google/gemini-3.1-flash-lite` gave the cleanest Russian: "девятипунктирной линии" and "исторических правах".
- `openai/gpt-5.4-nano` wrote "девяти пунктирной линии", awkward Russian.
- `mistralai/mistral-small-2603` added "территориальные претензии"; not wrong, but slightly more interpretive.

### `quality_translation_ru_en_hongkong_001`

All five preserved:

- author/post attribution
- law used to suppress protests
- PRC representatives say/call it necessary for stability

Best: `google/gemini-3.1-flash-lite`, `mistralai/mistral-small-2603`.

Overall translation verdict:

1. `google/gemini-3.1-flash-lite`
2. `mistralai/mistral-small-2603`
3. `openai/gpt-5.4-nano`
4. `google/gemini-2.5-flash-lite`
5. `mistralai/mistral-large-2512`

The ordering is close. None of the western models showed a serious translation failure.

## Enrichment JSON Cases

### `quality_enrich_telegram_dirty_001`

Task: extract a Telegram post with a quote, a pressure claim, an Actor A verification caveat, sarcasm, and no explicit fake label.

Best: `openai/gpt-5.4-nano`.

Good:

- `openai/gpt-5.4-nano` kept Russian, preserved the quote, the caveat, and explicitly noted that there was no direct fake claim.
- `google/gemini-2.5-flash-lite` was concise and mostly accurate.

Caveats:

- `mistralai/mistral-large-2512` added "Actor A may be biased or unreliable" as a thesis. The source only says the data requires verification; bias is an extra inference.
- `mistralai/mistral-small-2603` added "geopolitical pressure" and a more analytical layer than the source strictly gives.
- Gemini outputs were English because the bakeoff prompt did not force Russian.

### `quality_enrich_conflict_claims_001`

Task: two conflicting sources about casualty figures; do not decide who is correct.

Best: `openai/gpt-5.4-nano`, `google/gemini-3.1-flash-lite`.

Good:

- Both cleanly preserved Source A vs Source B and did not adjudicate.

Caveats:

- `mistralai/mistral-large-2512` wrote theses like "officials may have concealed casualty figures"; this is labelled by source, but it is more interpretive.
- `mistralai/mistral-small-2603` put source sentences into `quotes`, even though they were not direct quotes. For the project, that can pollute quote fields.

### `quality_enrich_china_trade_controls_001`

Task: extract China export-control response, de minimis 0.1%, presumption of denial, US high-tech slowdown risk from rare-earth dependence.

Best: `openai/gpt-5.4-nano`.

Good:

- `openai/gpt-5.4-nano` repeatedly marked the content as "Автор утверждает" / "Утверждение", which is exactly right for source-fidelity.
- `mistralai/mistral-small-2603` was detailed and useful, but more verbose.

Caveats:

- `google/gemini-3.1-flash-lite` and `mistralai/mistral-large-2512` phrased some claims as if China did implement the measures, not only that the author says so.
- `mistralai/mistral-large-2512` used `key_facts` as a dict in this case; current project normalizer is safer with list strings or dicts containing `text`.

### `quality_enrich_real_quote_attribution_001`

Task: preserve a direct quote about "legal gray zone" and attribute the Taiwan quarantine/blockade framing.

Best: `openai/gpt-5.4-nano`, `mistralai/mistral-small-2603`.

Good:

- Both preserved the Russian direct quote.
- Both kept author/source attribution.

Caveats:

- `google/gemini-2.5-flash-lite` wrote "A measure has created a legal gray area" in `key_facts`, which weakens the source attribution.
- `mistralai/mistral-large-2512` wrote "a certain measure by Beijing", while the quote itself only says "this measure"; the Beijing framing comes from the author sentence.

### `quality_enrich_uncertain_claim_001`

Task: preserve uncertainty: analysts say supplies may be dual-use; no independent confirmation supplier knew military use.

Best: `openai/gpt-5.4-nano`, `mistralai/mistral-large-2512`.

Good:

- Both preserved "may/could" and lack of independent confirmation.
- `openai/gpt-5.4-nano` was especially careful in Russian.

Caveats:

- `google/gemini-2.5-flash-lite` wrote a thesis: "supplier may have unknowingly provided components for military use." That is plausible, but it is not stated by the source.
- `mistralai/mistral-small-2603` was good, but terse in theses.

### `quality_enrich_sensitive_no_softening_001`

Task: preserve two sides on Xinjiang surveillance: rights group alleges mass surveillance; authorities call measures counter-terrorism.

Best: `openai/gpt-5.4-nano`.

Good:

- `openai/gpt-5.4-nano` cleanly separated rights-group claim and authorities' counter-framing.
- `mistralai/mistral-small-2603` was also strong and Russian.

Caveats:

- `google/gemini-3.1-flash-lite` wrote "under the guise of counter-terrorism" in theses. That takes a side beyond the provided context.
- `mistralai/mistral-large-2512` wrote "tools of systemic control" and "under the guise"; also too assertive.
- `google/gemini-2.5-flash-lite` was accurate but English and more generic.

Overall enrichment verdict:

1. `openai/gpt-5.4-nano`
2. `mistralai/mistral-small-2603`
3. `google/gemini-3.1-flash-lite`
4. `google/gemini-2.5-flash-lite`
5. `mistralai/mistral-large-2512`

Project-specific schema note:

- The real project normalizer accepts `key_facts` as list strings or dicts with `text`.
- Several models used `fact` or `claim` keys in JSON objects.
- Before relying on any model heavily, it would be wise to harden `_normalize_result()` to also accept `fact`, `claim`, and `statement` as aliases for `text`.

## Query And Synthesis Cases

### `quality_synth_conflict_sources_001`

Task: explain what is known and where sources disagree.

Best: `mistralai/mistral-large-2512`, `openai/gpt-5.4-nano`.

Good:

- `mistralai/mistral-large-2512` explicitly said the conflict is unresolved in the provided data.
- `openai/gpt-5.4-nano` was very clear on Source A vs Source B.

Caveats:

- `google/gemini-2.5-flash-lite` was correct but very short and duplicated the Source B reference wording.

### `quality_query_taiwan_quarantine_001`

Task: explain Taiwan quarantine strategy from two sources.

Best: `openai/gpt-5.4-nano`, `mistralai/mistral-small-2603`.

Good:

- Both preserved quarantine as a framing for blockade/ship inspections.
- Both preserved economic pressure through insurance/logistics rather than immediate destruction.

Caveats:

- `mistralai/mistral-large-2512` used "может служить оправданием действий"; not wrong, but a little interpretive.

### `quality_query_china_iran_energy_001`

Task: why Iran conflict is risk for China.

Best: `mistralai/mistral-small-2603`, `google/gemini-3.1-flash-lite`.

Good:

- `mistralai/mistral-small-2603` compactly included trade routes, energy imports, Hormuz, insurance costs, exports.
- `google/gemini-3.1-flash-lite` included dollar system and energy model.

Caveats:

- `google/gemini-2.5-flash-lite` omitted energy imports and dollar-system dependence. It covered trade routes, Hormuz, insurance, and exports, but missed one key axis.
- `openai/gpt-5.4-nano` wrote "Стрейт-оф-Хормуз" instead of natural "Ормузский пролив".

### `quality_query_xinjiang_competing_claims_001`

Task: summarize the dispute without choosing a side.

Best: `openai/gpt-5.4-nano`, `google/gemini-3.1-flash-lite`.

Good:

- Both preserved the rights-group claim and official counter-terrorism denial without deciding the truth.
- `openai/gpt-5.4-nano` was most explicit about the difference in evaluation.

Caveats:

- `mistralai/mistral-small-2603` wrote "official position" for Source B. This is reasonable, but adds a role label not directly specified.

Overall query verdict:

1. `mistralai/mistral-small-2603`
2. `openai/gpt-5.4-nano`
3. `google/gemini-3.1-flash-lite`
4. `mistralai/mistral-large-2512`
5. `google/gemini-2.5-flash-lite`

For `QUERY_MODEL`, `mistralai/mistral-small-2603` is the best default. For high-risk fallback synthesis, `openai/gpt-5.4-nano` is safer.

## Script Pack Cases

### `quality_script_pack_001`

Task: research pack for China pressure on Taiwan.

Best: `mistralai/mistral-large-2512`.

Good:

- `mistralai/mistral-large-2512` gave a compact research pack with two source-grounded points and a limitation note.
- `google/gemini-3.1-flash-lite` was also clean and source-grounded.

Caveats:

- `google/gemini-2.5-flash-lite` was too thin: two sentences, not really a pack.
- `mistralai/mistral-small-2603` over-expanded into recommendations for further collection: US State Department, PRC MFA, RAND, CSIS, historical context. It labels these as further research, but for source-only generation it is noisy.
- `openai/gpt-5.4-nano` produced a good pack but ended with conversational "Если хотите..." text, undesirable in pipeline output.

### `quality_script_pack_sensitive_sources_001`

Task: research pack on Chinese dual-use technologies and Russia's war against Ukraine.

Best: `openai/gpt-5.4-nano`, `google/gemini-3.1-flash-lite`.

Good:

- `openai/gpt-5.4-nano` was rich, cautious, and explicitly preserved the "not proven supplier knew" limitation.
- `google/gemini-3.1-flash-lite` gave a clean, compact, source-grounded pack.

Caveats:

- `google/gemini-2.5-flash-lite` again was too thin.
- `mistralai/mistral-large-2512` said source_a and source_b "agree" that components have dual use and can be used militarily. That is close, but source_a says used by combat drones while source_b says supplier describes them as civilian dual-use; this should be kept as two different claims.
- `mistralai/mistral-small-2603` added useful research questions but again expands beyond the immediate source pack.

Overall script-pack verdict:

1. `openai/gpt-5.4-nano`
2. `google/gemini-3.1-flash-lite`
3. `mistralai/mistral-large-2512`
4. `mistralai/mistral-small-2603`
5. `google/gemini-2.5-flash-lite`

## Model-By-Model Conclusions

### `google/gemini-2.5-flash-lite`

Strengths:

- Cheapest and fastest.
- Good literal translations.
- Very concise answers.

Weaknesses:

- Too compressed for query/script-pack work.
- Missed energy/dollar-system axis in the Iran risk query.
- Script packs were often just short summaries, not real packs.
- Enrichment often English under the weak bakeoff prompt.

Use it for:

- Vision/OCR/audio where it is already configured.
- Very cheap translation or low-risk extraction if post-processing checks are active.

Do not use it as:

- Main high-risk `QUERY_MODEL`.
- Main script-pack/fallback synthesis model.

### `google/gemini-3.1-flash-lite`

Strengths:

- Best pure translation quality overall.
- Good structured query answers.
- Good concise script packs.
- Better recall than Gemini 2.5 on multi-factor questions.

Weaknesses:

- Enrichment often English under weak prompt.
- In one Xinjiang enrichment thesis, it used "under the guise of counter-terrorism", which takes a side beyond the supplied text.

Use it for:

- `TRANSLATION_MODEL`.
- Cheap script packs if you want compact, source-grounded output.

### `mistralai/mistral-small-2603`

Strengths:

- Best general-purpose default.
- Strong query answers with good completeness and low cost.
- Often writes Russian naturally.
- Good translation quality.

Weaknesses:

- Can over-expand script packs into generic research suggestions.
- JSON schema can drift: uses `fact`, `claim`, `statement` keys instead of the project's preferred `text`.
- One translation used gendered "spokesman".

Use it for:

- `ENRICHMENT_MODEL` if schema normalizer is hardened.
- `QUERY_MODEL`.
- Budget default for translation if one-model simplicity matters.

### `mistralai/mistral-large-2512`

Strengths:

- Strong source-aware query/script answers.
- Good limitation notes.
- Useful for final synthesis.

Weaknesses:

- Slowest and most expensive in this batch.
- Not clearly better than cheaper models.
- Sometimes adds interpretive claims: "Actor A may be biased", "under the guise", "systemic control".
- JSON schema drift in enrichment.

Use it for:

- Rare high-risk fallback/script-pack runs where cost/latency is acceptable.

Do not use it as:

- Main high-volume enrichment model.

### `openai/gpt-5.4-nano`

Strengths:

- Best cautious enrichment behavior.
- Strong attribution and limitation handling.
- Good high-risk query and script-pack synthesis.
- Usually keeps Russian well in sensitive cases.

Weaknesses:

- Verbose.
- More expensive than Mistral Small and Gemini Lite models.
- Sometimes adds conversational tail text.
- One awkward Russian term: "Стрейт-оф-Хормуз".

Use it for:

- `FALLBACK_SYNTH_MODEL`.
- High-risk enrichment if budget allows.
- Judge/checker role, if added later.

## Final Practical Answer

For the current project, the best production split is:

```env
ENRICHMENT_MODEL=mistralai/mistral-small-2603
TRANSLATION_MODEL=google/gemini-3.1-flash-lite
QUERY_MODEL=mistralai/mistral-small-2603
FALLBACK_SYNTH_MODEL=openai/gpt-5.4-nano
```

Before using `mistralai/mistral-small-2603` heavily for enrichment, harden the enrichment normalizer to accept `fact`, `claim`, and `statement` as aliases for `text` inside `key_facts`.

If high-risk China/Taiwan/Xinjiang/Tibet material matters more than cost, use:

```env
ENRICHMENT_MODEL=openai/gpt-5.4-nano
TRANSLATION_MODEL=google/gemini-3.1-flash-lite
QUERY_MODEL=mistralai/mistral-small-2603
FALLBACK_SYNTH_MODEL=openai/gpt-5.4-nano
```

The key conclusion: no single western model is best everywhere. `mistralai/mistral-small-2603` is the best default workhorse, `google/gemini-3.1-flash-lite` is the best translator, and `openai/gpt-5.4-nano` is the best cautious high-risk synthesizer/enricher.
