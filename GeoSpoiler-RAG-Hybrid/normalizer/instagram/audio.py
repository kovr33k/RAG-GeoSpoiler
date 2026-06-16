"""Audio extraction and transcription helpers for Instagram Reels."""

import base64
import logging
import subprocess
from pathlib import Path

import requests

import config
from llm_auth import get_openai_api_key

logger = logging.getLogger("geospoiler.normalizer.instagram")

def _extract_audio(video_path: Path, work_dir: Path, post_id: str) -> Path | None:
    """Extract audio from video as mono 48kbps mp3."""
    audio_path = work_dir / f"{post_id}_audio.mp3"
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-ac", "1",
                "-b:a", "48k",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        logger.warning(f"ffmpeg audio extraction timeout for {video_path}")
        return None
    except FileNotFoundError:
        logger.error("ffmpeg not found")
        return None

    return audio_path if audio_path.exists() else None

def _transcribe_audio(audio_path: Path) -> str | None:
    """Transcribe audio via Gemini 2.5 Flash Lite (chat-completions)."""
    api_key = config.TRANSCRIPTION_API_KEY
    if not api_key or api_key == "your-api-key-here":
        return None

    audio_b64 = base64.b64encode(audio_path.read_bytes()).decode("utf-8")
    base_url = config.TRANSCRIPTION_BASE_URL.rstrip("/")
    headers = {
        "Authorization": f"Bearer {get_openai_api_key(api_key, base_url)}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json={
                "model": config.TRANSCRIPTION_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_audio",
                                "input_audio": {"data": audio_b64, "format": "mp3"},
                            },
                            {
                                "type": "text",
                                "text": (
                                    "Транскрибируй это аудио дословно на русском языке. "
                                    "Верни только текст транскрипции, без комментариев. "
                                    "Если аудио содержит только музыку без речи, верни: [только музыка]"
                                ),
                            },
                        ],
                    }
                ],
                "max_tokens": 16000,
            },
            timeout=config.TRANSCRIPTION_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        text = str(payload["choices"][0]["message"].get("content") or "").strip()

        # Skip music-only transcripts
        if text.lower() in ("[только музыка]", "[only music]", ""):
            logger.info("  Instagram audio: music only, no speech")
            return None

        return text if text else None

    except requests.Timeout:
        logger.warning(f"Transcription API timeout for Instagram audio {audio_path}")
    except Exception as exc:
        logger.warning(f"Transcription failed for Instagram audio: {exc}")
    return None


# ─────────────────────── Frame extraction & processing ───────────────────────
