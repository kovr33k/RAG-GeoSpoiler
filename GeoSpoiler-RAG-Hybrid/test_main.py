import io
import json
import sys
import tempfile
import unittest
import asyncio as py_asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent))

import main  # noqa: E402


class _FakeRag:
    def __init__(self):
        self.finalized = False

    async def finalize_storages(self):
        self.finalized = True


class MainQueryTests(unittest.IsolatedAsyncioTestCase):
    async def test_cmd_query_exits_nonzero_when_rag_returns_no_answer(self):
        rag = _FakeRag()
        output = io.StringIO()

        with patch.object(main, "create_rag", AsyncMock(return_value=rag)):
            with patch.object(main, "query_rag_result", AsyncMock(return_value={"llm_response": {"content": None}})):
                with patch("sys.stdout", output):
                    with self.assertRaises(SystemExit) as ctx:
                        await main.cmd_query("test question")

        self.assertEqual(ctx.exception.code, 1)
        self.assertTrue(rag.finalized)
        self.assertIn("Query failed: LightRAG returned no answer.", output.getvalue())

    async def test_cmd_query_prints_sources_only_when_requested(self):
        rag = _FakeRag()
        output = io.StringIO()
        result = {
            "llm_response": {"content": "Answer body"},
            "data": {
                "references": [
                    {"reference_id": "ref-1", "file_path": str(Path("D:/topic/1.txt").resolve(strict=False))}
                ]
            },
        }
        source_index = {
            str(Path("D:/topic/1.txt").resolve(strict=False)): {
                "post_url": "https://t.me/example/1",
                "channel_name": "Topic",
                "date": "2026-04-30 12:00",
            }
        }

        with patch.object(main, "create_rag", AsyncMock(return_value=rag)):
            with patch.object(main, "query_rag_result", AsyncMock(return_value=result)):
                with patch.object(main, "load_source_metadata_index", return_value=source_index):
                    with patch("sys.stdout", output):
                        await main.cmd_query("Откуда эта информация? Дай ссылку")

        text = output.getvalue()
        self.assertTrue(rag.finalized)
        self.assertIn("Answer body", text)
        self.assertIn("Источники:", text)
        self.assertIn("https://t.me/example/1", text)

    async def test_cmd_query_skips_sources_when_not_requested(self):
        rag = _FakeRag()
        output = io.StringIO()
        result = {
            "llm_response": {"content": "Answer body"},
            "data": {"references": [{"reference_id": "ref-1", "file_path": "D:/topic/1.txt"}]},
        }

        with patch.object(main, "create_rag", AsyncMock(return_value=rag)):
            with patch.object(main, "query_rag_result", AsyncMock(return_value=result)):
                with patch("sys.stdout", output):
                    await main.cmd_query("Что в базе говорится про AfD?")

        text = output.getvalue()
        self.assertTrue(rag.finalized)
        self.assertIn("Answer body", text)
        self.assertNotIn("Источники:", text)

    def test_extract_query_sources_prefers_cited_references(self):
        result = {
            "llm_response": {"content": "Answer\n\n### References\n- [2] Some cited chunk"},
            "data": {
                "references": [
                    {"reference_id": "ref-a", "file_path": str(Path("D:/topic/1.txt").resolve(strict=False))},
                    {"reference_id": "ref-b", "file_path": str(Path("D:/topic/2.txt").resolve(strict=False))},
                ]
            },
        }
        source_index = {
            str(Path("D:/topic/1.txt").resolve(strict=False)): {"post_url": "https://t.me/example/1"},
            str(Path("D:/topic/2.txt").resolve(strict=False)): {"post_url": "https://t.me/example/2"},
        }

        with patch.object(main, "load_source_metadata_index", return_value=source_index):
            sources = main._extract_query_sources(result)

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["post_url"], "https://t.me/example/2")

    def test_extract_query_sources_uses_direct_reference_metadata(self):
        result = {
            "llm_response": {"content": "Answer\n\n### References\n- [1] Wiki source"},
            "data": {
                "references": [
                    {
                        "reference_id": "wiki-1-1",
                        "file_path": "output/normalized/test/10.txt",
                        "post_url": "https://t.me/c/1/10",
                        "channel": "Test",
                        "date": "2026-05-27T00:00:00+00:00",
                    }
                ]
            },
        }

        with patch.object(main, "load_source_metadata_index", return_value={}):
            sources = main._extract_query_sources(result)

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["post_url"], "https://t.me/c/1/10")
        self.assertEqual(sources[0]["channel"], "Test")

    def test_extract_query_sources_reads_adjacent_meta_when_index_is_stale(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "topic" / "148.txt"
            source_path.parent.mkdir(parents=True, exist_ok=True)
            source_path.write_text("Body", encoding="utf-8")
            source_path.with_suffix(".meta.json").write_text(
                json.dumps(
                    {
                        "post_url": "https://t.me/c/3328128766/148",
                        "channel_name": "Hungary",
                        "date": "2026-04-10T16:41:09+00:00",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            result = {
                "llm_response": {"content": "Answer\n\n### References\n- [1] Source"},
                "data": {"references": [{"reference_id": "card-1", "file_path": str(source_path)}]},
            }

            with patch.object(main, "load_source_metadata_index", return_value={}):
                sources = main._extract_query_sources(result)

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["post_url"], "https://t.me/c/3328128766/148")
        self.assertEqual(sources[0]["channel"], "Hungary")

    def test_main_query_cli_joins_full_question_and_mode(self):
        captured = {}
        original_run = py_asyncio.run

        async def fake_cmd_query(question, mode, query_profile=None):
            captured["question"] = question
            captured["mode"] = mode
            captured["query_profile"] = query_profile

        def fake_run(coro):
            original_run(coro)

        with patch.object(main, "setup_logging"):
            with patch.object(main, "cmd_query", fake_cmd_query):
                with patch.object(main.asyncio, "run", side_effect=fake_run):
                    with patch.object(
                        sys,
                        "argv",
                        ["main.py", "query", "Откуда", "в", "базе", "тезис", "hybrid"],
                    ):
                        main.main()

        self.assertEqual(captured.get("question"), "Откуда в базе тезис")
        self.assertEqual(captured.get("mode"), "hybrid")
        self.assertIsNone(captured.get("query_profile"))

    def test_main_query_cli_parses_query_profile(self):
        captured = {}
        original_run = py_asyncio.run

        async def fake_cmd_query(question, mode, query_profile=None):
            captured["question"] = question
            captured["mode"] = mode
            captured["query_profile"] = query_profile

        def fake_run(coro):
            original_run(coro)

        with patch.object(main, "setup_logging"):
            with patch.object(main, "cmd_query", fake_cmd_query):
                with patch.object(main.asyncio, "run", side_effect=fake_run):
                    with patch.object(
                        sys,
                        "argv",
                        ["main.py", "query", "Откуда", "это?", "mix", "source"],
                    ):
                        main.main()

        self.assertEqual(captured.get("question"), "Откуда это?")
        self.assertEqual(captured.get("mode"), "mix")
        self.assertEqual(captured.get("query_profile"), "source")

    def test_main_query_cli_uses_configured_default_when_mode_is_omitted(self):
        captured = {}
        original_run = py_asyncio.run

        async def fake_cmd_query(question, mode, query_profile=None):
            captured["question"] = question
            captured["mode"] = mode
            captured["query_profile"] = query_profile

        def fake_run(coro):
            original_run(coro)

        with patch.object(main, "setup_logging"):
            with patch.object(main, "cmd_query", fake_cmd_query):
                with patch.object(main.asyncio, "run", side_effect=fake_run):
                    with patch.object(
                        sys,
                        "argv",
                        ["main.py", "query", "Ð§Ñ‚Ð¾", "Ð²", "Ð±Ð°Ð·Ðµ", "Ð¿Ñ€Ð¾", "ÐšÑƒÐ±Ñƒ"],
                    ):
                        main.main()

        self.assertEqual(captured.get("question"), "Ð§Ñ‚Ð¾ Ð² Ð±Ð°Ð·Ðµ Ð¿Ñ€Ð¾ ÐšÑƒÐ±Ñƒ")
        self.assertEqual(captured.get("mode"), main._default_query_mode())
        self.assertIsNone(captured.get("query_profile"))

    def test_main_rebuild_cli_defaults_to_normalized_graph(self):
        captured = {}
        original_run = py_asyncio.run

        async def fake_cmd_rebuild(from_enriched=False):
            captured["from_enriched"] = from_enriched

        def fake_run(coro):
            original_run(coro)

        with patch.object(main, "setup_logging"):
            with patch.object(main, "cmd_rebuild", fake_cmd_rebuild):
                with patch.object(main.asyncio, "run", side_effect=fake_run):
                    with patch.object(sys, "argv", ["main.py", "rebuild"]):
                        main.main()

        self.assertFalse(captured.get("from_enriched"))

    def test_main_rebuild_cli_requires_explicit_enriched_flag(self):
        captured = {}
        original_run = py_asyncio.run

        async def fake_cmd_rebuild(from_enriched=False):
            captured["from_enriched"] = from_enriched

        def fake_run(coro):
            original_run(coro)

        with patch.object(main, "setup_logging"):
            with patch.object(main, "cmd_rebuild", fake_cmd_rebuild):
                with patch.object(main.asyncio, "run", side_effect=fake_run):
                    with patch.object(sys, "argv", ["main.py", "rebuild", "--from-enriched"]):
                        main.main()

        self.assertTrue(captured.get("from_enriched"))

    def test_main_load_cli_defaults_to_normalized_graph(self):
        captured = {}
        original_run = py_asyncio.run

        async def fake_cmd_load(texts_with_paths=None, from_enriched=False):
            captured["from_enriched"] = from_enriched
            return main.LoadStats()

        def fake_run(coro):
            return original_run(coro)

        with patch.object(main, "setup_logging"):
            with patch.object(main, "cmd_load", fake_cmd_load):
                with patch.object(main, "_print_load_summary"):
                    with patch.object(main.asyncio, "run", side_effect=fake_run):
                        with patch.object(sys, "argv", ["main.py", "load"]):
                            main.main()

        self.assertFalse(captured.get("from_enriched"))

    def test_main_fts_search_cli_parses_flags(self):
        captured = {}

        def fake_cmd_fts_search(query, top_k=10, compare_shadow=False):
            captured["query"] = query
            captured["top_k"] = top_k
            captured["compare_shadow"] = compare_shadow

        with patch.object(main, "setup_logging"):
            with patch.object(main, "cmd_fts_search", fake_cmd_fts_search):
                with patch.object(
                    sys,
                    "argv",
                    [
                        "main.py",
                        "fts",
                        "search",
                        "Trump",
                        "Orban",
                        "--top-k",
                        "3",
                        "--compare-shadow",
                    ],
                ):
                    main.main()

        self.assertEqual(captured.get("query"), "Trump Orban")
        self.assertEqual(captured.get("top_k"), 3)
        self.assertTrue(captured.get("compare_shadow"))

    def test_main_fts_rebuild_cli_dispatches(self):
        captured = {}

        def fake_cmd_fts_rebuild():
            captured["called"] = True

        with patch.object(main, "setup_logging"):
            with patch.object(main, "cmd_fts_rebuild", fake_cmd_fts_rebuild):
                with patch.object(sys, "argv", ["main.py", "fts", "rebuild"]):
                    main.main()

        self.assertTrue(captured.get("called"))

    def test_main_registry_resolve_cli_passes_source_id(self):
        captured = {}

        def fake_cmd_registry_resolve(source_id):
            captured["source_id"] = source_id

        with patch.object(main, "setup_logging"):
            with patch.object(main, "cmd_registry_resolve", fake_cmd_registry_resolve):
                with patch.object(
                    sys,
                    "argv",
                    ["main.py", "registry", "resolve", "telegram:1:10"],
                ):
                    main.main()

        self.assertEqual(captured.get("source_id"), "telegram:1:10")

    def test_main_registry_rebuild_cli_dispatches(self):
        captured = {}

        def fake_cmd_registry_rebuild():
            captured["called"] = True

        with patch.object(main, "setup_logging"):
            with patch.object(main, "cmd_registry_rebuild", fake_cmd_registry_rebuild):
                with patch.object(sys, "argv", ["main.py", "registry", "rebuild"]):
                    main.main()

        self.assertTrue(captured.get("called"))

    def test_main_transcribe_backfill_cli_parses_flags(self):
        captured = {}

        def fake_cmd_transcribe_backfill(limit=3, channel=None, media_type=None, dry_run=False):
            captured["limit"] = limit
            captured["channel"] = channel
            captured["media_type"] = media_type
            captured["dry_run"] = dry_run

        with patch.object(main, "setup_logging"):
            with patch.object(main, "cmd_transcribe_backfill", fake_cmd_transcribe_backfill):
                with patch.object(
                    sys,
                    "argv",
                    [
                        "main.py",
                        "transcribe",
                        "backfill",
                        "--limit",
                        "2",
                        "--channel",
                        "Channel",
                        "--media-type",
                        "voice",
                        "--dry-run",
                    ],
                ):
                    main.main()

        self.assertEqual(captured.get("limit"), 2)
        self.assertEqual(captured.get("channel"), "Channel")
        self.assertEqual(captured.get("media_type"), "voice")
        self.assertTrue(captured.get("dry_run"))

    def test_main_validate_enriched_cli_parses_fail_flag(self):
        captured = {}

        def fake_cmd_validate_enriched(fail_on_error=False):
            captured["fail_on_error"] = fail_on_error

        with patch.object(main, "setup_logging"):
            with patch.object(main, "cmd_validate_enriched", fake_cmd_validate_enriched):
                with patch.object(sys, "argv", ["main.py", "validate", "enriched", "--fail-on-error"]):
                    main.main()

        self.assertTrue(captured.get("fail_on_error"))

    def test_main_experiments_index_cli_dispatches(self):
        captured = {}

        def fake_cmd_experiments_index():
            captured["called"] = True

        with patch.object(main, "cmd_experiments_index", fake_cmd_experiments_index):
            with patch.object(sys, "argv", ["main.py", "experiments", "index"]):
                main.main()

        self.assertTrue(captured.get("called"))

    def test_cmd_wiki_init_creates_minimal_scaffold(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            with patch.object(main.config, "WIKI_DIR", wiki_dir):
                with patch.object(main.config, "WIKI_INDEX_DIR", wiki_dir / "indexes"):
                    stats = main.cmd_wiki_init()

            self.assertEqual(len(stats.directories_created), 5)
            self.assertEqual(len(stats.files_created), 6)
            for dirname in ["entities", "topics", "claims", "indexes"]:
                self.assertTrue((wiki_dir / dirname).is_dir())
            for filename in [
                "_master_index.md",
                "_schema.md",
                "_health.md",
                "_change_log.md",
                "_log.md",
                "_pending_updates.json",
            ]:
                self.assertTrue((wiki_dir / filename).is_file())

    def test_cmd_wiki_init_does_not_overwrite_existing_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            with patch.object(main.config, "WIKI_DIR", wiki_dir):
                with patch.object(main.config, "WIKI_INDEX_DIR", wiki_dir / "indexes"):
                    main.cmd_wiki_init()
                    schema_path = wiki_dir / "_schema.md"
                    schema_path.write_text("manual edit\n", encoding="utf-8")

                    stats = main.cmd_wiki_init()

            self.assertEqual(stats.files_created, [])
            self.assertEqual(schema_path.read_text(encoding="utf-8"), "manual edit\n")
