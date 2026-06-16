"""Output builders and review queue handoff for Instagram extraction."""

from datetime import datetime

import config
from normalizer.instagram.downloader import _get_subtitles_from_info
from normalizer.review_queue import REVIEW_TYPE_INSTAGRAM_LONG_REEL
from normalizer.review_queue import queue_item as queue_review_item


def build_reel_text(
    url: str,
    caption: str,
    uploader: str,
    transcript: str,
    ocr_text: str,
    summary: str | None,
) -> str:
    parts = [_instagram_header("Reel", url, uploader)]
    parts.append(_trim_caption(caption) if caption else "[Подпись пуста]")

    if transcript:
        parts.append(f"[Транскрипция аудио]\n{transcript}")
    if ocr_text:
        parts.append(f"[Текст с экрана (OCR)]\n{ocr_text}")
    if summary:
        parts.append(f"[Описание ролика]\n{summary}")
    elif not caption.strip() and not transcript and not ocr_text:
        parts.append("[Не удалось извлечь ни аудио, ни текст с кадров]")

    return "\n\n".join(parts)


def build_carousel_text(
    url: str,
    caption: str,
    uploader: str,
    image_descriptions: list[str],
) -> str:
    parts = [_instagram_header("Post", url, uploader)]
    parts.append(_trim_caption(caption) if caption else "[Подпись пуста]")

    total = len(image_descriptions)
    for index, description in enumerate(image_descriptions, 1):
        parts.append(f"[Изображение {index}/{total}]\n{description}")

    return "\n\n".join(parts)


def _queue_long_reel_for_review(
    url: str,
    caption: str,
    uploader: str,
    duration: float,
    *,
    channel_name: str,
    message_id: int,
    message_text: str,
    message_date: datetime | None,
) -> str:
    """Queue a long Reel through the unified manual review queue."""
    result = queue_review_item(
        review_type=REVIEW_TYPE_INSTAGRAM_LONG_REEL,
        channel_name=channel_name,
        message_id=message_id,
        message_text=message_text or caption,
        message_date=message_date,
        url=url,
        reason=f"Duration {duration}s exceeds limit {config.INSTAGRAM_MAX_VIDEO_DURATION_SEC}s",
    )
    parts = [_instagram_header("Reel", url, uploader)]
    if caption:
        parts.append(_trim_caption(caption))
    parts.append(result.placeholder_text)
    return "\n\n".join(parts)


def _caption_only(
    url: str, info: dict, caption: str, uploader: str, is_reel: bool
) -> str:
    """Original extraction: caption + subtitles from yt-dlp metadata."""
    subtitles = _get_subtitles_from_info(url, info)

    post_type = "Reel" if is_reel else "Post"
    parts = [_instagram_header(post_type, url, uploader)]
    parts.append(_trim_caption(caption) if caption else "[Подпись пуста]")

    if subtitles:
        parts.append(f"[Субтитры / текст из видео]\n{subtitles}")
    elif is_reel:
        parts.append(
            "[Текст из самого видео недоступен: Instagram не отдал субтитры, "
            "сохранена только подпись.]"
        )

    return "\n\n".join(parts)


def _instagram_header(post_type: str, url: str, uploader: str) -> str:
    header = f"[Instagram {post_type}: {url}"
    if uploader:
        header += f" - @{uploader}"
    return header + "]"


def _trim_caption(caption: str) -> str:
    return caption[:3000] + "..." if len(caption) > 3000 else caption
