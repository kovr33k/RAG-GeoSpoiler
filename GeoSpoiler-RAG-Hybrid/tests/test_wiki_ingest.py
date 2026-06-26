import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from retrieval import wiki_index  # noqa: E402
from retrieval.wiki_ingest import run_wiki_ingest  # noqa: E402
from retrieval.wiki_update import SOURCE_HASHES_FILENAME  # noqa: E402


class WikiIngestTests(unittest.TestCase):
    def test_wiki_ingest_creates_grounded_pages_and_updates_hashes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir, enriched_dir, index_dir = _make_dirs(root)
            card_path = enriched_dir / "Cuba" / "10.enriched.json"
            _write_card(
                card_path,
                channel_id=1,
                message_id=10,
                fact="A source claimed that protests continued in Cuba.",
                entities={"countries": ["Cuba"], "people": []},
                topics=["cuba protests"],
            )
            expected_hash = _hash_for_card(card_path)

            stats = run_wiki_ingest(
                wiki_dir=wiki_dir,
                enriched_dir=enriched_dir,
                index_dir=index_dir,
                today=date(2026, 6, 26),
                llm_call=lambda _prompt: {
                    "operations": [
                        {
                            "action": "create",
                            "page_type": "claim",
                            "slug": "cuba-protests-continued",
                            "title": "Cuba protests continued",
                            "status": "supported_by_corpus",
                            "source_ids": ["telegram:1:10"],
                            "evidence": [
                                {
                                    "source_id": "telegram:1:10",
                                    "evidence_type": "source_claim",
                                    "text": "A source claimed that protests continued in Cuba.",
                                }
                            ],
                            "guardrails": ["Do not generalize beyond the cited source."],
                        },
                        {
                            "action": "create",
                            "page_type": "entity",
                            "slug": "cuba",
                            "title": "Cuba",
                            "summary": "Country mentioned by the ingested source.",
                            "source_ids": ["telegram:1:10"],
                            "related_claims": ["claims/cuba-protests-continued.md"],
                        },
                    ]
                },
            )

            claim_text = (wiki_dir / "claims" / "cuba-protests-continued.md").read_text(encoding="utf-8")
            entity_text = (wiki_dir / "entities" / "cuba.md").read_text(encoding="utf-8")
            source_hashes = json.loads((index_dir / SOURCE_HASHES_FILENAME).read_text(encoding="utf-8"))
            page_to_sources = json.loads((index_dir / wiki_index.PAGE_INDEX_FILENAME).read_text(encoding="utf-8"))

        self.assertEqual(stats.cards_processed, 1)
        self.assertEqual([path.name for path in stats.pages_created], ["cuba-protests-continued.md", "cuba.md"])
        self.assertEqual(stats.pages_updated, [])
        self.assertEqual(stats.pending, [])
        self.assertIn("generated_by: wiki_ingest_v1", claim_text)
        self.assertIn("review_status: auto", claim_text)
        self.assertIn("- telegram:1:10 - source_claim: A source claimed", claim_text)
        self.assertIn("Do not generalize beyond the cited source.", claim_text)
        self.assertIn("wiki_type: entity", entity_text)
        self.assertEqual(source_hashes["telegram:1:10"]["content_hash"], expected_hash)
        self.assertEqual(page_to_sources["claims/cuba-protests-continued.md"], ["telegram:1:10"])

    def test_wiki_ingest_rejects_operations_with_external_source_ids(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir, enriched_dir, index_dir = _make_dirs(root)
            _write_card(
                enriched_dir / "Cuba" / "10.enriched.json",
                channel_id=1,
                message_id=10,
                fact="A source claimed that protests continued in Cuba.",
                entities={"countries": ["Cuba"]},
                topics=["cuba protests"],
            )

            stats = run_wiki_ingest(
                wiki_dir=wiki_dir,
                enriched_dir=enriched_dir,
                index_dir=index_dir,
                today=date(2026, 6, 26),
                llm_call=lambda _prompt: {
                    "operations": [
                        {
                            "action": "create",
                            "page_type": "claim",
                            "slug": "bad-external-claim",
                            "title": "Bad external claim",
                            "status": "supported_by_corpus",
                            "source_ids": ["telegram:999:999"],
                            "evidence": [
                                {
                                    "source_id": "telegram:999:999",
                                    "evidence_type": "source_claim",
                                    "text": "This source was not in the input batch.",
                                }
                            ],
                        }
                    ]
                },
            )

            pending = json.loads((wiki_dir / "_pending_updates.json").read_text(encoding="utf-8"))

        self.assertEqual(stats.pages_created, [])
        self.assertEqual(len(stats.pending), 1)
        self.assertEqual(stats.pending[0].reason, "invalid_operation")
        self.assertEqual(pending[0]["source_id"], "telegram:1:10")
        self.assertFalse((wiki_dir / "claims" / "bad-external-claim.md").exists())


def _make_dirs(root: Path) -> tuple[Path, Path, Path]:
    wiki_dir = root / "wiki"
    enriched_dir = root / "enriched"
    index_dir = wiki_dir / "indexes"
    for directory in [
        wiki_dir / "claims",
        wiki_dir / "entities",
        wiki_dir / "topics",
        index_dir,
        enriched_dir / "Cuba",
    ]:
        directory.mkdir(parents=True, exist_ok=True)
    (wiki_dir / "_schema.md").write_text("# Schema\n", encoding="utf-8")
    (wiki_dir / "_master_index.md").write_text("# Wiki Memory\n", encoding="utf-8")
    return wiki_dir, enriched_dir, index_dir


def _write_card(
    path: Path,
    *,
    channel_id: int,
    message_id: int,
    fact: str,
    entities: dict,
    topics: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "triage": "keep",
                "summary": fact,
                "provenance": {
                    "channel_name": "Cuba",
                    "channel_id": channel_id,
                    "message_id": message_id,
                    "post_url": f"https://t.me/c/{channel_id}/{message_id}",
                    "normalized_file": f"output/normalized/Cuba/{message_id}.txt",
                    "date": "2026-06-26T00:00:00+00:00",
                },
                "key_facts": [{"text": fact, "claim_type": "source_claim"}],
                "entities": entities,
                "topics": topics,
                "quotes": [],
                "events": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _hash_for_card(path: Path) -> str:
    return wiki_index.compute_content_hash(json.loads(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
