---
wiki_type: claim
status: supported_by_corpus
generated_by: wiki_ingest_v1
review_status: auto
source_count: 1
updated_at: 2026-06-26
---

# Утверждается, что материал на Militarnyi («Миллионы глаз и ушей») описывает использование гражданских китайских устройств в гибридных воздействиях против Украины и стран Запада через сбор и хранение данных

Status: supported_by_corpus
Review status: auto
Source count: 1

## Evidence

- telegram:3001055698:39 - source_claim: На «Миллитарном» вышел материал команды «Миллионы глаз и ушей. Как китайские электрокары и девайсы угрожают Украине и Западу».
  - post_url: https://t.me/c/3001055698/39
  - date: 2025-12-30T14:14:45+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\39.enriched.json
  - content_hash: 7b4ad211daabfbb4d6082b0b3f04ea2d6c189e75785b778ba79665b7522a4ebf
- telegram:3001055698:39 - source_claim: В материале указано, что гражданские китайские устройства могут использоваться Пекином в гибридных воздействиях против Украины.
  - post_url: https://t.me/c/3001055698/39
  - date: 2025-12-30T14:14:45+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\39.enriched.json
  - content_hash: 7b4ad211daabfbb4d6082b0b3f04ea2d6c189e75785b778ba79665b7522a4ebf
- telegram:3001055698:39 - source_claim: В посте говорится, что в материале раскрывается, как и где хранится информация с устройств, и как Китай может потом использовать это против Украины и ее страны.
  - post_url: https://t.me/c/3001055698/39
  - date: 2025-12-30T14:14:45+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\39.enriched.json
  - content_hash: 7b4ad211daabfbb4d6082b0b3f04ea2d6c189e75785b778ba79665b7522a4ebf

## Guardrails

- Treat Status as corpus status, not external fact-check status.
- Use only cited evidence items when answering from this page.
- Do not use summaries, theses, or hypotheses as direct evidence.
- Separate source claims from author interpretation.
- Treat Status как статус доказанности в рамках локального корпуса, а не как внешнюю проверку утверждений из материала.
- Описывать именно то, что заявлено в source_claim в карточке (про содержание материала), без самостоятельных технических выводов.
- Не добавлять деталей о методах или последствиях, не присутствующих в процитированных source_claim.

## Related

- indexes/page_to_sources.json
