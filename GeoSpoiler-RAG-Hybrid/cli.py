"""Small CLI command helpers extracted from main.py."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import config
from data_validation import EnrichedValidationReport, scan_enriched_cards, write_enriched_validation_report
from experiment_registry import ExperimentRegistry, write_experiment_registry
from normalizer.transcription_backfill import BackfillStats, backfill_transcripts
from retrieval.card_fts import CardFtsBuildStats, CardFtsMatch, rebuild_card_index, search_card_index
from retrieval.shadow_search import ShadowMatch, search as shadow_search_cards
from retrieval.source_registry import (
    SourcePassport,
    SourceRegistryStats,
    rebuild_source_registry,
    resolve_source,
)


def cmd_experiments_index(
    write_registry: Callable[[], ExperimentRegistry] = write_experiment_registry,
) -> ExperimentRegistry:
    """Build and print the local experiment registry summary."""
    registry = write_registry()

    print("Experiment registry complete.")
    print(f"  Records: {len(registry.records)}")
    print(f"  Manifest: {registry.manifest_path}")
    print(f"  Report: {registry.report_path}")
    return registry


def cmd_validate_enriched(
    fail_on_error: bool = False,
    enriched_dir: Path | None = None,
    scan_cards: Callable[[Path], EnrichedValidationReport] = scan_enriched_cards,
    write_report: Callable[[EnrichedValidationReport], Path] = write_enriched_validation_report,
) -> EnrichedValidationReport:
    """Validate enriched cards and print a compact CLI summary."""
    report = scan_cards(enriched_dir or config.ENRICHED_DIR)
    report_path = write_report(report)

    print("Enriched validation complete.")
    print(f"  Cards seen: {report.cards_seen}")
    print(f"  Cards valid: {report.cards_valid}")
    print(f"  Cards invalid: {report.cards_invalid}")
    print(f"  Errors: {report.error_count}")
    print(f"  Warnings: {report.warning_count}")
    print(f"  Report: {report_path}")
    if fail_on_error and report.error_count:
        raise SystemExit(1)
    return report


def cmd_registry_rebuild(
    rebuild_registry: Callable[..., SourceRegistryStats] = rebuild_source_registry,
) -> SourceRegistryStats:
    """Rebuild the local source registry and print its summary."""
    stats = rebuild_registry(
        normalized_dir=config.NORMALIZED_DIR,
        enriched_dir=config.ENRICHED_DIR,
        db_path=config.SOURCE_REGISTRY_DB_PATH,
    )
    print("Source registry rebuild complete.")
    print(f"  DB: {stats.db_path}")
    print(f"  Run: {stats.run_id}")
    print(f"  Sources: {stats.sources}")
    print(f"  Normalized docs: {stats.normalized_docs}")
    print(f"  Enriched cards: {stats.enriched_cards}")
    print(f"  References: {stats.references}")
    return stats


def cmd_registry_resolve(
    source_id: str,
    resolve_registry_source: Callable[..., SourcePassport | None] = resolve_source,
) -> SourcePassport | None:
    """Resolve one source id and print a source passport."""
    passport = resolve_registry_source(source_id, db_path=config.SOURCE_REGISTRY_DB_PATH)
    if passport is None:
        print(f"Source not found: {source_id}")
        return None

    print(f"Source: {passport.source_id}")
    print(f"  primary_url: {passport.primary_url}")
    print(f"  post_url: {passport.post_url}")
    if passport.youtube_url:
        print(f"  youtube_url: {passport.youtube_url}")
    print(f"  normalized_file: {passport.normalized_file}")
    print(f"  enriched_card: {passport.card_path}")
    print(f"  meta_file: {passport.meta_file}")
    print(f"  channel: {passport.channel_name}")
    print(f"  message_id: {passport.message_id}")
    print(f"  date: {passport.date}")
    return passport


def cmd_fts_rebuild(
    rebuild_index: Callable[[], CardFtsBuildStats] = rebuild_card_index,
) -> CardFtsBuildStats:
    """Rebuild the local card FTS index and print its summary."""
    stats = rebuild_index()
    print("Card FTS rebuild complete.")
    print(f"  DB: {stats.db_path}")
    print(f"  Cards seen: {stats.cards_seen}")
    print(f"  Cards indexed: {stats.cards_indexed}")
    print(f"  Cards skipped: {stats.cards_skipped}")
    return stats


def cmd_fts_search(
    query: str,
    top_k: int = 10,
    compare_shadow: bool = False,
    search_index: Callable[..., list[CardFtsMatch]] = search_card_index,
    search_shadow: Callable[..., list[ShadowMatch]] = shadow_search_cards,
) -> list[CardFtsMatch]:
    """Search the local card FTS index and print a CLI report."""
    matches = search_index(query, top_k=top_k)
    print("\n" + "=" * 80)
    print(f"Card FTS search: {query}")
    print(f"Results: {len(matches)}")
    print("=" * 80)
    if not matches:
        print("No FTS matches. Run `python main.py fts rebuild` if the index is empty.")
    for idx, match in enumerate(matches, 1):
        print(f"\n[{idx}] {match.title}")
        print(f"score: {match.score:g}")
        if match.post_url:
            print(f"url: {match.post_url}")
        print(f"source_id: {match.source_id or 'unknown'}")
        print(f"normalized: {match.normalized_file}")
        if match.snippet:
            print(f"snippet: {match.snippet}")

    if compare_shadow:
        shadow_matches = search_shadow(query, top_k=top_k)
        print("\n" + "-" * 80)
        print(f"Shadow search comparison: {len(shadow_matches)}")
        for idx, match in enumerate(shadow_matches, 1):
            print(f"[{idx}] score={match.score:g} title={match.title} source={match.source_path}")
    return matches


def cmd_transcribe_backfill(
    limit: int = 3,
    channel: str | None = None,
    media_type: str | None = None,
    dry_run: bool = False,
    backfill: Callable[..., BackfillStats] = backfill_transcripts,
) -> BackfillStats:
    """Run a controlled native media transcription backfill and print a summary."""
    stats = backfill(
        limit=limit,
        channel=channel,
        media_type=media_type,
        dry_run=dry_run,
    )
    print("Transcription backfill complete.")
    print(f"  Dry run: {stats.dry_run}")
    print(f"  Attempted: {stats.attempted}")
    print(f"  Transcribed/cached: {stats.transcribed}")
    print(f"  Disabled: {stats.disabled}")
    print(f"  Skipped: {stats.skipped}")
    print(f"  Failed: {stats.failed}")
    print(f"  Normalized files updated: {stats.normalized_updated}")
    for item in stats.items:
        detail = f"{item.status} {item.media_type} msg={item.message_id}"
        if item.updated:
            detail += " updated"
        if item.error:
            detail += f" error={item.error}"
        print(f"  - {item.normalized_file}: {detail}")
    return stats
