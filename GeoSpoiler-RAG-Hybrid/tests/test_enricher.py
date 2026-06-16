import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from enricher import pipeline as enricher_pipeline  # noqa: E402
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


class EnrichmentPipelineConcurrencyTests(unittest.TestCase):
    def test_enrich_all_runs_independent_posts_with_bounded_concurrency(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            normalized_dir = root / "normalized"
            enriched_dir = root / "enriched"
            state_dir = root / "state"
            channel_dir = normalized_dir / "Channel"
            channel_dir.mkdir(parents=True)
            state_dir.mkdir()

            for message_id in (1, 2):
                (channel_dir / f"{message_id}.txt").write_text(
                    (
                        "[Канал: Channel | Дата: 2026-01-01 00:00]\n\n"
                        f"Useful post body {message_id} with enough text for enrichment."
                    ),
                    encoding="utf-8",
                )
                (channel_dir / f"{message_id}.meta.json").write_text(
                    json.dumps(
                        {
                            "channel_name": "Channel",
                            "message_id": message_id,
                            "date": "2026-01-01T00:00:00",
                            "post_url": "",
                        }
                    ),
                    encoding="utf-8",
                )

            active = 0
            max_active = 0
            lock = threading.Lock()
            both_started = threading.Event()

            def fake_enrich_single_post(*, msg_id: str, **_kwargs):
                nonlocal active, max_active
                with lock:
                    active += 1
                    max_active = max(max_active, active)
                    if active >= 2:
                        both_started.set()
                try:
                    both_started.wait(0.2)
                    return {
                        "triage": "keep",
                        "summary": f"summary {msg_id}",
                        "content_type": "text",
                    }
                finally:
                    with lock:
                        active -= 1

            with patch.object(enricher_pipeline.config, "NORMALIZED_DIR", normalized_dir):
                with patch.object(enricher_pipeline.config, "ENRICHED_DIR", enriched_dir):
                    with patch.object(enricher_pipeline.config, "ENRICHMENT_CONCURRENCY", 2, create=True):
                        with patch.object(
                            enricher_pipeline,
                            "_PROGRESS_FILE",
                            state_dir / "enrichment_progress.json",
                        ):
                            with patch.object(
                                enricher_pipeline,
                                "_enrich_single_post",
                                side_effect=fake_enrich_single_post,
                            ):
                                with patch.object(enricher_pipeline, "mark_duplicates", return_value=0):
                                    stats = enricher_pipeline.enrich_all(channel_filter="Channel", force=True)

            progress = json.loads(
                (state_dir / "enrichment_progress.json").read_text(encoding="utf-8")
            )
            file_1_exists = (enriched_dir / "Channel" / "1.enriched.json").exists()
            file_2_exists = (enriched_dir / "Channel" / "2.enriched.json").exists()

        self.assertEqual(stats.enriched, 2)
        self.assertGreaterEqual(max_active, 2)
        self.assertTrue(file_1_exists)
        self.assertTrue(file_2_exists)
        self.assertEqual(set(progress["enriched"]), {"Channel/1", "Channel/2"})


if __name__ == "__main__":
    unittest.main()
