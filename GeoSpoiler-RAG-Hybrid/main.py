"""
GeoSpoiler-RAG - Main Pipeline Entry Point

Batch mode:
  python main.py fetch [N]     - Fetch last N messages from Telegram (default: all new)
  python main.py normalize [N] - Fetch + normalize only (NO load into LightRAG)
  python main.py enrich        - Enrich normalized posts into memory cards
  python main.py load          - Load normalized .txt files into LightRAG (default) or --from-enriched
  python main.py rebuild       - Backup current LightRAG storage and rebuild from normalized texts (default) or --from-enriched
  python main.py search "query" --mode [recall|broll|thesis|entity|shadow] - Multi-index search
  python main.py run [N]       - Full pipeline: fetch -> normalize -> enrich -> load
  python main.py query "?"     - Query the knowledge graph
  python main.py baseline probe [N] - Record baseline model metadata and run N manual queries
  python main.py wiki init     - Create the local wiki-memory scaffold
  python main.py wiki build --claims-only - Seed source-grounded claim pages
  python main.py wiki build --entities-topics - Seed entity/topic pages
  python main.py wiki health   - Run wiki-memory health checks
  python main.py wiki update   - Run incremental wiki-memory update
  python main.py fts rebuild   - Rebuild local SQLite FTS index for enriched cards
  python main.py fts search "query" [--top-k N] [--compare-shadow] - Search the card FTS index
  python main.py registry rebuild - Rebuild local SQLite source registry
  python main.py registry resolve SOURCE_ID - Resolve source id to source paths/urls
  python main.py transcribe backfill [--limit N] [--dry-run] - Backfill a small batch of native media transcripts
  python main.py validate enriched [--fail-on-error] - Soft-validate enriched card data contracts
  python main.py experiments index - Build local experiment registry/report
  python main.py quality       - Show graph quality report
  python main.py review        - Show pending AI chat review items
  python main.py status        - Show progress status

Enrich options:
  python main.py enrich                        - Enrich new/changed posts
  python main.py enrich --channel "Куба"        - Only enrich one channel
  python main.py enrich --force                 - Re-enrich all posts
"""

import asyncio
import json
import logging
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import config
from baseline_probe import collect_baseline_metadata, run_baseline_probe, write_baseline_metadata, write_probe_report
from cli import (
    cmd_experiments_index,
    cmd_fts_rebuild,
    cmd_fts_search,
    cmd_registry_rebuild,
    cmd_registry_resolve,
    cmd_transcribe_backfill,
    cmd_validate_enriched,
)
from fetcher.state import get_all_progress, mark_message_processed
from fetcher.telegram_client import TelegramFetcher, TelegramMessage
from loader.lightrag_loader import (
    auto_fix_safe_entity_merges,
    create_rag,
    get_query_profile,
    load_from_directory,
    load_from_enriched,
    load_source_metadata_index,
    load_texts,
    query_rag,
    query_rag_result,
    rebuild_rag_storage,
)
from loader.graph_quality import build_quality_report
from normalizer.ai_chat_handler import get_pending_reviews
from normalizer.pipeline import NormalizationBatchResult, normalize_batch
from enricher.pipeline import EnrichmentStats, enrich_all
from retrieval.composer import search as composer_search
from retrieval.response_formatter import format_search_results
from retrieval.wiki_claims import seed_claim_pages
from retrieval.wiki_health import run_wiki_health, write_health_report
from retrieval.wiki_index import build_wiki_indexes
from retrieval.wiki_pages import seed_entity_topic_pages
from retrieval.wiki_update import run_wiki_incremental_update


@dataclass
class LoadStats:
    """Summary of what reached LightRAG during a load step."""

    normalized_attempted: int = 0
    normalized_loaded: int = 0
    reviewed_attempted: int = 0
    reviewed_loaded: int = 0
    review_pending: int = 0
    review_processed: int = 0
    review_skipped: int = 0

    @property
    def total_loaded(self) -> int:
        return self.normalized_loaded + self.reviewed_loaded


@dataclass
class WikiInitStats:
    """Summary of wiki scaffold paths created or left untouched."""

    directories_created: list[Path]
    directories_existing: list[Path]
    files_created: list[Path]
    files_existing: list[Path]


