---
wiki_type: claim
status: supported_by_corpus
generated_by: wiki_ingest_v1
review_status: auto
source_count: 1
updated_at: 2026-06-26
---

# Утверждается, что Пхеньян еще не освоил технологию повторного входа в атмосферу, но этот вопрос может быть решен в ближайшее время

Status: supported_by_corpus
Review status: auto
Source count: 1

## Evidence

- telegram:3001055698:12 - source_claim: В заявлении говорится, что Пхеньян еще не освоил технологию повторного входа в атмосферу.
  - post_url: https://t.me/c/3001055698/12
  - date: 2025-09-25T22:09:22+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\12.enriched.json
  - content_hash: a771e5ecfb1da4e58fef968af9806d108144224358a486f3691a73bceb419873
- telegram:3001055698:12 - source_claim: Ли Чжэ Мён сказал, что вопрос повторного входа может быть решен в ближайшее время.
  - post_url: https://t.me/c/3001055698/12
  - date: 2025-09-25T22:09:22+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\12.enriched.json
  - content_hash: a771e5ecfb1da4e58fef968af9806d108144224358a486f3691a73bceb419873

## Guardrails

- Treat Status as corpus status, not external fact-check status.
- Use only cited evidence items when answering from this page.
- Do not use summaries, theses, or hypotheses as direct evidence.
- Separate source claims from author interpretation.
- Формулировать как переданное утверждение из поста (source_claim).
- Не расширять до утверждений о конкретных сроках или технических методах вне карты.

## Related

- indexes/page_to_sources.json
