---
wiki_type: claim
status: supported_by_corpus
generated_by: wiki_ingest_v1
review_status: auto
source_count: 1
updated_at: 2026-06-26
---

# Утверждается, что северокорейские айтишники проникают в IT-компании, используя поддельные личности, дипфейки и фальшивые резюме

Status: supported_by_corpus
Review status: auto
Source count: 1

## Evidence

- telegram:3001055698:24 - source_claim: В последнее время в IT-компании начали проникать северокорейские айтишники.
  - post_url: https://t.me/c/3001055698/24
  - date: 2025-10-11T13:32:49+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\24.enriched.json
  - content_hash: 1d25311e4a38eeecab1619d5033f547b34cb939145892e2a6fd59f1db3f6cd80
- telegram:3001055698:24 - source_claim: В посте утверждается, что северокорейские айтишники покупают или крадут чужие личности, подделывают резюме или проходят собеседования с помощью дипфейков.
  - post_url: https://t.me/c/3001055698/24
  - date: 2025-10-11T13:32:49+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\24.enriched.json
  - content_hash: 1d25311e4a38eeecab1619d5033f547b34cb939145892e2a6fd59f1db3f6cd80

## Guardrails

- Treat Status as corpus status, not external fact-check status.
- Use only cited evidence items when answering from this page.
- Do not use summaries, theses, or hypotheses as direct evidence.
- Separate source claims from author interpretation.
- Не подтверждать описанную схему за пределами текста поста; отражать как утверждение из карты (source_claim).
- Не добавлять новых механизмов/инструментов, которых нет в key_facts.

## Related

- indexes/page_to_sources.json