_SOURCE_REQUEST_RE = re.compile(
    r"(откуда|источник|источники|дай ссылк|ссылк|source|sources|citation|citations|where.*from)",
    re.IGNORECASE,
)
_REFERENCE_ID_RE = re.compile(r"\[reference_id:\s*([^\]]+)\]", re.IGNORECASE)
_REFERENCE_BULLET_RE = re.compile(r"^\s*-\s*\[(\d+)\]", re.MULTILINE)
_QUERY_MODES = {"local", "global", "hybrid", "naive", "mix", "bypass"}
_QUERY_PROFILES = {"answer", "source", "overview"}
_SEARCH_CARDS_ONLY_MODES = {"shadow", "cards", "cards-only"}

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


async def _finalize_rag_safely(rag: Any) -> None:
    try:
        await asyncio.wait_for(
            rag.finalize_storages(),
            timeout=config.RAG_FINALIZE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "LightRAG finalize_storages timed out after %ss; continuing.",
            config.RAG_FINALIZE_TIMEOUT_SECONDS,
        )


def _default_query_mode() -> str:
    """Prefer mix mode when reranking is enabled because it combines graph and chunk retrieval."""
    return "mix" if config.RERANKER_ENABLED else "hybrid"


def setup_logging():
    """Configure logging to file and console (UTF-8 safe on Windows)."""
    log_file = config.LOG_DIR / f"pipeline_{datetime.now().strftime('%Y%m%d')}.log"

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


async def cmd_fetch(limit: int | None = None) -> list[tuple[str, list[TelegramMessage]]]:
    """Fetch new messages from all Telegram channels."""
    logger.info("=== FETCH: Starting Telegram fetch ===")

    fetcher = TelegramFetcher()
    await fetcher.connect()

    try:
        all_messages = await fetcher.fetch_all_channels(limit_per_channel=limit)
        total = sum(len(msgs) for msgs in all_messages.values())
        logger.info(f"=== FETCH complete: {total} messages from {len(all_messages)} channels ===")
        return list(all_messages.items())
    finally:
        await fetcher.disconnect()


async def cmd_normalize(channel_messages: list[tuple[str, list[TelegramMessage]]]) -> NormalizationBatchResult:
    """Normalize fetched messages into text files."""
    logger.info("=== NORMALIZE: Processing messages ===")

    summary = NormalizationBatchResult()

    for channel_name, messages in channel_messages:
        if not messages:
            continue
        logger.info(f"Processing channel: {channel_name} ({len(messages)} messages)")

        result = normalize_batch(messages)
        successful_ids = {int(Path(fp).stem) for fp, _ in result.texts_with_paths}

        for msg in messages:
            if msg.message_id in successful_ids:
                mark_message_processed(msg.channel_id, msg.channel_name, msg.message_id)
                result.processed_messages += 1
            else:
                logger.warning(
                    f"  Message {msg.message_id} from '{msg.channel_name}' not marked processed "
                    "(will be retried next run)."
                )

        summary.merge(result)

    logger.info(f"=== NORMALIZE complete: {summary.normalized_messages} texts normalized ===")
    return summary


async def cmd_load(
    texts_with_paths: list[tuple[str, str]] | None = None,
    from_enriched: bool = False,
) -> LoadStats:
    """Load texts into LightRAG.

    By default loads normalized texts into LightRAG. Enriched-card graph
    loading is retained only as an explicit experimental mode.
    """
    logger.info("=== LOAD: Loading into LightRAG ===")

    rag = await create_rag()
    load_stats = LoadStats()

    try:
        if texts_with_paths is not None:
            # Explicit texts passed (e.g. from cmd_run after normalize)
            load_stats.normalized_attempted = len(texts_with_paths)
            load_stats.normalized_loaded = await load_texts(rag, texts_with_paths)
        elif from_enriched:
            # Experimental mode: load from enriched cards
            enriched_stats = await load_from_enriched(rag)
            load_stats.normalized_attempted = enriched_stats.get(
                "normalized_found",
                enriched_stats["loaded"] + enriched_stats["skipped_triage"]
                + enriched_stats["skipped_dedup"],
            )
            load_stats.normalized_loaded = enriched_stats["loaded"]
            if (
                enriched_stats["skipped_triage"]
                or enriched_stats["skipped_dedup"]
                or enriched_stats.get("missing_enriched")
            ):
                logger.info(
                    f"  Enriched load: skipped {enriched_stats['skipped_triage']} triage, "
                    f"{enriched_stats['skipped_dedup']} dedup, "
                    f"{enriched_stats['fallback_normalized']} fallback to normalized, "
                    f"{enriched_stats.get('missing_enriched', 0)} missing enriched"
                )
        else:
            # Default: load raw normalized texts
            load_stats.normalized_attempted = sum(1 for _ in config.NORMALIZED_DIR.rglob("*.txt"))
            load_stats.normalized_loaded = await load_from_directory(rag)

        reviewed = _collect_reviewed_ai_texts()
        if reviewed:
            logger.info(f"  Loading {len(reviewed)} reviewed AI-chat item(s) into LightRAG.")
            load_stats.reviewed_attempted = len(reviewed)
            load_stats.reviewed_loaded = await load_texts(rag, reviewed)

        queue_stats = _get_review_queue_status_counts()
        load_stats.review_pending = queue_stats["pending"]
        load_stats.review_processed = queue_stats["processed"]
        load_stats.review_skipped = queue_stats["skipped"]

        merges = await auto_fix_safe_entity_merges(rag)
        if merges:
            logger.info(f"=== AUTO-FIX complete: {len(merges)} safe entity merge(s) applied ===")
            _print_entity_autofix_summary(merges)

        logger.info(f"=== LOAD complete: {load_stats.total_loaded} texts loaded ===")
        return load_stats
    finally:
        await _finalize_rag_safely(rag)


