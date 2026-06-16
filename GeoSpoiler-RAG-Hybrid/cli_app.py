"""Argument parser and dispatcher for the GeoSpoiler RAG CLI."""

import argparse
import asyncio
import sys

from cli_pipeline import (
    LoadStats,
    _maybe_launch_reviewer,
    _print_enriched_graph_load_unsupported,
    _print_load_summary,
    _print_run_summary,
    cmd_baseline_probe,
    cmd_enrich,
    cmd_fetch,
    cmd_load,
    cmd_normalize,
    cmd_quality,
    cmd_rebuild,
    cmd_rebuild_embedding,
    cmd_review,
    cmd_run,
    cmd_status,
)
from cli_query import _QUERY_MODES, _QUERY_PROFILES, _default_query_mode, cmd_query, cmd_search
from cli_runtime import setup_logging
from cli_tools import (
    cmd_experiments_index,
    cmd_fts_rebuild,
    cmd_fts_search,
    cmd_registry_rebuild,
    cmd_registry_resolve,
    cmd_transcribe_backfill,
    cmd_validate_enriched,
)
from cli_wiki import (
    _print_wiki_init_summary,
    cmd_wiki_build_claims,
    cmd_wiki_build_entities_topics,
    cmd_wiki_health,
    cmd_wiki_init,
    cmd_wiki_update,
)

CLI_DESCRIPTION = "Telegram-to-RAG pipeline for GeoSpoiler local memory."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=CLI_DESCRIPTION)
    subparsers = parser.add_subparsers(dest="command")

    fetch = subparsers.add_parser("fetch")
    fetch.add_argument("limit", nargs="?", type=int)

    normalize = subparsers.add_parser("normalize")
    normalize.add_argument("limit", nargs="?", type=int)

    enrich = subparsers.add_parser("enrich")
    enrich.add_argument("--channel", dest="channel_filter")
    enrich.add_argument("--force", action="store_true")

    load = subparsers.add_parser("load")
    load.add_argument("--from-enriched", action="store_true", dest="from_enriched")

    run = subparsers.add_parser("run")
    run.add_argument("limit", nargs="?", type=int)

    rebuild = subparsers.add_parser("rebuild")
    rebuild.add_argument("--from-enriched", action="store_true", dest="from_enriched")

    rebuild_embedding = subparsers.add_parser("rebuild-embedding")
    rebuild_embedding.add_argument("--from-enriched", action="store_true", dest="from_enriched")

    query = subparsers.add_parser("query")
    query.add_argument("query_args", nargs="*")

    search = subparsers.add_parser("search")
    search.add_argument("query", nargs="*")
    search.add_argument("--mode", default="recall")

    baseline = subparsers.add_parser("baseline")
    baseline_sub = baseline.add_subparsers(dest="subcommand")
    baseline_probe = baseline_sub.add_parser("probe")
    baseline_probe.add_argument("limit", nargs="?", type=int, default=3)

    wiki = subparsers.add_parser("wiki")
    wiki_sub = wiki.add_subparsers(dest="subcommand")
    wiki_sub.add_parser("init")
    wiki_build = wiki_sub.add_parser("build")
    wiki_build.add_argument("--claims-only", action="store_true")
    wiki_build.add_argument("--entities-topics", action="store_true")
    wiki_sub.add_parser("health")
    wiki_sub.add_parser("update")

    experiments = subparsers.add_parser("experiments")
    experiments_sub = experiments.add_subparsers(dest="subcommand")
    experiments_sub.add_parser("index")

    fts = subparsers.add_parser("fts")
    fts_sub = fts.add_subparsers(dest="subcommand")
    fts_sub.add_parser("rebuild")
    fts_search = fts_sub.add_parser("search")
    fts_search.add_argument("query", nargs="*")
    fts_search.add_argument("--top-k", type=int, default=10)
    fts_search.add_argument("--compare-shadow", action="store_true")

    registry = subparsers.add_parser("registry")
    registry_sub = registry.add_subparsers(dest="subcommand")
    registry_sub.add_parser("rebuild")
    registry_resolve = registry_sub.add_parser("resolve")
    registry_resolve.add_argument("source_id", nargs="*")

    transcribe = subparsers.add_parser("transcribe")
    transcribe_sub = transcribe.add_subparsers(dest="subcommand")
    backfill = transcribe_sub.add_parser("backfill")
    backfill.add_argument("--limit", type=int, default=3)
    backfill.add_argument("--channel")
    backfill.add_argument("--media-type", choices=("video", "audio", "voice"))
    backfill.add_argument("--dry-run", action="store_true")

    validate = subparsers.add_parser("validate")
    validate_sub = validate.add_subparsers(dest="subcommand")
    validate_enriched = validate_sub.add_parser("enriched")
    validate_enriched.add_argument("--fail-on-error", action="store_true")

    subparsers.add_parser("quality")

    review = subparsers.add_parser("review")
    review.add_argument("--web", action="store_true")

    subparsers.add_parser("status")
    return parser


def _parse_query_tail(query_args: list[str]) -> tuple[str, str, str | None] | None:
    mode = _default_query_mode()
    query_profile = None
    args = list(query_args)
    if args and args[-1].lower() in _QUERY_PROFILES:
        query_profile = args[-1].lower()
        args = args[:-1]
    if args and args[-1].lower() in _QUERY_MODES:
        mode = args[-1].lower()
        args = args[:-1]
    question = " ".join(args).strip()
    if not question:
        return None
    return question, mode, query_profile


