# Wiki Coverage Backfill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an automatic wiki coverage backfill pass that creates/updates missing high-value entity and topic pages such as `entities/china.md` from existing enriched cards and claim pages.

**Architecture:** Keep enriched cards as source of truth and claim pages as the primary grounded wiki layer. Add a deterministic coverage planner that detects missing entity/topic pages, links them to already-grounded claim pages, and renders hub pages without inventing new facts. Wire it into `python main.py wiki ingest` after core claim ingest, and expose a standalone CLI command for reruns.

**Tech Stack:** Python stdlib, existing file-based wiki modules under `retrieval/`, `unittest`, `ruff`.

---

## Problem Summary

The current wiki ingest creates claim pages well, but entity/topic coverage is opportunistic. Health can detect that important names like `Китай` appear in many enriched cards without an `entities/*.md` page, but no command currently turns those coverage gaps into hub pages. This leaves the wiki usable as claim memory, but weak as a navigable Karpathy-style wiki.

The fix is not to ask LLM to “try harder” inside each small ingest batch. The fix is a second deterministic/LLM-optional coverage pass that sees the whole corpus and creates hub pages from existing grounded claims.

---

## File Structure

- Create: `retrieval/wiki_coverage.py`
  - Computes missing entity/topic gaps.
  - Maps entity/topic names to related claim pages through enriched cards and existing claim source indexes.
  - Renders or updates hub pages.
  - Does not add direct raw `telegram:*` source ids to entity/topic pages.

- Modify: `config.py`
  - Add `WIKI_COVERAGE_THRESHOLD` and `WIKI_COVERAGE_LIMIT` env-backed settings.

- Modify: `.env.example`
  - Document `WIKI_COVERAGE_THRESHOLD=3` and `WIKI_COVERAGE_LIMIT=20`.

- Modify: `retrieval/wiki_ingest.py`
  - Call coverage backfill after core LLM claim ingest.
  - Keep this step after `build_wiki_indexes()` so claim/source indexes are fresh.

- Modify: `cli_wiki.py`
  - Add `cmd_wiki_coverage_backfill()`.
  - Print created/updated/skipped counts.

- Modify: `cli_app.py`
  - Add `python main.py wiki coverage-backfill`.

- Modify: `retrieval/wiki_overview.py`
  - Import `coverage_gaps()` from `retrieval/wiki_coverage`.
  - Keep the existing public API stable for callers.

- Test: `tests/test_wiki_coverage.py`
  - Unit tests for backfill planning, rendering, idempotency, and no raw source leakage.

- Modify: `tests/test_wiki_ingest.py`
  - Verify `run_wiki_ingest()` invokes coverage backfill after claim pages are written.

- Modify: `tests/test_main.py`
  - Verify CLI dispatch for `wiki coverage-backfill`.

---

### Task 1: Create Deterministic Coverage Backfill Planner

**Files:**
- Modify: `config.py`
- Modify: `.env.example`
- Create: `retrieval/wiki_coverage.py`
- Test: `tests/test_wiki_coverage.py`

- [ ] **Step 1: Write the failing tests**

Add `tests/test_wiki_coverage.py`:

