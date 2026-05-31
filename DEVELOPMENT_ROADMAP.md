# GeoSpoiler RAG: пошаговая дорожная карта разработки

Дата: 2026-05-25

## 0. Что учитывает этот план

Этот документ сводит в один порядок всё, что обсуждалось:

- идеи из отчёта по внешним проектам: GraphRAG, LightRAG, LlamaIndex, Haystack, Onyx, RAGFlow, Ragas/Phoenix, txtai, Khoj, AnythingLLM, Quivr, PrivateGPT;
- вывод по текущему проекту: это уже не простой RAG, а локальная OSINT-memory система;
- решение не делать "идеальный LightRAG" главным направлением;
- идею Karpathy-style LLM wiki;
- файл `wiki_memory_implementation_plan.md`;
- текущее пожелание: **hygiene репозитория пока не трогать**.

## 1. Главная стратегия

Не пытаться превращать LightRAG в идеальное ядро системы.

Основное направление:

```text
Telegram / media / web
  -> normalized source of truth
  -> enriched evidence cards
  -> wiki-memory / claim ledger
  -> search/query/eval
```

LightRAG остаётся полезным нижним слоем для широких связей и ассоциативного поиска, но не должен быть местом, куда запекаются все LLM-интерпретации.

Главная новая ценность должна быть в:

- claim ledger;
- source grounding;
- индексах;
- схемах данных;
- controlled query workflow;
- eval/experiment harness.

## 2. Временно не делаем

### 2.1. Repository hygiene

Пока не трогаем:

- `.env`;
- `state/telegram.session`;
- `rag_storage/`;
- `output/`;
- `media_cache/`;
- `logs/`;
- другие локальные артефакты.

Причина: текущий режим работы удобнее для быстрой разработки, API-ключи пробные, репозиторий приватный.

Важно: это не отменяет того, что позже hygiene нужно будет сделать отдельным этапом. Но в текущей дорожной карте это **не блокер** и **не первый шаг**.

Отдельно: `output/wiki/` на MVP лучше считать локальным generated artifact. Решение, коммитить ли wiki целиком, делать sanitized export или держать её только локально, принимается позже.

### 2.2. Тяжёлые архитектурные действия

Пока не делаем:

- полный rebuild LightRAG без необходимости;
- enriched-card graph rebuild как основной путь;
- новый тяжёлый GraphRAG;
- vector DB для wiki;
- FAISS/Chroma для wiki;
- переписывание всей wiki после каждого импорта;
- LLM synthesis до baseline-проверок;
- большой рефакторинг `main.py` до появления тестовых страховок.

## 3. Принцип выполнения

Работать только маленькими шагами.

Каждый шаг должен иметь:

- конкретный результат;
- маленький набор изменённых файлов;
- проверку;
- понятный failure point.

Если что-то ломается, должно быть ясно, на каком подпункте это произошло.

Рекомендуемый формат работы:

```text
1. Сделать один маленький подпункт.
2. Запустить точечные тесты.
3. Зафиксировать результат в заметке/логах.
4. Только потом переходить дальше.
```

## 4. Этап A. Базовая управляемость без repo hygiene

Цель: сделать проект более контролируемым, но не чистить репозиторий и не менять текущие артефакты.

### A1. Зафиксировать текущую рабочую конфигурацию

Подпункты:

- записать текущие команды запуска pipeline;
- записать текущие команды тестов;
- записать, какие режимы считаются стабильными;
- отдельно отметить, что `rag_storage/` не трогаем.

Проверка:

- `python -m unittest discover -p "test_*.py" -v`;
- ручной `status`;
- ручной `quality`;
- ручной `search --mode shadow`.

Если проблема:

- она относится к текущему baseline, а не к новым изменениям.

### A2. Добавить минимальный `pyproject.toml`

Подпункты:

