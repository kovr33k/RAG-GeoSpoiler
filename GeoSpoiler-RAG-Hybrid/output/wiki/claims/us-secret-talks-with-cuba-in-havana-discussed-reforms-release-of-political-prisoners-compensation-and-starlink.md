---
wiki_type: claim
status: supported_by_corpus
generated_by: wiki_ingest_v1
review_status: auto
source_count: 1
updated_at: 2026-06-26
---

# США впервые за 10 лет провели тайные переговоры с Кубой в Гаване, обсуждая реформы, освобождение политзаключённых, компенсации и Starlink

Status: supported_by_corpus
Review status: auto
Source count: 1

## Evidence

- telegram:3841808641:8 - source_claim: В посте сообщается, что США впервые за 10 лет провели тайные переговоры с Кубой в Гаване.
  - post_url: https://t.me/c/3841808641/8
  - date: 2026-04-18T16:14:14+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Куба\8.enriched.json
  - content_hash: f8d0ae47c3e5c346fce3618d7f9c57aedae25ea0a39de4c3300f06628b43d149
- telegram:3841808641:8 - source_claim: В посте говорится, что во время встреч обсуждались экономические реформы, освобождение политзаключённых и выплата компенсации американским гражданам и корпорациям за конфискованные активы после 1959 года.
  - post_url: https://t.me/c/3841808641/8
  - date: 2026-04-18T16:14:14+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Куба\8.enriched.json
  - content_hash: f8d0ae47c3e5c346fce3618d7f9c57aedae25ea0a39de4c3300f06628b43d149
- telegram:3841808641:8 - source_claim: В посте утверждается, что в обмен на выполнение требований США предложили обсудить снятие торгового эмбарго и предоставить доступ к спутниковой связи Starlink.
  - post_url: https://t.me/c/3841808641/8
  - date: 2026-04-18T16:14:14+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Куба\8.enriched.json
  - content_hash: f8d0ae47c3e5c346fce3618d7f9c57aedae25ea0a39de4c3300f06628b43d149

## Guardrails

- Treat Status as corpus status, not external fact-check status.
- Use only cited evidence items when answering from this page.
- Do not use summaries, theses, or hypotheses as direct evidence.
- Separate source claims from author interpretation.
- Сохранять привязку к содержанию поста (как источник утверждений), не расширять перечень тем сверх карты.
- Не утверждать внешние причинно-следственные связи, которых нет в карте.

## Related

- indexes/page_to_sources.json