```python
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from retrieval.wiki_coverage import run_wiki_coverage_backfill
from retrieval.wiki_index import build_wiki_indexes


class WikiCoverageBackfillTests(unittest.TestCase):
    def test_creates_entity_page_for_frequent_missing_entity_from_existing_claims(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir = root / "wiki"
            enriched_dir = root / "enriched"
            index_dir = wiki_dir / "indexes"
            (wiki_dir / "claims").mkdir(parents=True)
            (wiki_dir / "entities").mkdir(parents=True)
            (wiki_dir / "topics").mkdir(parents=True)
            enriched_dir.mkdir()

            for message_id in [10, 11, 12]:
                _write_card(
                    enriched_dir / f"{message_id}.enriched.json",
                    message_id=message_id,
                    entity="Китай",
                    topic="геополитика",
                    fact=f"China-related source claim {message_id}.",
                )
                (wiki_dir / "claims" / f"china-claim-{message_id}.md").write_text(
                    "---\n"
                    "wiki_type: claim\n"
                    "status: supported_by_corpus\n"
                    "generated_by: wiki_ingest_v1\n"
                    "review_status: auto\n"
                    "source_count: 1\n"
                    "updated_at: 2026-06-27\n"
                    "---\n\n"
                    f"# China claim {message_id}\n\n"
                    "## Evidence\n\n"
                    f"- telegram:1:{message_id} - source_claim: China-related source claim {message_id}.\n"
                    f"  - card_path: {enriched_dir / f'{message_id}.enriched.json'}\n",
                    encoding="utf-8",
                )
            build_wiki_indexes(wiki_dir=wiki_dir, enriched_dir=enriched_dir, index_dir=index_dir)

            stats = run_wiki_coverage_backfill(
                wiki_dir=wiki_dir,
                enriched_dir=enriched_dir,
                index_dir=index_dir,
                today=date(2026, 6, 27),
                threshold=3,
                limit=20,
            )

            entity_path = wiki_dir / "entities" / "китай.md"
            entity_text = entity_path.read_text(encoding="utf-8")

        self.assertEqual([path.name for path in stats.pages_created], ["китай.md", "геополитика.md"])
        self.assertIn("wiki_type: entity", entity_text)
        self.assertIn("# Китай", entity_text)
        self.assertIn("- claims/china-claim-10.md", entity_text)
        self.assertIn("- claims/china-claim-11.md", entity_text)
        self.assertIn("- claims/china-claim-12.md", entity_text)
        self.assertIn("Resolve primary sources through claim evidence", entity_text)
        self.assertNotIn("telegram:1:10", entity_text)

    def test_backfill_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir = root / "wiki"
            enriched_dir = root / "enriched"
            index_dir = wiki_dir / "indexes"
            (wiki_dir / "claims").mkdir(parents=True)
            (wiki_dir / "entities").mkdir(parents=True)
            (wiki_dir / "topics").mkdir(parents=True)
            enriched_dir.mkdir()
            for message_id in [10, 11, 12]:
                _write_card(
                    enriched_dir / f"{message_id}.enriched.json",
                    message_id=message_id,
                    entity="Россия",
                    topic="санкции",
                    fact=f"Russia-related source claim {message_id}.",
                )
                (wiki_dir / "claims" / f"russia-claim-{message_id}.md").write_text(
                    "# Russia claim\n\n"
                    "## Evidence\n\n"
                    f"- telegram:1:{message_id} - source_claim: Russia-related source claim {message_id}.\n"
                    f"  - card_path: {enriched_dir / f'{message_id}.enriched.json'}\n",
                    encoding="utf-8",
                )
            build_wiki_indexes(wiki_dir=wiki_dir, enriched_dir=enriched_dir, index_dir=index_dir)

            first = run_wiki_coverage_backfill(
                wiki_dir=wiki_dir,
                enriched_dir=enriched_dir,
                index_dir=index_dir,
                today=date(2026, 6, 27),
                threshold=3,
            )
            second = run_wiki_coverage_backfill(
                wiki_dir=wiki_dir,
                enriched_dir=enriched_dir,
                index_dir=index_dir,
                today=date(2026, 6, 27),
                threshold=3,
            )

        self.assertEqual(len(first.pages_created), 2)
        self.assertEqual(second.pages_created, [])
        self.assertEqual(second.pages_updated, [])


def _write_card(path: Path, *, message_id: int, entity: str, topic: str, fact: str) -> None:
    path.write_text(
        json.dumps(
            {
                "triage": "keep",
                "summary": fact,
                "provenance": {
                    "channel_id": 1,
                    "message_id": message_id,
                    "post_url": f"https://t.me/c/1/{message_id}",
                    "normalized_file": f"output/normalized/test/{message_id}.txt",
                    "date": "2026-06-27T00:00:00+00:00",
                },
                "key_facts": [{"text": fact, "claim_type": "source_claim"}],
                "entities": {"countries": [entity]},
                "topics": [topic],
                "quotes": [],
                "events": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m unittest tests.test_wiki_coverage
```

