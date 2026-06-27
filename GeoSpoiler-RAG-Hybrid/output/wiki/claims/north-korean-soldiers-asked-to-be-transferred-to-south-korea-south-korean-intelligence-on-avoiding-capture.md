---
wiki_type: claim
status: supported_by_corpus
generated_by: wiki_ingest_v1
review_status: auto
source_count: 1
updated_at: 2026-06-26
---

# Утверждается, что северокорейские военнопленные в Украине просили передать их Южной Корее; южнокорейская разведка заявляет об инструкциях избегать плена

Status: supported_by_corpus
Review status: auto
Source count: 1

## Evidence

- telegram:3215620297:2 - source_claim: Двое северокорейских военнопленных в Украине обратились с просьбой передать их Южной Корее.
  - post_url: https://t.me/c/3215620297/2
  - date: 2025-11-02T15:31:45+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Корея\2.enriched.json
  - content_hash: a5dd4532be4ce5b2403587b846054e50400cf35b4d346b58e8fe5f0ad736893c
- telegram:3215620297:2 - source_claim: По данным разведслужбы Южной Кореи, северокорейские солдаты обычно получают приказ покончить с собой, чтобы не попасть в плен.
  - post_url: https://t.me/c/3215620297/2
  - date: 2025-11-02T15:31:45+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Корея\2.enriched.json
  - content_hash: a5dd4532be4ce5b2403587b846054e50400cf35b4d346b58e8fe5f0ad736893c
- telegram:3215620297:2 - source_claim: В сообщении говорится, что в случае ранения северокорейские солдаты совершают самоподрыв с помощью гранат.
  - post_url: https://t.me/c/3215620297/2
  - date: 2025-11-02T15:31:45+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Корея\2.enriched.json
  - content_hash: a5dd4532be4ce5b2403587b846054e50400cf35b4d346b58e8fe5f0ad736893c

## Guardrails

- Treat Status as corpus status, not external fact-check status.
- Use only cited evidence items when answering from this page.
- Do not use summaries, theses, or hypotheses as direct evidence.
- Separate source claims from author interpretation.
- Treat Status as corpus status, not external fact-check status (supported_by_corpus).
- Use only cited evidence items when writing from this page.
- Не использовать неподтвержденные интерпретации: фиксировать только то, что прямо следует из evidence.

## Related

- indexes/page_to_sources.json
