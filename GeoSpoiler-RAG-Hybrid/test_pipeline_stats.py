import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import ANY, patch

sys.path.insert(0, str(Path(__file__).parent))

from fetcher.telegram_client import TelegramMessage  # noqa: E402
from normalizer.ai_chat_handler import AIReviewResult  # noqa: E402
from normalizer.pipeline import normalize_batch  # noqa: E402


class PipelineStatsTests(unittest.TestCase):
    def test_normalize_batch_collects_content_type_and_review_stats(self):
        msg1 = TelegramMessage(
            channel_name="Channel",
            channel_id=1,
            channel_username="channel",
            message_id=101,
            date=datetime(2026, 4, 29),
            text="post 1",
            image_paths=["img1.jpg", "img2.jpg"],
            has_video=True,
            urls=[
                "https://youtube.com/watch?v=abc123",
                "https://instagram.com/reel/reel123",
                "https://instagram.com/p/post123",
                "https://chatgpt.com/share/aaa111",
                "https://claude.ai/share/bbb222",
                "https://example.com/story",
            ],
        )
        msg2 = TelegramMessage(
            channel_name="Channel",
            channel_id=1,
            channel_username="channel",
            message_id=102,
            date=datetime(2026, 4, 29),
            text="   ",
            urls=[],
        )

        with patch("normalizer.pipeline.normalize_text", side_effect=lambda text: text):
            with patch("normalizer.pipeline.extract_youtube_text", return_value="[yt]"):
                with patch("normalizer.pipeline.extract_instagram_text", return_value="[ig]"):
                    with patch("normalizer.pipeline.extract_web_text", return_value="[web]"):
                        with patch("normalizer.pipeline.describe_image", return_value="[img]"):
                            with patch(
                                "normalizer.pipeline.queue_for_review",
                                side_effect=[
                                    AIReviewResult("[ai1]", "queued", "a.json"),
                                    AIReviewResult("[ai2]", "already_reviewed", "b.json"),
                                ],
                            ):
                                with patch(
                                    "normalizer.pipeline._save_normalized",
                                    return_value=Path("D:/fake/101.txt"),
                                ):
                                    with patch(
                                        "normalizer.pipeline.translate_to_russian_if_needed",
                                        side_effect=lambda text: text,
                                    ):
                                        result = normalize_batch([msg1, msg2])

        self.assertEqual(result.messages_total, 2)
        self.assertEqual(result.messages_with_text, 1)
        self.assertEqual(result.messages_with_images, 1)
        self.assertEqual(result.images_total, 2)
        self.assertEqual(result.messages_with_native_video, 1)
        self.assertEqual(result.messages_with_youtube, 1)
        self.assertEqual(result.youtube_links_total, 1)
        self.assertEqual(result.messages_with_instagram_reels, 1)
        self.assertEqual(result.instagram_reel_links_total, 1)
        self.assertEqual(result.messages_with_instagram_posts, 1)
        self.assertEqual(result.instagram_post_links_total, 1)
        self.assertEqual(result.messages_with_ai_chat, 1)
        self.assertEqual(result.ai_chat_links_total, 2)
        self.assertEqual(result.messages_with_web, 1)
        self.assertEqual(result.web_links_total, 1)
        self.assertEqual(result.normalized_messages, 1)
        self.assertEqual(result.skipped_messages, 1)
        self.assertEqual(result.failed_messages, 0)
        self.assertEqual(result.ai_review_created, 1)
        self.assertEqual(result.ai_review_already_reviewed, 1)
        self.assertEqual(len(result.texts_with_paths), 1)
        self.assertEqual(Path(result.texts_with_paths[0][0]), Path("D:/fake/101.txt"))
        self.assertEqual(ANY, result.texts_with_paths[0][1])
