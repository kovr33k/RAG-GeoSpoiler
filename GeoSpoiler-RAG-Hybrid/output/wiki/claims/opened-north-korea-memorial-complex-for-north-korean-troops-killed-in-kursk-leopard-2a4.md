---
wiki_type: claim
status: supported_by_corpus
generated_by: wiki_ingest_v1
review_status: auto
source_count: 1
updated_at: 2026-06-26
---

# В Северной Корее открыли мемориальный комплекс для бойцов северокорейских войск, погибших в Курской области; среди экспонатов — Leopard 2A4 с отметкой об уничтожении 11 февраля 2025 года

Status: supported_by_corpus
Review status: auto
Source count: 1

## Evidence

- telegram:3215620297:37 - source_claim: В посте: «В Северной Корее открыли мемориальный комплекс, посвящённый бойцам северокорейских войск, погибшим в Курской области».
  - post_url: https://t.me/c/3215620297/37
  - date: 2026-04-26T19:58:31+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Корея\37.enriched.json
  - content_hash: 6d3378fe28e47b38834f8042882bdd70a3b3d5fbb9b9cc0d5c7090f25bbc2b63
- telegram:3215620297:37 - source_claim: На табличке у танка указано: «Танк немецкого производства» и «Leopard 2A4 MBT (Германия)».
  - post_url: https://t.me/c/3215620297/37
  - date: 2026-04-26T19:58:31+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Корея\37.enriched.json
  - content_hash: 6d3378fe28e47b38834f8042882bdd70a3b3d5fbb9b9cc0d5c7090f25bbc2b63
- telegram:3215620297:37 - source_claim: На табличке у танка указано: «Уничтожен 11 февраля 2025 года вблизи города Чутья, Курская область».
  - post_url: https://t.me/c/3215620297/37
  - date: 2026-04-26T19:58:31+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Корея\37.enriched.json
  - content_hash: 6d3378fe28e47b38834f8042882bdd70a3b3d5fbb9b9cc0d5c7090f25bbc2b63

## Guardrails

- Treat Status as corpus status, not external fact-check status.
- Use only cited evidence items when answering from this page.
- Do not use summaries, theses, or hypotheses as direct evidence.
- Separate source claims from author interpretation.
- Описывать только подтвержденные карточкой факты (например, табличку с Leopard 2A4 и датой уничтожения) и не делать выводов по hypothesis-элементам. [telegram:3215620297:37]
- Если в карточке упомянуты предположения (hypothesis) про тип других машин, их не включать в утверждение без отдельного подтверждения. [telegram:3215620297:37]

## Related

- claims/kim-jong-un-opened-new-housing-area-sebeol-for-families-of-fallen-north-korean-soldiers-from-kursk.md
- claims/north-korean-soldiers-sent-to-russia-to-fight-in-ukraine-over-10000-in-claimed-report.md
