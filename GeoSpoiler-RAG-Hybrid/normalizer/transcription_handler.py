"""Native Telegram audio/video transcription via an OpenAI-compatible Whisper API."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

import config
from fetcher.telegram_client import TelegramMedia
from llm_auth import get_openai_api_key

logger = logging.getLogger("geospoiler.normalizer.transcription")


@dataclass
class TranscriptionResult:
    """Result of a native media transcription attempt."""

    status: str
    text: str = ""
    artifact_path: str = ""
    error: str = ""


def transcribe_media(
    item: TelegramMedia,
    channel_name: str,
    message_id: int,
) -> TranscriptionResult:
    """
    Transcribe one downloaded Telegram video/audio/voice file.

    Returns cached artifacts when present. Network calls happen only when
    TRANSCRIPTION_ENABLED=true and a usable API key is configured.
    """
    if item.media_type not in {"video", "audio", "voice"}:
        return TranscriptionResult(status="unsupported_media_type")

    if item.download_status != "downloaded":
        return TranscriptionResult(
            status="skipped",
            error=f"download_status={item.download_status}",
        )

    if not item.file_path:
        return TranscriptionResult(status="skipped", error="missing_file_path")

    artifact_path = _artifact_path(channel_name, message_id, item)
    cached = _read_cached_artifact(artifact_path)
    if cached:
        return cached

    if not config.TRANSCRIPTION_ENABLED:
        return TranscriptionResult(status="disabled")

    api_key = config.TRANSCRIPTION_API_KEY
    if not api_key or api_key == "your-api-key-here":
        return TranscriptionResult(status="disabled", error="missing_api_key")

    media_path = _resolve_media_path(item.file_path)
    if not media_path.exists():
        return TranscriptionResult(status="failed", error=f"file_not_found:{item.file_path}")

    try:
        result = _call_transcription_api(media_path)
    except requests.Timeout:
        result = TranscriptionResult(status="failed", error="timeout")
    except Exception as exc:
        logger.warning("Transcription failed for %s: %s", media_path, exc)
        result = TranscriptionResult(status="failed", error=str(exc))

    if result.status == "transcribed":
        result.artifact_path = str(artifact_path)
        _write_artifact(artifact_path, item, result, media_path)
    return result


def _call_transcription_api(media_path: Path) -> TranscriptionResult:
    headers = {
        "Authorization": (
            "Bearer "
            f"{get_openai_api_key(config.TRANSCRIPTION_API_KEY, config.TRANSCRIPTION_BASE_URL)}"
        )
    }
    data: dict[str, str] = {
        "model": config.TRANSCRIPTION_MODEL,
        "response_format": "json",
    }
    if config.TRANSCRIPTION_LANGUAGE:
        data["language"] = config.TRANSCRIPTION_LANGUAGE

    with media_path.open("rb") as fh:
        response = requests.post(
            f"{config.TRANSCRIPTION_BASE_URL.rstrip('/')}/audio/transcriptions",
            headers=headers,
            data=data,
            files={"file": (media_path.name, fh)},
            timeout=config.TRANSCRIPTION_TIMEOUT_SECONDS,
        )
    response.raise_for_status()
    payload = response.json()
    text = str(payload.get("text") or "").strip()
    if not text:
        return TranscriptionResult(status="failed", error="empty_transcript")
    return TranscriptionResult(status="transcribed", text=text)


def _artifact_path(channel_name: str, message_id: int, item: TelegramMedia) -> Path:
    media_id = item.message_id or message_id
    filename = f"{message_id}_{media_id}_{item.media_type}.json"
    return config.TRANSCRIPTION_DIR / _sanitize(channel_name) / filename


def _read_cached_artifact(path: Path) -> TranscriptionResult | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if payload.get("status") != "transcribed":
        return None
    text = str(payload.get("text") or "").strip()
    if not text:
        return None
    return TranscriptionResult(
        status="transcribed",
        text=text,
        artifact_path=str(path),
    )


def _write_artifact(
    path: Path,
    item: TelegramMedia,
    result: TranscriptionResult,
    media_path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "status": result.status,
        "text": result.text,
        "model": config.TRANSCRIPTION_MODEL,
        "transcribed_at": datetime.now(timezone.utc).isoformat(),
        "media": {
            "media_type": item.media_type,
            "mime_type": item.mime_type,
            "message_id": item.message_id,
            "file_path": item.file_path,
            "resolved_file_path": str(media_path),
        },
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _resolve_media_path(file_path: str) -> Path:
    path = Path(file_path)
    if path.is_absolute():
        return path
    return config.PROJECT_ROOT / path


def _sanitize(name: str) -> str:
    return "".join(c if c.isalnum() or c in " _-" else "_" for c in name).strip()
