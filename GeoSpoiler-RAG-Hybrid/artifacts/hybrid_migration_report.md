# Hybrid Migration Report

Дата: 2026-05-19

## Итог

Создана отдельная рабочая версия:

`D:\ObsidianWiki\GeoSpoiler-RAG-Hybrid`

Источник базы:

`D:\back up\GeoSpoiler-RAG BackUp v2`

Важно: backup v2 не удалялся и не изменялся.

## Что сохранено из v2

- `output/normalized`: 220 normalized документов.
- `rag_storage`: v2 LightRAG graph.
- `rag_storage/kv_store_doc_status.json`: 220 документов со статусом `processed`.
- `state/progress.json`: v2 progress по каналам.
- Старый `.env` сохранен как `.env.v2_before_hybrid`.

## Что перенесено из текущей версии

- `enricher/`
- `retrieval/`
- `loader/`
- `normalizer/`
- `fetcher/`
- `main.py`
- `config.py`
- `reranker.py`
- `README.md`
- `run_pipeline.ps1`
- `run_pipeline.cmd`
- `run_pipeline_and_test.cmd`
- `.env`
- `.env.example`
- основные тесты
- `artifacts/implementation_plan_hybrid_rag.md`
- `state/enrichment_progress.json`

## Данные enriched-слоя

Из текущей версии перенесены enriched-карточки:

- `output/enriched`: 218 `*.enriched.json`

Они используются как side retrieval / fallback слой, а не как основной источник для LightRAG graph rebuild.

## Зафиксированное поведение

Команды по умолчанию:

```powershell
python main.py load
python main.py rebuild
```

используют `output/normalized`.

Experimental enriched graph build доступен только явно:

```powershell
python main.py load --from-enriched
python main.py rebuild --from-enriched
```

## Полезные улучшения, которые теперь есть в hybrid

- Source-fidelity правила в promptах и postprocess.
- Запрет на вывод технических маркеров в пользовательский ответ.
- Query profiles: `answer`, `source`, `overview`.
- Shadow-search fallback по enriched-карточкам.
- Source metadata index / citation resolver.
- Stable path-based document IDs.
- Timeout/skip логика для зависших inserts.
- `rag_insert_skipped.md` report для пропущенных документов.
- Role-specific model config:
  - `RAG_BUILD_MODEL`
  - `QUERY_MODEL`
  - `FALLBACK_SYNTH_MODEL`
  - `TRANSLATION_MODEL`
  - `ENRICHMENT_MODEL`
- Раздельные задержки:
  - `RAG_BUILD_DELAY_SECONDS`
  - `QUERY_DELAY_SECONDS`
- Triage без `low-value` как нормального пути.
- Enricher chunking/dedup/source card logic.

## Проверки

Syntax check:

```text
py_compile: OK
```

Unit tests:

```text
test_main.py
test_loader.py
test_enricher.py
test_pipeline_stats.py
test_reranker.py

Ran 39 tests
OK
```

Status command:

```text
Normalized files: 220
Pending reviews: 0
```

## Что специально не запускалось

- `main.py rebuild`
- golden set generation
- сетевые тесты `test_openai.py` и `test_api_prompt.py`

Причина: они обращаются к LLM/API или могут занять много времени.

Cards-only search:

```text
python main.py search "Трамп Орбан Венгрия" --mode shadow
OK
```

Этот режим читает enriched-карточки и не вызывает LightRAG/LLM.

## Замечание

Пробный `main.py search "Трамп Орбан Венгрия" --mode recall` был остановлен по таймауту 30 секунд. Это не rebuild и не повредило данные. Причина: `recall` поднимает LightRAG query, а не только быстрый lexical search по карточкам.

После этого добавлен быстрый режим:

```powershell
python main.py search "..." --mode shadow
```