Expected:

```text
ModuleNotFoundError: No module named 'retrieval.wiki_coverage'
```

- [ ] **Step 3: Add config knobs**

In `config.py`, add near the other wiki settings:

```python
WIKI_COVERAGE_THRESHOLD = int(os.getenv("WIKI_COVERAGE_THRESHOLD", "3"))
WIKI_COVERAGE_LIMIT = int(os.getenv("WIKI_COVERAGE_LIMIT", "20"))
```

In `.env.example`, add:

```env
# Wiki coverage backfill creates entity/topic hub pages after repeated mentions.
WIKI_COVERAGE_THRESHOLD=3
WIKI_COVERAGE_LIMIT=20
```

- [ ] **Step 4: Implement the minimal planner**

Create `retrieval/wiki_coverage.py`:

```python
"""Coverage backfill for entity/topic wiki hub pages."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import config
from retrieval import wiki_index


@dataclass(frozen=True)
class WikiCoverageBackfillStats:
    pages_created: list[Path]
    pages_updated: list[Path]
    entities_considered: int
    topics_considered: int
    entities_created_or_updated: int
    topics_created_or_updated: int


@dataclass(frozen=True)
class CoverageCandidate:
    page_type: str
    name: str
    count: int
    related_claims: list[str]


def run_wiki_coverage_backfill(
    wiki_dir: Path = config.WIKI_DIR,
    enriched_dir: Path = config.ENRICHED_DIR,
    index_dir: Path | None = None,
    today: date | None = None,
    threshold: int | None = None,
    limit: int | None = None,
) -> WikiCoverageBackfillStats:
    today = today or date.today()
    threshold = threshold if threshold is not None else config.WIKI_COVERAGE_THRESHOLD
    limit = limit if limit is not None else config.WIKI_COVERAGE_LIMIT
    index_dir = index_dir or (wiki_dir / "indexes")
    for directory in [wiki_dir / "entities", wiki_dir / "topics", index_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    wiki_index.build_wiki_indexes(wiki_dir=wiki_dir, enriched_dir=enriched_dir, index_dir=index_dir)
    page_to_sources = _load_json(index_dir / wiki_index.PAGE_INDEX_FILENAME)
    source_to_claims = _source_to_claims(page_to_sources)
    cards = list(wiki_index.iter_enriched_cards(enriched_dir))
    existing_entities = _existing_page_names(wiki_dir / "entities")
    existing_topics = _existing_page_names(wiki_dir / "topics")

    entity_candidates = _coverage_candidates(
        cards=cards,
        page_type="entity",
        existing_names=existing_entities,
        source_to_claims=source_to_claims,
        threshold=threshold,
        limit=limit,
    )
    topic_candidates = _coverage_candidates(
        cards=cards,
        page_type="topic",
        existing_names=existing_topics,
        source_to_claims=source_to_claims,
        threshold=threshold,
        limit=limit,
    )

    created: list[Path] = []
    updated: list[Path] = []
    for candidate in entity_candidates + topic_candidates:
        if not candidate.related_claims:
            continue
        directory = wiki_dir / ("entities" if candidate.page_type == "entity" else "topics")
        path = directory / f"{_slugify(candidate.name)}.md"
        text = _render_hub_page(candidate, today)
        old_text = path.read_text(encoding="utf-8") if path.exists() else None
        if old_text == text:
            continue
        path.write_text(text, encoding="utf-8")
        if old_text is None:
            created.append(path)
        else:
            updated.append(path)

    wiki_index.build_wiki_indexes(wiki_dir=wiki_dir, enriched_dir=enriched_dir, index_dir=index_dir)
    entity_changes = sum(1 for path in created + updated if path.parent.name == "entities")
    topic_changes = sum(1 for path in created + updated if path.parent.name == "topics")
    return WikiCoverageBackfillStats(
        pages_created=created,
        pages_updated=updated,
        entities_considered=len(entity_candidates),
        topics_considered=len(topic_candidates),
        entities_created_or_updated=entity_changes,
        topics_created_or_updated=topic_changes,
    )


def coverage_gaps(
    wiki_dir: Path = config.WIKI_DIR,
    enriched_dir: Path = config.ENRICHED_DIR,
    threshold: int | None = None,
    limit: int | None = None,
) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    threshold = threshold if threshold is not None else config.WIKI_COVERAGE_THRESHOLD
    limit = limit if limit is not None else config.WIKI_COVERAGE_LIMIT
    cards = list(wiki_index.iter_enriched_cards(enriched_dir))
    existing_entities = _existing_page_names(wiki_dir / "entities")
    existing_topics = _existing_page_names(wiki_dir / "topics")
    entity_counts = _mention_counts(cards, "entity")
    topic_counts = _mention_counts(cards, "topic")
    return (
        _missing_counts(entity_counts, existing_entities, threshold, limit),
        _missing_counts(topic_counts, existing_topics, threshold, limit),
    )


def _coverage_candidates(
    *,
    cards: list[tuple[Path, dict[str, Any]]],
    page_type: str,
    existing_names: set[str],
    source_to_claims: dict[str, list[str]],
    threshold: int,
    limit: int,
) -> list[CoverageCandidate]:
    counts: Counter[str] = Counter()
    related: dict[str, set[str]] = defaultdict(set)
    for _path, card in cards:
        if card.get("triage") != "keep":
            continue
        source_id = wiki_index.extract_source_id(card)
        names = _flatten_entities(card.get("entities")) if page_type == "entity" else _string_list(card.get("topics"))
        for name in names:
            counts[name] += 1
            for claim in source_to_claims.get(source_id or "", []):
                related[name].add(claim)

    candidates: list[CoverageCandidate] = []
    for name, count in counts.items():
        if count < threshold:
            continue
        if _normalize_name(name) in existing_names:
            continue
        candidates.append(
            CoverageCandidate(
                page_type=page_type,
                name=name,
                count=count,
                related_claims=sorted(related[name]),
            )
        )
    candidates.sort(key=lambda item: (-item.count, item.name.casefold()))
    return candidates[:limit]


def _mention_counts(cards: list[tuple[Path, dict[str, Any]]], page_type: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for _path, card in cards:
        if card.get("triage") != "keep":
            continue
        names = _flatten_entities(card.get("entities")) if page_type == "entity" else _string_list(card.get("topics"))
        for name in names:
            counts[name] += 1
    return counts


def _missing_counts(
    counts: Counter[str],
    existing_names: set[str],
    threshold: int,
    limit: int,
) -> list[tuple[str, int]]:
    missing = []
    for name, count in counts.items():
        if count < threshold:
            continue
        if _normalize_name(name) in existing_names:
            continue
        missing.append((name, count))
    missing.sort(key=lambda item: (-item[1], item[0].casefold()))
    return missing[:limit]


def _render_hub_page(candidate: CoverageCandidate, today: date) -> str:
    lines = [
        "---",
        f"wiki_type: {candidate.page_type}",
        "generated_by: wiki_coverage_backfill_v1",
        "review_status: auto",
        f"coverage_count: {candidate.count}",
        f"related_claim_count: {len(candidate.related_claims)}",
        f"updated_at: {today.isoformat()}",
        "---",
        "",
        f"# {candidate.name}",
        "",
        f"This {candidate.page_type} page is a coverage hub generated from enriched-card mentions.",
        "",
        "## Related Claims",
        "",
    ]
    lines.extend(f"- {claim}" for claim in candidate.related_claims)
    lines.extend(
        [
            "",
            "## Source Resolution",
            "",
            "- Resolve primary sources through the linked claim evidence and output/wiki/indexes/page_to_sources.json.",
            "- This page does not add direct evidence beyond its related claim pages.",
            "",
        ]
    )
    return "\n".join(lines)


def _source_to_claims(page_to_sources: dict[str, Any]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = defaultdict(list)
    for page, sources in page_to_sources.items():
        if not str(page).startswith("claims/") or not isinstance(sources, list):
            continue
        for source_id in sources:
            mapping[str(source_id)].append(str(page))
    return {source_id: sorted(set(claims)) for source_id, claims in mapping.items()}


def _existing_page_names(directory: Path) -> set[str]:
    names: set[str] = set()
    if not directory.exists():
        return names
    for path in directory.glob("*.md"):
        names.add(_normalize_name(path.stem.replace("-", " ")))
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                names.add(_normalize_name(line[2:].strip()))
                break
    return names


def _flatten_entities(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    items: list[str] = []
    for group in value.values():
        if isinstance(group, list):
            items.extend(str(item).strip() for item in group if str(item).strip())
        elif str(group).strip():
            items.append(str(group).strip())
    return items


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip() if value is not None else ""
    return [text] if text else []


def _slugify(value: str) -> str:
    text = value.casefold()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text, flags=re.UNICODE).strip("-")
    return text[:120]


def _normalize_name(value: str) -> str:
    return " ".join(re.findall(r"[\w-]+", value.casefold()))


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```powershell
python -m unittest tests.test_wiki_coverage
```

Expected:

```text
Ran 2 tests
OK
```

- [ ] **Step 6: Commit**

```powershell
git add config.py .env.example retrieval/wiki_coverage.py tests/test_wiki_coverage.py
git commit -m "feat: add wiki coverage backfill planner"
```

---

### Task 2: Add Standalone CLI Command

**Files:**
- Modify: `cli_wiki.py`
- Modify: `cli_app.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Write failing CLI dispatch test**

