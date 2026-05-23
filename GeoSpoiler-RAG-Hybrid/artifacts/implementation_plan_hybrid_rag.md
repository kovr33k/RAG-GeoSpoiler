# Implementation Plan: Stable Hybrid RAG

Дата: 2026-05-19

## Цель

Собрать новую рабочую версию GeoSpoiler-RAG без полного отката к v2:

- использовать стабильный v2-подход для построения LightRAG-графа из `output/normalized`;
- не строить основной граф из `output/enriched`, потому что это перегружает LLM build-этап;
- сохранить полезные улучшения текущей версии: enriched-карточки, source-fidelity правила, shadow search, query profiles, golden set checks;
- подключить enriched-карточки на этапе ответа, а не на этапе rebuild.

Итоговая архитектура:

```text
normalized .txt -> LightRAG graph build -> stable graph

enriched .json -> lexical/card retrieval -> extra context

question -> LightRAG retrieval + enriched retrieval -> final answer with sources
```

## Что полезного забираем из текущей версии

### 1. Enricher как отдельный knowledge-card слой

Файлы:

- `enricher/pipeline.py`
- `enricher/llm_enricher.py`
- `enricher/content_classifier.py`
- `enricher/chunker.py`
- `enricher/triage.py`
- `enricher/dedup.py`
- `enricher/graph_text_builder.py`

Что оставить:

- `summary`;
- `key_facts`;
- `entities`;
- `topics`;
- `theses`;
- `quotes`;
- `events`;
- `query_aliases`;
- `visual.broll_notes`;
- `source_chain`;
- `provenance`.

Как использовать:

- не отправлять enriched `graph_text` в основной LightRAG build;
- использовать `search_text`, `key_facts`, `entities`, `theses` для card retrieval во время query;
- использовать `visual` только для визуальных/B-roll вопросов.

Почему полезно:

- enriched-карточки дают готовые короткие факты;
- можно улучшать ответы без перестройки графа;
- можно точнее отвечать на source/thesis/visual вопросы.

### 2. Source-fidelity правила

Файлы:

- `enricher/llm_enricher.py`
- `loader/lightrag_loader.py`

Что оставить:

- запрет на самостоятельное fact-checking;
- запрет на слова вроде "fake", "false", "фальшивый", если этого явно нет в источнике;
- запрет добавлять "якобы", если источник сам так не пишет;
- `claim_type=fact|source_claim|hypothesis`;
- sanitizer unsupported fake verdicts.

Почему полезно:

- это исправляет проблему, где модель называла реальные claims "фальшивыми";
- это важно и для enrichment, и для final synthesis.

### 3. Triage без low-value

Файл:

- `enricher/triage.py`

Что оставить:

- `low-value` оставить только как legacy value;
- новые карточки не должны уходить в low-value;
- curated Telegram folder = high recall priority;
- `review` только для AI-chat, placeholder-only video, пустых/ручных случаев.

Почему полезно:

- пользователь уже отфильтровал источники вручную;
- aggressive filtering вредил recall.

### 4. Chunking long-form content

Файл:

- `enricher/chunker.py`

Что оставить:

- chunking для длинных YouTube/web/analysis материалов;
- timestamp-aware splitting;
- overlap между chunks;
- merge chunk results.

Почему полезно:

- это нужно для enriched-карточек;
- но результат chunking не должен напрямую утяжелять LightRAG graph build.

### 5. Dedup by YouTube URL

Файл:

- `enricher/dedup.py`

Что оставить:

- marking duplicates by video ID;
- canonical memory id;
- не удалять данные, только помечать.

Как использовать:

- card retrieval должен по умолчанию не возвращать duplicate cards;
- но source view может показывать duplicate/canonical relation.

### 6. Shadow search

Файлы:

- `retrieval/shadow_search.py`
- fallback helpers in `loader/lightrag_loader.py`

Что оставить:

- быстрый keyword search по enriched cards;
- matching русских словоформ через prefix;
- snippets;
- top topic grouping;
- fallback при no-context LightRAG answer.