- описать project metadata;
- перенести/продублировать зависимости из `requirements.txt`;
- добавить настройки pytest/unittest-compatible test discovery;
- добавить ruff config;
- не запускать массовое автоформатирование всего проекта.

Проверка:

- тесты запускаются старым способом;
- ruff можно запустить в report-only режиме.

Если проблема:

- она локализуется в tooling, а не в runtime pipeline.

### A3. Добавить no-network unit-test правило

Подпункты:

- отделить быстрые unit tests от тестов, которые требуют API/Telegram/LLM;
- добавить маркировку или convention для integration tests;
- убедиться, что import тестов не вызывает реальные API.

Проверка:

- быстрые тесты проходят без `.env` и без сети.

Если проблема:

- значит где-то import имеет side effect.

### A4. Добавить pre-commit и CI без блокировки разработки

Подпункты:

- добавить `.pre-commit-config.yaml` с ruff/checks, но сначала использовать мягко;
- добавить GitHub Actions для быстрых no-network tests;
- не делать CI зависимым от `.env`, Telegram session, LLM endpoints или активного `rag_storage`;
- не включать массовое автоформатирование всего проекта одним коммитом.

Проверка:

- локально pre-commit проходит на изменённых файлах;
- CI запускает быстрые тесты без секретов;
- старый ручной workflow остаётся рабочим.

Если проблема:

- проблема относится к workflow/tooling, а не к pipeline.

### A5. Замокать внешние HTTP/LLM/Telegram зависимости

Подпункты:

- для `requests`-кода использовать `responses`, `requests-mock` или `vcrpy`;
- для будущего `httpx`-кода можно использовать `respx`;
- отделить реальные integration tests для Telegram/LLM от unit tests;
- добавить fixtures для типовых LLM ответов, timeout, 429, битого JSON.

Проверка:

- unit tests проходят без сети;
- import тестов не делает API call;
- simulated timeout/429 покрыты отдельными тестами.

Если проблема:

- значит внешний вызов всё ещё спрятан в unit path.

### A6. Проверить кодировки и mojibake без массовой переписи

Подпункты:

- проверить README/docs/test strings на реальные mojibake-артефакты;
- отличать реальную порчу текста от Windows/PowerShell display issue;
- исправлять только подтверждённые битые строки;
- не переписывать большие файлы только ради косметики.

Проверка:

- файлы читаются как UTF-8;
- русские query examples отображаются корректно;
- тесты не меняют смысл из-за перекодировки.

Если проблема:

- проблема в конкретном файле/строке, а не во всей документации сразу.

## 5. Этап B. Data contracts через Pydantic

Цель: перестать верить JSON-файлам на слово.

### B1. Ввести `models.py` или пакет `models/`

Минимальные модели:

- `NormalizedMeta`;
- `EnrichedCard`;
- `Provenance`;
- `KeyFact`;
- `Reference`;
- `SearchResult`;
- `LoadStats`;
- `SourceId`;
- `ContentHash`;
- `WikiPageRef`;
- `QueryProfile`;
- `ExperimentRun`.

Проверка:

- модели импортируются без запуска pipeline;
- тесты создают валидные объекты из минимальных fixtures.

Если проблема:

- видно, какой JSON-контракт расходится с реальными файлами.

### B2. Добавить мягкую валидацию enriched cards

Подпункты:

- читать enriched JSON через Pydantic в новом коде;
- сначала не ломать pipeline на ошибке;
- логировать invalid cards;
- добавить health/report команду позже.

Проверка:

- можно просканировать `output/enriched`;
- получить список проблемных карточек без падения всего процесса.

Если проблема:

- проблема относится к конкретному файлу/card schema.

### B3. Закрепить `claim_type`

Подпункты:

- явно разрешить `fact`, `source_claim`, `hypothesis`;
- неизвестные значения помечать как warning;
- не использовать `summary` и `theses` как прямое доказательство claim.

Проверка:

- тест: `source_claim` проходит;
- тест: `hypothesis` не становится supported claim;
- тест: неизвестный claim_type не ломает весь scan.

