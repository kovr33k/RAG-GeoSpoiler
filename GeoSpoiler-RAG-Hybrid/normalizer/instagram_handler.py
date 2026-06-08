"""
Instagram Handler — deep extraction from Instagram Reels and carousel posts.

Strategy:
1. Normalize archived kkinstagram URLs to canonical www.instagram.com
2. Check cache — skip API calls on re-runs
3. For Reels:
   a. Download video via yt-dlp
   b. Extract audio → transcribe via Gemini 2.5 Flash Lite (chat-completions)
   c. Extract frames → dedup (phash) → filter empty → batched OCR (MiMo-V2.5)
   d. Generate LLM summary (DeepSeek V4 Flash)
4. For Carousel posts (/p/):
   a. Download images via yt-dlp
   b. Vision analysis via MiMo-V2.5
5. Fallback: caption-only extraction when deep extract is disabled or fails
"""

import base64
import json
import logging
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import requests

import config
from llm_auth import get_openai_api_key
from normalizer.review_queue import REVIEW_TYPE_INSTAGRAM_LONG_REEL
from normalizer.review_queue import queue_item as queue_review_item

logger = logging.getLogger("geospoiler.normalizer.instagram")
_INSTAGRAM_CACHE_VERSION = 2

# ─────────────────────── Public API ───────────────────────


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
        return (
            f"[Instagram: {canonical_url}]\n"
            "[Содержание не удалось извлечь - пост может быть приватным]"
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
        else:
            result = _deep_extract_carousel(canonical_url, info, caption, uploader)
            if result:
                if post_id:
                    _write_cache(post_id, result)
                return result

    # Fallback: caption-only (original behavior)
    result = _caption_only(canonical_url, info, caption, uploader, is_reel)
    if post_id and not config.INSTAGRAM_DEEP_EXTRACT_ENABLED:
        _write_cache(post_id, result)
    return result


def canonicalize_instagram_url(url: str) -> str:
    """Rewrite archived kkinstagram links back to canonical Instagram URLs."""
    parts = urlsplit(url)
    host = parts.netloc.lower()

    if host == "kkinstagram.com":
        return urlunsplit(
            (parts.scheme or "https", "www.instagram.com", parts.path, parts.query, parts.fragment)
        )

    if host.startswith("kkinstagram.com:"):
        return urlunsplit(
            (
                parts.scheme or "https",
                host.replace("kkinstagram.com", "www.instagram.com", 1),
                parts.path,
                parts.query,
                parts.fragment,
            )
        )

    return url


# ─────────────────────── Deep Extract: Reel ───────────────────────


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

        # Step 4: Build output
        parts = []
        header = f"[Instagram Reel: {url}"
        if uploader:
            header += f" - @{uploader}"
        header += "]"
        parts.append(header)

        if caption:
            if len(caption) > 3000:
                caption = caption[:3000] + "..."
            parts.append(caption)
        else:
            parts.append("[Подпись пуста]")

        if transcript:
            parts.append(f"[Транскрипция аудио]\n{transcript}")

        ocr_combined = "\n".join(t for t in ocr_texts if t)
        if ocr_combined:
            parts.append(f"[Текст с экрана (OCR)]\n{ocr_combined}")

        # Step 5: LLM Summary
        if transcript or ocr_combined:
            summary = _summarize_reel(caption, transcript, ocr_combined, uploader)
            if summary:
                parts.append(f"[Описание ролика]\n{summary}")
        elif not caption.strip():
            parts.append("[Не удалось извлечь ни аудио, ни текст с кадров]")

        return "\n\n".join(parts)

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

        parts = []
        header = f"[Instagram Post: {url}"
        if uploader:
            header += f" - @{uploader}"
        header += "]"
        parts.append(header)

        if caption:
            if len(caption) > 3000:
                caption = caption[:3000] + "..."
            parts.append(caption)
        else:
            parts.append("[Подпись пуста]")

        # Analyze each image
        total = len(image_paths)
        for i, img_path in enumerate(image_paths, 1):
            description = _describe_single_image(img_path)
            parts.append(f"[Изображение {i}/{total}]\n{description}")

        return "\n\n".join(parts)

    except Exception as e:
        logger.error(f"Instagram carousel extract error for {url}: {e}", exc_info=True)
        return None
    finally:
        if carousel_dir.exists():
            shutil.rmtree(carousel_dir, ignore_errors=True)


# ─────────────────────── Review queue for long Reels ───────────────────────


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
    parts = [
        f"[Instagram Reel: {url}" + (f" - @{uploader}" if uploader else "") + "]",
    ]
    if caption:
        if len(caption) > 3000:
            caption = caption[:3000] + "..."
        parts.append(caption)
    parts.append(result.placeholder_text)
    return "\n\n".join(parts)


# ─────────────────────── Caption-only fallback ───────────────────────


def _caption_only(
    url: str, info: dict, caption: str, uploader: str, is_reel: bool
) -> str:
    """Original extraction: caption + subtitles from yt-dlp metadata."""
    subtitles = _get_subtitles_from_info(url, info)

    parts = []
    post_type = "Reel" if is_reel else "Post"
    header = f"[Instagram {post_type}: {url}"
    if uploader:
        header += f" - @{uploader}"
    header += "]"
    parts.append(header)

    if caption:
        if len(caption) > 3000:
            caption = caption[:3000] + "..."
        parts.append(caption)
    else:
        parts.append("[Подпись пуста]")

    if subtitles:
        parts.append(f"[Субтитры / текст из видео]\n{subtitles}")
    elif is_reel:
        parts.append(
            "[Текст из самого видео недоступен: Instagram не отдал субтитры, "
            "сохранена только подпись.]"
        )

    return "\n\n".join(parts)


# ─────────────────────── yt-dlp helpers ───────────────────────


def _get_info_ytdlp(url: str) -> dict | None:
    """Get post metadata via yt-dlp --dump-json."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--no-download", "--no-warnings", url],
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
        )
        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        logger.warning(f"yt-dlp timeout for {url}")
    except json.JSONDecodeError:
        logger.warning(f"yt-dlp returned invalid JSON for {url}")
    except FileNotFoundError:
        logger.error("yt-dlp not found — install it: pip install yt-dlp")
    return None


def _download_video(url: str, work_dir: Path, post_id: str) -> Path | None:
    """Download video via yt-dlp."""
    out_path = work_dir / f"{post_id}.%(ext)s"
    try:
        subprocess.run(
            [
                "yt-dlp",
                "-f", "best[ext=mp4]/best",
                "--no-warnings",
                "--max-filesize", f"{config.INSTAGRAM_MAX_VIDEO_SIZE_MB}M",
                "-o", str(out_path),
                url,
            ],
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
        )
    except subprocess.TimeoutExpired:
        logger.warning(f"yt-dlp video download timeout for {url}")
        return None
    except FileNotFoundError:
        logger.error("yt-dlp not found")
        return None

    # Find downloaded file
    for ext in ("mp4", "webm", "mkv"):
        candidate = work_dir / f"{post_id}.{ext}"
        if candidate.exists():
            return candidate

    # Glob fallback
    matches = list(work_dir.glob(f"{post_id}.*"))
    video_exts = {".mp4", ".webm", ".mkv", ".avi", ".mov"}
    for m in matches:
        if m.suffix.lower() in video_exts:
            return m
    return None


def _download_carousel_images(
    url: str, carousel_dir: Path, post_id: str, info: dict
) -> list[Path]:
    """Download carousel images via yt-dlp."""
    out_template = str(carousel_dir / f"{post_id}_%(autonumber)s.%(ext)s")
    try:
        subprocess.run(
            [
                "yt-dlp",
                "--no-warnings",
                "-o", out_template,
                url,
            ],
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
        )
    except subprocess.TimeoutExpired:
        logger.warning(f"yt-dlp carousel download timeout for {url}")
        return []
    except FileNotFoundError:
        logger.error("yt-dlp not found")
        return []

    image_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    images = sorted(
        p for p in carousel_dir.iterdir()
        if p.suffix.lower() in image_exts
    )
    return images


# ─────────────────────── Audio extraction & transcription ───────────────────────


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


def _extract_frames(
    video_path: Path, frames_dir: Path, interval: float
) -> list[Path]:
    """Extract frames from video at given interval."""
    pattern = str(frames_dir / "frame_%04d.jpg")
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-vf", f"fps=1/{interval}",
                "-q:v", "3",
                pattern,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        logger.warning(f"ffmpeg frame extraction timeout for {video_path}")
        return []
    except FileNotFoundError:
        logger.error("ffmpeg not found")
        return []

    return sorted(frames_dir.glob("frame_*.jpg"))


def _dedup_frames(frames: list[Path], threshold: int = 5) -> list[Path]:
    """
    Remove near-duplicate frames using perceptual hash (phash).
    Keeps a frame only if its Hamming distance to the previous kept frame > threshold.
    """
    if not frames:
        return []

    unique = [frames[0]]
    prev_hash = _compute_phash(frames[0])
    if prev_hash is None:
        return frames  # Can't compute hashes, return all

    for frame_path in frames[1:]:
        current_hash = _compute_phash(frame_path)
        if current_hash is None:
            unique.append(frame_path)
            continue

        distance = _hamming_distance(prev_hash, current_hash)
        if distance > threshold:
            unique.append(frame_path)
            prev_hash = current_hash

    return unique


def _compute_phash(image_path: Path, hash_size: int = 8) -> int | None:
    """
    Compute a perceptual hash for an image.
    Resize to (hash_size+1)×hash_size, convert to grayscale,
    compute horizontal gradient, produce hash_size² bit hash.
    """
    try:
        from PIL import Image

        img = Image.open(image_path).convert("L").resize(
            (hash_size + 1, hash_size), Image.LANCZOS
        )
        pixels = list(img.getdata()) if not hasattr(img, 'get_flattened_data') else list(img.get_flattened_data())
        width = hash_size + 1

        bits = []
        for y in range(hash_size):
            for x in range(hash_size):
                bits.append(1 if pixels[y * width + x] > pixels[y * width + x + 1] else 0)

        return int("".join(str(b) for b in bits), 2)

    except Exception as e:
        logger.debug(f"phash computation failed for {image_path}: {e}")
        return None


def _hamming_distance(h1: int, h2: int) -> int:
    """Compute Hamming distance between two integer hashes."""
    return bin(h1 ^ h2).count("1")


def _filter_empty_frames(frames: list[Path], edge_threshold: float = 0.10) -> list[Path]:
    """
    Filter out frames with low edge density (blank screens, talking heads without text).
    Uses Pillow-based Laplacian approximation.
    """
    if not frames:
        return []

    content_frames = []
    for frame_path in frames:
        density = _compute_edge_density(frame_path)
        if density is None or density >= edge_threshold:
            content_frames.append(frame_path)

    return content_frames if content_frames else frames[:1]  # Keep at least 1 frame


def _compute_edge_density(image_path: Path) -> float | None:
    """
    Estimate edge density using Pillow (no OpenCV needed).
    Applies a Laplacian-like kernel and measures fraction of "edge" pixels.
    """
    try:
        from PIL import Image, ImageFilter

        img = Image.open(image_path).convert("L").resize((160, 120), Image.LANCZOS)

        # Apply edge-finding filter
        edges = img.filter(ImageFilter.FIND_EDGES)

        pixels = list(edges.getdata()) if not hasattr(edges, 'get_flattened_data') else list(edges.get_flattened_data())
        total = len(pixels)
        edge_pixels = sum(1 for p in pixels if p > 30)

        return edge_pixels / total if total > 0 else 0.0

    except Exception as e:
        logger.debug(f"Edge density computation failed for {image_path}: {e}")
        return None


def _ocr_frames_batched(frames: list[Path], batch_size: int = 5) -> list[str]:
    """
    Send frames in batches to MiMo-V2.5 for OCR and visual content analysis.
    Returns list of OCR texts (one per batch).
    """
    if not frames:
        return []

    api_key = config.INSTAGRAM_VISION_API_KEY
    if not api_key or api_key == "your-api-key-here":
        logger.warning("Instagram vision API key not configured")
        return []

    results = []
    for batch_start in range(0, len(frames), batch_size):
        batch = frames[batch_start : batch_start + batch_size]
        batch_text = _ocr_single_batch(batch, batch_start)
        if batch_text:
            results.append(batch_text)

    return results


def _ocr_single_batch(frames: list[Path], start_idx: int) -> str | None:
    """Send a batch of frames to Vision API for OCR."""
    api_key = config.INSTAGRAM_VISION_API_KEY
    base_url = config.INSTAGRAM_VISION_BASE_URL.rstrip("/")

    content_parts = [
        {
            "type": "text",
            "text": (
                "Проанализируй эти кадры из Instagram видео. Для каждого кадра:\n"
                "1. Извлеки ВЕСЬ видимый текст (заголовки, подписи, данные, цитаты)\n"
                "2. Опиши визуальный контент: инфографика, карты, графики, таблицы\n"
                "3. Если на кадре только лицо/фон без текста — кратко отметь\n\n"
                "Формат ответа:\n"
                "Кадр N: [описание и текст]\n\n"
                "Отвечай на русском языке."
            ),
        }
    ]

    for frame_path in frames:
        try:
            img_b64 = base64.b64encode(frame_path.read_bytes()).decode("utf-8")
            content_parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                }
            )
        except Exception as e:
            logger.warning(f"Failed to read frame {frame_path}: {e}")

    if len(content_parts) < 2:
        return None

    headers = {
        "Authorization": f"Bearer {get_openai_api_key(api_key, base_url)}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json={
                "model": config.INSTAGRAM_VISION_MODEL,
                "messages": [{"role": "user", "content": content_parts}],
                "max_tokens": 2000,
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        text = str(payload["choices"][0]["message"].get("content") or "").strip()
        return text if text else None

    except requests.Timeout:
        logger.warning("Instagram OCR API timeout")
    except Exception as exc:
        logger.warning(f"Instagram OCR failed: {exc}")
    return None


# ─────────────────────── Vision for carousel images ───────────────────────


def _describe_single_image(image_path: Path) -> str:
    """Describe a single carousel image via Vision API."""
    api_key = config.INSTAGRAM_VISION_API_KEY
    if not api_key or api_key == "your-api-key-here":
        return "[Описание недоступно — Vision API не настроен]"

    base_url = config.INSTAGRAM_VISION_BASE_URL.rstrip("/")
    headers = {
        "Authorization": f"Bearer {get_openai_api_key(api_key, base_url)}",
        "Content-Type": "application/json",
    }

    try:
        img_b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        suffix = image_path.suffix.lower()
        mime_map = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".gif": "gif", ".webp": "webp"}
        mime = mime_map.get(suffix, "jpeg")

        response = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json={
                "model": config.INSTAGRAM_VISION_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Проанализируй это изображение из Instagram поста для OSINT базы знаний.\n"
                                    "Фокусируйся на:\n"
                                    "- Весь видимый текст (OCR — транскрибируй полностью)\n"
                                    "- Инфографика, графики, таблицы (извлеки данные)\n"
                                    "- Карты, локации (опиши что показано)\n"
                                    "- Люди, организации, логотипы\n"
                                    "- Скриншоты постов (извлеки текст)\n\n"
                                    "Отвечай на русском языке."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/{mime};base64,{img_b64}"},
                            },
                        ],
                    }
                ],
                "max_tokens": 800,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        return str(payload["choices"][0]["message"].get("content") or "").strip()

    except requests.Timeout:
        return "[Описание недоступно — таймаут Vision API]"
    except Exception as e:
        logger.warning(f"Vision API error for {image_path}: {e}")
        return "[Описание недоступно — ошибка Vision API]"


# ─────────────────────── LLM Summary ───────────────────────


def _summarize_reel(
    caption: str, transcript: str, ocr_text: str, uploader: str
) -> str | None:
    """Generate a concise summary of the Reel using DeepSeek V4."""
    api_key = config.LLM_API_KEY
    if not api_key or api_key == "your-api-key-here":
        return None

    base_url = config.LLM_BASE_URL.rstrip("/")
    headers = {
        "Authorization": f"Bearer {get_openai_api_key(api_key, base_url)}",
        "Content-Type": "application/json",
    }

    prompt_parts = [
        "Ты аналитик OSINT. Объедини информацию из Instagram Reel в краткое связное описание "
        "для базы знаний. Сохрани ВСЕ факты, имена, даты, цифры, организации.",
    ]
    if uploader:
        prompt_parts.append(f"\nАвтор: @{uploader}")
    if caption:
        prompt_parts.append(f"\nПодпись поста:\n{caption[:2000]}")
    if transcript:
        prompt_parts.append(f"\nТранскрипция аудио:\n{transcript[:3000]}")
    if ocr_text:
        prompt_parts.append(f"\nТекст с экрана (OCR):\n{ocr_text[:2000]}")
    prompt_parts.append(
        "\nНапиши краткое связное описание на русском. "
        "Не повторяй информацию, объедини. Убери мусор и рекламу."
    )

    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json={
                "model": config.LLM_MODEL,
                "messages": [{"role": "user", "content": "\n".join(prompt_parts)}],
                "max_tokens": 1500,
            },
            timeout=config.LLM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        return str(payload["choices"][0]["message"].get("content") or "").strip() or None

    except requests.Timeout:
        logger.warning("LLM summary timeout for Instagram Reel")
    except Exception as exc:
        logger.warning(f"LLM summary failed: {exc}")
    return None


# ─────────────────────── Subtitles (legacy fallback) ───────────────────────


def _get_subtitles_from_info(url: str, info: dict) -> str | None:
    """Download and return subtitles if yt-dlp exposes them."""
    subtitles = info.get("subtitles", {})
    auto_captions = info.get("automatic_captions", {})
    lang = None
    use_auto = False

    for preferred in ("ru", "uk", "es", "en"):
        if preferred in subtitles:
            lang = preferred
            break
    if not lang:
        for preferred in ("ru", "uk", "es", "en"):
            if preferred in auto_captions:
                lang = preferred
                use_auto = True
                break

    if not lang:
        return None

    sub_dir = config.MEDIA_CACHE_DIR / "subs"
    sub_dir.mkdir(parents=True, exist_ok=True)

    try:
        cmd = [
            "yt-dlp",
            "--skip-download",
            "--no-warnings",
            "--write-subs" if not use_auto else "--write-auto-subs",
            "--sub-lang", lang,
            "--sub-format", "vtt",
            "--convert-subs", "srt",
            "-o", str(sub_dir / "%(id)s"),
            url,
        ]
        subprocess.run(cmd, capture_output=True, text=True, timeout=30, encoding="utf-8")

        video_id = info.get("id", "")
        srt_files = list(sub_dir.glob(f"{video_id}*.srt"))
        if not srt_files:
            return None

        srt_text = srt_files[0].read_text(encoding="utf-8", errors="replace")
        clean = _srt_to_text(srt_text)

        # Cleanup
        for f in srt_files:
            f.unlink(missing_ok=True)

        return clean if clean and clean.strip() else None

    except subprocess.TimeoutExpired:
        logger.warning(f"yt-dlp subtitle timeout for Instagram {url}")
        return None


def _srt_to_text(srt: str) -> str:
    """Convert SRT subtitle format to plain text."""
    lines = []
    prev_line = ""

    for line in srt.splitlines():
        line = line.strip()
        if not line or line.isdigit():
            continue
        if re.match(r"\d{2}:\d{2}:\d{2}", line):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"\{[^}]+\}", "", line)
        if line != prev_line:
            lines.append(line)
            prev_line = line

    text = " ".join(lines).strip()
    return text or None


# ─────────────────────── Cache ───────────────────────


def _is_review_queue_placeholder(text: str) -> bool:
    """Return True for review placeholders that should not be cached as extraction output."""
    return (
        "Отправлено в очередь на ручной просмотр:" in text
        or "Уже обработано:" in text
    )


def _cache_signature() -> dict:
    return {
        "deep_extract_enabled": config.INSTAGRAM_DEEP_EXTRACT_ENABLED,
        "transcription_model": config.TRANSCRIPTION_MODEL,
        "vision_base_url": config.INSTAGRAM_VISION_BASE_URL,
        "vision_model": config.INSTAGRAM_VISION_MODEL,
        "llm_model": config.LLM_MODEL,
    }


def _read_cache(post_id: str) -> str | None:
    """Read cached extraction result for a post."""
    cache_path = config.INSTAGRAM_CACHE_DIR / f"{post_id}.json"
    if not cache_path.exists():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        if payload.get("cache_version") != _INSTAGRAM_CACHE_VERSION:
            return None
        if payload.get("signature") != _cache_signature():
            return None
        text = payload.get("text")
        return text if text else None
    except (OSError, json.JSONDecodeError, KeyError):
        return None


def _write_cache(post_id: str, text: str) -> None:
    """Write extraction result to cache."""
    cache_path = config.INSTAGRAM_CACHE_DIR / f"{post_id}.json"
    try:
        config.INSTAGRAM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "post_id": post_id,
            "text": text,
            "cached_at": datetime.now(UTC).isoformat(),
            "cache_version": _INSTAGRAM_CACHE_VERSION,
            "signature": _cache_signature(),
        }
        cache_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as e:
        logger.warning(f"Failed to write Instagram cache for {post_id}: {e}")


# ─────────────────────── Utilities ───────────────────────


def _extract_post_id(url: str) -> str | None:
    """Extract the post/reel ID from an Instagram URL."""
    match = re.search(r"instagram\.com/(?:reel|p)/([A-Za-z0-9_-]+)", url)
    return match.group(1) if match else None