def cmd_enrich(
    channel_filter: str | None = None,
    force: bool = False,
) -> EnrichmentStats:
    """Enrich normalized posts into structured memory cards."""
    logger.info("=== ENRICH: Building memory cards ===")

    stats = enrich_all(channel_filter=channel_filter, force=force)
    _print_enrich_summary(stats)

    logger.info("=== ENRICH complete ===")
    return stats


async def cmd_run(limit: int | None = None):
    """Full pipeline: fetch -> normalize -> enrich -> load."""
    logger.info("=== FULL PIPELINE START ===")

    channel_messages = await cmd_fetch(limit=limit)

    normalize_stats = NormalizationBatchResult()
    total_msgs = sum(len(msgs) for _, msgs in channel_messages)
    if total_msgs > 0:
        normalize_stats = await cmd_normalize(channel_messages)
    else:
        logger.info("No new Telegram messages to normalize.")

    # Enrich all posts (incremental — only new/changed)
    enrich_stats = cmd_enrich()

    load_stats = await cmd_load(normalize_stats.texts_with_paths)
    _print_run_summary(channel_messages, normalize_stats, load_stats)

    logger.info("=== FULL PIPELINE COMPLETE ===")


async def cmd_rebuild(from_enriched: bool = False):
    """Backup current RAG storage, then rebuild from normalized sources by default."""
    source = "enriched" if from_enriched else "normalized"
    logger.info(f"=== REBUILD: Resetting LightRAG storage (source: {source}) ===")

    backup_path = rebuild_rag_storage()
    if backup_path:
        logger.info(f"RAG storage backup created at: {backup_path}")
    _clear_lightrag_query_cache()

    logger.info(f"=== REBUILD: Loading all {source} sources into fresh LightRAG storage ===")
    load_stats = await cmd_load(from_enriched=from_enriched)
    _print_load_summary(load_stats, heading="REBUILD SUMMARY")
    logger.info("=== REBUILD COMPLETE ===")


def _clear_lightrag_query_cache() -> None:
    """Remove stale LLM query cache after storage reset/rebuild."""
    cache_path = config.RAG_STORAGE_DIR / "kv_store_llm_response_cache.json"
    if not cache_path.exists():
        return
    try:
        cache_path.unlink()
        logger.info("Cleared LightRAG LLM response cache for rebuild.")
    except OSError as exc:
        logger.warning(f"Could not clear LightRAG LLM response cache: {exc}")


def _collect_reviewed_ai_texts() -> list[tuple[str, str]]:
    """
    Collect all reviewed AI-chat items whose extracted_text is non-empty.
    Returns list of (source_path, text) ready for LightRAG insertion.
    """
    results = []
    for f in config.REVIEW_QUEUE_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("status") == "processed" and data.get("extracted_text"):
                text = data["extracted_text"].strip()
                if text:
                    results.append((str(f), text))
        except (json.JSONDecodeError, OSError):
            continue
    return results