Что доработать:

- добавить fallback по normalized text, если enriched cards недостаточно;
- добавить better scoring: title/path/topic/entity boost;
- убрать любые user-facing технические слова `shadow_search`, `fallback`, `точный поиск по карточкам`.

### 7. Retrieval composer

Файлы:

- `retrieval/composer.py`
- `retrieval/response_formatter.py`

Что оставить:

- идея multi-index search;
- modes: `recall`, `broll`, `thesis`, `entity`;
- SearchPackage / SearchResult как промежуточный формат.

Что доработать:

- composer сейчас больше похож на debugging/search report, а не основной answer pipeline;
- нужно превратить его в retrieval layer для `query`;
- `response_formatter.py` может остаться CLI/report tool, но не должен напрямую формировать обычный ответ пользователю.

### 8. Query profiles

Файл:

- `loader/lightrag_loader.py`

Что оставить:

- `answer`;
- `source`;
- `overview`;
- разные `top_k/chunk_top_k`;
- source questions auto-detection в `main.py`.

Почему полезно:

- source-вопросы и overview-вопросы требуют разного retrieval behavior;
- это уже отражено в golden set.

### 9. Source metadata index and citation resolver

Файлы:

- `loader/lightrag_loader.py`
- `main.py`

Что оставить:

- stable path-based doc id;
- `doc_metadata_index.json`;
- `_extract_query_sources()`;
- `_print_query_sources()`;
- sidecar `.meta.json` parsing.

Что доработать:

- enriched retrieval должен возвращать те же source records:
  - `post_url`;
  - `file_path`;
  - `channel`;
  - `date`;
  - `card_path`;
  - optional `canonical_memory_id`.

### 10. Build safety improvements

Файлы:

- `loader/lightrag_loader.py`
- `artifacts/rag_insert_skipped.md`

Что оставить:

- stable source doc id;
- timeout per insert;
- cleanup skipped doc;
- skipped report;
- detection of LightRAG `failed` status;
- final status wait after `ainsert`.

Что изменить:

- эти механизмы нужны, но default build должен снова быть normalized;
- enriched build оставить только experimental flag.

### 11. Role-specific models

Файл:

- `config.py`

Что оставить:

- `RAG_BUILD_MODEL`;
- `QUERY_MODEL`;
- `FALLBACK_SYNTH_MODEL`;
- `TRANSLATION_MODEL`;
- `ENRICHMENT_MODEL`;
- separate API keys/base URLs.

Что исправить:

- основной `llm_func` сейчас всё ещё использует `LLM_DELAY_SECONDS`, а не `RAG_BUILD_DELAY_SECONDS/QUERY_DELAY_SECONDS`;
- `RAG_BUILD_DELAY_SECONDS` должен применяться только при `_LLM_ROLE == "build"`;
- `QUERY_DELAY_SECONDS` должен применяться только для query;
- fallback synthesis не должен ссылаться на undefined role variables.

### 12. Query fallback and finalize safety

Файлы:

- `loader/lightrag_loader.py`
- `main.py`
- `test_loader.py`

Что оставить:

- query timeout;
- shadow fallback when LightRAG returns no-context;
- fallback answer sanitizer;
- safe finalize timeout.

Что пересмотреть:

- `os._exit(0)` after fallback is a rough emergency workaround;
- лучше сделать нормальную cancellation/finalize strategy, но можно оставить временно, если LightRAG worker hangs.

### 13. Golden set improvements

Файл:

- `test_golden_set.py`

Что оставить:

- expanded cases;
- `source_any`;
- `source_required`;
- forbidden technical markers;
- forbidden B-roll for non-visual questions;
- `golden_set_scores.json`.

Что добавить:

- сравнение режимов:
  - `v2 graph`;
  - `normalized graph + enriched retrieval`;
  - `enriched graph` only as small experimental subset;
- report table by question: answer quality, source quality, forbidden terms, hallucination risk.

## Что не переносим как default

### 1. Enriched graph build as default

Не делать:

```text
python main.py rebuild
```