Add to `tests/test_main.py` near other wiki dispatch tests:

```python
    def test_main_wiki_coverage_backfill_cli_dispatches(self):
        calls = []

        def fake_cmd_wiki_coverage_backfill():
            calls.append("coverage")

        with patch.object(cli_app, "cmd_wiki_coverage_backfill", fake_cmd_wiki_coverage_backfill):
            cli_app.dispatch(
                argparse.Namespace(command="wiki", subcommand="coverage-backfill"),
                argparse.ArgumentParser(),
            )

        self.assertEqual(calls, ["coverage"])
```

If `argparse` is not already imported in `tests/test_main.py`, add:

```python
import argparse
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m unittest tests.test_main.MainDispatchTests.test_main_wiki_coverage_backfill_cli_dispatches
```

Expected:

```text
AttributeError: module 'cli_app' has no attribute 'cmd_wiki_coverage_backfill'
```

- [ ] **Step 3: Implement `cmd_wiki_coverage_backfill`**

In `cli_wiki.py`, add import:

```python
from retrieval.wiki_coverage import run_wiki_coverage_backfill
```

Add command function:

```python
def cmd_wiki_coverage_backfill() -> None:
    cmd_wiki_init()
    stats = run_wiki_coverage_backfill()
    index_stats = build_wiki_indexes()
    overview = build_wiki_overview()
    overview_path = write_wiki_overview(overview)

    print("Wiki coverage backfill complete.")
    print(f"  Pages created: {len(stats.pages_created)}")
    print(f"  Pages updated: {len(stats.pages_updated)}")
    print(f"  Entities considered: {stats.entities_considered}")
    print(f"  Topics considered: {stats.topics_considered}")
    print(f"  Entity pages changed: {stats.entities_created_or_updated}")
    print(f"  Topic pages changed: {stats.topics_created_or_updated}")
    print(f"  Indexed pages: {index_stats.page_count}")
    print(f"  Indexed sources: {index_stats.source_count}")
    print(f"  Overview: {overview_path}")
    _print_wiki_git_status_hint()
```

