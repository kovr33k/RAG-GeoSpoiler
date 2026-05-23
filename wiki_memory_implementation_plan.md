# GeoSpoiler RAG Hybrid: Wiki Memory Implementation Plan

Дата: 2026-05-21

## Контекст

Проект: `D:\ObsidianWiki\GeoSpoiler-RAG-Hybrid`

Текущая цель: не делать тяжёлый rebuild LightRAG на enriched-документах, а добавить лёгкий wiki-memory слой поверх уже рабочей hybrid-архитектуры.

Почему так:

- v2 `rag_storage` уже стабилен и построен на `output/normalized`;
- тяжёлый enriched rebuild оказался долгим, хрупким и склонным к ухудшению ответов;
- дополнительные LLM-шаги внутри rebuild могут искажать факты;
- enriched cards полезны как evidence layer, но их лучше держать рядом с графом, а не запекать внутрь нового тяжёлого графа;
- wiki-memory слой может улучшить точность ответов без полного rebuild.

## Что уже есть

Текущая hybrid-структура:

```text
GeoSpoiler-RAG-Hybrid/
  inputs/
  media_cache/
  output/
    normalized/       источник истины: очищенные посты
    enriched/         карточки: summary, facts, b-roll, tags
  rag_storage/        стабильный v2 LightRAG graph
  retrieval/          shadow/card search и composer
  loader/             LightRAG load/query логика
  normalizer/
  enricher/
  artifacts/
```

Важное состояние:

- `rag_storage/` нельзя трогать без необходимости;
- `output/normalized/` остаётся главным источником истины;
- `output/enriched/` используется как быстрый evidence/retrieval слой;
- обычный `query` уже умеет работать как `LightRAG + enriched cards`;
- `search --mode shadow` работает без LLM и быстро находит карточки;
- rebuild/golden после hybrid-перехода ещё не запускались;
- главный runtime-риск сейчас: нестабильный выбор LLM endpoint/model.

Фактическая сверка на 2026-05-21:

```text
output/normalized/*.txt       220
output/normalized/*.meta.json 220
output/enriched/*.json        218
output/wiki/                  ещё не создан
```

В enriched-карточках уже есть `provenance.channel_id`, `provenance.message_id`, `provenance.post_url`, `provenance.normalized_file`, но пока нет явного `source_id` и `content_hash`. Это нужно добавить или вычислять в wiki-index слое.

## Идея Карпати, адаптированная под проект

Не полагаться только на RAG, который каждый раз заново ищет куски и просит LLM собрать ответ.

Добавить persistent wiki layer:

```text
raw/normalized sources
  -> enriched cards
  -> wiki memory
  -> query answer
```

Wiki layer — это не ещё один граф и не rebuild. Это папка markdown-страниц, которые хранят накопленное знание:

- кто есть кто;
- какие темы есть в базе;
- какие claims подтверждены источниками;
- какие claims спорные;
- какие sources относятся к каким темам/людям/утверждениям.

Что конкретно берём из идеи Карпати:

- raw/normalized sources остаются immutable source of truth;
- wiki — отдельный markdown-слой, который можно читать глазами и проверять;
- index/log обязательны, чтобы агент не терялся при росте базы;
- нужен schema/instructions файл, который дисциплинирует агента и запрещает свободную фантазию;
- ingest/query/lint должны быть отдельными операциями;
- wiki должна обновляться инкрементально, а не пересобираться целиком.

Что НЕ берём напрямую:

- не отдаём LLM полное право переписывать всё без проверок;
- не делаем wiki заменой `output/normalized`;
- не делаем новый тяжёлый graph rebuild;
- не превращаем wiki в очередной LLM-summary слой без source grounding.

## Главный принцип

Не делать:

```text
1000 документов -> всё заново через LLM -> полный graph rebuild
```

Делать:

```text
новые документы -> enrich только новые -> обновить только затронутые wiki pages
```

Wiki должна быть инкрементальной.

## Целевая структура

Добавить:

```text
output/wiki/
  _master_index.md
  _schema.md
  _health.md
  _change_log.md
  _log.md
  _pending_updates.json

  entities/
    viktor-orban.md
    donald-trump.md
    peter-magyar.md
    fidesz.md
    tisza.md
    russia.md
    european-union.md

  topics/
    hungary-election-2026.md
    trump-orban-support.md
    russia-hungary-relations.md
    far-right-europe.md
    slovakia-fico.md
    cuba-us-relations.md
    baltic-security.md

  claims/
    trump-supported-orban-2026.md
    trump-jr-supported-orban.md
    vance-supported-orban.md
    orban-russia-energy-sanctions.md
    tisza-defeated-orban.md

  timelines/
    hungary-2026-election.md
    trump-orban-events.md
    orban-political-evolution.md

  indexes/
    source_to_pages.json
    page_to_sources.json
    entity_to_pages.json
    topic_to_pages.json
    claim_to_sources.json
```

