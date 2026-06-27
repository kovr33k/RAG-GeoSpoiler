---
wiki_type: claim
status: supported_by_corpus
generated_by: wiki_ingest_v1
review_status: auto
source_count: 1
updated_at: 2026-06-26
---

# Утверждается, что с 2022 года Китай сэкономил в торговле с Россией более $20 млрд, а по газу и СПГ экономия добавляет Пекину $7–10 млрд в год

Status: supported_by_corpus
Review status: auto
Source count: 1

## Evidence

- telegram:3001055698:36 - source_claim: В посте говорится, что с 2022 года Китай сэкономил в торговле с Россией более 20 млрд долларов.
  - post_url: https://t.me/c/3001055698/36
  - date: 2025-12-15T10:45:58+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\36.enriched.json
  - content_hash: 75948a69664a1f7b6c6935b30045b9b8dfb67d71786694e5a6f3617763c8f663
- telegram:3001055698:36 - source_claim: В посте утверждается, что по газу и СПГ (включая скидки до 20–30% по санкционным партиям) экономия приносит Пекину еще 7-10 млрд долларов в год.
  - post_url: https://t.me/c/3001055698/36
  - date: 2025-12-15T10:45:58+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\36.enriched.json
  - content_hash: 75948a69664a1f7b6c6935b30045b9b8dfb67d71786694e5a6f3617763c8f663

## Guardrails

- Treat Status as corpus status, not external fact-check status.
- Use only cited evidence items when answering from this page.
- Do not use summaries, theses, or hypotheses as direct evidence.
- Separate source claims from author interpretation.
- Treat Status как статус доказанности в рамках локального корпуса, а не как внешнюю проверку фактов.
- Использовать только процитированные/заявленные в Evidence элементы из карты при изложении содержания на странице.
- Не добавлять оценок и выводов сверх того, что содержится в source_claim в карте.

## Related

- indexes/page_to_sources.json
