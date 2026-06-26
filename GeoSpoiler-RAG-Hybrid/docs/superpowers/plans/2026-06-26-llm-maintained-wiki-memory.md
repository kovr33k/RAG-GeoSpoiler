# LLM-Maintained Wiki Memory Plan

## Goal

Turn the current wiki module from a static, hardcoded claim ledger into a Karpathy-style living wiki:

- raw sources and enriched cards remain the source of truth;
- the LLM maintains markdown wiki pages;
- health checks keep the LLM disciplined;
- `_pending_updates.json` becomes a fallback, not the main workflow;
- Obsidian is not required.

## Current Problem

The current wiki layer has useful foundations:

- source ids;
- claim/entity/topic page structure;
- wiki indexes;
- wiki health checks;
- query integration;
- enriched cards with summaries, key facts, entities, topics, quotes, and provenance.

But the wiki does not yet grow naturally from the corpus.

The main issues are:

- claim/entity/topic specs are hardcoded in Python;
- `wiki update` updates linked pages but does not create new pages;
- `_pending_updates.json` can become a passive pile of unprocessed sources;
- query-time wiki context does not fully use page guardrails;
- search over wiki pages is still basic;
- the current corpus already has enriched cards, but the wiki has little or no actual content pages.

## Core Decision

Use the Karpathy model:

```text
raw sources -> enriched cards -> LLM-maintained wiki -> query/search/eval
```

The LLM should be allowed to create and update wiki pages, but only inside strict rules:

- no outside fact-checking;
- every claim must be grounded in provided source ids;
- source ids, card paths, post URLs, and content hashes must remain traceable;
- health checks must validate wiki output after each ingest;
- unsafe or unclear sources go to `_pending_updates.json`.

## What We Will Not Do

We will not add `obsidian-skills`.

We will not make Obsidian graph view a requirement.

We will not build a manual proposal review system as the primary flow.

We will not make `_pending_updates.json` the normal way to grow the wiki.

We will not replace normalized/enriched sources with wiki pages as the source of truth.

## Target Workflow

The main workflow should become:

```powershell
python main.py wiki ingest
```

This command should:

1. Find new or changed enriched cards.
2. Give the LLM the selected cards, current wiki schema, and relevant existing wiki pages.
3. Let the LLM create or update wiki pages.
4. Validate that generated pages are safe and source-grounded.
5. Write the pages to `output/wiki/`.
6. Rebuild wiki indexes.
7. Run wiki health checks.
8. Update source hashes.
9. Append a readable log entry.

If a source cannot be safely processed, it should be written to `_pending_updates.json`.

## Proposed Phases

### Phase 1: Safe LLM Wiki Ingest

Add the core `wiki ingest` command.

This is the most important phase.

It should select new/changed enriched cards and ask the LLM to maintain the wiki directly.

Expected result:

```text
output/wiki/entities/*.md
output/wiki/topics/*.md
output/wiki/claims/*.md
```

The generated pages must cite the original source ids.

### Phase 2: Validation And Health Checks

Strengthen `wiki health` so it checks not only claim evidence, but also wiki quality.

Add checks for:

- wiki is empty while enriched cards exist;
- page source ids are missing from page body;
- broken wiki page references;
- claim pages without direct evidence;
- entity/topic pages with no related claims or sources;
- generated pages that look too broad;
- pending queue growing too large.

Expected result:

```powershell
python main.py wiki health
```

becomes the lint step for LLM-maintained wiki output.

### Phase 3: Overview Page

Add a deterministic overview page:

```text
output/wiki/_overview.md
```

It should summarize:

- number of claims/entities/topics;
- recently updated pages;
- pending sources;
- health issue count;
- top entities/topics if available.

Expected command:

```powershell
python main.py wiki overview
```

This gives a quick state-of-the-wiki view without needing Obsidian.

### Phase 4: Query Integration Improvements

Improve how wiki pages are used during query.

Main improvement:

- include claim guardrails from wiki pages in prompt context.

This matters because generated claim pages may contain important instructions like:

```text
Do not call this fake unless the evidence explicitly says so.
```

Expected result:

Answers should use wiki memory more carefully and avoid flattening distinct claims.

### Phase 5: Wiki FTS

Add full-text search for wiki pages.

This can be added in the same overall project, but after `wiki ingest` exists.

Reason:

- FTS is useful once there are pages to search;
- it will improve `find_wiki_context`;
- it can power a future command like:

```powershell
python main.py wiki search "Китай КНДР"
```

Implementation preference:

- either add a separate `artifacts/wiki_fts.sqlite`;
- or add a separate `wiki_fts` table near the existing card FTS infrastructure.

