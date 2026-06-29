import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from retrieval.wiki_overview import build_wiki_overview, format_wiki_overview, write_wiki_overview  # noqa: E402


class WikiOverviewTests(unittest.TestCase):
    def test_wiki_overview_reports_counts_pending_and_enriched_coverage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir = root / "wiki"
            enriched_dir = root / "enriched"
            (wiki_dir / "claims").mkdir(parents=True)
            (wiki_dir / "entities").mkdir()
            (wiki_dir / "topics").mkdir()
            (enriched_dir / "Cuba").mkdir(parents=True)
            (wiki_dir / "claims" / "cuba-protests.md").write_text(
                "---\n"
                "wiki_type: claim\n"
                "status: supported_by_corpus\n"
                "generated_by: wiki_ingest_v1\n"
                "review_status: auto\n"
                "source_count: 1\n"
                "updated_at: 2026-06-26\n"
                "---\n\n"
                "# Cuba protests\n\n"
                "## Evidence\n\n"
                "- telegram:1:10 - source_claim: Evidence.\n",
                encoding="utf-8",
            )
            (wiki_dir / "entities" / "cuba.md").write_text("# Cuba\n", encoding="utf-8")
            (wiki_dir / "_pending_updates.json").write_text(
                json.dumps([{"source_id": "telegram:1:11", "reason": "failed_llm"}]),
                encoding="utf-8",
            )
            for message_id in [10, 11, 12]:
                _write_card(enriched_dir / "Cuba" / f"{message_id}.enriched.json", "Russia", "sanctions")

            overview = build_wiki_overview(
                wiki_dir=wiki_dir,
                enriched_dir=enriched_dir,
                today=date(2026, 6, 26),
            )
            text = format_wiki_overview(overview)
            output_path = write_wiki_overview(overview)
            output_exists = output_path.exists()

        self.assertEqual(overview.claim_count, 1)
        self.assertEqual(overview.entity_count, 1)
        self.assertEqual(overview.topic_count, 0)
        self.assertEqual(overview.pending_count, 1)
        self.assertIn("Claims: 1", text)
        self.assertIn("supported_by_corpus: 1", text)
        self.assertIn("Pending Sources", text)
        self.assertIn("Important entities in enriched cards without wiki page", text)
        self.assertIn("Россия: 3", text)
        self.assertTrue(output_exists)

    def test_wiki_overview_does_not_report_existing_entity_hub_as_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir = root / "wiki"
            enriched_dir = root / "enriched"
            (wiki_dir / "entities").mkdir(parents=True)
            (wiki_dir / "topics").mkdir()
            enriched_dir.mkdir(parents=True)
            for message_id in [10, 11, 12]:
                _write_card(enriched_dir / f"{message_id}.enriched.json", "Китай", "геополитика")
            (wiki_dir / "entities" / "китай.md").write_text(
                "# Китай\n\n## Related Claims\n\n- none\n",
                encoding="utf-8",
            )

            overview = build_wiki_overview(wiki_dir=wiki_dir, enriched_dir=enriched_dir)

        self.assertNotIn(("Китай", 3), overview.missing_entities)


def _write_card(path: Path, entity: str, topic: str) -> None:
    path.write_text(
        json.dumps(
            {
                "triage": "keep",
                "provenance": {"channel_id": 1, "message_id": path.stem.split(".")[0]},
                "summary": "Card",
                "entities": {"countries": [entity]},
                "topics": [topic],
                "key_facts": [{"text": "Fact", "claim_type": "source_claim"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
