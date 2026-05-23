# Hybrid Project Audit

Дата: 2026-05-19

## Короткий вывод

Рабочая hybrid-версия собрана на базе v2. Основная работа из implementation plan уже сделана: сохранён стабильный v2 `rag_storage`, добавлен enriched-card слой, обычный `query` теперь умеет усиливать ответ LightRAG релевантными карточками, а быстрый локальный поиск доступен через `--mode shadow`.

Что ещё не сделано:

- golden set на hybrid ещё не прогонялся;
- rebuild после перехода на hybrid не запускался;
- модель для обычного `query` / golden пока не выбрана окончательно.

Главный текущий риск не в коде, а в LLM-конфигурации: разные NVIDIA endpoints дают разные проблемы, поэтому golden сейчас нельзя честно запускать без выбора стабильной модели.

## Что проверено

Команды:

```text
python -m py_compile main.py loader/lightrag_loader.py test_loader.py
python -m unittest discover -p "test_*.py" -v
python main.py status
python main.py quality
python main.py search "Трамп Орбан Венгрия" --mode shadow
```

Результаты:

```text
Unit tests: 51 tests OK
Status: 220 normalized files, 0 pending reviews
Quality: 991 nodes, 1315 edges, largest component 757
Shadow search: OK, нашёл релевантные карточки по Трамп/Орбан/Венгрия
Active python processes after checks: none
```

`git status` не сработал, потому что `GeoSpoiler-RAG-Hybrid` сейчас не является git-репозиторием.

## Что уже перенесено из новой версии

- `enricher/` и `output/enriched/` как side retrieval слой.
- `retrieval/` composer и shadow/card search.
- Улучшенный `loader/lightrag_loader.py` с timeout/skip логикой для зависших insert.
- Отчёт по пропущенным insert: `artifacts/rag_insert_skipped.md`.
- Role-specific задержки/таймауты для LLM.
- Обновлённые CLI wrappers: `run_pipeline.ps1`, `run_pipeline.cmd`, `run_pipeline_and_test.cmd`.
- Тесты для loader/main/reranker/enricher/handlers.
- `.env.example` с гибридными и role-specific настройками.

## Что изменено в hybrid

1. `main.py`

- `load` и `rebuild` по умолчанию строят граф из `output/normalized`.
- Enriched graph теперь включается только явно через `--from-enriched`.
- `query` безопасно вызывает `_finalize_rag_safely(rag)` даже после fallback, чтобы не оставлять зависший Python-процесс.
- `run_pipeline.ps1` получил команду `golden`.

2. `loader/lightrag_loader.py`

- Обычный `query` теперь работает как hybrid path:
  - сначала получает ответ от LightRAG;
  - затем подбирает релевантные enriched-card совпадения;
  - добавляет card references в `data.references`;
  - при включённом `HYBRID_SYNTH_ENABLED=true` пересобирает финальный ответ из `LightRAG answer + enriched-card context`.
- Если LightRAG query падает, timeout-ится или возвращает мусор, включается shadow fallback.
- Добавлена защита от явно битых LLM-ответов с маркерами вроде `malloc`, `qqball`, `трамппс`.
- Fallback больше не показывает пользователю техническую фразу `Точный поиск по карточкам`.

3. Тесты

- `test_openai.py` и `test_api_prompt.py` больше не делают реальные API-запросы при import.
- `test_handlers.py` больше не тянет старый проект через hardcoded path.
- `test_pipeline_stats.py` мокает translation и не ждёт LLM timeout.
- Добавлены тесты для hybrid-card context, fallback при падении LightRAG и детекции мусорных ответов.

## LLM-находки

Проверки показали три разные проблемы на runtime:

- `mistralai/mistral-large-3-675b-instruct-2512`: endpoint вернул `400 DEGRADED function cannot be invoked`.
- `mistralai/mistral-nemotron`: endpoint ответил, но сгенерировал мусорный mixed-language текст с признаками повреждённого вывода.
- `qwen/qwen3-next-80b-a3b-instruct`: на обычном query ушёл в timeout.

Также найден важный источник путаницы: LightRAG LLM cache может переиспользовать плохой ответ после смены модели. Активный cache был сохранён как:

```text
rag_storage/kv_store_llm_response_cache.before_hybrid_query_20260519_154036.json
```

Сейчас это backup-файл, его не надо удалять до сравнения. Но перед честным golden желательно стартовать с чистым активным LLM cache.

## Ненужные файлы

Уже очищено:

- все найденные `__pycache__/`;
- `.tmp-tests/`;
- старые top-level `query_output.txt`;
- старый top-level `test_results.txt`.

Можно удалять без потери логики, если появятся снова:

- `__pycache__/`;
- `.tmp-tests/`;
- временные `query_output.txt` / `test_results.txt`;
- старые `logs/*.log`, если они не нужны для истории.

Не удалять автоматически:

- `rag_storage/` — активный v2 graph;
- `output/normalized/` — источник истины;
- `output/enriched/` — side retrieval слой;
- `media_cache/` — нужен для повторной нормализации/визуалов;
- `.env.v2_before_hybrid` — снимок v2 config;
- `rag_storage_backups/`;
- `rag_storage_failed_rebuild_20260430_010418/`;
- `rag_storage_failed_rebuild_20260430_010659/`;
- `kv_store_llm_response_cache.before_hybrid_query_20260519_154036.json`.

## Оставшиеся проблемы

1. Нужно выбрать стабильную `QUERY_MODEL`.

Без этого golden будет проверять не качество hybrid-архитектуры, а случайные проблемы endpoint/model.

2. Reranker может мешать оценке.

Для первого честного golden лучше временно поставить:

```env
RERANKER_ENABLED=false
```

Потом отдельно включить и сравнить.

3. Alias-дубли в graph ещё есть.

Не блокер для hybrid, но перед финальной оценкой можно отдельно почистить:

- `Viktor Orbán`;
- `Orbán`;
- `Viktor Orban`;
- другие case-only пары из `quality`.

4. `recall` search использует LightRAG/LLM.

Для быстрого локального поиска без LLM использовать:

```powershell
python main.py search "..." --mode shadow
```

5. Golden ещё не запускался.

Запускать стоит только после выбора модели и решения, включать ли synthesis:

```env
HYBRID_QUERY_CARDS_ENABLED=true
HYBRID_SYNTH_ENABLED=true
HYBRID_QUERY_CARDS_TOP_K=3
```

Для первого сравнения можно начать с более стабильного режима:

```env
HYBRID_SYNTH_ENABLED=false
RERANKER_ENABLED=false
```

Так мы проверим, что LightRAG-ответы хотя бы получают правильные card references, без второго LLM-вызова.