- [ ] **Step 4: Wire CLI parser and dispatcher**

In `cli_app.py`, import:

```python
    cmd_wiki_coverage_backfill,
```

In wiki subparser setup, add:

```python
    wiki_sub.add_parser("coverage-backfill")
```

In wiki dispatch block, add:

```python
        if args.subcommand == "coverage-backfill":
            cmd_wiki_coverage_backfill()
            return
```

- [ ] **Step 5: Run CLI dispatch test**

Run:

```powershell
python -m unittest tests.test_main.MainDispatchTests.test_main_wiki_coverage_backfill_cli_dispatches
```

Expected:

```text
OK
```

- [ ] **Step 6: Run command manually**

Run:

```powershell
python main.py wiki coverage-backfill
```

Expected:

```text
Wiki coverage backfill complete.
```

- [ ] **Step 7: Commit**

```powershell
git add cli_wiki.py cli_app.py tests/test_main.py
git commit -m "feat: expose wiki coverage backfill command"
```

---

### Task 3: Integrate Backfill Into Main `wiki ingest`

**Files:**
- Modify: `retrieval/wiki_ingest.py`
- Test: `tests/test_wiki_ingest.py`

- [ ] **Step 1: Write failing integration test**

Add to `tests/test_wiki_ingest.py`:

