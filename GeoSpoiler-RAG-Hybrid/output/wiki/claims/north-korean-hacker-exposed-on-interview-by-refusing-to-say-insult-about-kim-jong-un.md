---
wiki_type: claim
status: supported_by_corpus
generated_by: wiki_ingest_v1
review_status: auto
source_count: 1
updated_at: 2026-06-26
---

# Утверждается, что вероятный северокорейский хакер выдал себя на собеседовании, отказавшись произнести оскорбительную фразу про Ким Чен Ына

Status: supported_by_corpus
Review status: auto
Source count: 1

## Evidence

- telegram:3215620297:33 - source_claim: В посте: «Вероятный северокорейский хакер выдал себя во время собеседования».
  - post_url: https://t.me/c/3215620297/33
  - date: 2026-04-07T18:03:26+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Корея\33.enriched.json
  - content_hash: d04407e80651b3bf0685bdcccc67767c3d126d9eb870991eaafd77d0cd20cc04
- telegram:3215620297:33 - source_claim: В посте: «Кандидата попросили сказать: „Ким Чен Ын — толстая уродливая свинья“».
  - post_url: https://t.me/c/3215620297/33
  - date: 2026-04-07T18:03:26+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Корея\33.enriched.json
  - content_hash: d04407e80651b3bf0685bdcccc67767c3d126d9eb870991eaafd77d0cd20cc04
- telegram:3215620297:33 - source_claim: В посте: «Кандидат заколебался, начал тянуть время и молчал, отказавшись произнести фразу».
  - post_url: https://t.me/c/3215620297/33
  - date: 2026-04-07T18:03:26+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Корея\33.enriched.json
  - content_hash: d04407e80651b3bf0685bdcccc67767c3d126d9eb870991eaafd77d0cd20cc04

## Guardrails

- Treat Status as corpus status, not external fact-check status.
- Use only cited evidence items when answering from this page.
- Do not use summaries, theses, or hypotheses as direct evidence.
- Separate source claims from author interpretation.
- Сохранять формулировку «вероятный северокорейский хакер» как в карточке, не усиливая до установленной идентификации. [telegram:3215620297:33]
- Не расширять набор доказательств за пределы того, что указано в key_facts карточки. [telegram:3215620297:33]

## Related

- claims/north-korea-agents-infiltrate-it-companies-using-fake-identities-deepfakes-and-resume-forgeries.md
