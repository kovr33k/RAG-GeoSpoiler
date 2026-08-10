import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fetcher.telegram_client import TelegramMedia  # noqa: E402
from normalizer.image_handler import _candidate_api_keys, describe_image  # noqa: E402
from normalizer.instagram_handler import (  # noqa: E402
    _compute_edge_density,
    _compute_phash,
    _dedup_frames,
    _extract_post_id,
    _filter_empty_frames,
    _hamming_distance,
    _read_cache,
    _write_cache,
    canonicalize_instagram_url,
)
from normalizer.transcription_handler import transcribe_media  # noqa: E402
from normalizer.youtube_handler import _clean_description, extract_youtube_text  # noqa: E402


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

    def test_extract_youtube_text_starts_with_author_title_and_url(self):
        url = "https://www.youtube.com/watch?v=abc123"
        info = {
            "title": "Video title",
            "channel": "Video channel",
            "description": "Description",
        }

        with patch("normalizer.youtube_handler._get_video_info", return_value=info):
            with patch("normalizer.youtube_handler._get_subtitles", return_value="Transcript body"):
                result = extract_youtube_text(url)

        self.assertTrue(
            result.startswith(
                "[YouTube]\n"
                "Автор: Video channel\n"
                "Название: Video title\n"
                "URL: https://www.youtube.com/watch?v=abc123"
            )
        )
        self.assertIn("Transcript body", result)

    def test_extract_youtube_text_preserves_chapters_when_only_description_available(self):
        url = "https://www.youtube.com/watch?v=vVmfBZvpfHg"
        info = {
            "title": "Китай, военный экспорт, K-pop",
            "channel": "BBC News - Русская служба",
            "description": "\n".join(
                [
                    "Еще не подписаны на наш YouTube-канал?",
                    "ᐅ https://bit.ly/4aHdtrk ᐊ",
                    "",
                    "Почему власть в Северной Корее остается устойчивой?",
                    "17:55 Как военный экспорт в Россию повысил уровень жизни в Северной Корее",
                    "21:53 Как Китай воспринимает сотрудничество КНДР и России",
                ]
            ),
        }

        with patch("normalizer.youtube_handler._get_video_info", return_value=info):
            with patch("normalizer.youtube_handler._get_subtitles", return_value=None):
                with patch("normalizer.youtube_handler._transcribe_audio", return_value=None):
                    result = extract_youtube_text(url)

        self.assertIn("Почему власть в Северной Корее остается устойчивой?", result)
        self.assertIn(
            "17:55 Как военный экспорт в Россию повысил уровень жизни в Северной Корее",
            result,
        )
        self.assertNotIn("Еще не подписаны", result)
        self.assertNotIn("bit.ly", result)

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


# ─────────────────────── Instagram Deep Extract Tests ───────────────────────


class InstagramPostIdTests(unittest.TestCase):
    """Tests for _extract_post_id utility."""

    def test_extracts_reel_id(self):
        url = "https://www.instagram.com/reel/DVRCLW0DZT9/?igsh=cWI0ejYzYnZvMzVi"
        self.assertEqual(_extract_post_id(url), "DVRCLW0DZT9")

    def test_extracts_post_id(self):
        url = "https://www.instagram.com/p/ABC123def/"
        self.assertEqual(_extract_post_id(url), "ABC123def")

    def test_returns_none_for_invalid_url(self):
        self.assertIsNone(_extract_post_id("https://www.instagram.com/stories/user/"))
        self.assertIsNone(_extract_post_id("https://example.com"))


