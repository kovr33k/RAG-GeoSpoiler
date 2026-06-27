---
wiki_type: claim
status: supported_by_corpus
generated_by: wiki_ingest_v1
review_status: auto
source_count: 1
updated_at: 2026-06-26
---

# Утверждается, что Вьетнам ускорил намыв в Спратли в 2025 году, строил на ранее нетронутых рифах и превратил контролируемые им рифы и отмели в искусственные острова с военной инфраструктурой

Status: supported_by_corpus
Review status: auto
Source count: 1

## Evidence

- telegram:3001055698:38 - source_claim: В 2025 году Вьетнам существенно ускорил работы по намыву искусственных островов в архипелаге Спратли.
  - post_url: https://t.me/c/3001055698/38
  - date: 2025-12-20T14:56:52+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\38.enriched.json
  - content_hash: 87312b90ad5a75f0fa2378e0cb5a29028627b79f66edff643eac8d60732f64d1
- telegram:3001055698:38 - source_claim: Вьетнам в 2025 году начал строительство на восьми ранее нетронутых рифах в архипелаге Спратли.
  - post_url: https://t.me/c/3001055698/38
  - date: 2025-12-20T14:56:52+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\38.enriched.json
  - content_hash: 87312b90ad5a75f0fa2378e0cb5a29028627b79f66edff643eac8d60732f64d1
- telegram:3001055698:38 - source_claim: В посте утверждается, что таким образом Ханой завершил расширение всех 21 контролируемых им рифов и отмелей.
  - post_url: https://t.me/c/3001055698/38
  - date: 2025-12-20T14:56:52+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\38.enriched.json
  - content_hash: 87312b90ad5a75f0fa2378e0cb5a29028627b79f66edff643eac8d60732f64d1
- telegram:3001055698:38 - source_claim: В посте утверждается, что рифы и отмели превращены в искусственные острова с военной инфраструктурой.
  - post_url: https://t.me/c/3001055698/38
  - date: 2025-12-20T14:56:52+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\38.enriched.json
  - content_hash: 87312b90ad5a75f0fa2378e0cb5a29028627b79f66edff643eac8d60732f64d1

## Guardrails

- Treat Status as corpus status, not external fact-check status.
- Use only cited evidence items when answering from this page.
- Do not use summaries, theses, or hypotheses as direct evidence.
- Separate source claims from author interpretation.
- Treat Status как статус доказанности в рамках локального корпуса, а не как внешнюю проверку фактов.
- Не расширять доказательную базу за пределы source_claim, приведенных в Evidence.
- Не добавлять интерпретации (например, мотивов), если они не отражены в процитированных source_claim.

## Related

- indexes/page_to_sources.json
