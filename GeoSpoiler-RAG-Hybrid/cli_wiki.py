"""Wiki-memory CLI command implementations."""

import sys
from dataclasses import dataclass
from pathlib import Path

import config
from retrieval.wiki_claims import seed_claim_pages
from retrieval.wiki_coverage import run_wiki_coverage_backfill
from retrieval.wiki_health import run_wiki_health, write_health_report
from retrieval.wiki_index import build_wiki_indexes
from retrieval.wiki_ingest import run_wiki_ingest
from retrieval.wiki_localize import localize_wiki_pages
from retrieval.wiki_overview import build_wiki_overview, write_wiki_overview
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


def _console_safe_text(value: object) -> str:
    text = str(value)
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        text.encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return text.encode(encoding, errors="backslashreplace").decode(encoding, errors="strict")
    return text


def _print_console(value: object = "") -> None:
    print(_console_safe_text(value))


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

    _print_console("Wiki health complete.")
    _print_console(f"  Pages checked: {report.page_count}")
    _print_console(f"  Issues: {report.issue_count}")
    _print_console(f"  Indexed pages: {index_stats.page_count}")
    _print_console(f"  Indexed sources: {index_stats.source_count}")
    _print_console(f"  Report: {report_path}")
    if report.issues:
        _print_console("  First issues:")
        for issue in report.issues[:10]:
            _print_console(f"    - [{issue.severity}] {issue.code}: {issue.page_path} - {issue.message}")


def cmd_wiki_ingest() -> None:
    cmd_wiki_init()
    stats = run_wiki_ingest()
    index_stats = build_wiki_indexes()
    report = run_wiki_health()
    report_path = write_health_report(report)
    overview = build_wiki_overview()
    overview_path = write_wiki_overview(overview)

    print("Wiki ingest complete.")
    print(f"  Cards processed: {stats.cards_processed}")
    print(f"  Pages created: {len(stats.pages_created)}")
    print(f"  Pages updated: {len(stats.pages_updated)}")
    print(f"  Pending (failed/unclear): {len(stats.pending)}")
    print(f"  Indexed pages: {index_stats.page_count}")
    print(f"  Indexed sources: {index_stats.source_count}")
    print(f"  Health issues: {report.issue_count}")
    print(f"  Health report: {report_path}")
    print(f"  Overview: {overview_path}")
    _print_wiki_git_status_hint()


def cmd_wiki_overview() -> None:
    cmd_wiki_init()
    build_wiki_indexes()
    overview = build_wiki_overview()
    overview_path = write_wiki_overview(overview)

    print("Wiki overview complete.")
    print(f"  Claims: {overview.claim_count}")
    print(f"  Entities: {overview.entity_count}")
    print(f"  Topics: {overview.topic_count}")
    print(f"  Pending sources: {overview.pending_count}")
    print(f"  Missing entity coverage: {len(overview.missing_entities)}")
    print(f"  Missing topic coverage: {len(overview.missing_topics)}")
    print(f"  Overview: {overview_path}")


def cmd_wiki_coverage_backfill() -> None:
    cmd_wiki_init()
    stats = run_wiki_coverage_backfill()
    index_stats = build_wiki_indexes()
    overview = build_wiki_overview()
    overview_path = write_wiki_overview(overview)

    print("Wiki coverage backfill complete.")
    print(f"  Pages created: {len(stats.pages_created)}")
    print(f"  Pages updated: {len(stats.pages_updated)}")
    print(f"  Pages skipped: {len(stats.pages_skipped)}")
    print(f"  Entities considered: {stats.entities_considered}")
    print(f"  Topics considered: {stats.topics_considered}")
    print(f"  Entity pages changed: {stats.entities_created_or_updated}")
    print(f"  Topic pages changed: {stats.topics_created_or_updated}")
    print(f"  Indexed pages: {index_stats.page_count}")
    print(f"  Indexed sources: {index_stats.source_count}")
    print(f"  Overview: {overview_path}")
    _print_wiki_git_status_hint()


def cmd_wiki_localize() -> None:
    cmd_wiki_init()
    stats = localize_wiki_pages()
    overview = build_wiki_overview()
    overview_path = write_wiki_overview(overview)

    print("Wiki localization complete.")
    print(f"  Claim pages renamed: {stats.claims_renamed}")
    print(f"  Pages rewritten: {stats.pages_rewritten}")
    print(f"  Indexed pages: {stats.indexed_pages}")
    print(f"  Indexed sources: {stats.indexed_sources}")
    print(f"  Overview: {overview_path}")
    _print_wiki_git_status_hint()


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


def _print_wiki_git_status_hint() -> None:
    """Show changed wiki files so LLM-generated edits are easy to commit or revert."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "status", "--short", "--", "output/wiki"],
            cwd=str(config.PROJECT_ROOT),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError:
        return
    changed = result.stdout.strip()
    if not changed:
        print("  Git wiki changes: none")
        return
    print("  Git wiki changes:")
    for line in changed.splitlines()[:20]:
        print(f"    {line}")
    print("  Preserve after review: git add output/wiki && git commit -m \"wiki: ingest enriched cards\"")