def _get_review_queue_status_counts() -> dict[str, int]:
    """Count current review queue items by status."""
    counts = {
        "pending": 0,
        "processed": 0,
        "skipped": 0,
    }

    for f in config.REVIEW_QUEUE_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        status = data.get("status")
        if status in counts:
            counts[status] += 1

    return counts


def _print_run_summary(
    channel_messages: list[tuple[str, list[TelegramMessage]]],
    normalize_stats: NormalizationBatchResult,
    load_stats: LoadStats,
) -> None:
    """Print an end-of-run summary with content breakdown and final delivery counts."""
    total_channels = len(channel_messages)
    channels_with_posts = sum(1 for _, msgs in channel_messages if msgs)

    print("\n📈 RUN SUMMARY")
    print("═" * 60)
    print(f"Каналов проверено: {total_channels}")
    print(f"Каналов с новыми постами: {channels_with_posts}")
    print(f"Новых постов найдено: {normalize_stats.messages_total}")
    print()
    print("Контент по новым постам:")
    print(f"  С текстом: {normalize_stats.messages_with_text}")
    print(
        f"  С изображениями: {normalize_stats.messages_with_images} постов / "
        f"{normalize_stats.images_total} изображений"
    )
    print(f"  С Telegram-видео: {normalize_stats.messages_with_native_video}")
    print(
        f"  С YouTube: {normalize_stats.messages_with_youtube} постов / "
        f"{normalize_stats.youtube_links_total} ссылок"
    )
    print(
        f"  С Instagram Reels: {normalize_stats.messages_with_instagram_reels} постов / "
        f"{normalize_stats.instagram_reel_links_total} ссылок"
    )
    print(
        f"  С Instagram posts: {normalize_stats.messages_with_instagram_posts} постов / "
        f"{normalize_stats.instagram_post_links_total} ссылок"
    )
    print(
        f"  С AI chat links: {normalize_stats.messages_with_ai_chat} постов / "
        f"{normalize_stats.ai_chat_links_total} ссылок"
    )
    print(
        f"  С web-ссылками: {normalize_stats.messages_with_web} постов / "
        f"{normalize_stats.web_links_total} ссылок"
    )
    print()
    print("Нормализация:")
    print(f"  Успешно нормализовано: {normalize_stats.normalized_messages}")
    print(f"  Пустых/пропущено: {normalize_stats.skipped_messages}")
    print(f"  Ошибок: {normalize_stats.failed_messages}")
    print(f"  Отмечено processed в state: {normalize_stats.processed_messages}")
    print()
    print("AI review queue:")
    print(f"  Новых ссылок отправлено на ручной review: {normalize_stats.ai_review_created}")
    print(f"  Уже ранее обработанных AI ссылок встречено: {normalize_stats.ai_review_already_reviewed}")
    print(f"  Pending сейчас: {load_stats.review_pending}")
    print(f"  Processed сейчас: {load_stats.review_processed}")
    print(f"  Skipped сейчас: {load_stats.review_skipped}")
    print()
    print("Дошло до LightRAG:")
    print(f"  Нормализованных текстов к загрузке: {load_stats.normalized_attempted}")
    print(f"  Нормализованных текстов загружено: {load_stats.normalized_loaded}")
    print(f"  Reviewed AI items к загрузке: {load_stats.reviewed_attempted}")
    print(f"  Reviewed AI items загружено: {load_stats.reviewed_loaded}")
    print(f"  Итого загружено в LightRAG: {load_stats.total_loaded}")
    print("═" * 60)


def _print_load_summary(load_stats: LoadStats, heading: str = "LOAD SUMMARY") -> None:
    """Print a compact summary for load/rebuild commands."""
    print(f"\n📦 {heading}")
    print("═" * 60)
    print(f"Нормализованных текстов к загрузке: {load_stats.normalized_attempted}")
    print(f"Нормализованных текстов загружено: {load_stats.normalized_loaded}")
    print(f"Reviewed AI items к загрузке: {load_stats.reviewed_attempted}")
    print(f"Reviewed AI items загружено: {load_stats.reviewed_loaded}")
    print(f"Pending review сейчас: {load_stats.review_pending}")
    print(f"Processed review сейчас: {load_stats.review_processed}")
    print(f"Skipped review сейчас: {load_stats.review_skipped}")
    print(f"Итого загружено в LightRAG: {load_stats.total_loaded}")
    print("═" * 60)


