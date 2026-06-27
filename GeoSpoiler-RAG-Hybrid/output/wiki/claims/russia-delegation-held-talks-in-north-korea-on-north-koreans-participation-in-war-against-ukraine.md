---
wiki_type: claim
status: supported_by_corpus
generated_by: wiki_ingest_v1
review_status: auto
source_count: 1
updated_at: 2026-06-26
---

# Утверждается, что делегация РФ провела в КНДР переговоры об участии северокорейцев в войне против Украины

Status: supported_by_corpus
Review status: auto
Source count: 1

## Evidence

- telegram:3215620297:4 - source_claim: Делегация РФ провела в КНДР новые переговоры об участии северокорейцев в войне против Украины.
  - post_url: https://t.me/c/3215620297/4
  - date: 2025-11-07T15:56:17+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Корея\4.enriched.json
  - content_hash: 3087343ab38bd3f7fb4cee9d4602b2834c34ddcd3aa2146ff398e552048c6c55
- telegram:3215620297:4 - source_claim: В сообщении северокорейского государственного информационного агентства ЦТАК говорится, что переговоры прошли в дружественной обстановке.
  - post_url: https://t.me/c/3215620297/4
  - date: 2025-11-07T15:56:17+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Корея\4.enriched.json
  - content_hash: 3087343ab38bd3f7fb4cee9d4602b2834c34ddcd3aa2146ff398e552048c6c55
- telegram:3215620297:4 - source_claim: Южнокорейская разведка (NIS) ранее сообщала, что по итогам этих переговоров в Россию будет направлено до пяти тысяч северокорейских военных.
  - post_url: https://t.me/c/3215620297/4
  - date: 2025-11-07T15:56:17+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Корея\4.enriched.json
  - content_hash: 3087343ab38bd3f7fb4cee9d4602b2834c34ddcd3aa2146ff398e552048c6c55

## Guardrails

- Treat Status as corpus status, not external fact-check status.
- Use only cited evidence items when answering from this page.
- Do not use summaries, theses, or hypotheses as direct evidence.
- Separate source claims from author interpretation.
- Разделять утверждения разных источников в карточке (ЦТАК vs NIS) и не объединять их в один факт без оговорок. (telegram:3215620297:4)

## Related

- indexes/page_to_sources.json