```python
    def test_wiki_ingest_runs_coverage_backfill_after_claim_pages(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir, enriched_dir, index_dir = _make_dirs(root)
            for message_id in [10, 11, 12]:
                _write_card(
                    enriched_dir / "China" / f"{message_id}.enriched.json",
                    channel_id=1,
                    message_id=message_id,
                    fact=f"China source claim {message_id}.",
                    entities={"countries": ["Китай"]},
                    topics=["геополитика"],
                )

            def fake_llm(prompt):
                payload = json.loads(prompt)
                operations = []
                for card in payload["cards"]:
                    source_id = card["source_id"]
                    message_id = source_id.split(":")[-1]
                    operations.append(
                        {
                            "action": "create",
                            "page_type": "claim",
                            "slug": f"china-claim-{message_id}",
                            "title": f"China claim {message_id}",
                            "status": "supported_by_corpus",
                            "source_ids": [source_id],
                            "evidence": [
                                {
                                    "source_id": source_id,
                                    "evidence_type": "source_claim",
                                    "text": f"China source claim {message_id}.",
                                }
                            ],
                        }
                    )
                return {"operations": operations}

            run_wiki_ingest(
                wiki_dir=wiki_dir,
                enriched_dir=enriched_dir,
                index_dir=index_dir,
                today=date(2026, 6, 27),
                batch_size=3,
                llm_call=fake_llm,
            )

            entity_text = (wiki_dir / "entities" / "китай.md").read_text(encoding="utf-8")

        self.assertIn("# Китай", entity_text)
        self.assertIn("- claims/china-claim-10.md", entity_text)
        self.assertIn("- claims/china-claim-11.md", entity_text)
        self.assertIn("- claims/china-claim-12.md", entity_text)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m unittest tests.test_wiki_ingest.WikiIngestTests.test_wiki_ingest_runs_coverage_backfill_after_claim_pages
```

Expected:

```text
FileNotFoundError: ... entities\китай.md
```

- [ ] **Step 3: Add backfill call after core ingest**

In `retrieval/wiki_ingest.py`, import:

```python
from retrieval.wiki_coverage import run_wiki_coverage_backfill
```

Inside `run_wiki_ingest()`, after the existing first `wiki_index.build_wiki_indexes(...)`, add:

```python
    run_wiki_coverage_backfill(
        wiki_dir=wiki_dir,
        enriched_dir=enriched_dir,
        index_dir=index_dir,
        today=today,
    )
    wiki_index.build_wiki_indexes(wiki_dir=wiki_dir, enriched_dir=enriched_dir, index_dir=index_dir)
```

Do not include coverage-created pages in `WikiIngestStats.pages_created`; that stat should stay scoped to direct LLM operations. The CLI coverage command reports coverage pages separately.

- [ ] **Step 4: Run integration test**

Run:

```powershell
python -m unittest tests.test_wiki_ingest.WikiIngestTests.test_wiki_ingest_runs_coverage_backfill_after_claim_pages
```

Expected:

```text
OK
```

- [ ] **Step 5: Run ingest test file**

Run:

```powershell
python -m unittest tests.test_wiki_ingest tests.test_wiki_coverage
```

Expected:

```text
OK
```

- [ ] **Step 6: Commit**

