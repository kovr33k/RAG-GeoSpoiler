# Additions To Opus Wiki Plan

These are the only additions recommended for the new Opus implementation plan.

## 1. Separate Wiki LLM Configuration

Add dedicated wiki LLM settings:

```text
WIKI_LLM_MODEL
WIKI_LLM_API_KEY
WIKI_LLM_BASE_URL
```

Fallback behavior:

```text
if WIKI_LLM_* is set:
  use WIKI_LLM_*
else:
  use ENRICHMENT_*
```

Reason:

- enrichment and wiki maintenance are similar but not identical tasks;
- later the wiki can use a different model, timeout, or provider without changing enrichment.

## 2. Enriched To Wiki Coverage Stats

Add coverage statistics to `wiki overview` or `wiki health`.

The system should show important entities/topics that appear often in enriched cards but do not yet have wiki pages.

Example:

```text
Important entities in enriched cards without wiki page:
- Китай: 64
- Россия: 62
- США: 43
- Украина: 43
```

Reason:

- shows what the wiki is missing;
- helps check whether `wiki ingest` is covering the corpus well;
- replaces the need for a separate `wiki discover` workflow in the MVP.

## 3. Git/GitHub Backup Policy

LLM-generated wiki changes must be recoverable through git history.

After `wiki ingest`, the workflow should make it easy to inspect and preserve changes:

```text
1. show changed wiki files
2. commit wiki changes to git
3. optionally push to GitHub
```

Reason:

- avoids a separate snapshot system;
- makes bad LLM edits reversible;
- gives a clear history of how wiki memory changed over time.
