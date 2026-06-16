import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cli_pipeline  # noqa: E402
import config  # noqa: E402


class ReviewQueueLoadTests(unittest.TestCase):
    def test_collect_reviewed_texts_loads_all_processed_review_types(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_dir = Path(tmpdir)
            for name, review_type, text in [
                ("ai.json", "ai_chat", "AI extracted"),
                ("link.json", "external_link", "External extracted"),
                ("low.json", "uninformative", "Approved low info"),
            ]:
                (queue_dir / name).write_text(
                    json.dumps(
                        {
                            "review_type": review_type,
                            "status": "processed",
                            "channel": "Channel",
                            "message_id": 10,
                            "url": "https://example.com" if review_type == "external_link" else "",
                            "extracted_text": text,
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

            with patch.object(config, "REVIEW_QUEUE_DIR", queue_dir):
                reviewed = cli_pipeline._collect_reviewed_texts()

        self.assertEqual(len(reviewed), 3)
        self.assertTrue(all("Review type:" in text for _, text in reviewed))
        self.assertEqual({Path(path).name for path, _ in reviewed}, {"ai.json", "link.json", "low.json"})


if __name__ == "__main__":
    unittest.main()
