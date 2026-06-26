"""Pipeline, review, status, and quality CLI command implementations."""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import config
from baseline_probe import collect_baseline_metadata, run_baseline_probe, write_baseline_metadata, write_probe_report
from cli_runtime import _finalize_rag_safely, logger
from cli_wiki import cmd_wiki_ingest
from enricher.pipeline import EnrichmentStats, enrich_all
from fetcher.state import get_all_progress, mark_message_processed
from fetcher.telegram_client import TelegramFetcher, TelegramMessage
from loader.entity_merge import auto_fix_safe_entity_merges
from loader.factory import create_rag
from loader.graph_quality import build_quality_report
from loader.ingest import load_from_directory, load_texts
from loader.storage import rebuild_rag_storage
from normalizer.pipeline import NormalizationBatchResult, normalize_batch
from normalizer.review_queue import get_pending_reviews


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


def _mark_contiguous_processed(messages: list[TelegramMessage], successful_ids: set[int]) -> int:
    """Advance fetch progress only through the first contiguous successful prefix."""
    marked = 0
    for msg in sorted(messages, key=lambda item: item.message_id):
        if msg.message_id not in successful_ids:
            break
        mark_message_processed(msg.channel_id, msg.channel_name, msg.message_id)
        marked += 1
    return marked


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
        marked_count = _mark_contiguous_processed(messages, successful_ids)
        result.processed_messages += marked_count
        sorted_messages = sorted(messages, key=lambda item: item.message_id)
        marked_ids = {msg.message_id for msg in sorted_messages[:marked_count]}

        for msg in messages:
            if msg.message_id not in marked_ids:
                logger.warning(
                    f"  Message {msg.message_id} from '{msg.channel_name}' not marked processed "
                    "(will be retried next run)."
                )

        summary.merge(result)

    logger.info(f"=== NORMALIZE complete: {summary.normalized_messages} texts normalized ===")
    return summary


async def cmd_load(texts_with_paths: list[tuple[str, str]] | None = None) -> LoadStats:
    """Load normalized texts into LightRAG."""
    logger.info("=== LOAD: Loading into LightRAG ===")

    rag = await create_rag()
    load_stats = LoadStats()

    try:
        if texts_with_paths is not None:
            # Explicit texts passed (e.g. from cmd_run after normalize)
            load_stats.normalized_attempted = len(texts_with_paths)
            load_stats.normalized_loaded = await load_texts(rag, texts_with_paths)
        else:
            # Default: load raw normalized texts
            load_stats.normalized_attempted = sum(1 for _ in config.NORMALIZED_DIR.rglob("*.txt"))
            load_stats.normalized_loaded = await load_from_directory(rag)

        reviewed = _collect_reviewed_texts()
        if reviewed:
            logger.info(f"  Loading {len(reviewed)} reviewed item(s) into LightRAG.")
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
    cmd_enrich()

    # Wiki ingest (incremental - only new/changed enriched cards)
    cmd_wiki_ingest()

    load_stats = await cmd_load(normalize_stats.texts_with_paths)
    _print_run_summary(channel_messages, normalize_stats, load_stats)

    logger.info("=== FULL PIPELINE COMPLETE ===")


async def cmd_rebuild():
    """Backup current RAG storage, then rebuild from normalized sources."""
    logger.info("=== REBUILD: Resetting LightRAG storage (source: normalized) ===")

    backup_path = rebuild_rag_storage()
    if backup_path:
        logger.info(f"RAG storage backup created at: {backup_path}")
    _clear_lightrag_query_cache()

    logger.info("=== REBUILD: Loading all normalized sources into fresh LightRAG storage ===")
    load_stats = await cmd_load()
    _print_load_summary(load_stats, heading="REBUILD SUMMARY")
    logger.info("=== REBUILD COMPLETE ===")


async def cmd_rebuild_embedding():
    """Backup current RAG storage, preserve LLM cache, then rebuild embeddings."""
    logger.info("=== REBUILD EMBEDDING: Resetting storage but preserving LLM cache ===")

    backup_path = rebuild_rag_storage(preserve_llm_cache=True)
    if backup_path:
        logger.info(f"RAG storage backup created at: {backup_path}")

    logger.info("=== REBUILD EMBEDDING: Loading sources to regenerate embeddings ===")
    load_stats = await cmd_load()
    _print_load_summary(load_stats, heading="REBUILD EMBEDDING SUMMARY")
    logger.info("=== REBUILD EMBEDDING COMPLETE ===")


def _print_enriched_graph_load_unsupported() -> None:
    print(
        "`--from-enriched` is not supported in the main CLI. "
        "Enriched-card graph loading was experimental and is no longer a v1.1 release path. "
        "Use `python main.py load` or `python main.py rebuild` to load normalized sources."
    )


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


