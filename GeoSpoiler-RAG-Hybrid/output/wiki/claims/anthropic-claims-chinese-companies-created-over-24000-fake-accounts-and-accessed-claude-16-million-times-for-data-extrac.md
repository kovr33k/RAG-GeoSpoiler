---
wiki_type: claim
status: supported_by_corpus
generated_by: wiki_ingest_v1
review_status: auto
source_count: 1
updated_at: 2026-06-26
---

# Anthropic обвиняет китайские компании в создании более 24 000 поддельных аккаунтов и в обращениях к Claude свыше 16 млн раз для извлечения данных

Status: supported_by_corpus
Review status: auto
Source count: 1

## Evidence

- telegram:3001055698:61 - source_claim: В посте говорится, что Anthropic заявила: три китайские компании создали более 24 000 поддельных аккаунтов.
  - post_url: https://t.me/c/3001055698/61
  - date: 2026-02-23T20:20:49+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\61.enriched.json
  - content_hash: b074973bcc52b5f507610d541e39a10d2eb37565d8379f8eae7a092b8eeec2c2
- telegram:3001055698:61 - source_claim: В посте утверждается, что эти три китайские компании более 16 миллионов раз обращались к модели Claude от Anthropic для извлечения данных для собственных систем.
  - post_url: https://t.me/c/3001055698/61
  - date: 2026-02-23T20:20:49+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\61.enriched.json
  - content_hash: b074973bcc52b5f507610d541e39a10d2eb37565d8379f8eae7a092b8eeec2c2

## Guardrails

- Treat Status as corpus status, not external fact-check status.
- Use only cited evidence items when answering from this page.
- Do not use summaries, theses, or hypotheses as direct evidence.
- Separate source claims from author interpretation.
- Фиксировать формулировки как утверждения из поста/сообщения (обвинения Anthropic), не подменяя их проверенными фактами.
- Не добавлять дополнительные детали, не присутствующие в источнике.

## Related

- indexes/page_to_sources.json