def _print_enrich_summary(stats: EnrichmentStats) -> None:
    """Print a compact summary for the enrich command."""
    print("\n🧠 ENRICH SUMMARY")
    print("═" * 60)
    print(f"Просканировано постов: {stats.scanned}")
    print(f"Обогащено полностью: {stats.enriched}")
    if stats.partial:
        print(f"⚠️  Частично (LLM не ответил, будет повтор): {stats.partial}")
    print(f"Пропущено (актуальных): {stats.skipped_up_to_date}")
    print(f"Пропущено (без meta.json): {stats.skipped_no_meta}")
    print(f"Ошибок: {stats.failed}")
    if stats.partial_posts:
        print()
        print("⚠️  Посты для повтора (запустите enrich ещё раз):")
        for post in stats.partial_posts:
            print(f"  - {post}")
    if stats.by_content_type:
        print()
        print("По типу контента:")
        for ct, count in sorted(stats.by_content_type.items(), key=lambda x: -x[1]):
            print(f"  {ct}: {count}")
    if stats.by_triage:
        print()
        print("По triage:")
        for tr, count in sorted(stats.by_triage.items(), key=lambda x: -x[1]):
            print(f"  {tr}: {count}")
    if stats.duplicates_marked:
        print(f"\nДубликатов помечено: {stats.duplicates_marked}")
    print("═" * 60)


async def cmd_query(question: str, mode: str | None = None, query_profile: str | None = None):
    """Query the LightRAG knowledge graph."""
    if mode is None:
        mode = _default_query_mode()
    if query_profile is None:
        query_profile = "source" if _question_requests_sources(question) else "answer"
    get_query_profile(query_profile)
    rag = await create_rag()
    query_result = None
    try:
        query_result = await query_rag_result(rag, question, mode=mode, query_profile=query_profile)
        answer = (
            query_result.get("llm_response", {}).get("content")
            if isinstance(query_result, dict)
            else None
        )
        if answer is None or not str(answer).strip() or str(answer).strip().lower() == "none":
            print("Query failed: LightRAG returned no answer. Check API connectivity and logs.")
            raise SystemExit(1)

        print("\n" + "═" * 60)
        print(f"Вопрос: {question}")
        print(f"Режим: {mode} (профиль: {query_profile})")
        print("Ответ:")
        print(answer)
        if query_profile == "source" or _question_requests_sources(question):
            _print_query_sources(query_result)
        print("═" * 60)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"Query failed: {exc}")
        raise SystemExit(1) from exc
    finally:
        await _finalize_rag_safely(rag)


async def cmd_search(query: str, mode: str = "recall"):
    """Execute multi-index search via Retrieval Composer."""
    if mode.strip().lower() in _SEARCH_CARDS_ONLY_MODES:
        package = await composer_search(None, query, mode)
        report = format_search_results(package)
        print("\n" + "=" * 80)
        print(report)
        print("=" * 80 + "\n")
        return

    rag = await create_rag()
    try:
        package = await composer_search(rag, query, mode)
        report = format_search_results(package)
        print("\n" + "=" * 80)
        print(report)
        print("=" * 80 + "\n")
    finally:
        await _finalize_rag_safely(rag)


def cmd_review():
    """Show pending AI chat review items."""
    items = get_pending_reviews()
    if not items:
        print("✅ Нет элементов в очереди на проверку.")
        return

    print(f"\n📋 Pending review items: {len(items)}\n")
    for i, item in enumerate(items, 1):
        print(f"  {i}. [{item['channel']}] msg_id={item['message_id']}")
        print(f"     URL: {item['url']}")
        if item.get("message_text"):
            preview = item["message_text"][:80]
            print(f"     Text: {preview}...")
        print(f"     File: {item['_filepath']}")
        print()

    print("Чтобы обработать: отредактируй JSON файл, заполни 'extracted_text' и измени 'status' на 'processed'.")
    print("Затем запусти: python main.py load")


def cmd_status():
    """Show current pipeline status."""
    progress = get_all_progress()

    print("\n📊 Pipeline Status")
    print("═" * 50)
    print(f"Last run: {progress.get('last_run', 'Never')}")
    print()

    channels = progress.get("channels", {})
    if not channels:
        print("  No channels processed yet.")
    else:
        for ch_id, data in sorted(channels.items()):
            display_name = data.get("title", ch_id)
            last_id = data.get("last_message_id", 0)
            updated = data.get("updated_at", "?")
            print(f"  📌 {display_name}")
            print(f"     Last message ID: {last_id}")
            print(f"     Updated: {updated}")

    txt_count = sum(1 for _ in config.NORMALIZED_DIR.rglob("*.txt"))
    print(f"\n  📄 Normalized files: {txt_count}")

    review_count = len(get_pending_reviews())
    print(f"  🔍 Pending reviews: {review_count}")


