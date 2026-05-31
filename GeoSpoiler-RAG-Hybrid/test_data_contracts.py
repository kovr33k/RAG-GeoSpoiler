import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data_validation import scan_enriched_cards, validate_enriched_card, write_enriched_validation_report  # noqa: E402
from models import EnrichedCard, NormalizedMeta  # noqa: E402


def _minimal_card(claim_type: str = "source_claim") -> dict:
    return {
        "version": 1,
        "enriched_at": "2026-05-30T00:00:00+00:00",
        "provenance": {
            "channel_name": "Hungary",
            "channel_id": 3328128766,
            "message_id": 148,
            "date": "2026-04-10T16:41:09+00:00",
            "post_url": "https://t.me/c/3328128766/148",
            "normalized_file": "output/normalized/Hungary/148.txt",
            "meta_file": "output/normalized/Hungary/148.meta.json",
        },
        "content_type": "text",
        "triage": "keep",
        "language": "ru",
        "summary": "Donald Trump supported Viktor Orban.",
        "key_facts": [
            {
                "text": "Donald Trump supported Viktor Orban before the 2026 Hungarian election.",
                "claim_type": claim_type,
            }
        ],
        "entities": {"people": ["Donald Trump", "Viktor Orban"]},
        "topics": ["trump-orban-support"],
        "graph_text": "Donald Trump supported Viktor Orban.",
        "search_text": "Donald Trump supported Viktor Orban.",
    }


class DataContractTests(unittest.TestCase):
    def test_enriched_card_contract_derives_source_id(self):
        card = EnrichedCard.model_validate(_minimal_card())

        self.assertEqual(card.source_id.value, "telegram:3328128766:148")
        self.assertEqual(card.key_facts[0].claim_type, "source_claim")

    def test_normalized_meta_contract_derives_source_id(self):
        meta = NormalizedMeta.model_validate(
            {
                "channel_name": "Hungary",
                "channel_id": 3328128766,
                "message_id": 148,
                "post_url": "https://t.me/c/3328128766/148",
                "has_text": True,
                "youtube_urls": None,
            }
        )

        self.assertEqual(meta.source_id.value, "telegram:3328128766:148")
        self.assertEqual(meta.youtube_urls, [])

    def test_validate_enriched_card_warns_on_unknown_claim_type(self):
        card, issues = validate_enriched_card(_minimal_card(claim_type="quote"), "card.enriched.json")

        self.assertIsNotNone(card)
        self.assertEqual([issue.code for issue in issues], ["unknown_claim_type"])
        self.assertEqual(issues[0].severity, "warning")

    def test_validate_enriched_card_errors_on_missing_provenance(self):
        bad_card = _minimal_card()
        bad_card.pop("provenance")

        card, issues = validate_enriched_card(bad_card, "bad.enriched.json")

        self.assertIsNone(card)
        self.assertTrue(any(issue.severity == "error" for issue in issues))
        self.assertTrue(any(issue.field == "provenance" for issue in issues))

    def test_scan_enriched_cards_and_write_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            enriched_dir = Path(tmpdir) / "enriched"
            enriched_dir.mkdir()
            (enriched_dir / "ok.enriched.json").write_text(
                json.dumps(_minimal_card(), ensure_ascii=False),
                encoding="utf-8",
            )
            (enriched_dir / "warn.enriched.json").write_text(
                json.dumps(_minimal_card(claim_type="claim"), ensure_ascii=False),
                encoding="utf-8",
            )
            (enriched_dir / "bad.enriched.json").write_text("{bad json", encoding="utf-8")

            report = scan_enriched_cards(enriched_dir)
            report_path = write_enriched_validation_report(report, Path(tmpdir) / "report.md")

        self.assertEqual(report.cards_seen, 3)
        self.assertEqual(report.cards_valid, 2)
        self.assertEqual(report.cards_invalid, 1)
        self.assertEqual(report.error_count, 1)
        self.assertEqual(report.warning_count, 1)
        self.assertTrue(report_path.name.endswith(".md"))


if __name__ == "__main__":
    unittest.main()
