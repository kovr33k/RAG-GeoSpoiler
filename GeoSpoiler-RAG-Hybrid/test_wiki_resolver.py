import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

from retrieval import composer, wiki_index  # noqa: E402
from retrieval.response_formatter import format_search_results  # noqa: E402
from retrieval.source_registry import rebuild_source_registry  # noqa: E402
from retrieval.wiki_resolver import resolve_wiki_references  # noqa: E402


class WikiReferenceResolverTests(unittest.TestCase):
    def test_wiki_references_resolve_to_original_sources(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir = _write_wiki(root / "wiki")
            enriched_dir = root / "enriched"
            enriched_dir.mkdir()
            _write_card(enriched_dir / "10.enriched.json")
            index_result = wiki_index.build_wiki_indexes(
                wiki_dir=wiki_dir,
                enriched_dir=enriched_dir,
                index_dir=wiki_dir / "indexes",
            )

            resolved = resolve_wiki_references(
                ["claims/trump-supported-orban.md"],
                wiki_dir=wiki_dir,
                index_dir=index_result.page_to_sources_path.parent,
                enriched_dir=enriched_dir,
            )

        source = resolved["claims/trump-supported-orban.md"][0]
        self.assertEqual(source.source_id, "telegram:1:10")
        self.assertEqual(source.post_url, "https://t.me/c/1/10")
        self.assertEqual(source.normalized_file, "output/normalized/test/10.txt")

    def test_wiki_references_resolve_via_registry_before_enriched_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir = _write_wiki(root / "wiki")
            normalized_dir = root / "normalized" / "test"
            enriched_dir = root / "enriched"
            normalized_dir.mkdir(parents=True)
            enriched_dir.mkdir()
            _write_normalized_meta(normalized_dir)
            _write_card(enriched_dir / "10.enriched.json")
            index_result = wiki_index.build_wiki_indexes(
                wiki_dir=wiki_dir,
                enriched_dir=enriched_dir,
                index_dir=wiki_dir / "indexes",
            )
            registry_db_path = root / "source_registry.sqlite"
            rebuild_source_registry(
                normalized_dir=root / "normalized",
                enriched_dir=enriched_dir,
                db_path=registry_db_path,
            )

            resolved = resolve_wiki_references(
                ["claims/trump-supported-orban.md"],
                wiki_dir=wiki_dir,
                index_dir=index_result.page_to_sources_path.parent,
                enriched_dir=root / "missing-enriched",
                registry_db_path=registry_db_path,
            )

        source = resolved["claims/trump-supported-orban.md"][0]
        self.assertEqual(source.source_id, "telegram:1:10")
        self.assertEqual(source.post_url, "https://t.me/c/1/10")
        self.assertEqual(source.normalized_file, "output/normalized/test/10.txt")
        self.assertIn("10.enriched.json", source.card_path)

    def test_wiki_search_output_shows_resolved_primary_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir = _write_wiki(root / "wiki")
            enriched_dir = root / "enriched"
            enriched_dir.mkdir()
            _write_card(enriched_dir / "10.enriched.json")
            wiki_index.build_wiki_indexes(
                wiki_dir=wiki_dir,
                enriched_dir=enriched_dir,
                index_dir=wiki_dir / "indexes",
            )

            with patch.multiple(
                composer.config,
                WIKI_ENABLED=True,
                WIKI_DIR=wiki_dir,
                WIKI_INDEX_DIR=wiki_dir / "indexes",
                ENRICHED_DIR=enriched_dir,
                WIKI_TOP_K=5,
            ):
                with patch.object(composer, "_load_all_cards", return_value=[]):
                    with patch.object(composer.shadow_search, "search", return_value=[]):
                        package = asyncio.run(composer.search(None, "Trump Orban support", mode="shadow"))
            rendered = format_search_results(package)

        self.assertIn("https://t.me/c/1/10", rendered)
        self.assertIn("normalized_file: output/normalized/test/10.txt", rendered)
        self.assertIn("Local wiki pages are memory/context, not primary sources", rendered)
        self.assertIn("**Memory page:** claims/trump-supported-orban.md", rendered)
        self.assertIn("**Primary Telegram/YouTube sources:**", rendered)
        self.assertIn("Telegram: https://t.me/c/1/10", rendered)


def _write_wiki(wiki_dir: Path) -> Path:
    (wiki_dir / "claims").mkdir(parents=True)
    (wiki_dir / "claims" / "trump-supported-orban.md").write_text(
        "# Trump supported Orban\n\n"
        "## Evidence\n\n"
        "- telegram:1:10 - source_claim: Trump supported Orban.\n",
        encoding="utf-8",
    )
    return wiki_dir


def _write_card(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "triage": "keep",
                "provenance": {
                    "channel_id": 1,
                    "message_id": 10,
                    "channel_name": "Test",
                    "date": "2026-05-27T00:00:00+00:00",
                    "post_url": "https://t.me/c/1/10",
                    "normalized_file": "output/normalized/test/10.txt",
                },
                "key_facts": [
                    {
                        "text": "Trump supported Orban.",
                        "claim_type": "source_claim",
                    }
                ],
                "source_chain": {"youtube_url": None},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _write_normalized_meta(directory: Path) -> None:
    (directory / "10.txt").write_text("Trump supported Orban.", encoding="utf-8")
    (directory / "10.meta.json").write_text(
        json.dumps(
            {
                "channel_id": 1,
                "message_id": 10,
                "channel_name": "Test",
                "date": "2026-05-27T00:00:00+00:00",
                "post_url": "https://t.me/c/1/10",
                "has_text": True,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