если он по умолчанию строит граф из `output/enriched`.

Почему:

- дорого;
- нестабильно на бесплатном NVIDIA endpoint;
- вызывает `429`, `failed`, skipped;
- не даёт честно протестировать качество, потому что граф получается неполным.

Нужно:

```text
python main.py rebuild
```

по умолчанию строит normalized graph.

А enriched graph build, если нужен, только явно:

```text
python main.py rebuild --from-enriched
```

или:

```text
python main.py rebuild-enriched-experimental
```

### 2. Использование B-roll в обычных ответах

Не делать:

- подмешивать `broll_notes` в обычные political/source/overview ответы.

Делать:

- использовать `visual` только если вопрос явно про кадры, видео, визуалы, b-roll.

### 3. User-facing technical fallback markers

Не показывать пользователю:

- `shadow_search`;
- `fallback`;
- `LightRAG не поднял`;
- `точный поиск по карточкам`.

## Target Architecture

### Build pipeline

```text
fetch -> normalize -> enrich
                 \
                  -> LightRAG load from normalized
```

Rules:

- `run` can still enrich incrementally;
- `load/rebuild` must use normalized by default;
- enriched cards are not graph source by default;
- reviewed AI-chat items can still be loaded if manually approved.

### Query pipeline

```text
question
  -> LightRAG query over normalized graph
  -> enriched card retrieval over search_text/key_facts/entities/theses
  -> merge retrieval contexts
  -> final synthesis via QUERY_MODEL
  -> answer + resolved sources
```

### Enriched retrieval inputs

Use these fields:

- `search_text`;
- `summary`;
- `key_facts[].text`;
- `entities.*`;
- `topics`;
- `theses`;
- `quotes`;
- `events`;
- `query_aliases`;
- `visual.broll_notes` only for visual mode.

### Enriched retrieval output

Every match should return:

```json
{
  "source_path": "...normalized/...txt",
  "card_path": "...enriched.json",
  "post_url": "...",
  "channel": "...",
  "date": "...",
  "reason": "key_fact|entity|thesis|keyword|visual",
  "facts": ["..."],
  "snippet": "..."
}
```

## Implementation Phases

### Phase 0: Safety baseline

What to do:

- Create a timestamped backup of current:
  - `rag_storage`;
  - `.env`;
  - `config.py`;
  - `main.py`;
  - `loader/lightrag_loader.py`;
  - `retrieval/`;
  - `enricher/`;
  - `test_golden_set.py`;
  - `test_loader.py`.
- Preserve current broken/partial graph only as diagnostic artifact.
- Restore or copy v2 `rag_storage` as baseline graph if immediate querying is needed.

Verification:

- `rag_storage/kv_store_doc_status.json` reports `processed=220`;
- no `failed` statuses in active baseline;
- `python main.py status` still works.

Anti-pattern guard:

- do not delete partial rebuild folders;
- do not overwrite v2 backup.

### Phase 1: Make normalized graph build the default

What to implement:

- Change `cmd_load()` default behavior:
  - default: `load_from_directory(rag)`;
  - `--from-enriched`: explicit experimental mode.
- Change `cmd_rebuild()` default behavior:
  - default source = `normalized`;
  - `--from-enriched` only if explicitly passed.
- Update CLI help text.
- Keep `load_from_enriched()` but mark it experimental in docstring/logs.

Files:

- `main.py`
- `loader/lightrag_loader.py`
- `README.md`
- tests in `test_main.py` / `test_loader.py`

Verification:

- `python main.py rebuild --dry-run` if added, or unit test command routing;
- `python -m unittest test_loader.py test_main.py`;
- grep confirms default rebuild log says `source: normalized`.

Anti-pattern guard:

- do not remove `load_from_enriched()`;
- do not silently use enriched graph_text when user runs plain rebuild.

### Phase 2: Fix model-role delay and timeout configuration

What to implement:

- In `create_rag().llm_func()`:
  - if `_LLM_ROLE == "build"`, use `RAG_BUILD_MODEL` and `RAG_BUILD_DELAY_SECONDS`;
  - otherwise use `QUERY_MODEL` and `QUERY_DELAY_SECONDS`.
- Keep `LLM_MAX_ASYNC=1` recommended for free NVIDIA build.
- Keep query faster by allowing `QUERY_DELAY_SECONDS=0`.
- Fix any fallback synthesis role/delay bug.

Files:

- `config.py`
- `loader/lightrag_loader.py`
- `.env.example`

Verification:

- unit test or smoke test stubs that assert build role selects build delay/model;
- `python -m py_compile config.py loader/lightrag_loader.py`;
- no runtime `NameError` from fallback synthesis.

Anti-pattern guard:

- do not apply build delay to query answers;
- do not apply query model to graph build.

### Phase 3: Keep enrichment as offline card generation

What to implement:

- Keep `python main.py enrich`.
- Keep incremental progress.
- Keep no-low-value triage.
- Ensure enrichment does not trigger LightRAG rebuild.
- Ensure `graph_text` still exists for debug/search, but is not default graph input.
- Keep `search_text` populated.

Files:

- `enricher/pipeline.py`
- `enricher/triage.py`
- `enricher/graph_text_builder.py`
- `main.py`

Verification:

- `python -m unittest test_enricher.py`;
- run `python main.py enrich --channel <small-channel>` on small subset if needed;
- enriched card has `search_text`, `summary`, `key_facts`, `provenance`.

Anti-pattern guard:

- no `low-value` for curated short posts;
- no B-roll in `graph_text` if graph_text is ever used experimentally.

### Phase 4: Build enriched retrieval layer

What to implement:

- Create or refactor an enriched retrieval module:
  - likely `retrieval/enriched_index.py`;
  - load all `*.enriched.json`;
  - skip `triage != keep`;
  - skip `dedup.is_duplicate` unless source mode asks for provenance;
  - search over `search_text`, `summary`, `key_facts`, `entities`, `topics`, `theses`, `query_aliases`;
  - visual fields only for visual queries.
- Add fallback normalized search if enriched cards are missing/partial.
- Return structured matches, not formatted markdown.

Files:

- `retrieval/shadow_search.py`
- new `retrieval/enriched_index.py` or refactor existing
- `retrieval/composer.py`
- tests in `test_loader.py` or new `test_retrieval.py`

Verification:

- query `Куба переговоры США` returns Cuba cards;
- query `AfD Россия` returns ultra-right/AfD cards;
- visual query returns `visual.broll_notes`;
- non-visual query does not return B-roll text.

Anti-pattern guard:

- do not use enriched search as a replacement for LightRAG;
- do not expose internal terms like `shadow_search`.

### Phase 5: Compose final answers from graph + cards

What to implement:

- Add a new function, conceptually:

```python
async def query_hybrid_result(rag, question, mode=None, query_profile=None) -> dict:
    graph_result = await query_rag_result(...)
    card_matches = search_enriched_cards(...)
    final_answer = synthesize_answer(question, graph_result, card_matches, profile)
    return {"llm_response": ..., "data": {"references": ...}, "hybrid": True}
```

- Use `QUERY_MODEL` for final synthesis.
- Keep source-fidelity rules:
  - no outside fact checking;
  - no fake/false labels unless source says it;
  - cite source claims as source claims.
- Source profile:
  - prioritize exact file/post references.
- Overview profile:
  - summarize across cards and graph.
- Visual profile:
  - include visual notes only when asked.

Files:

- `loader/lightrag_loader.py` or new `retrieval/hybrid_query.py`
- `main.py`
- `test_golden_set.py`

Verification:

- `python main.py query "..."`
- `python main.py query "... source"`
- `python main.py query "... overview"`
- no technical fallback markers in output.

Anti-pattern guard:

- do not ask LLM to invent citations;
- citations must come from metadata/card provenance/LightRAG references.

### Phase 6: Source resolver unification

What to implement:

