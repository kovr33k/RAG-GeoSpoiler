---
wiki_type: claim
status: supported_by_corpus
generated_by: wiki_ingest_v1
review_status: auto
source_count: 1
updated_at: 2026-06-26
---

# Утверждается, что более 10 000 северокорейских солдат были отправлены в Россию и что Россия использует их в войне против Украины

Status: supported_by_corpus
Review status: auto
Source count: 1

## Evidence

- telegram:3215620297:15 - source_claim: В посте утверждается, что в Россию было отправлено более 10 000 северокорейских солдат.
  - post_url: https://t.me/c/3215620297/15
  - date: 2026-02-15T14:47:03+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Корея\15.enriched.json
  - content_hash: 3ade6daf3dbdb19c6a98e1941b2fe46fe79ebe7a23dea6818161ca88f6a3b5fc
- telegram:3215620297:15 - source_claim: В посте утверждается, что Россия отправляет северокорейские войска в Украину.
  - post_url: https://t.me/c/3215620297/15
  - date: 2026-02-15T14:47:03+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Корея\15.enriched.json
  - content_hash: 3ade6daf3dbdb19c6a98e1941b2fe46fe79ebe7a23dea6818161ca88f6a3b5fc

## Guardrails

- Treat Status as corpus status, not external fact-check status.
- Use only cited evidence items when answering from this page.
- Do not use summaries, theses, or hypotheses as direct evidence.
- Separate source claims from author interpretation.
- Treat Status as corpus status, not external fact-check status (supported_by_corpus).
- Use only cited evidence items when writing from this page.
- Do not introduce или добавлять факты сверх формулировок, присутствующих в карточке.

## Related

- indexes/page_to_sources.json