## 6. Этап C. Wiki-memory MVP

Цель: реализовать Karpathy-style wiki layer, но с source grounding и guardrails.

Этот этап важнее дальнейшей полировки LightRAG.

### C1. Добавить wiki config

Файлы:

- `config.py`;
- `.env.example`.

Подпункты:

- `WIKI_ENABLED`;
- `WIKI_TOP_K`;
- `WIKI_DIR = OUTPUT_DIR / "wiki"`;
- `WIKI_INDEX_DIR = WIKI_DIR / "indexes"`.

Проверка:

- config импортируется;
- директории не создаются неожиданно при простом import, если проект так не делает в других местах.

Если проблема:

- ошибка изолирована в config.

### C2. Создать wiki scaffold

Структура MVP:

```text
output/wiki/
  _master_index.md
  _schema.md
  _health.md
  _change_log.md
  _log.md
  _pending_updates.json
  entities/
  topics/
  claims/
  indexes/
```

Подпункты:

- сделать команду `python main.py wiki init`;
- scaffold должен быть идемпотентным;
- повторный запуск не должен затирать вручную изменённые страницы.

Проверка:

- первый запуск создаёт файлы;
- второй запуск ничего не ломает.

Если проблема:

- ошибка относится только к scaffold.

### C3. Реализовать `retrieval/wiki_index.py`

Минимальные функции:

- читать enriched cards;
- извлекать `source_id`;
- вычислять `content_hash`;
- строить `source_to_pages.json`;
- строить `page_to_sources.json`;
- строить `claim_to_sources.json`;
- искать wiki pages по вопросу;
- возвращать ranked wiki context.

Правило `source_id`:

```text
telegram:{channel_id}:{message_id}
```

Fallback:

```text
telegram:{channel_name}:{message_id}
```

Проверка:

- тест `test_wiki_index_builds_source_id_from_telegram_provenance`;
- тест `test_wiki_index_computes_stable_content_hash`;
- тест на отсутствие падения при неполной provenance.

Если проблема:

- она в index layer, а не в query/LightRAG.

### C4. Seed первых claim pages без LLM

Не делать сразу 30 claims. Начать с 5-7 опасных claims, где ошибка особенно вредна:

- Trump supported Orban;
- Trump Jr supported Orban;
- Vance supported Orban;
- Orban/Russia energy sanctions;
- TISZA defeated Orban;
- Russia-Hungary relations;
- fake/deepfake separation.

Подпункты:

- брать только `triage=keep`;
- использовать `quotes` и `key_facts[source_claim]`;
- не повышать `hypothesis` до факта;
- не использовать `summary` как единственное evidence;
- использовать только явные claim statuses:
  `supported_by_corpus`, `contradicted_by_corpus`, `disputed_in_corpus`, `unclear_in_corpus`;
- конфликтующие evidence не "разруливать" автоматически, а сохранять как `disputed_in_corpus`;
- добавить `Guardrails` в каждую claim page;
- добавлять frontmatter: `wiki_type`, `status`, `generated_by`, `review_status`, `source_count`, `updated_at`;
- ставить `review_status: auto`.

Команда MVP:

```powershell
python main.py wiki build --claims-only
```

Проверка:

- тест `test_wiki_claim_seed_uses_source_claims_not_hypotheses`;
- тест `test_wiki_claim_seed_does_not_call_supported_claim_fake`;
- ручная проверка 2-3 claim pages.

Если проблема:

- проблема в claim extraction/seed, не в query.

### C5. Добавить entity/topic pages минимально

Подпункты:

- создать 5-10 entity pages по тем же claims;
- создать 5-10 topic pages;
- links должны вести к claim pages;
- source links должны оставаться через claim evidence/indexes.

Проверка:

- `_master_index.md` видит созданные страницы;
- wiki search возвращает claim раньше topic/entity для точного вопроса.

Если проблема:

- проблема в ranking или linking.

### C6. Wiki health

Команда:

```powershell
python main.py wiki health
```

Проверки:

- claim без sources;
- claim без status;
- claim без evidence;
- claim использует только `summary/theses`;
- `supported_by_corpus` при `source_count < 1`;
- fake/deepfake/false label без прямого evidence;
- конфликтующие claims без `disputed_in_corpus`;
- одна карточка попала в противоречащие claims без явной disputed-разметки;
- отсутствуют `generated_by`, `review_status` или `source_count`;
- source_id есть в index, но source file отсутствует;
- wiki page слишком большая;
- wiki reference не разворачивается в первоисточник.

Проверка:

- тест `test_wiki_health_flags_claim_without_evidence`;
- health report создаётся без LLM.

Если проблема:

- она относится к качеству wiki layer.

### C7. Инкрементальное обновление wiki

Цель: новые источники должны обновлять только затронутые страницы, а не всю wiki.

Подпункты:

- использовать `content_hash` для определения changed/unchanged sources;
- писать кандидаты в `_pending_updates.json`;
- обновлять только pages, связанные через `source_to_pages.json`;
- если source новый и не связан ни с одной page, отправлять его в pending review/build queue;
- `_log.md` вести append-only и parseable.

Проверка:

- повторный build без изменений не переписывает wiki pages;
- изменение одного enriched card затрагивает только связанные pages;
- `_pending_updates.json` объясняет, что осталось необработанным.

Если проблема:

- проблема в incremental index/update logic, а не в generation.

## 7. Этап D. Read-only подключение wiki к search

Цель: проверить пользу wiki без вмешательства в основной query и без второго LLM synthesis.

### D1. Подключить wiki context к `retrieval/composer.py`

Подпункты:

- добавить поиск wiki pages по вопросу;
- возвращать wiki results отдельным блоком;
- не менять LightRAG query;
- не вызывать LLM.

Проверка:

- `python main.py search "Трамп Орбан Венгрия" --mode shadow`;
- `python main.py search "Трамп реально поддерживал Орбана?" --mode recall`;
- wiki claim должен появляться выше topic/entity.

Если проблема:

- проблема в composer/ranking, не в LightRAG.

### D2. Добавить wiki references resolver

Подпункты:

- wiki page -> `page_to_sources.json`;
- source_id -> enriched card;
- enriched card -> normalized file/post_url;
- ответ должен показывать первичный Telegram/YouTube source, а не только wiki page.

Проверка:

- тест `test_wiki_references_resolve_to_original_sources`;
- ручной search показывает post_url или normalized_file.

Если проблема:

- проблема в source resolver.

### D3. Обновить formatter

Подпункты:

- в `format_search_results` показать wiki context аккуратно;
- не смешивать wiki page с primary source;
- явно помечать wiki как memory/context, а Telegram/YouTube как source.

Проверка:

- search output читаемый;
- нет ощущения, что wiki является первоисточником.

Если проблема:

- проблема только в presentation layer.

## 8. Этап E. Baseline и golden перед подключением к query

Цель: сравнивать изменения честно.

### E1. Выбрать стабильный query model

Подпункты:

- проверить 3-5 ручных вопросов;
- выбрать временно стабильный `QUERY_MODEL`;
- отдельно проверить кандидаты для query и synthesis, включая `minimaxai/minimax-m2.7`, если он доступен;
- записать выбранную модель и endpoint в baseline metadata;
- отключить нестабильные усложнения:

```env
RERANKER_ENABLED=false
HYBRID_SYNTH_ENABLED=false
HYBRID_QUERY_CARDS_ENABLED=true
```

Проверка:

- 3-5 ручных queries не timeout-ятся;
- ответы не содержат мусор/битую генерацию.

Если проблема:

- проблема в model/endpoint, а не в retrieval.

### E2. Прогнать baseline golden

Подпункты:

- не делать rebuild;
- очистку LightRAG cache делать только отдельным осознанным шагом;
- перед очисткой сохранить backup активного cache;
- помнить про существующий backup:
  `rag_storage/kv_store_llm_response_cache.before_hybrid_query_20260519_154036.json`;
- не сравнивать результаты разных моделей поверх старого LLM cache как честный baseline;
- сохранить результаты как baseline.

Проверка:

- `artifacts/golden_set_results.md`;
- `artifacts/golden_set_scores.json`.

Если проблема:

- baseline фиксирует текущее состояние до wiki-query integration.

### E3. Расширить golden до experiment harness

Добавить в результаты:

- model;
- query profile;
- config flags;
- graph/storage version marker;
- wiki enabled/disabled;
- card top-k;
- wiki top-k;
- latency;
- fallback reason;
- resolved sources;
- score breakdown.

Проверка:

- старые score поля сохраняются;
- новые metadata не ломают чтение results.

Если проблема:

- проблема в eval harness, не в retrieval.

## 9. Этап F. Подключение wiki к обычному query

Цель: дать обычным вопросам пользу от claim ledger, но не создавать новый тяжёлый pipeline.

### F1. Read-only wiki context в `loader/lightrag_loader.py`

Подпункты:

- найти релевантные wiki claims/topics/entities;
- добавить их в context/prompt;
- не включать второй synthesis;
- wiki references резолвить до первоисточников.

Проверка:

- тест `test_query_can_attach_wiki_context_without_second_llm`;
- ручной вопрос про Trump/Orban;
- ответ не должен называть support fake без прямого evidence.

Если проблема:

- проблема в query-context assembly.

### F2. Сравнить golden до/после wiki context

Подпункты:

- прогнать тот же golden;
- сравнить per-case;
- отдельно смотреть вопросы про fake/deepfake/source claims.

Проверка:

- меньше фактических ошибок;
- не хуже source grounding;
- нет роста technical leakage в ответах.

Если проблема:

- можно отключить `WIKI_ENABLED` и вернуться к baseline.

### F3. Только потом пробовать synthesis

Подпункты:

- включить `HYBRID_SYNTH_ENABLED=true` отдельно;
- добавить wiki context в synthesis prompt;
- сравнить golden ещё раз.

Проверка:

- synthesis не ухудшает source grounding;
- не появляются уверенные утверждения без evidence.

Если проблема:

- synthesis выключить, read-only wiki оставить.

### F4. Отдельно проверить reranker

Подпункты:

- включать `RERANKER_ENABLED=true` только после baseline без reranker;
- прогнать тот же набор manual queries;
- прогнать golden и сравнить per-case;
- смотреть отдельно latency, source grounding и ложные уверенные ответы.

Проверка:

- reranker улучшает retrieval/source quality по измеримым cases;
- нет ухудшения на source/provenance questions;
- latency остаётся приемлемой.

Если проблема:

- reranker выключить и не смешивать его эффект с wiki/synthesis изменениями.

## 10. Этап G. Нормальный индекс вместо `shadow_search`

Цель: заменить handmade prefix search на предсказуемый локальный индекс.

### G1. SQLite FTS5 MVP

Почему SQLite FTS5 первым:

- локально;
- без тяжёлой инфраструктуры;
- прозрачно;
- можно хранить metadata рядом с searchable text.

Подпункты:

- создать card index;
- поля: `source_id`, `card_path`, `normalized_file`, `post_url`, `title`, `search_text`, `entities`, `topics`, `claim_types`;
- сделать rebuild command для индекса;
- не заменять старый `shadow_search` сразу.

Проверка:

- одинаковый запрос можно прогнать через old shadow и FTS;
- FTS возвращает не хуже на ручных вопросах.

Если проблема:

- можно временно оставить old shadow как fallback.

### G2. Перевести composer на FTS

Подпункты:

- использовать FTS в `recall`, `shadow/cards-only`;
- старый `shadow_search.py` оставить как compatibility fallback;
- добавить score explanation.

