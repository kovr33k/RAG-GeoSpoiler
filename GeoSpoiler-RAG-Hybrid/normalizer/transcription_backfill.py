"""Controlled backfill for native Telegram media transcripts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import config
from fetcher.telegram_client import TelegramMedia
from normalizer.transcription_handler import TranscriptionResult, transcribe_media


@dataclass
class BackfillItemResult:
    """One media item considered by the transcription backfill."""

    normalized_file: str
    media_type: str
    message_id: int
    status: str
    artifact_path: str = ""
    error: str = ""
    updated: bool = False


@dataclass
class BackfillStats:
    """Summary of a controlled transcription backfill run."""

    candidates_seen: int = 0
    attempted: int = 0
    transcribed: int = 0
    cached: int = 0
    disabled: int = 0
    skipped: int = 0
    failed: int = 0
    normalized_updated: int = 0
    dry_run: bool = False
    items: list[BackfillItemResult] = field(default_factory=list)


def backfill_transcripts(
    normalized_dir: Path | None = None,
    limit: int = 3,
    channel: str | None = None,
    media_type: str | None = None,
    dry_run: bool = False,
) -> BackfillStats:
    """
    Transcribe a small, controlled batch of previously captured native media.

    The default limit is intentionally small. This function updates normalized
    text files only after a transcript is available from the handler or cache.
    """
    normalized_dir = normalized_dir or config.NORMALIZED_DIR
    limit = max(0, int(limit))
    wanted_type = (media_type or "").strip().lower()
    wanted_channel = (channel or "").strip().casefold()
    stats = BackfillStats(dry_run=dry_run)

    for candidate in _iter_candidates(normalized_dir):
        if wanted_channel and candidate["channel_name"].casefold() != wanted_channel:
            continue
        item: TelegramMedia = candidate["media"]
        if wanted_type and item.media_type != wanted_type:
            continue
        if limit and stats.attempted >= limit:
            break

        stats.candidates_seen += 1
        stats.attempted += 1
        normalized_path = candidate["normalized_path"]

        if dry_run:
            result = TranscriptionResult(status="dry_run")
        else:
            result = transcribe_media(
                item,
                candidate["channel_name"],
                candidate["message_id"],
            )

        updated = False
        if result.status == "transcribed":
            if result.artifact_path and Path(result.artifact_path).exists():
                stats.cached += int(_transcript_already_present(normalized_path, result))
            stats.transcribed += 1
            updated = _append_transcript_if_missing(normalized_path, item, result)
            if updated:
                _update_meta(candidate["meta_path"], item, result)
                stats.normalized_updated += 1
        elif result.status == "disabled":
            stats.disabled += 1
        elif result.status in {"skipped", "unsupported_media_type", "dry_run"}:
            stats.skipped += 1
        else:
            stats.failed += 1

        stats.items.append(
            BackfillItemResult(
                normalized_file=str(normalized_path),
                media_type=item.media_type,
                message_id=item.message_id,
                status=result.status,
                artifact_path=result.artifact_path,
                error=result.error,
                updated=updated,
            )
        )

    return stats


def _iter_candidates(normalized_dir: Path) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if not normalized_dir.exists():
        return candidates

    for meta_path in sorted(normalized_dir.rglob("*.meta.json")):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        normalized_path = meta_path.with_suffix("").with_suffix(".txt")
        if not normalized_path.exists():
            continue
        for payload in meta.get("media") or []:
            media = _media_from_payload(payload)
            if media.media_type not in {"video", "audio", "voice"}:
                continue
            if media.download_status != "downloaded":
                continue
            if not media.file_path:
                continue
            candidates.append(
                {
                    "meta_path": meta_path,
                    "normalized_path": normalized_path,
                    "channel_name": str(meta.get("channel_name") or meta_path.parent.name),
                    "message_id": int(meta.get("message_id") or media.message_id or 0),
                    "media": media,
                }
            )
    return candidates


def _media_from_payload(payload: dict[str, Any]) -> TelegramMedia:
    return TelegramMedia(
        media_type=str(payload.get("media_type") or ""),
        mime_type=str(payload.get("mime_type") or ""),
        message_id=int(payload.get("message_id") or 0),
        file_path=str(payload.get("file_path") or ""),
        download_status=str(payload.get("download_status") or "not_attempted"),
        error=str(payload.get("error") or ""),
    )


def _append_transcript_if_missing(
    normalized_path: Path,
    item: TelegramMedia,
    result: TranscriptionResult,
) -> bool:
    text = normalized_path.read_text(encoding="utf-8")
    if _transcript_already_present(normalized_path, result):
        return False
    section = _format_transcript_section(item, result)
    normalized_path.write_text(f"{text.rstrip()}\n\n{section}\n", encoding="utf-8")
    return True


def _transcript_already_present(
    normalized_path: Path,
    result: TranscriptionResult,
) -> bool:
    text = normalized_path.read_text(encoding="utf-8")
    if result.artifact_path and result.artifact_path in text:
        return True
    return bool(result.text and result.text.strip() in text)


def _format_transcript_section(item: TelegramMedia, result: TranscriptionResult) -> str:
    label = "Transcript"
    if item.media_type == "voice":
        label = "Voice transcript"
    elif item.media_type == "video":
        label = "Video transcript"
    artifact = f" | artifact={result.artifact_path}" if result.artifact_path else ""
    return f"[{label}{artifact}]\n{result.text.strip()}"


def _update_meta(meta_path: Path, item: TelegramMedia, result: TranscriptionResult) -> None:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    transcript = {
        "media_type": item.media_type,
        "message_id": item.message_id,
        "source_file_path": item.file_path,
        "status": result.status,
        "artifact_path": result.artifact_path,
        "error": result.error,
    }

    transcriptions = [
        existing
        for existing in (meta.get("transcriptions") or [])
        if not (
            existing.get("message_id") == item.message_id
            and existing.get("source_file_path") == item.file_path
        )
    ]
    transcriptions.append(transcript)
    meta["transcriptions"] = transcriptions

    for media in meta.get("media") or []:
        if media.get("message_id") == item.message_id and media.get("file_path") == item.file_path:
            media["transcription_status"] = result.status
            media["transcript_path"] = result.artifact_path
            media["transcription_error"] = result.error
            break

    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
