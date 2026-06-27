---
wiki_type: claim
status: supported_by_corpus
generated_by: wiki_ingest_v1
review_status: auto
source_count: 1
updated_at: 2026-06-26
---

# Утверждается, что за последние 5 лет схема с северокорейскими агентами принесла около $1 млрд на ядерную программу КНДР

Status: supported_by_corpus
Review status: auto
Source count: 1

## Evidence

- telegram:3001055698:24 - source_claim: В посте утверждается, что за последние 5 лет схема принесла Северной Корее около 1 миллиарда долларов.
  - post_url: https://t.me/c/3001055698/24
  - date: 2025-10-11T13:32:49+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\24.enriched.json
  - content_hash: 1d25311e4a38eeecab1619d5033f547b34cb939145892e2a6fd59f1db3f6cd80
- telegram:3001055698:24 - source_claim: В посте указано, что заработанные деньги идут «на благо родине».
  - post_url: https://t.me/c/3001055698/24
  - date: 2025-10-11T13:32:49+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\24.enriched.json
  - content_hash: 1d25311e4a38eeecab1619d5033f547b34cb939145892e2a6fd59f1db3f6cd80

## Guardrails

- Treat Status as corpus status, not external fact-check status.
- Use only cited evidence items when answering from this page.
- Do not use summaries, theses, or hypotheses as direct evidence.
- Separate source claims from author interpretation.
- Отразить как оценку/утверждение, приведенное в исходном посте (source_claim).
- Не конкретизировать метод расчета суммы или источники оценки, которых нет в ключевых фактах карты.

## Related

- indexes/page_to_sources.json
