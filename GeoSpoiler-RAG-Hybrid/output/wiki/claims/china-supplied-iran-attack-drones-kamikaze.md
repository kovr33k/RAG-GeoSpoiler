---
wiki_type: claim
status: supported_by_corpus
generated_by: wiki_ingest_v1
review_status: auto
source_count: 1
updated_at: 2026-06-26
---

# Утверждается, что Китай поставил Ирану «наступательные» вооружения, включая боевые дроны-камикадзе

Status: supported_by_corpus
Review status: auto
Source count: 1

## Evidence

- telegram:3001055698:67 - source_claim: Китай поставил Ирану «наступательные» вооружения.
  - post_url: https://t.me/c/3001055698/67
  - date: 2026-02-28T15:43:39+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\67.enriched.json
  - content_hash: 699808edfc56a53a93590ca6cd4c6d37c164587e39a79a0d31e23da15386bb10
- telegram:3001055698:67 - source_claim: В поставки входят боевые дроны-камикадзе.
  - post_url: https://t.me/c/3001055698/67
  - date: 2026-02-28T15:43:39+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\67.enriched.json
  - content_hash: 699808edfc56a53a93590ca6cd4c6d37c164587e39a79a0d31e23da15386bb10

## Guardrails

- Treat Status as corpus status, not external fact-check status.
- Use only cited evidence items when answering from this page.
- Do not use summaries, theses, or hypotheses as direct evidence.
- Separate source claims from author interpretation.
- Фиксировать как утверждение из поста, не расширяя номенклатуру вооружений сверх указанных в источнике.
- Не добавлять оценок эффективности/назначения, не содержащихся в источнике.

## Related

- indexes/page_to_sources.json
