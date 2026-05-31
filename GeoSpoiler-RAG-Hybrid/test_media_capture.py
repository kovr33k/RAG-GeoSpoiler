import json
import asyncio
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

from fetcher import telegram_client as fetcher_module  # noqa: E402
from fetcher.telegram_client import (  # noqa: E402
    TelegramMedia,
    TelegramFetcher,
    TelegramMessage,
    _document_media_type,
)
from normalizer import pipeline  # noqa: E402
from normalizer.transcription_handler import TranscriptionResult  # noqa: E402


class MediaCaptureTests(unittest.TestCase):
    def test_document_media_type_detects_video_audio_and_voice(self):
        self.assertEqual(
            _document_media_type(SimpleNamespace(mime_type="video/mp4", attributes=[])),
            "video",
        )
        self.assertEqual(
            _document_media_type(SimpleNamespace(mime_type="audio/mpeg", attributes=[])),
            "audio",
        )
        self.assertEqual(
            _document_media_type(
                SimpleNamespace(
                    mime_type="audio/ogg",
                    attributes=[SimpleNamespace(voice=True)],
                )
            ),
            "voice",
        )

    def test_download_native_media_records_path_and_status(self):
        class FakeMessage:
            id = 301
            file = SimpleNamespace(size=123)
            media = None

            async def download_media(self, file):
                target = Path(file).with_suffix(".mp4")
                target.write_text("fake media", encoding="utf-8")
                return str(target)

        with tempfile.TemporaryDirectory() as tmpdir:
            media_dir = Path(tmpdir) / "media_cache"
            fetcher = TelegramFetcher.__new__(TelegramFetcher)

            with patch.object(fetcher_module.config, "MEDIA_CACHE_DIR", media_dir):
                with patch.object(fetcher_module.config, "MEDIA_CAPTURE_ENABLED", True):
                    with patch.object(fetcher_module.config, "MEDIA_CAPTURE_MAX_BYTES", 0):
                        record = asyncio.run(
                            fetcher._download_native_media(
                                FakeMessage(),
                                {"title": "Channel"},
                                media_type="video",
                                mime_type="video/mp4",
                            )
                        )

            self.assertEqual(record.download_status, "downloaded")
            self.assertEqual(record.media_type, "video")
            self.assertEqual(record.mime_type, "video/mp4")
            self.assertTrue(Path(record.file_path).is_file())
            self.assertIn("video", Path(record.file_path).parts)

    def test_normalized_metadata_keeps_native_media_path_and_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            normalized_dir = Path(tmpdir) / "normalized"
            msg = TelegramMessage(
                channel_name="Channel",
                channel_id=1,
                channel_username="channel",
                message_id=201,
                date=datetime(2026, 5, 27),
                text="",
                has_video=True,
                media=[
                    TelegramMedia(
                        media_type="video",
                        mime_type="video/mp4",
                        message_id=201,
                        file_path="media_cache/Channel/video/msg_201.mp4",
                        download_status="downloaded",
                    )
                ],
            )

            with patch.object(pipeline.config, "NORMALIZED_DIR", normalized_dir):
                with patch.object(
                    pipeline,
                    "translate_to_russian_if_needed",
                    side_effect=lambda text: text,
                ):
                    result = pipeline.normalize_message(msg)

            self.assertEqual(result.status, "normalized")
            self.assertIn("status=downloaded", result.text)
            self.assertIn("media_cache/Channel/video/msg_201.mp4", result.text)

            meta = json.loads(Path(result.filepath).with_suffix(".meta.json").read_text(encoding="utf-8"))
            self.assertTrue(meta["has_video"])
            self.assertEqual(meta["media_count"], 1)
            self.assertEqual(meta["media"][0]["media_type"], "video")
            self.assertEqual(meta["media"][0]["download_status"], "downloaded")
            self.assertEqual(meta["native_media_paths"], ["media_cache/Channel/video/msg_201.mp4"])

    def test_normalized_text_includes_native_media_transcript(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            normalized_dir = Path(tmpdir) / "normalized"
            msg = TelegramMessage(
                channel_name="Channel",
                channel_id=1,
                channel_username="channel",
                message_id=202,
                date=datetime(2026, 5, 28),
                text="",
                has_voice=True,
                media=[
                    TelegramMedia(
                        media_type="voice",
                        mime_type="audio/ogg",
                        message_id=202,
                        file_path="media_cache/Channel/voice/msg_202.ogg",
                        download_status="downloaded",
                    )
                ],
            )

            with patch.object(pipeline.config, "NORMALIZED_DIR", normalized_dir):
                with patch.object(
                    pipeline,
                    "translate_to_russian_if_needed",
                    side_effect=lambda text: text,
                ):
                    with patch.object(
                        pipeline,
                        "transcribe_media",
                        return_value=TranscriptionResult(
                            status="transcribed",
                            text="spoken evidence from voice message",
                            artifact_path="output/transcripts/Channel/202_202_voice.json",
                        ),
                    ):
                        result = pipeline.normalize_message(msg)

            self.assertEqual(result.status, "normalized")
            self.assertIn("[Voice transcript", result.text)
            self.assertIn("spoken evidence from voice message", result.text)

            meta = json.loads(Path(result.filepath).with_suffix(".meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["transcriptions"][0]["status"], "transcribed")
            self.assertEqual(meta["media"][0]["transcription_status"], "transcribed")
            self.assertEqual(
                meta["media"][0]["transcript_path"],
                "output/transcripts/Channel/202_202_voice.json",
            )


if __name__ == "__main__":
    unittest.main()