Для MVP можно начать только с:

```text
output/wiki/
  _master_index.md
  _schema.md
  _health.md
  _log.md
  entities/
  topics/
  claims/
  indexes/
```

`timelines/` добавить позже.

`_schema.md` — важный файл. Он должен описывать правила для агента:

- какие типы страниц существуют;
- какие поля обязательны;
- как писать claim status;
- как цитировать источники;
- какие страницы можно автоматически обновлять;
- какие страницы требуют ручной проверки;
- что запрещено называть claim фейком без явного evidence.

`_log.md` должен быть append-only и parseable. Пример записи:

```md
## [2026-05-21] wiki-build | claims/trump-supported-orban-2026.md

- action: created
- sources: telegram:3328128766:148, telegram:3328128766:150
- notes: seeded from enriched key_facts[source_claim]
```

## Самый важный слой: claims

Главная боль проекта: модель иногда смешивает реальные claims с fake/deepfake контекстом и делает ложный вывод.

Пример проблемы:

Модель написала, что поддержка Трампа/Вэнса/Трампа-младшего Орбану якобы фейковая, хотя в базе это должно трактоваться как факт/утверждение источников.

Для этого нужен claim ledger.

Пример страницы:

```md
# Trump supported Orban before the 2026 Hungarian election

Status: supported_by_corpus

Summary:
Donald Trump publicly supported Viktor Orban before the 2026 Hungarian election.

Evidence:
- telegram:3328128766:148 — quote/source_claim
- telegram:3328128766:150 — source_claim
- telegram:3328128766:163 — source_claim
- telegram:3328128766:189 — source_claim

Do not say:
- Do not describe this as fake unless a cited source explicitly says it is fake.
- Do not merge this with unrelated fake/deepfake claims.

Related:
- entities/donald-trump.md
- entities/viktor-orban.md
- topics/trump-orban-support.md
```

Claim statuses:

```text
supported     подтверждается источниками
contradicted  источники явно опровергают
disputed      есть конфликтующие источники
unclear       недостаточно данных
```

Важно: `Status` означает статус внутри корпуса, а не внешнюю проверку факта в интернете.

Лучше формулировать точнее:

```text
supported_by_corpus     утверждение поддержано источниками в базе
contradicted_by_corpus  источники в базе явно опровергают
disputed_in_corpus      в базе есть конфликтующие источники
unclear_in_corpus       данных в базе недостаточно
```

## Правила против искажения фактов

Это критично для нашего проекта.

При создании claim pages нельзя считать все поля enriched-карточки одинаково надёжными.

Приоритет evidence:

```text
1. quotes
2. key_facts с claim_type=source_claim
3. events
4. provenance / post_url / date
5. summary
6. theses / hypothesis
```

`summary` можно использовать только как вспомогательный пересказ.

`theses` и `hypothesis` нельзя использовать как прямое доказательство факта. Они часто содержат авторскую интерпретацию, сарказм или оценку.

Для примера с Трампом/Орбаном:

- факт поддержки должен браться из `quotes` и `key_facts[source_claim]`;
- тезис вида "это манипуляция" не должен превращаться в claim "поддержка фейковая";
- claim можно назвать fake/deepfake/ложным только если конкретный source прямо это утверждает.

Каждая claim page должна иметь блок:

```md
## Guardrails

- Do not call this fake unless an evidence item explicitly says it is fake.
- Separate source claims from author interpretation.
- Preserve uncertainty labels from sources.
```

## Как должен работать query

Новая логика ответа:

```text
user question
  -> find relevant wiki claims
  -> find relevant wiki topics/entities
  -> find enriched cards
  -> ask LightRAG graph if needed
  -> synthesize answer with strict source grounding
```

Приоритет контекста:

```text
1. wiki/claims      точные утверждения и запреты на ложные трактовки
2. wiki/topics      общий контекст
3. wiki/entities    кто есть кто
4. output/enriched  evidence cards
5. LightRAG graph   связи и широкий поиск
```

