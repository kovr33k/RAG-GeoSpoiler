import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent))

from retrieval import composer  # noqa: E402
from retrieval.response_formatter import format_search_results  # noqa: E402


class ComposerWikiContextTests(unittest.TestCase):
    def test_shadow_search_attaches_wiki_context_without_lightrag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = _write_wiki_pages(Path(tmpdir) / "wiki")
            with _patched_wiki(wiki_dir):
                with patch.object(composer, "_load_all_cards", return_value=[]):
                    with patch.object(composer.shadow_search, "search", return_value=[]):
                        package = asyncio.run(composer.search(None, "Trump Orban support", mode="shadow"))

        self.assertEqual(package.llm_answer, "Cards-only search: LightRAG/LLM query was not run.")
        self.assertEqual(package.wiki_results[0].page_path, "claims/trump-supported-orban.md")
        self.assertTrue(package.wiki_results[0].page_path.startswith("claims/"))

    def test_recall_search_keeps_lightrag_to_one_call_and_adds_wiki_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = _write_wiki_pages(Path(tmpdir) / "wiki")
            query_mock = AsyncMock(return_value={"response": "Graph answer."})
            with _patched_wiki(wiki_dir):
                with patch.object(composer.config, "RERANKER_ENABLED", False):
                    with patch.object(composer, "_load_all_cards", return_value=[]):
                        with patch.object(composer.shadow_search, "search", return_value=[]):
                            with patch.object(composer, "query_rag_result", query_mock):
                                package = asyncio.run(composer.search(object(), "Trump Orban support", mode="recall"))

        query_mock.assert_awaited_once()
        self.assertEqual(package.llm_answer, "Graph answer.")
        self.assertEqual(package.wiki_results[0].page_path, "claims/trump-supported-orban.md")

    def test_formatter_exposes_wiki_context_block(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = _write_wiki_pages(Path(tmpdir) / "wiki")
            with _patched_wiki(wiki_dir):
                with patch.object(composer, "_load_all_cards", return_value=[]):
                    with patch.object(composer.shadow_search, "search", return_value=[]):
                        package = asyncio.run(composer.search(None, "Trump Orban support", mode="shadow"))

        rendered = format_search_results(package)

        self.assertIn("## Wiki Memory Context", rendered)
        self.assertIn("not primary sources", rendered)
        self.assertIn("claims/trump-supported-orban.md", rendered)
        self.assertLess(
            rendered.index("claims/trump-supported-orban.md"),
            rendered.index("topics/trump-orban-support.md"),
        )


def _patched_wiki(wiki_dir: Path):
    return patch.multiple(
        composer.config,
        WIKI_ENABLED=True,
        WIKI_DIR=wiki_dir,
        WIKI_INDEX_DIR=wiki_dir / "indexes",
        ENRICHED_DIR=wiki_dir.parent / "enriched",
        CARD_FTS_DB_PATH=wiki_dir.parent / "missing_card_fts.sqlite",
        WIKI_TOP_K=5,
    )


def _write_wiki_pages(wiki_dir: Path) -> Path:
    (wiki_dir / "claims").mkdir(parents=True)
    (wiki_dir / "topics").mkdir()
    (wiki_dir / "entities").mkdir()
    (wiki_dir / "claims" / "trump-supported-orban.md").write_text(
        "# Trump supported Orban\n\nEvidence:\n- telegram:1:1 - source_claim: Trump supported Orban.\n",
        encoding="utf-8",
    )
    (wiki_dir / "topics" / "trump-orban-support.md").write_text(
        "# Trump Orban Support\n\nSupport topic with Trump and Orban context.\n",
        encoding="utf-8",
    )
    (wiki_dir / "entities" / "viktor-orban.md").write_text(
        "# Viktor Orban\n\nEntity page related to Trump support.\n",
        encoding="utf-8",
    )
    return wiki_dir


if __name__ == "__main__":
    unittest.main()