def cmd_quality():
    """Show graph quality diagnostics."""
    print()
    print(build_quality_report())


async def cmd_baseline_probe(limit: int = 3) -> None:
    metadata_path = write_baseline_metadata(collect_baseline_metadata())
    report = await run_baseline_probe(limit=limit)
    metadata_path, report_path = write_probe_report(report)

    print("Baseline model probe complete.")
    print(f"  Query model: {report.query_model}")
    print(f"  Query base URL: {report.query_base_url}")
    print(f"  Mode: {report.mode}")
    print(f"  Stable cases: {report.stable_count}/{len(report.results)}")
    print(f"  Metadata: {metadata_path}")
    print(f"  Report: {report_path}")


def _question_requests_sources(question: str) -> bool:
    """Detect whether the user explicitly asked for provenance links."""
    return bool(_SOURCE_REQUEST_RE.search(question))


def _extract_answer_reference_keys(answer: str) -> tuple[set[str], set[str]]:
    """Collect explicit citation keys that the LLM mentioned in the answer."""
    if not answer:
        return set(), set()

    reference_ids = {match.group(1).strip() for match in _REFERENCE_ID_RE.finditer(answer)}
    if "### References" in answer:
        answer = answer.split("### References", 1)[1]
    numbered_refs = {match.group(1) for match in _REFERENCE_BULLET_RE.finditer(answer)}
    return reference_ids, numbered_refs


def _load_adjacent_source_metadata(file_path: str) -> dict[str, Any]:
    """Read normalized sidecar metadata when the RAG metadata index is stale."""
    meta_path = Path(file_path).with_suffix(".meta.json")
    if not meta_path.exists():
        return {}
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _extract_query_sources(query_result: dict[str, Any], limit: int = 5) -> list[dict[str, str]]:
    """Map LightRAG references back to Telegram post metadata."""
    if not isinstance(query_result, dict):
        return []

    data = query_result.get("data", {})
    references = data.get("references", []) if isinstance(data, dict) else []
    metadata_index = load_source_metadata_index()
    answer = str(query_result.get("llm_response", {}).get("content") or "")
    explicit_ids, numbered_refs = _extract_answer_reference_keys(answer)

    results = []
    seen_keys = set()
    filtered_references = []
    for idx, ref in enumerate(references, start=1):
        if not isinstance(ref, dict):
            continue
        ref_id = str(ref.get("reference_id") or "").strip()
        if explicit_ids or numbered_refs:
            if ref_id and ref_id in explicit_ids:
                filtered_references.append(ref)
                continue
            if str(idx) in numbered_refs:
                filtered_references.append(ref)
                continue
            continue
        filtered_references.append(ref)

    for ref in filtered_references:
        if not isinstance(ref, dict):
            continue
        file_path = ref.get("file_path")
        post_url_from_ref = str(ref.get("post_url") or ref.get("youtube_url") or "").strip()
        if not isinstance(file_path, str) or not file_path:
            if post_url_from_ref and post_url_from_ref not in seen_keys:
                seen_keys.add(post_url_from_ref)
                results.append(
                    {
                        "post_url": post_url_from_ref,
                        "channel": str(ref.get("channel") or "").strip(),
                        "date": str(ref.get("date") or "").strip(),
                        "file_path": "",
                    }
                )
                if len(results) >= limit:
                    break
            continue
        canonical_path = str(Path(file_path).resolve(strict=False))
        meta = metadata_index.get(canonical_path, {})
        if not meta:
            meta = _load_adjacent_source_metadata(canonical_path)
        post_url = str(meta.get("пост") or meta.get("post_url") or post_url_from_ref).strip()
        channel = str(meta.get("канал") or meta.get("channel_name") or ref.get("channel") or "").strip()
        date = str(meta.get("дата") or meta.get("date") or ref.get("date") or "").strip()
        key = post_url or canonical_path
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        results.append(
            {
                "post_url": post_url,
                "channel": channel,
                "date": date,
                "file_path": canonical_path,
            }
        )
        if len(results) >= limit:
            break
    return results


