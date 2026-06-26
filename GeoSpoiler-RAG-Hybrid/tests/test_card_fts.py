import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from retrieval import card_fts
from retrieval.card_fts import rebuild_card_index, rebuild_wiki_index, search_card_index, search_wiki_index


def _fts5_available() -> bool:
    try:
        with sqlite3.connect(":memory:") as conn:
            conn.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        return True
    except sqlite3.OperationalError:
        return False


@unittest.skipUnless(_fts5_available(), "SQLite FTS5 is not available")
class CardFtsTests(unittest.TestCase):
    def test_rebuild_indexes_keep_cards_and_searches_metadata(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            enriched_dir = root / "enriched" / "Hungary"
            enriched_dir.mkdir(parents=True)
            db_path = root / "card_fts.sqlite"

            self._write_card(
                enriched_dir / "10.enriched.json",
                {
                    "triage": "keep",
                    "provenance": {
                        "channel_name": "Hungary",
                        "channel_id": 1,
                        "message_id": 10,
                        "date": "2026-05-27T00:00:00+00:00",
                        "post_url": "https://t.me/c/1/10",
                        "normalized_file": "output/normalized/Hungary/10.txt",
                    },
                    "search_text": "Trump supported Orban before the Hungarian election.",
                    "entities": {"people": ["Trump", "Viktor Orban"], "countries": ["Hungary"]},
                    "topics": ["elections", "support"],
                    "key_facts": [{"text": "Trump supported Orban.", "claim_type": "source_claim"}],
                },
            )
            self._write_card(
                enriched_dir / "11.enriched.json",
                {
                    "triage": "review",
                    "provenance": {"channel_name": "Hungary", "message_id": 11},
                    "search_text": "This reviewed card should not be indexed.",
                },
            )

            stats = rebuild_card_index(enriched_dir=enriched_dir, db_path=db_path)
            matches = search_card_index("Orban support", top_k=5, db_path=db_path)
            claim_matches = search_card_index("source_claim", top_k=5, db_path=db_path)

            self.assertEqual(stats.cards_seen, 2)
            self.assertEqual(stats.cards_indexed, 1)
            self.assertEqual(stats.cards_skipped, 1)
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0].source_id, "telegram:1:10")
            self.assertEqual(matches[0].post_url, "https://t.me/c/1/10")
            self.assertIn("Orban", matches[0].snippet)
            self.assertEqual(len(claim_matches), 1)

    def test_search_missing_index_or_empty_query_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "missing.sqlite"

            self.assertEqual(search_card_index("Orban", db_path=db_path), [])
            self.assertEqual(search_card_index("и в на", db_path=db_path), [])

    def test_rebuild_wiki_index_keeps_pages_separate_from_cards(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            wiki_dir = root / "wiki"
            db_path = root / "card_fts.sqlite"
            (wiki_dir / "claims").mkdir(parents=True)
            (wiki_dir / "claims" / "trump-supported-orban.md").write_text(
                "---\n"
                "wiki_type: claim\n"
                "status: supported_by_corpus\n"
                "---\n\n"
                "# Trump supported Orban\n\n"
                "## Evidence\n\n"
                "- telegram:1:10 - source_claim: Trump supported Orban.\n",
                encoding="utf-8",
            )

            stats = rebuild_wiki_index(wiki_dir=wiki_dir, db_path=db_path)
            matches = search_wiki_index("Orban support", top_k=5, db_path=db_path)
            card_matches = search_card_index("Orban support", top_k=5, db_path=db_path)

        self.assertEqual(stats.pages_seen, 1)
        self.assertEqual(stats.pages_indexed, 1)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].page_path, "claims/trump-supported-orban.md")
        self.assertEqual(matches[0].page_type, "claim")
        self.assertEqual(card_matches, [])

    def test_rebuild_uses_normalized_text_for_thin_similarity_cards(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            enriched_dir = root / "output" / "enriched" / "Ultra"
            normalized_dir = root / "output" / "normalized" / "Ultra"
            enriched_dir.mkdir(parents=True)
            normalized_dir.mkdir(parents=True)
            db_path = root / "card_fts.sqlite"

            canonical_source = normalized_dir / "11.txt"
            canonical_source.write_text("Ультра-левые и ультра-правые совпадают.", encoding="utf-8")
            broad_source = normalized_dir / "20.txt"
            broad_source.write_text(
                "Урсула фон дер Ляйен вызывает ненависть у ультралевых и ультраправых сил.",
                encoding="utf-8",
            )
            self._write_card(
                enriched_dir / "11.enriched.json",
                {
                    "triage": "keep",
                    "provenance": {
                        "channel_name": "Ultra",
                        "channel_id": 3299898370,
                        "message_id": 11,
                        "post_url": "https://t.me/c/3299898370/11",
                        "normalized_file": str(canonical_source.relative_to(root)),
                    },
                    "summary": "",
                    "key_facts": [],
                    "quotes": [],
                    "theses": [],
                    "events": [],
                    "chunks": [],
                    "search_text": "Источник: Ultra",
                    "graph_text": "Источник: Ultra",
                },
            )
            self._write_card(
                enriched_dir / "20.enriched.json",
                {
                    "triage": "keep",
                    "provenance": {
                        "channel_name": "Ultra",
                        "channel_id": 3299898370,
                        "message_id": 20,
                        "post_url": "https://t.me/c/3299898370/20",
                        "normalized_file": str(broad_source.relative_to(root)),
                    },
                    "summary": "Материал про совпадение идеологии ультраправых групп с джихадистами.",
                    "key_facts": [{"text": "Ультраправые группы совпадают с джихадистами по отдельным установкам."}],
                    "search_text": (
                        "[Канал: Ультра левые и ультра правые]\n\n"
                        "Ультраправые группы совпадают с джихадистами по отдельным установкам."
                    ),
                },
            )

            with patch.object(card_fts.config, "PROJECT_ROOT", root):
                rebuild_card_index(enriched_dir=enriched_dir, db_path=db_path)
                matches = search_card_index(
                    "сходство ультралевых ультраправых",
                    top_k=5,
                    db_path=db_path,
                )

            self.assertGreaterEqual(len(matches), 1)
            self.assertEqual(matches[0].source_id, "telegram:3299898370:11")
            self.assertIn("совпадают", matches[0].snippet)

    def _write_card(self, path: Path, data: dict) -> None:
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
