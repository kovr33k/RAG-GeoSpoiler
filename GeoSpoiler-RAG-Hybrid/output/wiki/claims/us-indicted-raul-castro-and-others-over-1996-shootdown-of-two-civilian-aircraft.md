---
wiki_type: claim
status: supported_by_corpus
generated_by: wiki_ingest_v1
review_status: auto
source_count: 1
updated_at: 2026-06-26
---

# В США предъявили уголовные обвинения Раулю Кастро и другим лицам по делу о гибели при атаке на два гражданских самолета в 1996 году

Status: supported_by_corpus
Review status: auto
Source count: 1

## Evidence

- telegram:3841808641:10 - source_claim: В посте утверждается, что и.о. генпрокурора США Тодд Бланш официально предъявил обвинения Раулю Кастро и нескольким другим лицам.
  - post_url: https://t.me/c/3841808641/10
  - date: 2026-05-21T04:11:25+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Куба\10.enriched.json
  - content_hash: d3498cda0a6e40200e070d20f15c966a6b9b0f7b462f94fb79b1bfd307cc5ace
- telegram:3841808641:10 - source_claim: В посте говорится, что обвиняемых считают причастными к сговору с целью убийства граждан США и уничтожении самолета.
  - post_url: https://t.me/c/3841808641/10
  - date: 2026-05-21T04:11:25+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Куба\10.enriched.json
  - content_hash: d3498cda0a6e40200e070d20f15c966a6b9b0f7b462f94fb79b1bfd307cc5ace
- telegram:3841808641:10 - source_claim: В посте сказано, что в 1996 году были сбиты два гражданских самолета; в результате погибли четверо мужчин, включая трех граждан США.
  - post_url: https://t.me/c/3841808641/10
  - date: 2026-05-21T04:11:25+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Куба\10.enriched.json
  - content_hash: d3498cda0a6e40200e070d20f15c966a6b9b0f7b462f94fb79b1bfd307cc5ace

## Guardrails

- Treat Status as corpus status, not external fact-check status.
- Use only cited evidence items when answering from this page.
- Do not use summaries, theses, or hypotheses as direct evidence.
- Separate source claims from author interpretation.
- Отражать формулировки как утверждения, представленные в посте, без подмены оценок внешней проверкой.
- Не добавлять новых деталей, которых нет в ключевых фактах карты.

## Related

- indexes/page_to_sources.json