Do not mix card records and wiki pages in a way that hides whether a result came from source cards or compiled wiki memory.

### Phase 6: Documentation And Operating Rules

Update `WIKI_MEMORY.md` and `_schema.md`.

They should explain:

- wiki is LLM-maintained;
- raw/enriched sources are still source of truth;
- `wiki ingest` is the main growth path;
- `_pending_updates.json` is fallback only;
- Obsidian is optional and not required;
- health checks are mandatory after ingest.

## Mapping From Opus Plan

The Opus plan is mostly preserved, but not one-to-one. Some items are kept as-is, some are changed because we decided to use the Karpathy-style LLM-maintained wiki, and some are intentionally downgraded.

| Opus item | Status in this plan | Notes |
|---|---|---|
| Guardrails in prompt context | Included | Covered in Phase 4. Claim-page guardrails should be passed into query context. |
| Wikilinks syntax | Downgraded / optional | Obsidian is not a target, so `[[wikilinks]]` are not a required quick win. Plain machine-readable links are enough for now. |
| Parseable log headers | Included | Covered by `wiki ingest` logging. Logs should have readable markdown headers plus machine-readable JSON/event data. |
| Deterministic overview page | Included | Covered in Phase 3 as `output/wiki/_overview.md`. |
| Expanded wiki health checks | Included | Covered in Phase 2. This becomes mandatory because the LLM writes wiki pages. |
| Specs from JSON instead of Python | Partly replaced | JSON specs are less important if `wiki ingest` becomes the main growth path. Existing hardcoded seed commands can remain legacy/bootstrap. |
| Auto-discover from enriched cards | Replaced by `wiki ingest` | Instead of only generating discovered specs, the LLM reads enriched cards and directly creates/updates wiki pages. |
| Wiki pages in FTS | Included | Covered in Phase 5. We can include FTS in the first implementation round, but after pages exist. |
| Auto-expand from pending updates | Not primary | We decided `_pending_updates.json` should be fallback only, not the normal workflow. |
| LLM-assisted page generation | Included and promoted | This is now the core of the plan: Karpathy-style LLM-maintained wiki pages. |

Short version:

```text
Kept:
  - guardrails in prompt
  - parseable logs
  - overview
  - health checks
  - wiki FTS
  - LLM page generation

Changed:
  - JSON specs and auto-discover are folded into wiki ingest
  - pending updates are fallback only

Dropped as requirement:
  - Obsidian-specific wikilinks
```

## Recommended Order

Recommended order for implementation:

1. `wiki ingest`
2. stronger validation and health checks
3. `_overview.md`
4. guardrails in query context
5. wiki FTS
6. documentation cleanup

## Success Criteria

The work is successful when:

- `python main.py wiki ingest` creates or updates wiki pages from enriched cards;
- generated pages cite source ids and provenance;
- `python main.py wiki health` catches unsafe or weak wiki output;
- `_pending_updates.json` is used only for failed/unclear sources;
- `python main.py wiki overview` gives a readable state summary;
- query context can use wiki guardrails;
- wiki FTS can search generated pages;
- no Obsidian dependency is introduced.

## Main Risks

### Risk: LLM invents or overstates facts

Mitigation:

- strict prompt;
- source ids required;
- health checks;
- no outside knowledge;
- evidence sections required for claims.

### Risk: LLM creates too many broad pages

Mitigation:

- prefer small claim pages;
- health warning for overly broad pages;
- page type rules in schema.

### Risk: wiki becomes disconnected from source truth

Mitigation:

- source ids in every generated page;
- content hashes;
- page/source indexes;
- health checks verify source grounding.

### Risk: search mixes raw evidence and wiki synthesis

Mitigation:

- keep card FTS and wiki FTS distinguishable;
- label result type clearly.

## Open Decisions For Approval

1. Should `wiki ingest` process one source at a time by default, or small batches such as 3-5 sources?

   Recommendation: small batches of 3-5.

2. Should LLM-generated wiki pages overwrite existing auto-generated pages directly?

   Recommendation: yes for `review_status: auto`; be more careful with manually reviewed pages later.

3. Should FTS be included in the first implementation round?

   Recommendation: yes, but after `wiki ingest` and health checks.

4. Should old hardcoded seed commands remain?

   Recommendation: yes, as legacy/bootstrap commands for now.

## Approval Summary

Approve this plan if the desired direction is:

```text
Karpathy-style LLM-maintained wiki
+ source-grounding guardrails
+ health/lint checks
+ no Obsidian dependency
+ FTS after pages exist
```
