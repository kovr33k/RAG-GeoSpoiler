"""Instagram extraction pipeline orchestration."""

import logging
import shutil
from datetime import datetime

import config
from normalizer.instagram.audio import _extract_audio, _transcribe_audio
from normalizer.instagram.builder import (
    _caption_only,
    _queue_long_reel_for_review,
    build_carousel_text,
    build_reel_text,
)
from normalizer.instagram.cache import _is_review_queue_placeholder, _read_cache, _write_cache
from normalizer.instagram.downloader import (
    _download_carousel_images,
    _download_video,
    _extract_post_id,
    _get_info_ytdlp,
    canonicalize_instagram_url,
)
from normalizer.instagram.frames import _dedup_frames, _extract_frames, _filter_empty_frames
from normalizer.instagram.vision import _describe_single_image, _ocr_frames_batched, _summarize_reel
from normalizer.review_queue import REVIEW_TYPE_EXTERNAL_LINK
from normalizer.review_queue import queue_item as queue_review_item

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
    Extract text content from an Instagram post/Reel.
    Returns formatted text with caption, transcription, OCR, and summary.
    """
    canonical_url = canonicalize_instagram_url(url)
    post_id = _extract_post_id(canonical_url)

    # Check cache first
    if post_id:
        cached = _read_cache(post_id)
        if cached:
            logger.info(f"  Instagram cache hit: {post_id}")
            return cached

    # Get metadata from yt-dlp
    info = _get_info_ytdlp(canonical_url)
    if not info:
        logger.warning(f"Could not extract Instagram content from {canonical_url}")
        return _queue_instagram_extraction_failure(
            canonical_url,
            channel_name=channel_name,
            message_id=message_id,
            message_text=message_text,
            message_date=message_date,
            reason=(
                "Instagram media metadata unavailable to yt-dlp; the page may still be "
                "visible in a browser (empty media response or extractor access block)"
            ),
        )

    caption = (info.get("description") or info.get("title") or "").strip()
    uploader = info.get("uploader") or info.get("channel") or ""
    duration = info.get("duration") or 0
    is_reel = "/reel/" in canonical_url.lower()

    # Deep extract path
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
            return _queue_instagram_extraction_failure(
                canonical_url,
                channel_name=channel_name,
                message_id=message_id,
                message_text=message_text,
                message_date=message_date,
                reason="Instagram Reel deep extraction failed",
            )
        else:
            result = _deep_extract_carousel(canonical_url, info, caption, uploader)
            if result:
                if post_id:
                    _write_cache(post_id, result)
                return result
            return _queue_instagram_extraction_failure(
                canonical_url,
                channel_name=channel_name,
                message_id=message_id,
                message_text=message_text,
                message_date=message_date,
                reason="Instagram carousel extraction failed",
                post_type="Post",
            )

    # Fallback: caption-only (original behavior)
    result = _caption_only(canonical_url, info, caption, uploader, is_reel)
    if post_id and not config.INSTAGRAM_DEEP_EXTRACT_ENABLED:
        _write_cache(post_id, result)
    return result


def _queue_instagram_extraction_failure(
    url: str,
    *,
    channel_name: str,
    message_id: int,
    message_text: str,
    message_date: datetime | None,
    reason: str,
    post_type: str = "Reel",
) -> str:
    """Make source-access failures visible without pretending caption-only success."""
    review = queue_review_item(
        review_type=REVIEW_TYPE_EXTERNAL_LINK,
        channel_name=channel_name,
        message_id=message_id,
        message_text=message_text,
        message_date=message_date,
        url=url,
        reason=reason,
        reopen_processed=True,
    )
    return f"[Instagram {post_type}: {url}]\n{review.placeholder_text}"

def _deep_extract_reel(
    url: str,
    info: dict,
    caption: str,
    uploader: str,
    duration: float,
    *,
    channel_name: str,
    message_id: int,
    message_text: str,
    message_date: datetime | None,
) -> str | None:
    """Full pipeline: video → audio transcription + frame OCR → LLM summary."""

    # Check duration limits — queue for manual review if too long
    if duration > config.INSTAGRAM_MAX_VIDEO_DURATION_SEC:
        logger.info(
            f"Instagram Reel longer than {config.INSTAGRAM_MAX_VIDEO_DURATION_SEC}s "
            f"({duration}s), queuing for review: {url}"
        )
        return _queue_long_reel_for_review(
            url,
            caption,
            uploader,
            duration,
            channel_name=channel_name,
            message_id=message_id,
            message_text=message_text,
            message_date=message_date,
        )

    work_dir = config.MEDIA_CACHE_DIR / "instagram_work"
    work_dir.mkdir(parents=True, exist_ok=True)
    post_id = _extract_post_id(url) or "unknown"

    video_path = None
    audio_path = None
    frames_dir = None

    try:
        # Step 1: Download video
        video_path = _download_video(url, work_dir, post_id)
        if not video_path:
            logger.warning(f"Could not download Instagram video: {url}")
            return None

        # Check file size
        size_mb = video_path.stat().st_size / (1024 * 1024)
        if size_mb > config.INSTAGRAM_MAX_VIDEO_SIZE_MB:
            logger.warning(f"Instagram video too large ({size_mb:.1f}MB), skipping deep extract")
            return None

        # Step 2: Extract audio and transcribe
        transcript = ""
        audio_path = _extract_audio(video_path, work_dir, post_id)
        if audio_path:
            transcript = _transcribe_audio(audio_path) or ""

        # Step 3: Extract and process frames
        frames_dir = work_dir / f"{post_id}_frames"
        frames_dir.mkdir(exist_ok=True)
        raw_frames = _extract_frames(video_path, frames_dir, config.INSTAGRAM_FRAME_INTERVAL_SEC)

        ocr_texts = []
        if raw_frames:
            # Deduplicate
            unique_frames = _dedup_frames(raw_frames)
            logger.info(
                f"  Frames: {len(raw_frames)} extracted → {len(unique_frames)} after dedup"
            )

            # Filter empty
            content_frames = _filter_empty_frames(unique_frames)
            logger.info(
                f"  Frames: {len(unique_frames)} unique → {len(content_frames)} with content"
            )

            # Batched OCR
            if content_frames:
                ocr_texts = _ocr_frames_batched(
                    content_frames, config.INSTAGRAM_FRAME_BATCH_SIZE
                )

        ocr_combined = "\n".join(t for t in ocr_texts if t)
        summary = None
        if transcript or ocr_combined:
            summary = _summarize_reel(caption, transcript, ocr_combined, uploader)

        return build_reel_text(url, caption, uploader, transcript, ocr_combined, summary)

    except Exception as e:
        logger.error(f"Instagram deep extract error for {url}: {e}", exc_info=True)
        return None
    finally:
        # Cleanup
        if video_path and video_path.exists():
            video_path.unlink(missing_ok=True)
        if audio_path and audio_path.exists():
            audio_path.unlink(missing_ok=True)
        if frames_dir and frames_dir.exists():
            shutil.rmtree(frames_dir, ignore_errors=True)


# ─────────────────────── Deep Extract: Carousel ───────────────────────

def _deep_extract_carousel(
    url: str, info: dict, caption: str, uploader: str
) -> str | None:
    """Download carousel images and analyze each with Vision API."""

    work_dir = config.MEDIA_CACHE_DIR / "instagram_work"
    work_dir.mkdir(parents=True, exist_ok=True)
    post_id = _extract_post_id(url) or "unknown"
    carousel_dir = work_dir / f"{post_id}_carousel"
    carousel_dir.mkdir(exist_ok=True)

    try:
        image_paths = _download_carousel_images(url, carousel_dir, post_id, info)
        if not image_paths:
            logger.info(f"No carousel images downloaded for {url}")
            return None

        image_descriptions = [
            _describe_single_image(img_path) for img_path in image_paths
        ]
        return build_carousel_text(url, caption, uploader, image_descriptions)

    except Exception as e:
        logger.error(f"Instagram carousel extract error for {url}: {e}", exc_info=True)
        return None
    finally:
        if carousel_dir.exists():
            shutil.rmtree(carousel_dir, ignore_errors=True)
