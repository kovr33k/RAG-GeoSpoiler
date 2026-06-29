import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from retrieval.wiki_index import PAGE_INDEX_FILENAME, build_wiki_indexes  # noqa: E402
from retrieval.wiki_localize import localize_wiki_pages  # noqa: E402


class WikiLocalizeTests(unittest.TestCase):
    def test_localize_renames_english_claim_paths_and_updates_hub_links(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir = root / "wiki"
            enriched_dir = root / "enriched"
            index_dir = wiki_dir / "indexes"
            for directory in [wiki_dir / "claims", wiki_dir / "topics", index_dir, enriched_dir]:
                directory.mkdir(parents=True, exist_ok=True)

            claim_path = wiki_dir / "claims" / "china-drone-components.md"
            claim_path.write_text(
                "---\n"
                "wiki_type: claim\n"
                "status: supported_by_corpus\n"
                "generated_by: wiki_ingest_v1\n"
                "review_status: auto\n"
                "source_count: 1\n"
                "updated_at: 2026-06-29\n"
                "---\n\n"
                "# Китай поставляет компоненты для дронов\n\n"
                "Status: supported_by_corpus\n"
                "Review status: auto\n"
                "Source count: 1\n\n"
                "## Evidence\n\n"
                "- telegram:1:10 - source_claim: Китай поставляет компоненты для дронов.\n"
                f"  - card_path: {enriched_dir / '10.enriched.json'}\n\n"
                "## Guardrails\n\n"
                "- Use only cited evidence items when answering from this page.\n",
                encoding="utf-8",
            )
            (wiki_dir / "topics" / "дроны.md").write_text(
                "---\n"
                "wiki_type: topic\n"
                "generated_by: wiki_coverage_backfill_v1\n"
                "review_status: auto\n"
                "coverage_count: 3\n"
                "related_claim_count: 1\n"
                "updated_at: 2026-06-29\n"
                "---\n\n"
                "# дроны\n\n"
                "This topic page is a coverage hub generated from enriched-card mentions.\n\n"
                "## Related Claims\n\n"
                "- claims/china-drone-components.md\n\n"
                "## Source Resolution\n\n"
                "- Resolve primary sources through claim evidence and output/wiki/indexes/page_to_sources.json.\n"
                "- This page does not add direct evidence beyond its related claim pages.\n",
                encoding="utf-8",
            )
            build_wiki_indexes(wiki_dir=wiki_dir, enriched_dir=enriched_dir, index_dir=index_dir)

            stats = localize_wiki_pages(wiki_dir=wiki_dir, enriched_dir=enriched_dir, index_dir=index_dir)

            new_claim_path = wiki_dir / "claims" / "китай-поставляет-компоненты-для-дронов.md"
            new_claim_exists = new_claim_path.exists()
            old_claim_exists = claim_path.exists()
            topic_text = (wiki_dir / "topics" / "дроны.md").read_text(encoding="utf-8")
            claim_text = new_claim_path.read_text(encoding="utf-8")
            page_to_sources = json.loads((index_dir / PAGE_INDEX_FILENAME).read_text(encoding="utf-8"))

        self.assertEqual(stats.claims_renamed, 1)
        self.assertTrue(new_claim_exists)
        self.assertFalse(old_claim_exists)
        self.assertIn("- claims/китай-поставляет-компоненты-для-дронов.md", topic_text)
        self.assertNotIn("claims/china-drone-components.md", topic_text)
        self.assertIn("## Связанные утверждения", topic_text)
        self.assertIn("## Как найти источники", topic_text)
        self.assertIn("## Доказательства", claim_text)
        self.assertIn("Статус:", claim_text)
        self.assertEqual(
            page_to_sources["claims/китай-поставляет-компоненты-для-дронов.md"],
            ["telegram:1:10"],
        )


if __name__ == "__main__":
    unittest.main()
