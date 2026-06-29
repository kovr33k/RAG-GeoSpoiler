import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from retrieval.wiki_health import run_wiki_health, write_health_report  # noqa: E402
from retrieval.wiki_index import build_wiki_indexes  # noqa: E402


class WikiHealthTests(unittest.TestCase):
    def test_wiki_health_flags_claim_without_evidence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            index_dir = wiki_dir / "indexes"
            (wiki_dir / "claims").mkdir(parents=True)
            index_dir.mkdir()
            (wiki_dir / "claims" / "unsupported.md").write_text(
                "---\n"
                "wiki_type: claim\n"
                "status: supported_by_corpus\n"
                "generated_by: test\n"
                "review_status: auto\n"
                "source_count: 0\n"
                "---\n\n"
                "# Unsupported claim\n\n"
                "Status: supported_by_corpus\n",
                encoding="utf-8",
            )

            report = run_wiki_health(wiki_dir=wiki_dir, index_dir=index_dir)

        codes = {issue.code for issue in report.issues}
        self.assertIn("claim_without_evidence", codes)
        self.assertIn("claim_without_sources", codes)
        self.assertIn("supported_claim_without_source_count", codes)

    def test_wiki_health_report_is_written_without_llm(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            index_dir = wiki_dir / "indexes"
            wiki_dir.mkdir()
            index_dir.mkdir()

            report = run_wiki_health(wiki_dir=wiki_dir, index_dir=index_dir)
            report_path = write_health_report(report)
            text = report_path.read_text(encoding="utf-8")

        self.assertIn("# Wiki Health", text)
        self.assertIn("Issues: 0", text)
        self.assertIn("Status: OK", text)

    def test_wiki_health_flags_missing_source_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            missing_card = Path(tmpdir) / "missing.enriched.json"
            (wiki_dir / "claims").mkdir(parents=True)
            (wiki_dir / "claims" / "claim.md").write_text(
                "---\n"
                "wiki_type: claim\n"
                "status: supported_by_corpus\n"
                "generated_by: test\n"
                "review_status: auto\n"
                "source_count: 1\n"
                "---\n\n"
                "# Claim\n\n"
                "Status: supported_by_corpus\n\n"
                "## Evidence\n\n"
                "- telegram:1:10 - source_claim: Direct evidence.\n"
                f"  - card_path: {missing_card}\n",
                encoding="utf-8",
            )
            index_result = build_wiki_indexes(
                wiki_dir=wiki_dir,
                enriched_dir=Path(tmpdir) / "missing-enriched",
            )

            report = run_wiki_health(wiki_dir=wiki_dir, index_dir=index_result.page_to_sources_path.parent)

        codes = {issue.code for issue in report.issues}
        self.assertIn("source_file_missing", codes)

    def test_wiki_health_reports_empty_wiki_and_missing_entity_coverage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir = root / "wiki"
            enriched_dir = root / "enriched" / "Cuba"
            index_dir = wiki_dir / "indexes"
            wiki_dir.mkdir(parents=True)
            enriched_dir.mkdir(parents=True)
            index_dir.mkdir(parents=True)
            for message_id in [10, 11, 12]:
                (enriched_dir / f"{message_id}.enriched.json").write_text(
                    json.dumps(
                        {
                            "triage": "keep",
                            "provenance": {"channel_id": 1, "message_id": message_id},
                            "summary": "Card",
                            "entities": {"countries": ["Russia"]},
                            "topics": ["sanctions"],
                            "key_facts": [{"text": "Fact", "claim_type": "source_claim"}],
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

            report = run_wiki_health(wiki_dir=wiki_dir, index_dir=index_dir, enriched_dir=root / "enriched")

        issues = {issue.code: issue for issue in report.issues}
        self.assertIn("wiki_empty_while_cards_exist", issues)
        self.assertIn("missing_entity_coverage", issues)
        self.assertIn("Россия", issues["missing_entity_coverage"].message)

    def test_wiki_health_ignores_fake_labels_in_related_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            card_path = Path(tmpdir) / "card.enriched.json"
            (wiki_dir / "claims").mkdir(parents=True)
            card_path.write_text("{}", encoding="utf-8")
            (wiki_dir / "claims" / "claim.md").write_text(
                "---\n"
                "wiki_type: claim\n"
                "status: supported_by_corpus\n"
                "generated_by: test\n"
                "review_status: auto\n"
                "source_count: 1\n"
                "---\n\n"
                "# Claim\n\n"
                "Status: supported_by_corpus\n\n"
                "## Evidence\n\n"
                "- telegram:1:10 - source_claim: Direct evidence.\n"
                f"  - card_path: {card_path}\n\n"
                "## Related\n\n"
                "- claims/fake-identities-deepfakes.md\n",
                encoding="utf-8",
            )
            index_result = build_wiki_indexes(wiki_dir=wiki_dir, enriched_dir=Path(tmpdir) / "enriched")

            report = run_wiki_health(wiki_dir=wiki_dir, index_dir=index_result.page_to_sources_path.parent)

        warnings = [
            issue
            for issue in report.issues
            if issue.code == "fake_label_without_direct_evidence" and issue.page_path == "claims/claim.md"
        ]
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