Важно: wiki не заменяет источники. Wiki помогает выбрать и стабилизировать смысл, но финальный ответ всё равно должен ссылаться на конкретные posts/cards.

## Почему это легче старого rebuild

Старый тяжёлый вариант:

```text
каждый документ
  -> LLM extraction
  -> entities/relations
  -> LightRAG insert
  -> graph finalize
  -> query
```

Минусы:

- много LLM-вызовов;
- тяжёлые insert/finalize;
- зависания на больших документах;
- искажения фактов закрепляются в графе;
- rebuild может идти часами.

Wiki-memory вариант:

```text
enriched cards
  -> cluster by entity/topic/claim
  -> create/update only affected markdown pages
  -> query reads relevant pages
```

Плюсы:

- не трогает `rag_storage`;
- можно делать постепенно;
- можно остановить и продолжить;
- обновляются только затронутые страницы;
- проще проверить руками;
- факты остаются рядом с evidence.

## Масштабирование на сотни YouTube-видео и тысячи TG-постов

Работать будет только при инкрементальном подходе.

Для каждого источника нужен стабильный `source_id`.

Пример:

```text
telegram:Венгрия Словакия:148
youtube:channel_id:video_id
```

Текущее правило вычисления `source_id` для Telegram:

```text
telegram:{channel_id}:{message_id}
```

Если `channel_id` отсутствует:

```text
telegram:{channel_name}:{message_id}
```

Для каждого источника нужен `content_hash`, чтобы понимать, изменился ли он.

`content_hash` лучше считать от нормализованного текста + ключевых provenance-полей:

```text
sha256(normalized_text + channel_id + message_id + date)
```

Для YouTube:

```text
youtube:{channel_id}:{video_id}
sha256(transcript_text + title + published_at)
```

Pipeline:

```text
new posts/videos
  -> normalize only new/changed
  -> enrich only new/changed
  -> extract candidate entities/topics/claims
  -> update source_to_pages index
  -> update only affected wiki pages
  -> update _master_index periodically
```

Нельзя:

- переписывать всю wiki после каждого импорта;
- обновлять все pages при каждом новом посте;
- давать LLM переписывать большие страницы целиком без diff;
- хранить summary без ссылок на источники;
- смешивать real claim и fake/deepfake claim в одной странице.

## Зачем нужна индексация

Индексация нужна, но только лёгкая служебная. Это не должна быть ещё одна тяжёлая vector DB, новый LightRAG graph или отдельный rebuild.

Без индексов система будет работать так:

```text
вопрос -> читать все wiki pages -> читать все cards -> пытаться угадать релевантное
```

На маленьком корпусе это терпимо, но на тысячах TG-постов и сотнях YouTube-видео станет медленно, дорого и хаотично.

Индексы нужны для трёх задач.

1. Быстро понять, какие страницы обновлять.

Например пришёл новый пост:

```text
telegram:3328128766:999
```

Индекс должен показать:

```json
{
  "telegram:3328128766:999": [
    "claims/trump-supported-orban-2026.md",
    "topics/trump-orban-support.md",
    "entities/donald-trump.md",
    "entities/viktor-orban.md"
  ]
}
```

Тогда обновляются 3-4 страницы, а не вся wiki.

2. Быстро найти, что читать для ответа.

Вопрос:

```text
Трамп реально поддерживал Орбана?
```

Индекс должен сразу привести к:

```text
claims/trump-supported-orban-2026.md
topics/trump-orban-support.md
entities/donald-trump.md
entities/viktor-orban.md
```

3. Не потерять первоисточники.

Wiki page не должна быть финальным источником. Индекс нужен, чтобы развернуть:

```text
claims/trump-supported-orban-2026.md
  -> telegram:3328128766:148
  -> post_url / normalized_file / enriched_card
```

То есть пользователь должен получать не "так написано в wiki", а реальные Telegram/YouTube источники.

Минимальные индексы для MVP:

```text
output/wiki/indexes/
  source_to_pages.json
  page_to_sources.json
```

Следующие индексы добавить после MVP:

```text
output/wiki/indexes/
  entity_to_pages.json
  topic_to_pages.json
  claim_to_sources.json
```

На старте индексация должна быть обычной файловой:

- JSON-файлы;
- keyword matching;
- entity/topic matching;
- fuzzy matching для русских/английских вариантов имён;
- без embeddings и vector DB.

Чего не делать сейчас:

- не добавлять FAISS/Chroma/другую vector DB для wiki;
- не embedding-овать каждую wiki page;
- не строить ещё один LightRAG graph;
- не индексировать всё через LLM;
- не делать полный rebuild индексов при каждом новом посте.

