import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent))

from normalizer.image_handler import _candidate_api_keys, describe_image  # noqa: E402
from normalizer.instagram_handler import canonicalize_instagram_url  # noqa: E402
from normalizer.youtube_handler import _clean_description  # noqa: E402


class HandlerTests(unittest.TestCase):
    def test_canonicalize_instagram_url_rewrites_kk_host(self):
        url = "https://kkinstagram.com/reel/DVRCLW0DZT9/?igsh=cWI0ejYzYnZvMzVi"
        self.assertEqual(
            canonicalize_instagram_url(url),
            "https://www.instagram.com/reel/DVRCLW0DZT9/?igsh=cWI0ejYzYnZvMzVi",
        )

    def test_candidate_api_keys_prefers_vision_then_llm_without_duplicates(self):
        with patch("normalizer.image_handler.config.VISION_API_KEY", "vision"):
            with patch("normalizer.image_handler.config.LLM_API_KEY", "llm"):
                self.assertEqual(_candidate_api_keys(), ["vision", "llm"])

        with patch("normalizer.image_handler.config.VISION_API_KEY", "same"):
            with patch("normalizer.image_handler.config.LLM_API_KEY", "same"):
                self.assertEqual(_candidate_api_keys(), ["same"])

    def test_describe_image_retries_with_llm_key_after_vision_403(self):
        responses = []

        forbidden = Mock()
        forbidden.raise_for_status.side_effect = __import__("requests").HTTPError(
            response=Mock(status_code=403)
        )
        responses.append(forbidden)

        success = Mock()
        success.raise_for_status.return_value = None
        success.json.return_value = {
            "choices": [{"message": {"content": "image description"}}]
        }
        responses.append(success)

        with patch("normalizer.image_handler.config.VISION_API_KEY", "vision-key"):
            with patch("normalizer.image_handler.config.LLM_API_KEY", "llm-key"):
                with patch("normalizer.image_handler.config.VISION_BASE_URL", "https://example.com/v1"):
                    with patch("normalizer.image_handler.config.VISION_MODEL", "vision-model"):
                        with patch("normalizer.image_handler.Path.exists", return_value=True):
                            with patch("builtins.open", unittest.mock.mock_open(read_data=b"jpg")):
                                with patch("normalizer.image_handler.requests.post", side_effect=responses) as post:
                                    result = describe_image("fake.jpg")

        self.assertEqual(result, "[Изображение]\nimage description")
        self.assertEqual(post.call_count, 2)
        self.assertIn("vision-key", post.call_args_list[0].kwargs["headers"]["Authorization"])
        self.assertIn("llm-key", post.call_args_list[1].kwargs["headers"]["Authorization"])

    def test_clean_youtube_description_drops_promo_blocks(self):
        description = "\n".join(
            [
                "Полезное описание по теме видео.",
                "Подробнее — в новом выпуске.",
                "🧡 Поддержать канал: https://base.monobank.ua/example",
                "Социальные сети канала:",
                "https://t.me/example",
                "0:00 — Вступление",
            ]
        )

        self.assertEqual(
            _clean_description(description),
            "Полезное описание по теме видео.\nПодробнее — в новом выпуске.",
        )

    def test_clean_youtube_description_drops_timeline_when_no_promo_marker(self):
        description = "\n".join(
            [
                "Краткое описание видео.",
                "0:00 — Вступление",
                "2:33 — Основная часть",
            ]
        )

        self.assertEqual(_clean_description(description), "Краткое описание видео.")

    def test_clean_youtube_description_trims_inline_promo_blocks(self):
        description = (
            "Полезное описание. ——— 🧡 Поддержать канал: https://base.monobank.ua/x "
            "Социальные сети: https://t.me/example Содержание: 0:00 — Вступление"
        )

        self.assertEqual(_clean_description(description), "Полезное описание.")
