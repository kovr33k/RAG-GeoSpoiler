---
wiki_type: claim
status: supported_by_corpus
generated_by: wiki_ingest_v1
review_status: auto
source_count: 1
updated_at: 2026-06-26
---

# Утверждается, что США внедрили «правило 50%», при котором экспортные ограничения автоматически распространяются на компанию, если доля связанной «черным списком» структуры превышает 50%

Status: supported_by_corpus
Review status: auto
Source count: 1

## Evidence

- telegram:3001055698:25 - source_claim: 29 сентября США внедрили «правило 50%»: экспортные ограничения автоматически распространяются на любую компанию, если доля компании из «черного списка» превышает 50% в её структуре собственности.
  - post_url: https://t.me/c/3001055698/25
  - date: 2025-10-11T23:00:54+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\25.enriched.json
  - content_hash: 6c4210bcea6af205335088df29a00c5030f1c087c326b271f16de0f04d15c07d
- telegram:3001055698:25 - quote: «Отныне под экспортные ограничения США автоматически попадает любая компания, если доля уже «ограниченной на экспорт США» компании в ней превышает 50%.»
  - post_url: https://t.me/c/3001055698/25
  - date: 2025-10-11T23:00:54+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\25.enriched.json
  - content_hash: 6c4210bcea6af205335088df29a00c5030f1c087c326b271f16de0f04d15c07d

## Guardrails

- Treat Status as corpus status, not external fact-check status.
- Use only cited evidence items when answering from this page.
- Do not use summaries, theses, or hypotheses as direct evidence.
- Separate source claims from author interpretation.
- Не трактовать как верифицированный юридический текст; отражать как утверждение, изложенное в карте (fact/quote).
- Не переносить детализацию (например, конкретные исключения) сверх приведенных в key_facts/quotes.

## Related

- indexes/page_to_sources.json
