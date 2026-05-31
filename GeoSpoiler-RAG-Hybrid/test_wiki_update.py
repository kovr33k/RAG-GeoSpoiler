import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from retrieval import wiki_index  # noqa: E402
from retrieval.wiki_update import SOURCE_HASHES_FILENAME, run_wiki_incremental_update  # noqa: E402


class WikiIncrementalUpdateTests(unittest.TestCase):
    def test_wiki_update_repeated_run_does_not_rewrite_pages(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir, enriched_dir, index_dir = _make_dirs(tmpdir)
            card_path = enriched_dir / "10.enriched.json"
            _write_card(card_path, 1, 10, "Direct evidence.")
            _write_claim(wiki_dir / "claims" / "claim.md", "telegram:1:10", "old-hash")
            wiki_index.build_wiki_indexes(wiki_dir=wiki_dir, enriched_dir=enriched_dir, index_dir=index_dir)

            first = run_wiki_incremental_update(
                wiki_dir=wiki_dir,
                enriched_dir=enriched_dir,
                index_dir=index_dir,
                today=date(2026, 5, 26),
            )
            before = (wiki_dir / "claims" / "claim.md").read_text(encoding="utf-8")
            second = run_wiki_incremental_update(
                wiki_dir=wiki_dir,
                enriched_dir=enriched_dir,
                index_dir=index_dir,
                today=date(2026, 5, 26),
            )
            after = (wiki_dir / "claims" / "claim.md").read_text(encoding="utf-8")
            pending = json.loads((wiki_dir / "_pending_updates.json").read_text(encoding="utf-8"))

        self.assertTrue(first.initialized)
        self.assertFalse(second.initialized)
        self.assertEqual(second.pages_updated, [])
        self.assertEqual(before, after)
        self.assertEqual(pending, [])

    def test_wiki_update_changed_card_updates_only_linked_pages(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir, enriched_dir, index_dir = _make_dirs(tmpdir)
            card_a = enriched_dir / "10.enriched.json"
            card_b = enriched_dir / "11.enriched.json"
            _write_card(card_a, 1, 10, "Changed source evidence.")
            _write_card(card_b, 1, 11, "Stable source evidence.")
            expected_hash = _hash_for_card(card_a)
            _write_claim(wiki_dir / "claims" / "changed.md", "telegram:1:10", "old-hash")
            _write_claim(wiki_dir / "claims" / "stable.md", "telegram:1:11", _hash_for_card(card_b))
            wiki_index.build_wiki_indexes(wiki_dir=wiki_dir, enriched_dir=enriched_dir, index_dir=index_dir)
            _write_source_hashes(
                index_dir,
                {
                    "telegram:1:10": {"content_hash": "old-hash"},
                    "telegram:1:11": {"content_hash": _hash_for_card(card_b)},
                },
            )
            stable_before = (wiki_dir / "claims" / "stable.md").read_text(encoding="utf-8")

            stats = run_wiki_incremental_update(
                wiki_dir=wiki_dir,
                enriched_dir=enriched_dir,
                index_dir=index_dir,
                today=date(2026, 5, 26),
            )
            changed_text = (wiki_dir / "claims" / "changed.md").read_text(encoding="utf-8")
            stable_after = (wiki_dir / "claims" / "stable.md").read_text(encoding="utf-8")

        self.assertEqual([path.name for path in stats.pages_updated], ["changed.md"])
        self.assertIn(f"content_hash: {expected_hash}", changed_text)
        self.assertEqual(stable_before, stable_after)

    def test_wiki_update_writes_unlinked_source_to_pending_updates_and_log(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir, enriched_dir, index_dir = _make_dirs(tmpdir)
            _write_card(enriched_dir / "12.enriched.json", 1, 12, "New unlinked source.")
            _write_source_hashes(index_dir, {"telegram:9:9": {"content_hash": "old"}})

            stats = run_wiki_incremental_update(
                wiki_dir=wiki_dir,
                enriched_dir=enriched_dir,
                index_dir=index_dir,
                today=date(2026, 5, 26),
            )
            pending = json.loads((wiki_dir / "_pending_updates.json").read_text(encoding="utf-8"))
            log_events = [
                json.loads(line)
                for line in (wiki_dir / "_log.md").read_text(encoding="utf-8").splitlines()
                if line.startswith("{")
            ]

        self.assertEqual(len(stats.pending_updates), 1)
        self.assertEqual(pending[0]["reason"], "new_unlinked_source")
        self.assertEqual(pending[0]["source_id"], "telegram:1:12")
        self.assertEqual(log_events[-1]["event"], "wiki_incremental_update")
        self.assertEqual(log_events[-1]["pending_updates"], 1)


def _make_dirs(tmpdir: str) -> tuple[Path, Path, Path]:
    root = Path(tmpdir)
    wiki_dir = root / "wiki"
    enriched_dir = root / "enriched"
    index_dir = wiki_dir / "indexes"
    (wiki_dir / "claims").mkdir(parents=True)
    enriched_dir.mkdir()
    index_dir.mkdir()
    return wiki_dir, enriched_dir, index_dir


def _write_card(path: Path, channel_id: int, message_id: int, text: str) -> None:
    path.write_text(
        json.dumps(
            {
                "triage": "keep",
                "provenance": {
                    "channel_id": channel_id,
                    "message_id": message_id,
                    "post_url": f"https://t.me/c/{channel_id}/{message_id}",
                    "normalized_file": f"output/normalized/{message_id}.txt",
                    "date": "2026-05-26T00:00:00+00:00",
                },
                "key_facts": [{"text": text, "claim_type": "source_claim"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _write_claim(path: Path, source_id: str, content_hash: str) -> None:
    path.write_text(
        "---\n"
        "wiki_type: claim\n"
        "status: supported_by_corpus\n"
        "generated_by: test\n"
        "review_status: auto\n"
        "source_count: 1\n"
        "updated_at: 2026-05-25\n"
        "---\n\n"
        "# Claim\n\n"
        "Status: supported_by_corpus\n\n"
        "## Evidence\n\n"
        f"- {source_id} - source_claim: Direct evidence.\n"
        "  - post_url: old\n"
        "  - date: old\n"
        "  - card_path: old\n"
        f"  - content_hash: {content_hash}\n\n"
        "## Guardrails\n\n"
        "- Use cited evidence only.\n",
        encoding="utf-8",
    )


def _hash_for_card(path: Path) -> str:
    return wiki_index.compute_content_hash(json.loads(path.read_text(encoding="utf-8")))


def _write_source_hashes(index_dir: Path, data: dict) -> None:
    (index_dir / SOURCE_HASHES_FILENAME).write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
