---
wiki_type: claim
status: supported_by_corpus
generated_by: wiki_ingest_v1
review_status: auto
source_count: 1
updated_at: 2026-06-26
---

# Утверждается, что Мариуполь подписал с китайским частным образовательным оператором рамочное «стратегическое» соглашение, связанное с рекрутингом студентов на оккупированных территориях

Status: supported_by_corpus
Review status: auto
Source count: 1

## Evidence

- telegram:3001055698:80 - source_claim: Мариуполь подписал соглашение с китайским частным образовательным оператором, которое подаётся как сотрудничество университетов.
  - post_url: https://t.me/c/3001055698/80
  - date: 2026-03-31T17:48:18+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\80.enriched.json
  - content_hash: 0a56b52c22940427024a51def176e8e67eea034e5992f9fda64ad093f37ba5dc
- telegram:3001055698:80 - source_claim: В публикации россияне использовали «неверный» перевод формулировок соглашения.
  - post_url: https://t.me/c/3001055698/80
  - date: 2026-03-31T17:48:18+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\80.enriched.json
  - content_hash: 0a56b52c22940427024a51def176e8e67eea034e5992f9fda64ad093f37ba5dc
- telegram:3001055698:80 - source_claim: Упоминается китайская формулировка 战略合作框架协议 (zhanlüe hezuo kuangjia xieyi) — «рамочное соглашение о стратегическом сотрудничестве».
  - post_url: https://t.me/c/3001055698/80
  - date: 2026-03-31T17:48:18+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\80.enriched.json
  - content_hash: 0a56b52c22940427024a51def176e8e67eea034e5992f9fda64ad093f37ba5dc
- telegram:3001055698:80 - hypothesis: Делается вывод, что компания займётся рекрутингом студентов с участием в китайских стипендиях (грантах), а отбор будет среди украинцев на оккупированных территориях.
  - post_url: https://t.me/c/3001055698/80
  - date: 2026-03-31T17:48:18+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\80.enriched.json
  - content_hash: 0a56b52c22940427024a51def176e8e67eea034e5992f9fda64ad093f37ba5dc

## Guardrails

- Treat Status as corpus status, not external fact-check status.
- Use only cited evidence items when answering from this page.
- Do not use summaries, theses, or hypotheses as direct evidence.
- Separate source claims from author interpretation.
- Разграничивать утверждения автора и формальные детали из текста/терминов карты (например, формулировку 戰略合作框架协议) без расширения за пределы карты.
- Не подменять гипотезы автора фактами: вывод о рекрутинге и грантах отражать как гипотезу/интерпретацию из карточки.

## Related

- indexes/page_to_sources.json
