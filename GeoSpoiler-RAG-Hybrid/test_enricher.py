import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from enricher.triage import auto_triage  # noqa: E402


class AutoTriageTests(unittest.TestCase):
    def test_short_curated_post_is_kept(self):
        text = (
            "[Канал: Ультра левые и ультра правые | Дата: 2026-02-09 19:05]\n\n"
            "Ультра-левые и ультра-правые совпадают."
        )

        triage, reason = auto_triage("text", {}, text)

        self.assertEqual(triage, "keep")
        self.assertIn("minimum quality", reason)

    def test_native_video_with_caption_is_kept(self):
        text = (
            "[Канал: Балтийские страны | Дата: 2026-03-24 21:18]\n\n"
            "На российском телевидении пропагандисты предлагают захватить эстонский город Нарва.\n"
            "[Видео: пост содержал видео - не обработано]"
        )

        triage, reason = auto_triage("video_native", {"has_video": True}, text)

        self.assertEqual(triage, "keep")
        self.assertIn("caption", reason)

    def test_placeholder_only_video_still_requires_review(self):
        text = (
            "[Канал: Example | Дата: 2026-03-24 21:18]\n\n"
            "[Видео: пост содержал видео - не обработано]"
        )

        triage, reason = auto_triage("video_native", {"has_video": True}, text)

        self.assertEqual(triage, "review")
        self.assertIn("needs Whisper", reason)


if __name__ == "__main__":
    unittest.main()
