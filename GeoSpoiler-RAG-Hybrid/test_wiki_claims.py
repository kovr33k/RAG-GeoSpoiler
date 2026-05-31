import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from retrieval.wiki_claims import ClaimSpec, seed_claim_pages  # noqa: E402


class WikiClaimSeedTests(unittest.TestCase):
    def test_wiki_claim_seed_uses_source_claims_not_hypotheses(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            enriched_dir = Path(tmpdir) / "enriched"
            enriched_dir.mkdir()
            _write_card(
                enriched_dir / "1.enriched.json",
                {
                    "triage": "keep",
                    "provenance": {"channel_id": 1, "message_id": 10, "post_url": "https://t.me/c/1/10"},
                    "summary": "Summary should not become evidence.",
                    "key_facts": [
                        {
                            "text": "Vance came to Hungary to support Viktor Orban.",
                            "claim_type": "source_claim",
                        },
                        {
                            "text": "Hypothesis text should not be used as evidence.",
                            "claim_type": "hypothesis",
                        },
                    ],
                    "theses": ["Thesis text should not be used as evidence."],
                },
            )

            spec = ClaimSpec(
                slug="vance-supported-orban",
                title="Vance supported Orban",
                status="supported_by_corpus",
                match_groups=(("vance",), ("orban",), ("support",)),
            )
            stats = seed_claim_pages(
                wiki_dir=wiki_dir,
                enriched_dir=enriched_dir,
                specs=(spec,),
                today=date(2026, 5, 26),
            )

            page = stats.created[0].read_text(encoding="utf-8")

        self.assertIn("Vance came to Hungary to support Viktor Orban.", page)
        self.assertNotIn("Hypothesis text should not be used as evidence.", page)
        self.assertNotIn("Thesis text should not be used as evidence.", page)
        self.assertNotIn("Summary should not become evidence.", page)

    def test_wiki_claim_seed_does_not_call_supported_claim_fake(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            enriched_dir = Path(tmpdir) / "enriched"
            enriched_dir.mkdir()
            _write_card(
                enriched_dir / "1.enriched.json",
                {
                    "triage": "keep",
                    "provenance": {"channel_id": 1, "message_id": 11, "post_url": "https://t.me/c/1/11"},
                    "summary": "Unsupported fake verdict should stay out of evidence.",
                    "key_facts": [
                        {
                            "text": "Trump supported Viktor Orban before the election.",
                            "claim_type": "source_claim",
                        },
                        {
                            "text": "Unsupported fake verdict should stay out of evidence.",
                            "claim_type": "hypothesis",
                        },
                    ],
                },
            )

            spec = ClaimSpec(
                slug="trump-supported-orban",
                title="Trump supported Orban",
                status="supported_by_corpus",
                match_groups=(("trump",), ("orban",), ("support",)),
            )
            stats = seed_claim_pages(
                wiki_dir=wiki_dir,
                enriched_dir=enriched_dir,
                specs=(spec,),
                today=date(2026, 5, 26),
            )

            page = stats.created[0].read_text(encoding="utf-8")

        self.assertIn("status: supported_by_corpus", page)
        self.assertIn("Trump supported Viktor Orban before the election.", page)
        self.assertNotIn("Unsupported fake verdict should stay out of evidence.", page)


def _write_card(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
