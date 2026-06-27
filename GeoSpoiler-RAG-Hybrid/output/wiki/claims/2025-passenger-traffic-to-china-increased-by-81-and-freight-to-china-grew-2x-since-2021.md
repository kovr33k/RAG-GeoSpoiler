---
wiki_type: claim
status: supported_by_corpus
generated_by: wiki_ingest_v1
review_status: auto
source_count: 1
updated_at: 2026-06-26
---

# Утверждается, что в 2025 году пассажиропоток в Китай вырос на 81%, а грузопоток в сообщении с Китаем с 2021 года — вдвое

Status: supported_by_corpus
Review status: auto
Source count: 1

## Evidence

- telegram:3001055698:83 - source_claim: В 2025 году пассажиропоток в Китай вырос на 81%.
  - post_url: https://t.me/c/3001055698/83
  - date: 2026-04-04T14:03:25+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\83.enriched.json
  - content_hash: aaa17c8977410aecda4b2eef1b9f6b7d4d08067e027ae32ef140dbd1478a450d
- telegram:3001055698:83 - source_claim: Грузопоток в сообщении с Китаем с 2021 года вырос вдвое.
  - post_url: https://t.me/c/3001055698/83
  - date: 2026-04-04T14:03:25+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\83.enriched.json
  - content_hash: aaa17c8977410aecda4b2eef1b9f6b7d4d08067e027ae32ef140dbd1478a450d

## Guardrails

- Treat Status as corpus status, not external fact-check status.
- Use only cited evidence items when answering from this page.
- Do not use summaries, theses, or hypotheses as direct evidence.
- Separate source claims from author interpretation.
- Оставлять цифры как утверждения из карточки, без проверки/пересчета.

## Related

- indexes/page_to_sources.json
