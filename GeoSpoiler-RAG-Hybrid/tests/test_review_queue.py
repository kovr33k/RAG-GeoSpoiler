import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from normalizer.review_queue import mark_reviewed  # noqa: E402


class ReviewQueueLoadTests(unittest.TestCase):
    def test_mark_reviewed_stores_prompt_extraction_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            review_file = Path(tmpdir) / "item.json"
            review_file.write_text(
                json.dumps(
                    {
                        "review_type": "external_link",
                        "status": "pending",
                        "extracted_text": None,
                    }
                ),
                encoding="utf-8",
            )

            mark_reviewed(
                str(review_file),
                extracted_text="Filtered extraction",
                extraction_prompt="Extract only the port blockade details",
                extraction_source="youtube",
            )

            payload = json.loads(review_file.read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], "processed")
        self.assertEqual(payload["extracted_text"], "Filtered extraction")
        self.assertEqual(
            payload["extraction_prompt"],
            "Extract only the port blockade details",
        )
        self.assertEqual(payload["extraction_source"], "youtube")

if __name__ == "__main__":
    unittest.main()