```powershell
git add retrieval/wiki_ingest.py tests/test_wiki_ingest.py
git commit -m "feat: run wiki coverage backfill after ingest"
```

---

### Task 4: Make Overview/Health Show Coverage Backfill Progress Clearly

**Files:**
- Modify: `retrieval/wiki_overview.py`
- Test: `tests/test_wiki_overview.py`

- [ ] **Step 1: Write failing overview test**

Add to `tests/test_wiki_overview.py`:

```python
    def test_overview_shows_no_missing_entity_after_backfill_page_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir = root / "wiki"
            enriched_dir = root / "enriched"
            (wiki_dir / "entities").mkdir(parents=True)
            (wiki_dir / "topics").mkdir(parents=True)
            enriched_dir.mkdir(parents=True)
            for message_id in [10, 11, 12]:
                (enriched_dir / f"{message_id}.enriched.json").write_text(
                    json.dumps(
                        {
                            "triage": "keep",
                            "provenance": {"channel_id": 1, "message_id": message_id},
                            "entities": {"countries": ["Китай"]},
                            "topics": ["геополитика"],
                            "key_facts": [{"text": "Fact", "claim_type": "source_claim"}],
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
            (wiki_dir / "entities" / "китай.md").write_text(
                "# Китай\n\n## Related Claims\n\n- none\n",
                encoding="utf-8",
            )

            overview = build_wiki_overview(wiki_dir=wiki_dir, enriched_dir=enriched_dir)

        self.assertNotIn(("Китай", 3), overview.missing_entities)
```

- [ ] **Step 2: Run test to verify current behavior**

Run:

```powershell
python -m unittest tests.test_wiki_overview
```

Expected:

```text
OK
```

If it already passes, keep the test as regression coverage and continue with the refactor below. The goal is not only behavior; it is also removing duplicated coverage-gap logic.

- [ ] **Step 3: Make `wiki_overview.py` use `wiki_coverage.coverage_gaps()`**

In `retrieval/wiki_overview.py`, replace the local coverage implementation with an import alias:

```python
from retrieval.wiki_coverage import coverage_gaps
```

Delete these now-duplicated helpers from `retrieval/wiki_overview.py` if they are no longer used:

```python
def coverage_gaps(...)
def _missing_counts(...)
def _existing_page_names(...)
def _flatten_entities(...)
def _string_list(...)
def _normalize_name(...)
```

Keep `_read_text()` if another overview helper still uses it. Keep `Counter` only if `build_wiki_overview()` still needs it for claim status counts.

- [ ] **Step 4: Run overview and coverage tests**

Run:

```powershell
python -m unittest tests.test_wiki_overview tests.test_wiki_coverage
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```powershell
git add retrieval/wiki_overview.py tests/test_wiki_overview.py
git commit -m "refactor: share wiki coverage gap logic"
```

---

### Task 5: Run Real Backfill And Verify Health Drops

**Files:**
- Generated local output: `output/wiki/entities/*.md`, `output/wiki/topics/*.md`, `output/wiki/indexes/*.json`, `output/wiki/_overview.md`, `output/wiki/_health.md`
- No production code changes unless verification exposes a bug.

- [ ] **Step 1: Run the standalone backfill**

Run:

```powershell
python main.py wiki coverage-backfill
```

Expected:

```text
Wiki coverage backfill complete.
```

Expected shape:

```text
Pages created: greater than 0
Entity pages changed: greater than 0
Topic pages changed: greater than 0
```

- [ ] **Step 2: Run health**

Run:

```powershell
python main.py wiki health
```

Expected:

```text
Wiki health complete.
Issues: 0
```

Acceptable alternative:

```text
Issues: fewer than 40
```

If fewer than 40 but not 0, inspect `output/wiki/_health.md`. Remaining `info` means some high-frequency entity/topic has no related claim pages yet. Do not force-create empty hub pages unless the user explicitly wants empty hub pages.

- [ ] **Step 3: Rebuild overview and FTS**

Run:

```powershell
python main.py wiki overview
python main.py fts rebuild
```

Expected:

```text
Wiki overview complete.
Card FTS rebuild complete.
Wiki pages indexed: greater than 94
```

- [ ] **Step 4: Inspect generated hub pages**

Run:

```powershell
Get-Content -Head 80 output/wiki/entities/китай.md
Get-Content -Head 80 output/wiki/topics/геополитика.md
```

Expected:

```text
## Related Claims
- claims/...
## Source Resolution
```

Must not contain:

```text
- telegram:
```

- [ ] **Step 5: Decide Git handling for generated wiki**

`output/` is ignored. If the user wants LLM-generated wiki changes recoverable through GitHub history, either force-add reviewed wiki output:

```powershell
git add -f output/wiki
git commit -m "wiki: add coverage backfill pages"
```

or change `.gitignore` so `output/wiki/**` is tracked while other `output/` runtime data remains ignored:

```gitignore
output/*
!output/wiki/
!output/wiki/**
```

Use the second option only after explicit user confirmation because it changes repository policy.

---

### Task 6: Final Verification

**Files:**
- All changed source and test files.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
python -m unittest tests.test_wiki_coverage tests.test_wiki_ingest tests.test_wiki_health tests.test_wiki_overview tests.test_main
```

Expected:

```text
OK
```

- [ ] **Step 2: Run full tests**

Run:

```powershell
python -m unittest
```

Expected:

```text
Ran ... tests
OK
```

- [ ] **Step 3: Run ruff**

Run:

```powershell
python -m ruff check retrieval/wiki_coverage.py retrieval/wiki_ingest.py retrieval/wiki_overview.py cli_wiki.py cli_app.py tests/test_wiki_coverage.py tests/test_wiki_ingest.py tests/test_wiki_overview.py tests/test_main.py
```

Expected:

```text
All checks passed!
```

- [ ] **Step 4: Run real commands**

Run:

```powershell
python main.py wiki ingest
python main.py wiki coverage-backfill
python main.py wiki health
python main.py wiki overview
python main.py fts rebuild
```

Expected:

```text
Wiki ingest complete.
Wiki coverage backfill complete.
Wiki health complete.
Wiki overview complete.
Card FTS rebuild complete.
```

- [ ] **Step 5: Commit final integration**

```powershell
git status --short
git add retrieval/wiki_coverage.py retrieval/wiki_ingest.py retrieval/wiki_overview.py cli_wiki.py cli_app.py tests/test_wiki_coverage.py tests/test_wiki_ingest.py tests/test_wiki_overview.py tests/test_main.py
git commit -m "feat: backfill wiki entity and topic coverage"
```

---

## Acceptance Criteria

- `python main.py wiki ingest` still creates/updates grounded claim pages from enriched cards.
- After ingest, missing high-frequency entity/topic pages are automatically created or updated from related claim pages.
- `python main.py wiki coverage-backfill` can be run independently.
- Coverage threshold and per-run limit are configurable through `WIKI_COVERAGE_THRESHOLD` and `WIKI_COVERAGE_LIMIT`.
- `wiki_overview.py` and `wiki_coverage.py` use the same coverage-gap logic.
- Entity/topic hub pages contain `Related Claims` and `Source Resolution`.
- Entity/topic hub pages do not contain raw `telegram:*` evidence lines.
- `python main.py wiki health` has no `error` or `warning`.
- The previous 40 `info` coverage gaps either disappear or shrink to only names that have no related claim pages.
- Full `python -m unittest` passes.
- `ruff` passes.

---

## Self-Review

- Spec coverage: The plan covers automatic creation of `entities/*` and `topics/*`, env-configurable thresholds, shared overview/backfill coverage logic, standalone CLI, integration into `wiki ingest`, health/overview verification, FTS rebuild, and Git handling for generated wiki history.
- Placeholder scan: No placeholder markers remain. Every implementation task includes exact files, code, commands, and expected results.
- Type consistency: `WikiCoverageBackfillStats`, `CoverageCandidate`, and `run_wiki_coverage_backfill()` signatures are consistent across tasks.
