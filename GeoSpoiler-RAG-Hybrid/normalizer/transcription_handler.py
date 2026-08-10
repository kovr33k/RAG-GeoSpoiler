"""Native Telegram audio/video transcription through OpenRouter audio APIs."""

from __future__ import annotations

import base64
import json
import logging
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
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
    model: str = ""


class TranscriptionRequestError(RuntimeError):
    """An HTTP/API contract error that may be eligible for the STT fallback."""

    def __init__(self, endpoint: str, status_code: int, detail: str) -> None:
        self.endpoint = endpoint
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"{endpoint} returned HTTP {status_code}: {detail}")


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
        result = _call_transcription_api(media_path, item.media_type)
    except requests.Timeout:
        result = TranscriptionResult(status="failed", error="timeout")
    except Exception as exc:
        logger.warning("Transcription failed for %s: %s", media_path, exc)
        result = TranscriptionResult(status="failed", error=str(exc))

    if result.status == "transcribed":
        result.artifact_path = str(artifact_path)
        _write_artifact(artifact_path, item, result, media_path)
    return result


def _call_transcription_api(media_path: Path, media_type: str = "") -> TranscriptionResult:
    """Transcribe native media using OpenRouter's actual audio contracts.

    Gemini-class models accept audio through ``chat/completions`` and an
    ``input_audio`` content part. OpenRouter's dedicated transcription route
    expects a base64 JSON body and a transcription-capable model, so it is used
    only as a controlled fallback.
    """
    with _prepared_audio(media_path, media_type) as audio_path:
        try:
            return _call_chat_audio(audio_path)
        except TranscriptionRequestError as primary_error:
            if primary_error.status_code not in {400, 404, 415, 422}:
                raise
            logger.warning(
                "Primary OpenRouter audio route failed; trying STT fallback: %s",
                primary_error,
            )
            try:
                return _call_stt_audio(audio_path)
            except TranscriptionRequestError as fallback_error:
                raise TranscriptionRequestError(
                    "chat/completions + audio/transcriptions",
                    fallback_error.status_code,
                    f"primary={primary_error.detail}; fallback={fallback_error.detail}",
                ) from fallback_error


def _call_chat_audio(audio_path: Path) -> TranscriptionResult:
    endpoint = f"{config.TRANSCRIPTION_BASE_URL.rstrip('/')}/chat/completions"
    payload = {
        "model": config.TRANSCRIPTION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": _audio_base64(audio_path),
                            "format": _audio_format(audio_path),
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Транскрибируй это аудио дословно на русском языке. "
                            "Верни только текст транскрипции, без комментариев. "
                            "Если в аудио только музыка без речи, верни: [только музыка]"
                        ),
                    },
                ],
            }
        ],
        "max_tokens": 16000,
    }
    response = requests.post(
        endpoint,
        headers=_json_headers(),
        json=payload,
        timeout=config.TRANSCRIPTION_TIMEOUT_SECONDS,
    )
    _check_response(response, endpoint)
    response_payload = response.json()
    content = response_payload.get("choices", [{}])[0].get("message", {}).get("content")
    text = _message_text(content)
    if text.lower() in {"[только музыка]", "[only music]"}:
        return TranscriptionResult(
            status="no_speech",
            error="music_only",
            model=config.TRANSCRIPTION_MODEL,
        )
    if not text:
        return TranscriptionResult(
            status="failed",
            error="empty_transcript",
            model=config.TRANSCRIPTION_MODEL,
        )
    return TranscriptionResult(
        status="transcribed",
        text=text,
        model=config.TRANSCRIPTION_MODEL,
    )