def dispatch(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    command = args.command
    if not command:
        parser.print_help()
        return

    if command == "baseline":
        if args.subcommand == "probe":
            asyncio.run(cmd_baseline_probe(limit=args.limit))
            return
        print("Usage: python main.py baseline probe [N]")
        return

    if command == "wiki":
        if args.subcommand == "init":
            _print_wiki_init_summary(cmd_wiki_init())
            return
        if args.subcommand == "build" and args.claims_only:
            cmd_wiki_build_claims()
            return
        if args.subcommand == "build" and args.entities_topics:
            cmd_wiki_build_entities_topics()
            return
        if args.subcommand == "build":
            print("Usage: python main.py wiki build --claims-only | python main.py wiki build --entities-topics")
            return
        if args.subcommand == "health":
            cmd_wiki_health()
            return
        if args.subcommand == "update":
            cmd_wiki_update()
            return
        print(
            "Usage: python main.py wiki init | python main.py wiki build --claims-only | "
            "python main.py wiki build --entities-topics | python main.py wiki health | "
            "python main.py wiki update"
        )
        return

    if command == "experiments":
        if args.subcommand == "index":
            cmd_experiments_index()
            return
        print("Usage: python main.py experiments index")
        return

    setup_logging()

    if command == "fetch":
        asyncio.run(cmd_fetch(args.limit))
        return

    if command == "normalize":
        async def _fetch_and_normalize():
            channel_messages = await cmd_fetch(limit=args.limit)
            total = sum(len(msgs) for _, msgs in channel_messages)
            if total == 0:
                print("No new messages found.")
                return
            normalize_stats = await cmd_normalize(channel_messages)
            print(f"\nDone: {normalize_stats.normalized_messages} texts normalized to output/normalized/")
            _print_run_summary(channel_messages, normalize_stats, LoadStats())
            print("Run 'python main.py load' when ready to load into LightRAG.")
            _maybe_launch_reviewer()

        asyncio.run(_fetch_and_normalize())
        return

    if command == "load":
        if args.from_enriched:
            _print_enriched_graph_load_unsupported()
            return
        load_stats = asyncio.run(cmd_load())
        _print_load_summary(load_stats)
        return

    if command == "rebuild":
        if args.from_enriched:
            _print_enriched_graph_load_unsupported()
            return
        asyncio.run(cmd_rebuild())
        return

    if command == "rebuild-embedding":
        if args.from_enriched:
            _print_enriched_graph_load_unsupported()
            return
        asyncio.run(cmd_rebuild_embedding())
        return

    if command == "enrich":
        cmd_enrich(channel_filter=args.channel_filter, force=args.force)
        return

    if command == "run":
        asyncio.run(cmd_run(args.limit))
        _maybe_launch_reviewer()
        return

    if command == "query":
        parsed = _parse_query_tail(args.query_args)
        if parsed is None:
            print('Usage: python main.py query "??? ??????" [mode] [profile]')
            return
        question, mode, query_profile = parsed
        asyncio.run(cmd_query(question, mode, query_profile))
        return

    if command == "search":
        query = " ".join(args.query).strip()
        if not query:
            print('Usage: python main.py search "query" [--mode recall|broll|thesis|entity|shadow]')
            return
        asyncio.run(cmd_search(query, args.mode))
        return

    if command == "fts":
        if args.subcommand == "rebuild":
            cmd_fts_rebuild()
            return
        if args.subcommand == "search":
            query = " ".join(args.query).strip()
            if not query:
                print('Usage: python main.py fts search "query" [--top-k N] [--compare-shadow]')
                return
            cmd_fts_search(query, top_k=args.top_k, compare_shadow=args.compare_shadow)
            return
        print('Usage: python main.py fts rebuild | python main.py fts search "query" [--top-k N] [--compare-shadow]')
        return

    if command == "registry":
        if args.subcommand == "rebuild":
            cmd_registry_rebuild()
            return
        if args.subcommand == "resolve":
            source_id = " ".join(args.source_id).strip()
            if not source_id:
                print("Usage: python main.py registry resolve SOURCE_ID")
                return
            cmd_registry_resolve(source_id)
            return
        print("Usage: python main.py registry rebuild | python main.py registry resolve SOURCE_ID")
        return

    if command == "transcribe":
        if args.subcommand == "backfill":
            cmd_transcribe_backfill(
                limit=args.limit,
                channel=args.channel,
                media_type=args.media_type,
                dry_run=args.dry_run,
            )
            return
        print(
            "Usage: python main.py transcribe backfill "
            "[--limit N] [--channel NAME] [--media-type video|audio|voice] [--dry-run]"
        )
        return

    if command == "validate":
        if args.subcommand == "enriched":
            cmd_validate_enriched(fail_on_error=args.fail_on_error)
            return
        print("Usage: python main.py validate enriched [--fail-on-error]")
        return

    if command == "quality":
        cmd_quality()
        return

    if command == "review":
        cmd_review(web=args.web)
        return

    if command == "status":
        cmd_status()
        return

    print(f"Unknown command: {command}")
    parser.print_help()


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    dispatch(args, parser)