Итог: индексы нужны не для "умности", а для управляемости. Они позволяют обновлять только затронутые страницы, быстро находить релевантную wiki-память и всегда возвращаться к первичным источникам.

## Этапы работы

### Этап 0. Подготовительные изменения

Перед созданием полноценной wiki нужно добавить базовые настройки и идентификаторы.

В `config.py`:

```python
WIKI_DIR = OUTPUT_DIR / "wiki"
WIKI_INDEX_DIR = WIKI_DIR / "indexes"
```

В `.env.example`:

```env
WIKI_ENABLED=true
WIKI_TOP_K=5
```

В wiki-index слое:

- вычислять `source_id` из provenance;
- вычислять `content_hash`;
- не требовать миграции всех enriched-карточек сразу;
- писать индексы в `output/wiki/indexes/`.

### Этап 1. Создать wiki scaffold

Создать папки:

```text
output/wiki/
output/wiki/entities/
output/wiki/topics/
output/wiki/claims/
output/wiki/indexes/
```

Создать файлы:

```text
output/wiki/_master_index.md
output/wiki/_schema.md
output/wiki/_health.md
output/wiki/_change_log.md
output/wiki/_log.md
output/wiki/_pending_updates.json
```

### Этап 2. Индексы

Добавить модуль, например:

```text
retrieval/wiki_index.py
```

Он должен уметь:

- читать `output/enriched`;
- извлекать `source_id`;
- вычислять `content_hash`;
- строить `source_to_pages.json`;
- строить `page_to_sources.json`;
- строить `claim_to_sources.json`;
- искать wiki pages по вопросу;
- возвращать ranked wiki context.

Начать можно без LLM:

- keyword matching;
- entity matching;
- topic matching;
- fuzzy matching для русских/английских вариантов имён.

### Этап 3. Генерация MVP wiki pages

Сделать команду:

```powershell
python main.py wiki build
```

Или отдельную:

```powershell
python main.py wiki init
```

Первый MVP:

- 10-20 entity pages;
- 10-20 topic pages;
- 10-30 claim pages;
- обязательно покрыть Венгрию/Орбана/Трампа/Россию/выборы.

На старте страницы можно генерировать шаблонно из enriched cards, без большого LLM.

Страницы, созданные автоматически, должны иметь frontmatter:

```yaml
---
wiki_type: claim
status: supported_by_corpus
generated_by: wiki_seed_v1
review_status: auto
source_count: 4
updated_at: 2026-05-21
---
```

Пока страница не проверена человеком или golden-тестом, `review_status` должен оставаться `auto`.

### Этап 4. Claim extraction

Добавить отдельную логику для claims:

```text
enriched card -> candidate claims -> merge similar claims -> write claim pages
```

Для спорных тем сделать ручные/полуручные правила:

- Trump supported Orban;
- Trump Jr supported Orban;
- Vance supported Orban;
- Orban/Russia energy sanctions;
- TISZA defeated Orban;
- Russia-Hungary relations.

Цель: убрать галлюцинации вида "это фейк", если источники говорят обратное.

Алгоритм первого MVP:

```text
1. читать только triage=keep карточки;
2. брать key_facts[source_claim] и quotes;
3. искать похожие claims по ключевым entities/topics;
4. объединять похожие claims в одну страницу;
5. записывать evidence items со ссылкой на source_id;
6. не повышать thesis/hypothesis до факта;
7. сохранять конфликтующие claims как disputed_in_corpus, а не выбирать сторону автоматически.
```

### Этап 5. Подключить wiki к query

В текущем проекте есть две реальные точки подключения:

```text
retrieval/composer.py        для search-режимов и report output
loader/lightrag_loader.py    для обычного query
```

Лучше начать с read-only подключения в `retrieval/composer.py`, потому что это можно проверить без LLM.

Потом подключать в `loader/lightrag_loader.py`.

Целевая логика:

```text
wiki_context = find_wiki_context(question)
card_context = find_card_context(question)
lightrag_answer = query_lightrag(question)
final_answer = synthesize(wiki_context + card_context + lightrag_answer)
```

Сначала можно без второго LLM synthesis:

- добавить wiki pages в references;
- добавить wiki snippets в prompt/context;
- посмотреть golden.

Потом включить LLM synthesis отдельно.

Важно: сейчас `_extract_query_sources()` в `main.py` умеет маппить references обратно на Telegram metadata через LightRAG/card file paths. Для wiki references нужно добавить resolver:

```text
wiki page -> page_to_sources.json -> source_id -> post_url/normalized_file
```

Иначе пользователь увидит ссылку на wiki page, но не увидит первичный источник.

### Этап 6. Health checks

Создать проверку:

```powershell
python main.py wiki health
```

Проверять:

- страницы без sources;
- claims без status;
- claims без evidence;
- источники, которые никуда не привязаны;
- дубли entities: `Orbán`, `Orban`, `Viktor Orbán`;
- конфликтующие claims;
- слишком большие pages;
- pages, которые давно не обновлялись.

Дополнительные проверки:

- claim page использует `summary/theses` как единственное evidence;
- claim page имеет `supported_by_corpus`, но source_count меньше 1;
- source_id встречается в indexes, но source file уже отсутствует;
- одна и та же карточка попала в противоречащие claims без `disputed_in_corpus`;
- wiki page слишком большая и требует split.

### Этап 7. Golden evaluation

Порядок тестирования:

1. Не делать rebuild.
2. Отключить нестабильные усложнения:

```env
RERANKER_ENABLED=false
HYBRID_SYNTH_ENABLED=false
HYBRID_QUERY_CARDS_ENABLED=true
```

3. Выбрать стабильную `QUERY_MODEL`.
4. Прогнать 3-5 ручных queries.
5. Прогнать golden baseline.
6. Подключить wiki context.
7. Снова прогнать golden.
8. Сравнить ответы по каждому вопросу.
9. Только потом включать:

```env
HYBRID_SYNTH_ENABLED=true
RERANKER_ENABLED=true
```

## LLM notes

Текущие наблюдения по NVIDIA endpoints:

- `mistralai/mistral-large-3-675b-instruct-2512` возвращал `400 DEGRADED function cannot be invoked`;
- `mistralai/mistral-nemotron` отвечал, но иногда генерировал мусорный mixed-language текст;
- `qwen/qwen3-next-80b-a3b-instruct` уходил в timeout;
- `minimaxai/minimax-m2.7` выглядит перспективным кандидатом для query/synthesis, но его нужно проверить отдельно.

Перед честным golden важно очистить активный LightRAG LLM cache, иначе старые плохие ответы могут подмешиваться после смены модели.

Backup cache уже был сохранён как:

```text
rag_storage/kv_store_llm_response_cache.before_hybrid_query_20260519_154036.json
```

## Что не делать сейчас

- Не запускать полный rebuild без необходимости.
- Не строить enriched LightRAG graph заново.
- Не переписывать `rag_storage/`.
- Не делать огромную wiki сразу.
- Не подключать LLM synthesis до baseline-тестов.
- Не включать reranker до baseline-тестов.

## Тесты, которые нужно добавить

Минимальный набор:

```text
test_wiki_index_builds_source_id_from_telegram_provenance
test_wiki_index_computes_stable_content_hash
test_wiki_claim_seed_uses_source_claims_not_hypotheses
test_wiki_claim_seed_does_not_call_supported_claim_fake
test_wiki_search_returns_claim_before_topic
test_wiki_references_resolve_to_original_sources
test_wiki_health_flags_claim_without_evidence
test_query_can_attach_wiki_context_without_second_llm
```

Эти тесты важнее, чем большой golden на старте: они проверяют, что wiki не повторяет главную ошибку старой версии.

## Definition of Done для MVP

MVP считается готовым, если:

- существует `output/wiki/`;
- есть `_master_index.md`;
- есть минимум 10 entity/topic/claim pages по ключевым темам;
- у claim pages есть `Status` и `Evidence`;
- у claim pages есть `review_status`;
- есть `source_to_pages.json` и `page_to_sources.json`;
- query может находить релевантные wiki pages;
- wiki references можно развернуть до исходных Telegram/YouTube sources;
- golden показывает меньше фактических ошибок, чем текущий hybrid без wiki;
- ошибка типа "реальная поддержка Трампа Орбану названа фейком" больше не повторяется.

## Рекомендуемый следующий шаг

Начать не с LLM, а с лёгкого scaffold:

1. создать `output/wiki/`;
2. сделать `retrieval/wiki_index.py`;
3. сгенерировать первые claim/topic/entity pages из `output/enriched`;
4. подключить wiki retrieval к `search` или `query` как read-only context;
5. прогнать 3 ручных вопроса про Трампа/Орбана;
6. только потом думать о LLM synthesis.