Проверка:

- тесты composer;
- ручные search queries.

Если проблема:

- fallback на старый search.

### G3. Рассмотреть txtai позже

txtai рассматривать только если:

- FTS/BM25 недостаточно;
- нужен embedding search по карточкам;
- есть стабильный eval, который показывает пользу.

## 11. Этап H. Source registry

Цель: получить единый паспорт источников.

### H1. SQLite/DuckDB source registry MVP

Минимальные таблицы:

- `sources`;
- `normalized_docs`;
- `enriched_cards`;
- `processing_runs`;
- `references`.

Подпункты:

- заполнить registry из текущих files;
- не удалять JSON-файлы;
- JSON остаётся export/source artifact.

Проверка:

- source_id резолвится в post_url;
- source_id резолвится в normalized/enriched path;
- registry можно rebuild из файлов.

Если проблема:

- JSON/files остаются fallback.

### H2. Подключить registry к wiki resolver

Подпункты:

- wiki page -> source_id -> registry -> source metadata;
- меньше ручного path lookup;
- единый resolver для query/search/eval.

Проверка:

- wiki references продолжают разворачиваться.

Если проблема:

- временно использовать JSON indexes.

## 12. Этап I. Native video/audio transcription

Цель: закрыть дыру, где Telegram video/voice сейчас превращаются в placeholder.

### I1. Media capture metadata

Подпункты:

- убедиться, что video/audio файлы сохраняются или доступны;
- добавить metadata path;
- не пытаться сразу транскрибировать всё.

Проверка:

- новый Telegram video получает media path/status.

Если проблема:

- проблема в fetcher/media handling.

### I2. Whisper transcription

Подпункты:

- добавить handler для audio/video -> text;
- сохранить transcript как отдельный artifact;
- normalizer добавляет transcript в normalized text;
- enriched pipeline видит это как обычный текст.

Проверка:

- один короткий video/voice проходит end-to-end;
- placeholder больше не единственный контент.

Если проблема:

- проблема в transcription layer, не в wiki/RAG.

### I3. Batch/backfill

Подпункты:

- выбрать несколько старых видео;
- сделать backfill;
- не запускать массовую транскрипцию без контроля.

Проверка:

- enriched cards улучшаются;
- wiki/source registry не ломаются.

## 13. Этап J. Документация

Цель: чтобы проект можно было восстановить и понять через месяц.

Документы:

- `ARCHITECTURE.md`;
- `DATA_CONTRACTS.md`;
- `OPERATIONS.md`;
- `EVAL.md`;
- `WIKI_MEMORY.md`;
- таблица env vars;
- recovery/rebuild runbook.

Порядок:

1. `WIKI_MEMORY.md` после MVP wiki.
2. `DATA_CONTRACTS.md` после Pydantic моделей.
3. `EVAL.md` после experiment harness.
4. `OPERATIONS.md` после source registry/transcription.
5. `ARCHITECTURE.md` после стабилизации query flow.

## 14. Этап K. Наблюдаемость и внешние идеи

Это делать после базового eval.

### K1. Ragas/Phoenix

Использовать для:

- retrieval quality;
- source quality;
- answer faithfulness;
- run comparison.

Не делать до того, как есть:

- baseline;
- experiment metadata;
- стабильный query model.

### K2. Что брать из внешних проектов

Microsoft GraphRAG:

- artifacted indexing pipeline;
- community summaries как идея для будущих topic pages, не для MVP;
- отчёты по build/index;
- local/global query split как идея.

LightRAG:

- upstream storage/query modes;
- rerank hooks;
- меньше локальных костылей вокруг query.

LlamaIndex:

- ingestion stages;
- document/node abstractions;
- metadata filters;
- eval patterns.

Haystack:

- component pipeline architecture;
- typed fetch/normalize/enrich/load components.

Onyx:

- connectors;
- source registry;
- document sets;
- background jobs;
- source permissions как future-proofing, если проект станет командным;
- provenance/admin/debug UX.

RAGFlow:

- ingestion observability;
- parsing/chunk debug UI;
- task status.

Ragas/Phoenix:

- structured experiment comparison;
- retrieval/source/answer-quality traces;
- regression reports after model or index changes.

LangGraph/LangChain:

- рассматривать только для state-machine query workflow;
- не тащить весь LangChain, если текущий код проще и прозрачнее.

Khoj/AnythingLLM/Quivr:

- только UX/workspace ideas;
- upload/source organization и review UX можно смотреть как inspiration, но не как backend reference.

PrivateGPT:

- local/offline packaging ideas;
- не использовать как backend reference до появления реальной offline-packaging цели.

Dify/Flowise:

- сейчас пропустить.

## 15. Этап L. Постепенный refactor

Цель: уменьшить размер и риск `main.py`/`lightrag_loader.py`, но только после тестов.

### L1. Разделить CLI и pipeline

Файлы-кандидаты:

- `cli.py`;
- `pipeline.py`;
- `query.py`;
- `storage.py`;
- `models.py`.

Правило:

- не делать большой refactor отдельным первым шагом;
- выносить функции, когда рядом добавляется новая функциональность;
- после каждого выноса запускать tests.

### L2. Разделить LightRAG query helpers

Кандидаты:

- fallback search;
- hybrid card context;
- reference resolver;
- prompt profiles;
- LightRAG creation/loading.

Проверка:

- golden/manual query до и после не меняются без причины.

## 16. Рекомендуемый порядок исполнения

Итоговая очередь:

```text
A. Базовая управляемость без repo hygiene
B. Pydantic data contracts
C. Wiki-memory MVP
D. Read-only wiki search integration
E. Baseline/golden experiment harness
F. Wiki context в обычный query
G. SQLite FTS вместо shadow_search
H. Source registry
I. Native video/audio transcription
J. Документация
K. Observability / Ragas / Phoenix
L. Постепенный refactor
```

Если хочется двигаться ещё быстрее именно к пользе, допустим короткий маршрут:

```text
C1 -> C2 -> C3 -> C4 -> C6 -> D1 -> D2 -> E1 -> E2 -> F1
```

То есть сначала wiki/claims, потом read-only search, потом baseline, потом query.

Если нужен максимально контролируемый короткий маршрут с инкрементальностью:

```text
C1 -> C2 -> C3 -> C4 -> C6 -> C7 -> D1 -> D2 -> E1 -> E2 -> F1
```

## 17. Definition of Done для ближайшего MVP

MVP считается готовым, если:

- существует `output/wiki/`;
- есть `_schema.md`, `_master_index.md`, `_log.md`;
- есть минимум 5-7 claim pages по опасным claims;
- у claim pages есть `status`, `review_status`, `Evidence`, `Guardrails`;
- есть `source_to_pages.json`;
- есть `page_to_sources.json`;
- есть `claim_to_sources.json`;
- у sources есть стабильный `source_id` и `content_hash`;
- wiki search находит claim раньше topic/entity;
- wiki reference разворачивается в Telegram/YouTube первоисточник;
- обычный `search` может показать wiki context без LLM;
- есть health check для claims без evidence;
- повторный wiki build без изменений не переписывает страницы;
- ручной вопрос про Trump/Orban больше не превращает supported source claim в fake/deepfake без прямого evidence.

## 18. Правило остановки

Останавливаем внедрение следующего этапа, если:

- тесты предыдущего этапа не проходят;
- wiki reference не резолвится в первоисточник;
- claim создаётся из `summary/theses` без evidence;
- модель начинает уверенно утверждать то, чего нет в источниках;
- изменение требует rebuild LightRAG без отдельного решения.

В этом случае фиксируется:

- этап;
- подпункт;
- изменённые файлы;
- команда проверки;
- фактический симптом.
