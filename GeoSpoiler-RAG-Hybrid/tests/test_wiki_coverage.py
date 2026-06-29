import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from retrieval.wiki_coverage import run_wiki_coverage_backfill  # noqa: E402
from retrieval.wiki_index import build_wiki_indexes  # noqa: E402


class WikiCoverageBackfillTests(unittest.TestCase):
    def test_creates_entity_and_topic_pages_from_existing_claims(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir, enriched_dir, index_dir = _make_dirs(root)
            for message_id in [10, 11, 12]:
                _write_card(
                    enriched_dir / f"{message_id}.enriched.json",
                    message_id=message_id,
                    entity="Китай",
                    topic="геополитика",
                    fact=f"China-related source claim {message_id}.",
                )
                _write_claim(
                    wiki_dir / "claims" / f"china-claim-{message_id}.md",
                    enriched_dir / f"{message_id}.enriched.json",
                    source_id=f"telegram:1:{message_id}",
                    title=f"China claim {message_id}",
                    fact=f"China-related source claim {message_id}.",
                )
            build_wiki_indexes(wiki_dir=wiki_dir, enriched_dir=enriched_dir, index_dir=index_dir)

            stats = run_wiki_coverage_backfill(
                wiki_dir=wiki_dir,
                enriched_dir=enriched_dir,
                index_dir=index_dir,
                today=date(2026, 6, 27),
                threshold=3,
                limit=20,
            )

            entity_path = wiki_dir / "entities" / "китай.md"
            topic_path = wiki_dir / "topics" / "геополитика.md"
            entity_text = entity_path.read_text(encoding="utf-8")
            topic_exists = topic_path.exists()

        self.assertEqual([path.name for path in stats.pages_created], ["китай.md", "геополитика.md"])
        self.assertEqual(stats.pages_updated, [])
        self.assertIn("wiki_type: entity", entity_text)
        self.assertIn("# Китай", entity_text)
        self.assertIn("- claims/china-claim-10.md", entity_text)
        self.assertIn("- claims/china-claim-11.md", entity_text)
        self.assertIn("- claims/china-claim-12.md", entity_text)
        self.assertIn("## Связанные утверждения", entity_text)
        self.assertIn("## Как найти источники", entity_text)
        self.assertIn("Первичные источники открываются через доказательства", entity_text)
        self.assertNotIn("## Related Claims", entity_text)
        self.assertNotIn("## Source Resolution", entity_text)
        self.assertNotIn("telegram:1:10", entity_text)
        self.assertTrue(topic_exists)

    def test_backfill_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir, enriched_dir, index_dir = _make_dirs(root)
            for message_id in [10, 11, 12]:
                _write_card(
                    enriched_dir / f"{message_id}.enriched.json",
                    message_id=message_id,
                    entity="Россия",
                    topic="санкции",
                    fact=f"Russia-related source claim {message_id}.",
                )
                _write_claim(
                    wiki_dir / "claims" / f"russia-claim-{message_id}.md",
                    enriched_dir / f"{message_id}.enriched.json",
                    source_id=f"telegram:1:{message_id}",
                    title=f"Russia claim {message_id}",
                    fact=f"Russia-related source claim {message_id}.",
                )
            build_wiki_indexes(wiki_dir=wiki_dir, enriched_dir=enriched_dir, index_dir=index_dir)

            first = run_wiki_coverage_backfill(
                wiki_dir=wiki_dir,
                enriched_dir=enriched_dir,
                index_dir=index_dir,
                today=date(2026, 6, 27),
                threshold=3,
            )
            second = run_wiki_coverage_backfill(
                wiki_dir=wiki_dir,
                enriched_dir=enriched_dir,
                index_dir=index_dir,
                today=date(2026, 6, 27),
                threshold=3,
            )

        self.assertEqual(len(first.pages_created), 2)
        self.assertEqual(second.pages_created, [])
        self.assertEqual(second.pages_updated, [])

    def test_backfill_updates_existing_generated_hub_page_with_new_claims(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir, enriched_dir, index_dir = _make_dirs(root)
            for message_id in [10, 11, 12]:
                _write_card(
                    enriched_dir / f"{message_id}.enriched.json",
                    message_id=message_id,
                    entity="Китай",
                    topic="геополитика",
                    fact=f"China-related source claim {message_id}.",
                )
                _write_claim(
                    wiki_dir / "claims" / f"china-claim-{message_id}.md",
                    enriched_dir / f"{message_id}.enriched.json",
                    source_id=f"telegram:1:{message_id}",
                    title=f"China claim {message_id}",
                    fact=f"China-related source claim {message_id}.",
                )
            (wiki_dir / "entities" / "китай.md").write_text(
                "---\n"
                "wiki_type: entity\n"
                "generated_by: wiki_coverage_backfill_v1\n"
                "review_status: auto\n"
                "coverage_count: 1\n"
                "related_claim_count: 1\n"
                "updated_at: 2026-06-26\n"
                "---\n\n"
                "# Китай\n\n"
                "## Related Claims\n\n"
                "- claims/china-claim-10.md\n\n"
                "## Source Resolution\n\n"
                "- Resolve primary sources through claim evidence and output/wiki/indexes/page_to_sources.json.\n",
                encoding="utf-8",
            )
            build_wiki_indexes(wiki_dir=wiki_dir, enriched_dir=enriched_dir, index_dir=index_dir)

            stats = run_wiki_coverage_backfill(
                wiki_dir=wiki_dir,
                enriched_dir=enriched_dir,
                index_dir=index_dir,
                today=date(2026, 6, 27),
                threshold=3,
            )

            entity_text = (wiki_dir / "entities" / "китай.md").read_text(encoding="utf-8")

        self.assertIn(wiki_dir / "entities" / "китай.md", stats.pages_updated)
        self.assertIn("- claims/china-claim-11.md", entity_text)
        self.assertIn("- claims/china-claim-12.md", entity_text)
        self.assertIn("related_claim_count: 3", entity_text)

    def test_backfill_creates_empty_hub_when_mentions_have_no_claim_pages(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir, enriched_dir, index_dir = _make_dirs(root)
            for message_id in [10, 11, 12]:
                _write_card(
                    enriched_dir / f"{message_id}.enriched.json",
                    message_id=message_id,
                    entity="Москва",
                    topic="безопасность",
                    fact=f"Unclaimed source card {message_id}.",
                )
            build_wiki_indexes(wiki_dir=wiki_dir, enriched_dir=enriched_dir, index_dir=index_dir)

            stats = run_wiki_coverage_backfill(
                wiki_dir=wiki_dir,
                enriched_dir=enriched_dir,
                index_dir=index_dir,
                today=date(2026, 6, 27),
                threshold=3,
            )

            entity_text = (wiki_dir / "entities" / "москва.md").read_text(encoding="utf-8")
            topic_text = (wiki_dir / "topics" / "безопасность.md").read_text(encoding="utf-8")

        self.assertEqual([path.name for path in stats.pages_created], ["москва.md", "безопасность.md"])
        self.assertIn("related_claim_count: 0", entity_text)
        self.assertIn("- нет", entity_text)
        self.assertNotIn("telegram:1:10", entity_text)
        self.assertIn("related_claim_count: 0", topic_text)


def _make_dirs(root: Path) -> tuple[Path, Path, Path]:
    wiki_dir = root / "wiki"
    enriched_dir = root / "enriched"
    index_dir = wiki_dir / "indexes"
    for directory in [wiki_dir / "claims", wiki_dir / "entities", wiki_dir / "topics", index_dir, enriched_dir]:
        directory.mkdir(parents=True, exist_ok=True)
    return wiki_dir, enriched_dir, index_dir


def _write_card(path: Path, *, message_id: int, entity: str, topic: str, fact: str) -> None:
    path.write_text(
        json.dumps(
            {
                "triage": "keep",
                "summary": fact,
                "provenance": {
                    "channel_id": 1,
                    "message_id": message_id,
                    "post_url": f"https://t.me/c/1/{message_id}",
                    "normalized_file": f"output/normalized/test/{message_id}.txt",
                    "date": "2026-06-27T00:00:00+00:00",
                },
                "key_facts": [{"text": fact, "claim_type": "source_claim"}],
                "entities": {"countries": [entity]},
                "topics": [topic],
                "quotes": [],
                "events": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _write_claim(path: Path, card_path: Path, *, source_id: str, title: str, fact: str) -> None:
    path.write_text(
        "---\n"
        "wiki_type: claim\n"
        "status: supported_by_corpus\n"
        "generated_by: wiki_ingest_v1\n"
        "review_status: auto\n"
        "source_count: 1\n"
        "updated_at: 2026-06-27\n"
        "---\n\n"
        f"# {title}\n\n"
        "## Evidence\n\n"
        f"- {source_id} - source_claim: {fact}\n"
        f"  - card_path: {card_path}\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