- One resolver for both LightRAG refs and enriched card refs.
- Returned references should include:
  - `post_url`;
  - `file_path`;
  - `channel`;
  - `date`;
  - optional `card_path`;
  - optional `canonical_memory_id`.
- Golden set source checks should work for hybrid answers.

Files:

- `main.py`
- `loader/lightrag_loader.py`
- `retrieval/hybrid_query.py`

Verification:

- source questions print resolved source block;
- `source_any` checks pass where expected;
- missing sources are explicitly reported, not invented.

Anti-pattern guard:

- do not rely only on `[1]` markers in generated text;
- structured references must exist in returned result.

### Phase 7: Evaluation without expensive enriched rebuild

What to implement:

- Golden set should be runnable against:
  - active graph;
  - hybrid retrieval;
  - optionally v2 backup graph.
- Add result metadata:
  - graph source: normalized/enriched;
  - doc status counts;
  - query mode/profile;
  - hybrid enabled true/false.
- Produce a comparison report:
  - per question;
  - v2 answer;
  - hybrid answer;
  - score delta;
  - source delta;
  - hallucination/forbidden markers.

Files:

- `test_golden_set.py`
- new optional `artifacts/golden_set_comparison.md`

Verification:

- run golden set without rebuild;
- no build API calls during golden set;
- average score and pass count are written to JSON.

Anti-pattern guard:

- do not trigger `main.py rebuild` inside evaluation;
- do not compare incomplete enriched graph as if it were valid.

### Phase 8: Optional experimental enriched graph subset

Purpose:

- Only to test whether enriched graph has real quality upside.
- Never use full corpus on free NVIDIA endpoint until small subset proves value.

What to implement:

- Add subset build command:

```text
python main.py rebuild --from-enriched --channel "Куба" --limit 20
```

or a separate script.

Verification:

- build 10-20 docs only;
- compare the same 5-7 golden questions;
- if not clearly better, do not pursue full enriched graph.

Anti-pattern guard:

- do not run full enriched rebuild as normal workflow;
- do not treat partial graph as production graph.

## Recommended execution order

1. Backup current project state.
2. Restore/use v2 `rag_storage` as immediate full baseline.
3. Change default build/rebuild to normalized.
4. Fix role-specific delay bug.
5. Keep enrichment but decouple it from graph build.
6. Implement structured enriched retrieval.
7. Implement hybrid query result.
8. Run golden set comparison.
9. Only then decide whether any enriched graph subset is worth testing.

## Success criteria

Functional:

- active graph has `220 processed`, `0 failed`;
- plain `python main.py rebuild` no longer attempts enriched graph build;
- `python main.py enrich` still produces/updates cards;
- `python main.py query` can use both LightRAG and enriched cards.

Quality:

- hybrid golden set average score >= v2 average score;
- no technical fallback markers in answers;
- no B-roll in non-visual answers;
- source questions include resolved sources;
- Trump/Orban/fake issue does not reappear.

Operational:

- no 5-hour rebuild needed for ordinary testing;
- no `429` storm during normal query tests;
- full rebuild is possible on normalized data within the v2-like runtime.

## Main risks

### Risk: hybrid context makes answer too verbose

Mitigation:

- cap enriched matches to 3-5;
- pass only summary/key_facts, not full card JSON;
- profile-specific answer length.

### Risk: lexical enriched retrieval returns topical but wrong cards

Mitigation:

- require at least 2 query term matches for multi-term questions;
- boost title/path/topic matches;
- use same-topic grouping;
- add source_any golden checks.

### Risk: source citations become inconsistent

Mitigation:

- structured reference resolver;
- references assembled before final synthesis;
- final LLM may cite only provided reference IDs.

### Risk: normalized graph misses facts that enriched cards capture

Mitigation:

- enriched cards are injected at query time;
- no need to rebuild graph to use those facts.

## Decision

Do not fully return to v2 code.

Use:

- v2 graph-building strategy;
- current enrichment/search/evaluation improvements;
- a new hybrid query layer to combine both.

The target is not "v2 rollback". The target is "v2-stable graph + current-version intelligence at query time".
