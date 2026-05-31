import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent))

from fetcher.telegram_client import TelegramMedia  # noqa: E402
from normalizer.image_handler import _candidate_api_keys, describe_image  # noqa: E402
from normalizer.instagram_handler import canonicalize_instagram_url  # noqa: E402
from normalizer.transcription_handler import transcribe_media  # noqa: E402
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

    def test_transcribe_media_writes_artifact(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"text": "transcribed native media"}

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            media_path = root / "media_cache" / "Channel" / "voice" / "msg_11.ogg"
            media_path.parent.mkdir(parents=True)
            media_path.write_bytes(b"fake audio")
            transcript_dir = root / "output" / "transcripts"
            item = TelegramMedia(
                media_type="voice",
                mime_type="audio/ogg",
                message_id=11,
                file_path=str(media_path),
                download_status="downloaded",
            )

            with patch("normalizer.transcription_handler.config.TRANSCRIPTION_ENABLED", True):
                with patch("normalizer.transcription_handler.config.TRANSCRIPTION_API_KEY", "api-key"):
                    with patch("normalizer.transcription_handler.config.TRANSCRIPTION_BASE_URL", "https://example.com/v1"):
                        with patch("normalizer.transcription_handler.config.TRANSCRIPTION_MODEL", "whisper-1"):
                            with patch("normalizer.transcription_handler.config.TRANSCRIPTION_LANGUAGE", ""):
                                with patch("normalizer.transcription_handler.config.TRANSCRIPTION_TIMEOUT_SECONDS", 10):
                                    with patch("normalizer.transcription_handler.config.TRANSCRIPTION_DIR", transcript_dir):
                                        with patch(
                                            "normalizer.transcription_handler.requests.post",
                                            return_value=response,
                                        ) as post:
                                            result = transcribe_media(item, "Channel", 11)

            artifact_path = Path(result.artifact_path)
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))

        self.assertEqual(result.status, "transcribed")
        self.assertEqual(result.text, "transcribed native media")
        self.assertEqual(payload["text"], "transcribed native media")
        self.assertEqual(payload["media"]["media_type"], "voice")
        self.assertEqual(post.call_args.kwargs["data"]["model"], "whisper-1")
        self.assertIn("/audio/transcriptions", post.call_args.args[0])