class InstagramPhashTests(unittest.TestCase):
    """Tests for perceptual hashing and frame deduplication."""

    def test_hamming_distance_identical(self):
        self.assertEqual(_hamming_distance(0, 0), 0)

    def test_hamming_distance_different(self):
        self.assertEqual(_hamming_distance(0b1111, 0b0000), 4)
        self.assertEqual(_hamming_distance(0b1010, 0b0101), 4)

    def test_hamming_distance_one_bit(self):
        self.assertEqual(_hamming_distance(0b1000, 0b0000), 1)

    def test_phash_identical_images_returns_same_hash(self):
        """Two identical images should have the same phash."""
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")

        with tempfile.TemporaryDirectory() as tmpdir:
            img = Image.new("L", (64, 64), color=128)
            path1 = Path(tmpdir) / "img1.jpg"
            path2 = Path(tmpdir) / "img2.jpg"
            img.save(path1)
            img.save(path2)

            h1 = _compute_phash(path1)
            h2 = _compute_phash(path2)

            self.assertIsNotNone(h1)
            self.assertEqual(h1, h2)

    def test_phash_different_images_returns_different_hash(self):
        """Very different images should have different phashes."""
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Solid gray image (uniform → all phash bits identical)
            img1 = Image.new("L", (64, 64), color=128)
            # Checkerboard pattern (alternating bright/dark → very different phash)
            img2 = Image.new("L", (64, 64))
            for x in range(64):
                for y in range(64):
                    img2.putpixel((x, y), 255 if (x + y) % 2 == 0 else 0)

            path1 = Path(tmpdir) / "solid.jpg"
            path2 = Path(tmpdir) / "checker.png"  # Use PNG to avoid JPEG compression artifacts
            img1.save(path1)
            img2.save(path2)

            h1 = _compute_phash(path1)
            h2 = _compute_phash(path2)

            self.assertIsNotNone(h1)
            self.assertIsNotNone(h2)
            self.assertGreater(_hamming_distance(h1, h2), 5)

    def test_dedup_frames_removes_duplicates(self):
        """Dedup should remove near-identical frames."""
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = []
            # Create 5 identical frames
            for i in range(5):
                img = Image.new("L", (64, 64), color=100)
                p = Path(tmpdir) / f"frame_{i:04d}.jpg"
                img.save(p)
                paths.append(p)

            # Different frame: checkerboard (very different phash from solid color)
            img_diff = Image.new("L", (64, 64))
            for x in range(64):
                for y in range(64):
                    img_diff.putpixel((x, y), 255 if (x + y) % 2 == 0 else 0)
            p_diff = Path(tmpdir) / "frame_0005.png"
            img_diff.save(p_diff)
            paths.append(p_diff)

            result = _dedup_frames(paths)

            # Should keep first + the different one
            self.assertLessEqual(len(result), 3)
            self.assertIn(paths[0], result)
            self.assertIn(p_diff, result)

    def test_dedup_empty_list(self):
        self.assertEqual(_dedup_frames([]), [])


class InstagramEdgeFilterTests(unittest.TestCase):
    """Tests for edge-based frame filtering."""

    def test_blank_frame_has_low_edge_density(self):
        """A solid-color image should have very low edge density."""
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")

        with tempfile.TemporaryDirectory() as tmpdir:
            img = Image.new("L", (160, 120), color=128)
            path = Path(tmpdir) / "blank.jpg"
            img.save(path)

            density = _compute_edge_density(path)
            self.assertIsNotNone(density)
            self.assertLess(density, 0.05)

    def test_textured_frame_has_higher_edge_density(self):
        """An image with strong edges should have higher density."""
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")

        with tempfile.TemporaryDirectory() as tmpdir:
            img = Image.new("L", (160, 120))
            # Create stripes pattern (lots of edges)
            for x in range(160):
                for y in range(120):
                    img.putpixel((x, y), 255 if x % 4 < 2 else 0)
            path = Path(tmpdir) / "stripes.jpg"
            img.save(path)

            density = _compute_edge_density(path)
            self.assertIsNotNone(density)
            self.assertGreater(density, 0.10)

    def test_filter_empty_keeps_at_least_one(self):
        """Even if all frames are 'empty', keep at least one."""
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = []
            for i in range(3):
                img = Image.new("L", (160, 120), color=128)
                p = Path(tmpdir) / f"blank_{i}.jpg"
                img.save(p)
                paths.append(p)

            result = _filter_empty_frames(paths)
            self.assertGreaterEqual(len(result), 1)


