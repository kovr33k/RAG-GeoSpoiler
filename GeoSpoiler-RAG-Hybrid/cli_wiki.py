"""Wiki-memory CLI command implementations."""

from dataclasses import dataclass
from pathlib import Path

import config
from retrieval.wiki_claims import seed_claim_pages
from retrieval.wiki_health import run_wiki_health, write_health_report
from retrieval.wiki_index import build_wiki_indexes
from retrieval.wiki_pages import seed_entity_topic_pages
from retrieval.wiki_update import run_wiki_incremental_update


@dataclass
class WikiInitStats:
    """Summary of wiki scaffold paths created or left untouched."""

    directories_created: list[Path]
    directories_existing: list[Path]
    files_created: list[Path]
    files_existing: list[Path]

_WIKI_SCAFFOLD_FILES = {
    "_master_index.md": """# Wiki Memory

This is the root index for the local wiki-memory layer.

## Sections

- entities/
- topics/
- claims/
- indexes/

## Notes

- Keep source-grounded pages separate from raw normalized sources.
- Do not treat this wiki as a replacement for original Telegram, web, or media sources.
""",
    "_schema.md": """# Wiki Memory Schema

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

## Update Rules

- Automatically created pages must keep review_status=auto until reviewed.
- Manual edits must not be overwritten by scaffold or build commands.
- Append to logs; do not rewrite existing log history.
""",
    "_health.md": """# Wiki Health

No wiki health check has been run yet.
""",
    "_change_log.md": """# Wiki Change Log

Append notable manual and automated wiki changes here.
""",
    "_log.md": """# Wiki Operation Log

Append machine-readable operation entries here.
""",
    "_pending_updates.json": "[]\n",
}

def _ensure_wiki_directory(path: Path, stats: WikiInitStats) -> None:
    if path.exists() and not path.is_dir():
        raise FileExistsError(f"Wiki scaffold path exists but is not a directory: {path}")
    if path.exists():
        stats.directories_existing.append(path)
        return
    path.mkdir(parents=True, exist_ok=True)
    stats.directories_created.append(path)


def _write_wiki_file_if_missing(path: Path, content: str, stats: WikiInitStats) -> None:
    if path.exists() and not path.is_file():
        raise FileExistsError(f"Wiki scaffold path exists but is not a file: {path}")
    if path.exists():
        stats.files_existing.append(path)
        return
    path.write_text(content, encoding="utf-8")
    stats.files_created.append(path)


def cmd_wiki_init() -> WikiInitStats:
    """Create the local wiki-memory scaffold without overwriting existing files."""
    stats = WikiInitStats([], [], [], [])
    wiki_dir = config.WIKI_DIR

    for directory in [
        wiki_dir,
        wiki_dir / "entities",
        wiki_dir / "topics",
        wiki_dir / "claims",
        config.WIKI_INDEX_DIR,
    ]:
        _ensure_wiki_directory(directory, stats)

    for filename, content in _WIKI_SCAFFOLD_FILES.items():
        _write_wiki_file_if_missing(wiki_dir / filename, content, stats)

    return stats


def _print_wiki_init_summary(stats: WikiInitStats) -> None:
    print("Wiki scaffold ready.")
    print(f"  Directories created: {len(stats.directories_created)}")
    print(f"  Directories existing: {len(stats.directories_existing)}")
    print(f"  Files created: {len(stats.files_created)}")
    print(f"  Files existing: {len(stats.files_existing)}")


def cmd_wiki_build_claims() -> None:
    cmd_wiki_init()
    stats = seed_claim_pages()
    index_stats = build_wiki_indexes()

    print("Wiki claims build complete.")
    print(f"  Claim pages created: {len(stats.created)}")
    print(f"  Claim pages existing: {len(stats.existing)}")
    print(f"  Claim specs skipped: {len(stats.skipped)}")
    print(f"  Indexed pages: {index_stats.page_count}")
    print(f"  Indexed sources: {index_stats.source_count}")


def cmd_wiki_build_entities_topics() -> None:
    cmd_wiki_init()
    stats = seed_entity_topic_pages()
    index_stats = build_wiki_indexes()

    print("Wiki entity/topic build complete.")
    print(f"  Pages created: {len(stats.created)}")
    print(f"  Pages existing: {len(stats.existing)}")
    print(f"  Page specs skipped: {len(stats.skipped)}")
    print(f"  Master index: {stats.master_index_path}")
    print(f"  Indexed pages: {index_stats.page_count}")
    print(f"  Indexed sources: {index_stats.source_count}")


def cmd_wiki_health() -> None:
    cmd_wiki_init()
    index_stats = build_wiki_indexes()
    report = run_wiki_health()
    report_path = write_health_report(report)

    print("Wiki health complete.")
    print(f"  Pages checked: {report.page_count}")
    print(f"  Issues: {report.issue_count}")
    print(f"  Indexed pages: {index_stats.page_count}")
    print(f"  Indexed sources: {index_stats.source_count}")
    print(f"  Report: {report_path}")
    if report.issues:
        print("  First issues:")
        for issue in report.issues[:10]:
            print(f"    - [{issue.severity}] {issue.code}: {issue.page_path} - {issue.message}")


def cmd_wiki_update() -> None:
    cmd_wiki_init()
    stats = run_wiki_incremental_update()
    index_stats = build_wiki_indexes()

    print("Wiki incremental update complete.")
    print(f"  Initialized source hash baseline: {stats.initialized}")
    print(f"  Current sources: {stats.current_sources}")
    print(f"  New sources: {len(stats.new_sources)}")
    print(f"  Changed sources: {len(stats.changed_sources)}")
    print(f"  Removed sources: {len(stats.removed_sources)}")
    print(f"  Pages updated: {len(stats.pages_updated)}")
    print(f"  Pending updates: {len(stats.pending_updates)}")
    print(f"  Indexed pages: {index_stats.page_count}")
    print(f"  Indexed sources: {index_stats.source_count}")
    print(f"  Pending queue: {stats.pending_updates_path}")
    print(f"  Source hashes: {stats.source_hashes_path}")
    print(f"  Operation log: {stats.log_path}")
