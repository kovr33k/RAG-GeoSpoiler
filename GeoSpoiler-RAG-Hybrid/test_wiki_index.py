import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from retrieval import wiki_index  # noqa: E402


class WikiIndexTests(unittest.TestCase):
    def test_wiki_index_builds_source_id_from_telegram_provenance(self):
        card = {
            "provenance": {
                "channel_id": 3328128766,
                "channel_name": "Hungary",
                "message_id": 148,
            }
        }

        self.assertEqual(
            wiki_index.extract_source_id(card),
            "telegram:3328128766:148",
        )

    def test_wiki_index_builds_source_id_from_channel_name_fallback(self):
        card = {
            "provenance": {
                "channel_name": "Hungary Notes",
                "message_id": 148,
            }
        }

        self.assertEqual(
            wiki_index.extract_source_id(card),
            "telegram:Hungary Notes:148",
        )

    def test_wiki_index_computes_stable_content_hash(self):
        card_a = {
            "summary": "Donald Trump supported Viktor Orban.",
            "topics": ["trump-orban-support"],
            "provenance": {"message_id": 148, "channel_id": 3328128766},
            "enriched_at": "2026-05-21T00:00:00Z",
        }
        card_b = {
            "enriched_at": "2026-05-22T00:00:00Z",
            "provenance": {"channel_id": 3328128766, "message_id": 148},
            "topics": ["trump-orban-support"],
            "summary": "Donald Trump supported Viktor Orban.",
        }

        self.assertEqual(
            wiki_index.compute_content_hash(card_a),
            wiki_index.compute_content_hash(card_b),
        )

    def test_wiki_index_handles_incomplete_provenance(self):
        card = {"provenance": {"channel_name": "Hungary"}}

        self.assertIsNone(wiki_index.extract_source_id(card))
        source = wiki_index.get_enriched_source(Path("card.enriched.json"), card)
        self.assertIsNone(source.source_id)
        self.assertTrue(source.content_hash)

    def test_wiki_index_builds_json_indexes_from_pages(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            claims_dir = wiki_dir / "claims"
            topics_dir = wiki_dir / "topics"
            claims_dir.mkdir(parents=True)
            topics_dir.mkdir()
            (claims_dir / "trump-supported-orban.md").write_text(
                "# Trump supported Orban\n\nEvidence:\n- telegram:3328128766:148\n",
                encoding="utf-8",
            )
            (topics_dir / "trump-orban-support.md").write_text(
                "# Trump Orban support\n\nRelated source: telegram:3328128766:148\n",
                encoding="utf-8",
            )

            result = wiki_index.build_wiki_indexes(
                wiki_dir=wiki_dir,
                enriched_dir=Path(tmpdir) / "missing-enriched",
            )

            page_to_sources = json.loads(result.page_to_sources_path.read_text(encoding="utf-8"))
            source_to_pages = json.loads(result.source_to_pages_path.read_text(encoding="utf-8"))
            claim_to_sources = json.loads(result.claim_to_sources_path.read_text(encoding="utf-8"))

        self.assertEqual(page_to_sources["claims/trump-supported-orban.md"], ["telegram:3328128766:148"])
        self.assertEqual(
            source_to_pages["telegram:3328128766:148"],
            ["claims/trump-supported-orban.md", "topics/trump-orban-support.md"],
        )
        self.assertEqual(claim_to_sources, {"claims/trump-supported-orban.md": ["telegram:3328128766:148"]})

    def test_wiki_search_returns_ranked_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            (wiki_dir / "claims").mkdir(parents=True)
            (wiki_dir / "topics").mkdir()
            (wiki_dir / "claims" / "trump-supported-orban.md").write_text(
                "# Trump supported Orban\n\nEvidence: telegram:3328128766:148\n",
                encoding="utf-8",
            )
            (wiki_dir / "topics" / "trump-orban-support.md").write_text(
                "# Trump Orban support\n\nGeneral context about support.\n",
                encoding="utf-8",
            )

            results = wiki_index.find_wiki_context("Trump Orban support", wiki_dir=wiki_dir, top_k=2)

        self.assertEqual(results[0].page_path, "claims/trump-supported-orban.md")
        self.assertGreaterEqual(results[0].score, results[1].score)

    def test_wiki_search_expands_russian_query_aliases(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            (wiki_dir / "claims").mkdir(parents=True)
            (wiki_dir / "claims" / "trump-supported-orban.md").write_text(
                "# Trump supported Orban\n\nEvidence: telegram:3328128766:148\n",
                encoding="utf-8",
            )

            results = wiki_index.find_wiki_context(
                "Трамп реально поддерживал Орбана?",
                wiki_dir=wiki_dir,
                top_k=1,
            )

        self.assertEqual(results[0].page_path, "claims/trump-supported-orban.md")


if __name__ == "__main__":
    unittest.main()
