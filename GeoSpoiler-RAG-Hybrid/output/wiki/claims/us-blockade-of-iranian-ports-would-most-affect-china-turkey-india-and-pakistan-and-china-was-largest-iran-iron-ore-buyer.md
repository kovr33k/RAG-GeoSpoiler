---
wiki_type: claim
status: supported_by_corpus
generated_by: wiki_ingest_v1
review_status: auto
source_count: 1
updated_at: 2026-06-26
---

# Утверждается, что блокада иранских портов со стороны США сильнее всего повлияет на Китай, Турцию, Индию и Пакистан; Китай — крупнейший экспортный партнер Ирана и единственный покупатель железной руды в 2023 году на $1,3 млрд

Status: supported_by_corpus
Review status: auto
Source count: 1

## Evidence

- telegram:3001055698:87 - source_claim: В посте утверждается, что блокада иранских портов со стороны США больше всего повлияет на Китай, Турцию, Индию и Пакистан.
  - post_url: https://t.me/c/3001055698/87
  - date: 2026-04-14T16:15:40+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\87.enriched.json
  - content_hash: 7ff55d59db517324982ee133a59d518d17a20bfd25ca3f3d3e220268bf32f916
- telegram:3001055698:87 - source_claim: В посте утверждается, что Китай является крупнейшим экспортным партнером Ирана.
  - post_url: https://t.me/c/3001055698/87
  - date: 2026-04-14T16:15:40+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\87.enriched.json
  - content_hash: 7ff55d59db517324982ee133a59d518d17a20bfd25ca3f3d3e220268bf32f916
- telegram:3001055698:87 - source_claim: В посте утверждается, что Китай является единственным покупателем железной руды у Ирана и закупил ее в 2023 году на сумму 1,3 миллиарда долларов.
  - post_url: https://t.me/c/3001055698/87
  - date: 2026-04-14T16:15:40+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\87.enriched.json
  - content_hash: 7ff55d59db517324982ee133a59d518d17a20bfd25ca3f3d3e220268bf32f916
- telegram:3001055698:87 - source_claim: В посте указано, что основными экспортными товарами Ирана в 2024 году были полимеры этилена и железная руда.
  - post_url: https://t.me/c/3001055698/87
  - date: 2026-04-14T16:15:40+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\87.enriched.json
  - content_hash: 7ff55d59db517324982ee133a59d518d17a20bfd25ca3f3d3e220268bf32f916
- telegram:3001055698:87 - source_claim: В тексте описания изображения указано, что Китай составляет 35% торговли на сумму 4,6 миллиарда долларов.
  - post_url: https://t.me/c/3001055698/87
  - date: 2026-04-14T16:15:40+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\87.enriched.json
  - content_hash: 7ff55d59db517324982ee133a59d518d17a20bfd25ca3f3d3e220268bf32f916

## Guardrails

- Treat Status as corpus status, not external fact-check status.
- Use only cited evidence items when answering from this page.
- Do not use summaries, theses, or hypotheses as direct evidence.
- Separate source claims from author interpretation.
- Разделять утверждения поста и конкретные факты из описаний изображений, помечая их как evidence в текущей карточке.
- Не переносить выводы за пределы указанного в карточке.

## Related

- indexes/page_to_sources.json
