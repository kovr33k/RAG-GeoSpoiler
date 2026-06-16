"""Compatibility wrapper for Instagram normalization helpers.

The implementation lives in :mod:`normalizer.instagram`; this module keeps the
legacy import path stable for the normalizer pipeline, scripts, and tests.
"""

import logging
from datetime import datetime

import config
from normalizer.instagram.audio import _extract_audio, _transcribe_audio
from normalizer.instagram.cache import (
    _cache_signature,
    _is_review_queue_placeholder,
    _read_cache,
    _write_cache,
)
from normalizer.instagram.downloader import (
    _download_carousel_images,
    _download_video,
    _extract_post_id,
    _get_info_ytdlp,
    _get_subtitles_from_info,
    _srt_to_text,
    canonicalize_instagram_url,
)
from normalizer.instagram.frames import (
    _compute_edge_density,
    _compute_phash,
    _dedup_frames,
    _extract_frames,
    _filter_empty_frames,
    _hamming_distance,
)
from normalizer.instagram.pipeline import (
    _caption_only,
    _deep_extract_carousel,
    _deep_extract_reel,
    _queue_long_reel_for_review,
)
from normalizer.instagram.vision import (
    _describe_single_image,
    _ocr_frames_batched,
    _ocr_single_batch,
    _summarize_reel,
)

logger = logging.getLogger("geospoiler.normalizer.instagram")


def extract_instagram_text(
    url: str,
    *,
    channel_name: str = "instagram",
    message_id: int = 0,
    message_text: str = "",
    message_date: datetime | None = None,
) -> str:
    """
    Compatibility entrypoint for legacy monkeypatches on this module.

    The heavy implementation lives under ``normalizer.instagram``; this wrapper
    intentionally resolves helpers from its own globals so existing tests and
    scripts that patch ``normalizer.instagram_handler._get_info_ytdlp`` keep
    affecting the public extraction path.
    """
    canonical_url = canonicalize_instagram_url(url)
    post_id = _extract_post_id(canonical_url)

    if post_id:
        cached = _read_cache(post_id)
        if cached:
            logger.info(f"  Instagram cache hit: {post_id}")
            return cached

    info = _get_info_ytdlp(canonical_url)
    if not info:
        logger.warning(f"Could not extract Instagram content from {canonical_url}")
        return (
            f"[Instagram: {canonical_url}]\n"
            "[Содержание не удалось извлечь - пост может быть приватным]"
        )

    caption = (info.get("description") or info.get("title") or "").strip()
    uploader = info.get("uploader") or info.get("channel") or ""
    duration = info.get("duration") or 0
    is_reel = "/reel/" in canonical_url.lower()

    if config.INSTAGRAM_DEEP_EXTRACT_ENABLED:
        if is_reel:
            result = _deep_extract_reel(
                canonical_url,
                info,
                caption,
                uploader,
                duration,
                channel_name=channel_name,
                message_id=message_id,
                message_text=message_text,
                message_date=message_date,
            )
            if result:
                if post_id and not _is_review_queue_placeholder(result):
                    _write_cache(post_id, result)
                return result
        else:
            result = _deep_extract_carousel(canonical_url, info, caption, uploader)
            if result:
                if post_id:
                    _write_cache(post_id, result)
                return result

    result = _caption_only(canonical_url, info, caption, uploader, is_reel)
    if post_id and not config.INSTAGRAM_DEEP_EXTRACT_ENABLED:
        _write_cache(post_id, result)
    return result


__all__ = [
    "_cache_signature",
    "_caption_only",
    "_compute_edge_density",
    "_compute_phash",
    "_dedup_frames",
    "_deep_extract_carousel",
    "_deep_extract_reel",
    "_describe_single_image",
    "_download_carousel_images",
    "_download_video",
    "_extract_audio",
    "_extract_frames",
    "_extract_post_id",
    "_filter_empty_frames",
    "_get_info_ytdlp",
    "_get_subtitles_from_info",
    "_hamming_distance",
    "_is_review_queue_placeholder",
    "_ocr_frames_batched",
    "_ocr_single_batch",
    "_queue_long_reel_for_review",
    "_read_cache",
    "_srt_to_text",
    "_summarize_reel",
    "_transcribe_audio",
    "_write_cache",
    "canonicalize_instagram_url",
    "config",
    "extract_instagram_text",
]