def _collect_reviewed_texts() -> list[tuple[str, str]]:
    """Collect processed review items whose extracted_text is non-empty."""
    results = []
    for f in config.REVIEW_QUEUE_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("status") != "processed" or not data.get("extracted_text"):
                continue
            extracted = str(data["extracted_text"]).strip()
            if not extracted:
                continue
            header = (
                f"[Review type: {data.get('review_type', 'unknown')} | "
                f"Channel: {data.get('channel', '')} | "
                f"Message: {data.get('message_id', '')} | "
                f"URL: {data.get('url', '')}]"
            )
            results.append((str(f), f"{header}\n\n{extracted}"))
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
    print("Review queue:")
    print(f"  AI чатов отправлено на review: {normalize_stats.ai_review_created}")
    print(f"  Внешних ссылок отправлено на review: {normalize_stats.link_review_created}")
    print(f"  Малоинформативных постов на review: {normalize_stats.uninformative_review_created}")
    print(f"  AI ссылок уже обработано ранее: {normalize_stats.ai_review_already_reviewed}")
    print(f"  Pending сейчас: {load_stats.review_pending}")
    print(f"  Processed сейчас: {load_stats.review_processed}")
    print(f"  Skipped сейчас: {load_stats.review_skipped}")
    print()
    print("Дошло до LightRAG:")
    print(f"  Нормализованных текстов к загрузке: {load_stats.normalized_attempted}")
    print(f"  Нормализованных текстов загружено: {load_stats.normalized_loaded}")
    print(f"  Reviewed items к загрузке: {load_stats.reviewed_attempted}")
    print(f"  Reviewed items загружено: {load_stats.reviewed_loaded}")
    print(f"  Итого загружено в LightRAG: {load_stats.total_loaded}")
    print("═" * 60)


def _print_load_summary(load_stats: LoadStats, heading: str = "LOAD SUMMARY") -> None:
    """Print a compact summary for load/rebuild commands."""
    print(f"\n📦 {heading}")
    print("═" * 60)
    print(f"Нормализованных текстов к загрузке: {load_stats.normalized_attempted}")
    print(f"Нормализованных текстов загружено: {load_stats.normalized_loaded}")
    print(f"Reviewed items к загрузке: {load_stats.reviewed_attempted}")
    print(f"Reviewed items загружено: {load_stats.reviewed_loaded}")
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

def launch_reviewer_web() -> None:
    """Launch the Streamlit reviewer web UI and open it in the default browser."""
    import subprocess
    import time
    import webbrowser

    app_path = config.PROJECT_ROOT / "reviewer_app.py"
    if not app_path.exists():
        print(f"Reviewer app not found at {app_path}")
        return

    port = 8501
    print(f"\n🌐 Запускаю Reviewer Web UI на http://localhost:{port}")
    print("Нажмите Ctrl+C в терминале, чтобы остановить.\n")

    # Open browser after a short delay
    def _open_browser():
        time.sleep(2)
        webbrowser.open(f"http://localhost:{port}")

    import threading
    threading.Thread(target=_open_browser, daemon=True).start()

    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app_path),
            "--server.port",
            str(port),
            "--server.headless",
            "true",
        ],
        cwd=str(config.PROJECT_ROOT),
    )


def _maybe_launch_reviewer() -> None:
    """Check for pending reviews and offer to launch the web UI."""
    pending = get_pending_reviews()
    if not pending:
        return

    print(f"\n🔍 Обнаружено {len(pending)} элемент(ов) в очереди ревью.")
    print("   Запустите: python main.py review --web")


def cmd_review(web: bool = False):
    """Show pending review items or launch the web UI."""
    if web:
        launch_reviewer_web()
        return

    items = get_pending_reviews()
    if not items:
        print("✅ Нет элементов в очереди на проверку.")
        print("\nДля веб-интерфейса: python main.py review --web")
        return

    print(f"\n📋 Pending review items: {len(items)}\n")
    for i, item in enumerate(items, 1):
        review_type = item.get('review_type', 'unknown')
        type_label = {
            'ai_chat': 'AI Chat',
            'external_link': 'Link',
            'uninformative': 'Low-info',
            'instagram_long_reel': 'Long Reel',
        }
        badge = type_label.get(review_type, review_type)
        print(f"  {i}. [{badge}] [{item.get('channel', '?')}] msg_id={item.get('message_id', '?')}")
        url = item.get('url', '')
        if url:
            print(f"     URL: {url}")
        reason = item.get('reason', '')
        if reason and not url:
            print(f"     Reason: {reason}")
        if item.get("message_text"):
            preview = item["message_text"][:80]
            print(f"     Text: {preview}...")
        print(f"     File: {item['_filepath']}")
        print()

    print(f"Всего: {len(items)} элемент(ов) ожидают ревью.")
    print("Для веб-интерфейса: python main.py review --web")
    print("Или отредактируй JSON файл вручную и запусти: python main.py load")


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

def _print_entity_autofix_summary(merges: list[dict[str, Any]]) -> None:
    """Print the entity alias fixes applied after load/rebuild."""
    print()
    print("Автофикс alias-дублей:")
    for merge in merges:
        print(f"  {', '.join(merge['sources'])} -> {merge['target']}")
