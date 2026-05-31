import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from retrieval.wiki_index import find_wiki_context  # noqa: E402
from retrieval.wiki_pages import WikiPageSpec, seed_entity_topic_pages  # noqa: E402


class WikiPageSeedTests(unittest.TestCase):
    def test_wiki_entity_topic_seed_updates_master_index(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            (wiki_dir / "claims").mkdir(parents=True)
            (wiki_dir / "_master_index.md").write_text("# Wiki Memory\n\nManual note.\n", encoding="utf-8")
            (wiki_dir / "claims" / "trump-supported-orban-2026.md").write_text(
                "# Trump supported Orban\n\nEvidence: telegram:1:1\n",
                encoding="utf-8",
            )

            specs = (
                WikiPageSpec(
                    page_type="entity",
                    slug="viktor-orban",
                    title="Viktor Orban",
                    summary="Entity page.",
                    claims=("trump-supported-orban-2026",),
                ),
                WikiPageSpec(
                    page_type="topic",
                    slug="trump-orban-support",
                    title="Trump-Orban Support",
                    summary="Topic page.",
                    claims=("trump-supported-orban-2026",),
                ),
            )

            stats = seed_entity_topic_pages(wiki_dir=wiki_dir, specs=specs, today=date(2026, 5, 26))
            master = (wiki_dir / "_master_index.md").read_text(encoding="utf-8")

        self.assertEqual(len(stats.created), 2)
        self.assertIn("Manual note.", master)
        self.assertIn("claims/trump-supported-orban-2026.md", master)
        self.assertIn("entities/viktor-orban.md", master)
        self.assertIn("topics/trump-orban-support.md", master)

    def test_wiki_search_returns_claim_before_topic_entity_for_exact_question(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            (wiki_dir / "claims").mkdir(parents=True)
            (wiki_dir / "entities").mkdir()
            (wiki_dir / "topics").mkdir()
            (wiki_dir / "claims" / "trump-supported-orban-2026.md").write_text(
                "# Trump supported Orban before the 2026 Hungarian election\n\n"
                "Evidence: telegram:1:1\n",
                encoding="utf-8",
            )
            (wiki_dir / "entities" / "viktor-orban.md").write_text(
                "# Viktor Orban\n\nRelated Claims\n- claims/trump-supported-orban-2026.md\n",
                encoding="utf-8",
            )
            (wiki_dir / "topics" / "trump-orban-support.md").write_text(
                "# Trump-Orban Support\n\nRelated Claims\n- claims/trump-supported-orban-2026.md\n",
                encoding="utf-8",
            )

            results = find_wiki_context("Trump Orban support", wiki_dir=wiki_dir, top_k=3)

        self.assertEqual(results[0].page_path, "claims/trump-supported-orban-2026.md")


if __name__ == "__main__":
    unittest.main()