def _call_stt_audio(audio_path: Path) -> TranscriptionResult:
    endpoint = f"{config.TRANSCRIPTION_BASE_URL.rstrip('/')}/audio/transcriptions"
    payload: dict[str, Any] = {
        "model": config.TRANSCRIPTION_STT_MODEL,
        "input_audio": {
            "data": _audio_base64(audio_path),
            "format": _audio_format(audio_path),
        },
    }
    if config.TRANSCRIPTION_LANGUAGE:
        payload["language"] = config.TRANSCRIPTION_LANGUAGE

    response = requests.post(
        endpoint,
        headers=_json_headers(),
        json=payload,
        timeout=config.TRANSCRIPTION_TIMEOUT_SECONDS,
    )
    _check_response(response, endpoint)
    response_payload = response.json()
    text = str(response_payload.get("text") or "").strip()
    if not text:
        return TranscriptionResult(
            status="failed",
            error="empty_transcript",
            model=config.TRANSCRIPTION_STT_MODEL,
        )
    return TranscriptionResult(
        status="transcribed",
        text=text,
        model=config.TRANSCRIPTION_STT_MODEL,
    )


def _json_headers() -> dict[str, str]:
    return {
        "Authorization": (
            "Bearer "
            f"{get_openai_api_key(config.TRANSCRIPTION_API_KEY, config.TRANSCRIPTION_BASE_URL)}"
        ),
        "Content-Type": "application/json",
    }


def _check_response(response: requests.Response, endpoint: str) -> None:
    if response.ok:
        return
    detail = (response.text or "").strip().replace("\n", " ")[:500] or "no response body"
    logger.warning("OpenRouter transcription HTTP %s at %s: %s", response.status_code, endpoint, detail)
    raise TranscriptionRequestError(endpoint, response.status_code, detail)


def _message_text(content: Any) -> str:
    if isinstance(content, list):
        return " ".join(
            str(part.get("text") or "").strip()
            for part in content
            if isinstance(part, dict) and part.get("text")
        ).strip()
    return str(content or "").strip()


def _audio_base64(audio_path: Path) -> str:
    return base64.b64encode(audio_path.read_bytes()).decode("ascii")


def _audio_format(audio_path: Path) -> str:
    suffix = audio_path.suffix.lower().lstrip(".")
    return {"oga": "ogg", "opus": "ogg"}.get(suffix, suffix or "mp3")


@contextmanager
def _prepared_audio(media_path: Path, media_type: str = ""):
    """Yield an audio file; extract a compact mp3 when the source is video."""
    is_video = media_type == "video" or media_path.suffix.lower() in {
        ".avi",
        ".m4v",
        ".mkv",
        ".mov",
        ".mp4",
        ".mpeg",
        ".mpg",
        ".webm",
    }
    if not is_video:
        yield media_path
        return

    with tempfile.TemporaryDirectory(prefix="geospoiler-transcription-") as temp_dir:
        audio_path = Path(temp_dir) / f"{media_path.stem}.mp3"
        try:
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(media_path),
                    "-vn",
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    "-b:a",
                    "48k",
                    str(audio_path),
                ],
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"audio_extract_timeout:{media_path}") from exc
        except FileNotFoundError as exc:
            raise RuntimeError("audio_extract_failed:ffmpeg_not_found") from exc

        if result.returncode != 0 or not audio_path.exists():
            detail = (result.stderr or "ffmpeg returned no details").strip().splitlines()[-1][:300]
            raise RuntimeError(f"audio_extract_failed:{detail}")
        yield audio_path


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
        model=str(payload.get("model") or ""),
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
        "model": result.model or config.TRANSCRIPTION_MODEL,
        "transcribed_at": datetime.now(UTC).isoformat(),
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
    if path.is_absolute() and path.exists():
        return path
    if path.is_absolute():
        # Older normalized sidecars may contain an absolute path from a
        # previous checkout (for example C:\\WikiRag). Re-anchor only paths
        # whose media_cache suffix exists in the active checkout.
        parts = list(path.parts)
        try:
            cache_index = next(i for i, part in enumerate(parts) if part.casefold() == "media_cache")
        except StopIteration:
            return path
        candidate = config.MEDIA_CACHE_DIR.joinpath(*parts[cache_index + 1 :])
        if candidate.exists():
            return candidate
        return path
    return config.PROJECT_ROOT / path


def _sanitize(name: str) -> str:
    return "".join(c if c.isalnum() or c in " _-" else "_" for c in name).strip()
