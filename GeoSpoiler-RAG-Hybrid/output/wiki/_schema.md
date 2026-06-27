# Wiki Memory Schema

## Page Types

- entity: people, organizations, countries, platforms, or other named actors.
- topic: recurring subjects, events, narratives, or research areas.
- claim: source-grounded statements tracked with explicit evidence.

## Claim Status Values

- supported_by_corpus: sources in the local corpus support the claim.
- contradicted_by_corpus: sources in the local corpus explicitly contradict the claim.
- disputed_in_corpus: local sources conflict with each other.
- unclear_in_corpus: local evidence is insufficient.

## Evidence Rules

Prefer evidence in this order:

1. Direct quotes.
2. key_facts with claim_type=source_claim.
3. Events.
4. Provenance, post_url, and date.
5. Summary as supporting context only.

Do not use theses, hypotheses, or summaries as the only direct evidence for a claim.
Do not call a claim fake, false, or deepfake unless an evidence item explicitly says that.
Keep source claims separate from author interpretation.

## LLM-Generated Page Rules

- `python main.py wiki ingest` is the primary wiki growth path.
- Enriched cards are the source of truth; wiki pages are compiled memory.
- LLM-generated pages must include generated_by=wiki_ingest_v1.
- LLM-generated pages must include review_status=auto until reviewed.
- LLM-generated pages must include source_count and updated_at.
- Claim pages must cite at least one telegram:* source_id in Evidence.
- Claim evidence source_ids must come from the current ingest batch.
- Claim pages must include a Guardrails section.
- Entity and topic pages should link related claim pages when possible.
- _pending_updates.json is only a fallback for failed or unclear ingest sources.

## Update Rules

- Automatically created pages must keep review_status=auto until reviewed.
- Manual edits must not be overwritten by scaffold or build commands.
- Append to logs; do not rewrite existing log history.
- Preserve accepted LLM-generated wiki changes through git history.