def _print_query_sources(query_result: dict[str, Any]) -> None:
    """Print a compact source block after the answer when requested."""
    sources = _extract_query_sources(query_result)
    print()
    print("Источники:")
    if not sources:
        print("  Не удалось поднять ссылки для этого ответа.")
        return

    for idx, source in enumerate(sources, start=1):
        label = source["post_url"] or source["file_path"]
        print(f"  {idx}. {label}")
        if source["channel"]:
            print(f"     Канал: {source['channel']}")
        if source["date"]:
            print(f"     Дата: {source['date']}")


def _print_entity_autofix_summary(merges: list[dict[str, Any]]) -> None:
    """Print the entity alias fixes applied after load/rebuild."""
    print()
    print("Автофикс alias-дублей:")
    for merge in merges:
        print(f"  {', '.join(merge['sources'])} -> {merge['target']}")


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


def _parse_int_flag(args: list[str], flag: str, default: int) -> int:
    if flag not in args:
        return default
    idx = args.index(flag)
    if idx + 1 >= len(args):
        return default
    try:
        return int(args[idx + 1])
    except ValueError:
        return default


def _parse_str_flag(args: list[str], flag: str) -> str | None:
    if flag not in args:
        return None
    idx = args.index(flag)
    if idx + 1 >= len(args):
        return None
    value = args[idx + 1].strip()
    return value or None