class InstagramCacheTests(unittest.TestCase):
    """Tests for cache read/write."""

    def test_write_and_read_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            with patch("normalizer.instagram_handler.config.INSTAGRAM_CACHE_DIR", cache_dir):
                with patch("normalizer.instagram_handler.config.INSTAGRAM_DEEP_EXTRACT_ENABLED", True):
                    with patch("normalizer.instagram_handler.config.TRANSCRIPTION_MODEL", "test-model"):
                        with patch("normalizer.instagram_handler.config.INSTAGRAM_VISION_MODEL", "test-vision"):
                            with patch("normalizer.instagram_handler.config.LLM_MODEL", "test-llm"):
                                _write_cache("ABC123", "cached text content")
                                result = _read_cache("ABC123")

            self.assertEqual(result, "cached text content")

    def test_read_cache_returns_none_when_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("normalizer.instagram_handler.config.INSTAGRAM_CACHE_DIR", Path(tmpdir)):
                self.assertIsNone(_read_cache("nonexistent"))

    def test_read_cache_returns_none_for_corrupt_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            (cache_dir / "corrupt.json").write_text("{bad json", encoding="utf-8")
            with patch("normalizer.instagram_handler.config.INSTAGRAM_CACHE_DIR", cache_dir):
                self.assertIsNone(_read_cache("corrupt"))

    def test_read_cache_ignores_different_signature(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            (cache_dir / "ABC123.json").write_text(
                json.dumps(
                    {
                        "post_id": "ABC123",
                        "text": "old cached text",
                        "cache_version": 2,
                        "signature": {"deep_extract_enabled": False},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch("normalizer.instagram_handler.config.INSTAGRAM_CACHE_DIR", cache_dir):
                with patch("normalizer.instagram_handler.config.INSTAGRAM_DEEP_EXTRACT_ENABLED", True):
                    self.assertIsNone(_read_cache("ABC123"))

    def test_deep_extract_failure_does_not_cache_caption_only_fallback(self):
        info = {"description": "Caption", "uploader": "user", "duration": 10}
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            with patch("normalizer.instagram_handler.config.INSTAGRAM_CACHE_DIR", cache_dir):
                with patch("normalizer.instagram_handler.config.INSTAGRAM_DEEP_EXTRACT_ENABLED", True):
                    with patch("normalizer.instagram_handler._get_info_ytdlp", return_value=info):
                        with patch("normalizer.instagram_handler._deep_extract_reel", return_value=None):
                            from normalizer.instagram_handler import extract_instagram_text

                            result = extract_instagram_text("https://www.instagram.com/reel/ABC123/")

            self.assertIn("Caption", result)
            self.assertFalse((cache_dir / "ABC123.json").exists())


class InstagramFallbackTests(unittest.TestCase):
    """Tests for fallback behavior when deep extract is disabled."""

    def test_deep_extract_disabled_uses_caption_only(self):
        """When INSTAGRAM_DEEP_EXTRACT_ENABLED=False, should use caption-only path."""
        info = {
            "description": "Test caption",
            "uploader": "testuser",
            "subtitles": {},
            "automatic_captions": {},
        }

        with patch("normalizer.instagram_handler.config.INSTAGRAM_DEEP_EXTRACT_ENABLED", False):
            with patch("normalizer.instagram_handler._get_info_ytdlp", return_value=info):
                with patch("normalizer.instagram_handler.config.INSTAGRAM_CACHE_DIR", Path(tempfile.mkdtemp())):
                    with patch("normalizer.instagram_handler.config.INSTAGRAM_DEEP_EXTRACT_ENABLED", False):
                        from normalizer.instagram_handler import extract_instagram_text
                        result = extract_instagram_text("https://www.instagram.com/reel/ABC123/")

        self.assertIn("Test caption", result)
        self.assertIn("@testuser", result)
        self.assertIn("[Instagram Reel:", result)
        # Should NOT contain deep extract sections
        self.assertNotIn("[Транскрипция аудио]", result)
        self.assertNotIn("[Текст с экрана", result)

    def test_canonicalize_preserves_normal_url(self):
        url = "https://www.instagram.com/p/ABC123/"
        self.assertEqual(canonicalize_instagram_url(url), url)

    def test_long_reel_uses_unified_review_queue(self):
        info = {"description": "Caption", "uploader": "user", "duration": 999}
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            queue_dir = root / "review_queue"
            cache_dir = root / "instagram_cache"
            queue_dir.mkdir()
            cache_dir.mkdir()
            with patch("normalizer.instagram_handler.config.REVIEW_QUEUE_DIR", queue_dir):
                with patch("normalizer.instagram_handler.config.INSTAGRAM_CACHE_DIR", cache_dir):
                    with patch("normalizer.instagram_handler.config.INSTAGRAM_DEEP_EXTRACT_ENABLED", True):
                        with patch("normalizer.instagram_handler.config.INSTAGRAM_MAX_VIDEO_DURATION_SEC", 180):
                            with patch("normalizer.instagram_handler._get_info_ytdlp", return_value=info):
                                from normalizer.instagram_handler import extract_instagram_text

                                result = extract_instagram_text(
                                    "https://www.instagram.com/reel/ABC123/",
                                    channel_name="Channel",
                                    message_id=42,
                                    message_text="Post text",
                                )

            files = list(queue_dir.glob("*.json"))
            self.assertEqual(len(files), 1)
            payload = json.loads(files[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["review_type"], "instagram_long_reel")
            self.assertEqual(payload["status"], "pending")
            self.assertEqual(payload["channel"], "Channel")
            self.assertEqual(payload["message_id"], 42)
            self.assertIn("очеред", result.lower())
            self.assertFalse((cache_dir / "ABC123.json").exists())
