---
wiki_type: claim
status: supported_by_corpus
generated_by: wiki_ingest_v1
review_status: auto
source_count: 1
updated_at: 2026-06-26
---

# Утверждается, что Мао Нин призвала уважать суверенитет всех стран после событий в Венесуэле и вновь напомнила, что позиция Китая по кризису в Украине «очень четкая»

Status: supported_by_corpus
Review status: auto
Source count: 1

## Evidence

- telegram:3001055698:40 - source_claim: Мао Нин призвала «уважать суверенитет всех стран» после событий в Венесуэле.
  - post_url: https://t.me/c/3001055698/40
  - date: 2026-01-06T13:39:23+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\40.enriched.json
  - content_hash: d780caa0bd46db968c16e60b0b4a1a9314b78fa9f1464c8c0f94971cd8426e3f
- telegram:3001055698:40 - source_claim: Мао Нин не смогла прямо ответить, касается ли этот призыв Украины.
  - post_url: https://t.me/c/3001055698/40
  - date: 2026-01-06T13:39:23+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\40.enriched.json
  - content_hash: d780caa0bd46db968c16e60b0b4a1a9314b78fa9f1464c8c0f94971cd8426e3f
- telegram:3001055698:40 - source_claim: Мао Нин вновь напомнила, что позиция Китая по кризису в Украине (как указано в посте) «очень четкая».
  - post_url: https://t.me/c/3001055698/40
  - date: 2026-01-06T13:39:23+00:00
  - card_path: C:\WikiRag\RAG-GeoSpoiler\GeoSpoiler-RAG-Hybrid\output\enriched\Китай\40.enriched.json
  - content_hash: d780caa0bd46db968c16e60b0b4a1a9314b78fa9f1464c8c0f94971cd8426e3f

## Guardrails

- Treat Status as corpus status, not external fact-check status.
- Use only cited evidence items when answering from this page.
- Do not use summaries, theses, or hypotheses as direct evidence.
- Separate source claims from author interpretation.
- Treat Status как статус доказанности в рамках локального корпуса, а не как внешнюю проверку содержания заявления.
- Не приписывать Мао Нин дополнительные формулировки или уточнения за пределами процитированных source_claim.
- Излагать только заявленное в Evidence.

## Related

- indexes/page_to_sources.json