logger = logging.getLogger("geospoiler")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command = sys.argv[1].lower()

    if command == "baseline":
        subcommand = sys.argv[2].lower() if len(sys.argv) > 2 else ""
        if subcommand == "probe":
            limit = int(sys.argv[3]) if len(sys.argv) > 3 else 3
            asyncio.run(cmd_baseline_probe(limit=limit))
            return
        print("Usage: python main.py baseline probe [N]")
        return

    if command == "wiki":
        subcommand = sys.argv[2].lower() if len(sys.argv) > 2 else ""
        if subcommand == "init":
            _print_wiki_init_summary(cmd_wiki_init())
            return
        if subcommand == "build" and "--claims-only" in sys.argv[3:]:
            cmd_wiki_build_claims()
            return
        if subcommand == "build" and "--entities-topics" in sys.argv[3:]:
            cmd_wiki_build_entities_topics()
            return
        if subcommand == "health":
            cmd_wiki_health()
            return
        if subcommand == "update":
            cmd_wiki_update()
            return
        if subcommand == "build":
            print("Usage: python main.py wiki build --claims-only | python main.py wiki build --entities-topics")
            return
        print(
            "Usage: python main.py wiki init | python main.py wiki build --claims-only | "
            "python main.py wiki build --entities-topics | python main.py wiki health | "
            "python main.py wiki update"
        )
        return

    if command == "experiments":
        subcommand = sys.argv[2].lower() if len(sys.argv) > 2 else ""
        if subcommand == "index":
            cmd_experiments_index()
            return
        print("Usage: python main.py experiments index")
        return

    setup_logging()

    if command == "fetch":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
        asyncio.run(cmd_fetch(limit))

    elif command == "normalize":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else None

        async def _fetch_and_normalize():
            channel_messages = await cmd_fetch(limit=limit)
            total = sum(len(msgs) for _, msgs in channel_messages)
            if total == 0:
                print("No new messages found.")
                return
            normalize_stats = await cmd_normalize(channel_messages)
            print(f"\nDone: {normalize_stats.normalized_messages} texts normalized to output/normalized/")
            _print_run_summary(channel_messages, normalize_stats, LoadStats())
            print("Run 'python main.py load' when ready to load into LightRAG.")

        asyncio.run(_fetch_and_normalize())

    elif command == "load":
        from_enriched = "--from-enriched" in sys.argv[2:]
        load_stats = asyncio.run(cmd_load(from_enriched=from_enriched))
        _print_load_summary(load_stats)

    elif command == "rebuild":
        from_enriched = "--from-enriched" in sys.argv[2:]
        asyncio.run(cmd_rebuild(from_enriched=from_enriched))

    elif command == "enrich":
        channel_filter = None
        force = False
        args = sys.argv[2:]
        if "--force" in args:
            force = True
            args.remove("--force")
        if "--channel" in args:
            idx = args.index("--channel")
            if idx + 1 < len(args):
                channel_filter = args[idx + 1]
        cmd_enrich(channel_filter=channel_filter, force=force)

    elif command == "run":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
        asyncio.run(cmd_run(limit))

    elif command == "query":
        if len(sys.argv) < 3:
            print('Usage: python main.py query "Ваш вопрос" [mode] [profile]')
            return
        query_args = sys.argv[2:]
        mode = _default_query_mode()
        query_profile = None
        if query_args and query_args[-1].lower() in _QUERY_PROFILES:
            query_profile = query_args[-1].lower()
            query_args = query_args[:-1]
        if query_args and query_args[-1].lower() in _QUERY_MODES:
            mode = query_args[-1].lower()
            query_args = query_args[:-1]
        question = " ".join(query_args).strip()
        if not question:
            print('Usage: python main.py query "Ваш вопрос" [mode] [profile]')
            return
        asyncio.run(cmd_query(question, mode, query_profile))

    elif command == "search":
        if len(sys.argv) < 3:
            print('Usage: python main.py search "query" [--mode recall|broll|thesis|entity|shadow]')
            return
        
        mode = "recall"
        args = sys.argv[2:]
        if "--mode" in args:
            idx = args.index("--mode")
            if idx + 1 < len(args):
                mode = args[idx+1]
                args.pop(idx+1)
                args.pop(idx)
        
        query = " ".join(args).strip()
        if not query:
            print('Usage: python main.py search "query" [--mode recall|broll|thesis|entity|shadow]')
            return
            
        asyncio.run(cmd_search(query, mode))

    elif command == "fts":
        subcommand = sys.argv[2].lower() if len(sys.argv) > 2 else ""
        if subcommand == "rebuild":
            cmd_fts_rebuild()
            return
        if subcommand == "search":
            args = sys.argv[3:]
            compare_shadow = "--compare-shadow" in args
            if compare_shadow:
                args.remove("--compare-shadow")
            top_k = 10
            if "--top-k" in args:
                idx = args.index("--top-k")
                if idx + 1 < len(args):
                    top_k = int(args[idx + 1])
                    args.pop(idx + 1)
                    args.pop(idx)
            query = " ".join(args).strip()
            if not query:
                print('Usage: python main.py fts search "query" [--top-k N] [--compare-shadow]')
                return
            cmd_fts_search(query, top_k=top_k, compare_shadow=compare_shadow)
            return
        print('Usage: python main.py fts rebuild | python main.py fts search "query" [--top-k N] [--compare-shadow]')

    elif command == "registry":
        subcommand = sys.argv[2].lower() if len(sys.argv) > 2 else ""
        if subcommand == "rebuild":
            cmd_registry_rebuild()
            return
        if subcommand == "resolve":
            source_id = " ".join(sys.argv[3:]).strip()
            if not source_id:
                print("Usage: python main.py registry resolve SOURCE_ID")
                return
            cmd_registry_resolve(source_id)
            return
        print("Usage: python main.py registry rebuild | python main.py registry resolve SOURCE_ID")

    elif command == "transcribe":
        subcommand = sys.argv[2].lower() if len(sys.argv) > 2 else ""
        if subcommand == "backfill":
            args = sys.argv[3:]
            dry_run = "--dry-run" in args
            limit = _parse_int_flag(args, "--limit", 3)
            channel = _parse_str_flag(args, "--channel")
            media_type = _parse_str_flag(args, "--media-type")
            if media_type and media_type not in {"video", "audio", "voice"}:
                print("--media-type must be one of: video, audio, voice")
                return
            cmd_transcribe_backfill(
                limit=limit,
                channel=channel,
                media_type=media_type,
                dry_run=dry_run,
            )
            return
        print(
            "Usage: python main.py transcribe backfill "
            "[--limit N] [--channel NAME] [--media-type video|audio|voice] [--dry-run]"
        )

    elif command == "validate":
        subcommand = sys.argv[2].lower() if len(sys.argv) > 2 else ""
        if subcommand == "enriched":
            cmd_validate_enriched(fail_on_error="--fail-on-error" in sys.argv[3:])
            return
        print("Usage: python main.py validate enriched [--fail-on-error]")

    elif command == "quality":
        cmd_quality()

    elif command == "review":
        cmd_review()

    elif command == "status":
        cmd_status()

    else:
        print(f"Unknown command: {command}")
        print(__doc__)


if __name__ == "__main__":
    main()
