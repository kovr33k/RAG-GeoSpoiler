"""
Instagram Handler - extracts text from Instagram posts/Reels.

Strategy:
1. Normalize archived kkinstagram URLs back to canonical www.instagram.com URLs
2. Use yt-dlp to get post description/caption
3. If subtitles exist, extract them too
4. If no subtitles exist, preserve the caption and say that spoken text was unavailable
"""

import json
import logging
import re
import subprocess
from urllib.parse import urlsplit, urlunsplit

logger = logging.getLogger("geospoiler.normalizer.instagram")


def extract_instagram_text(url: str) -> str:
    """
    Extract text content from an Instagram post/Reel.
    Returns formatted text with caption and subtitles when available.
    """
    canonical_url = canonicalize_instagram_url(url)

    text = _try_ytdlp(canonical_url)
    if text:
        return text

    logger.warning(f"Could not extract Instagram content from {canonical_url}")
    return f"[Instagram: {canonical_url}]\n[Содержание не удалось извлечь - пост может быть приватным]"


def canonicalize_instagram_url(url: str) -> str:
    """Rewrite archived kkinstagram links back to canonical Instagram URLs."""
    parts = urlsplit(url)
    host = parts.netloc.lower()

    if host == "kkinstagram.com":
        return urlunsplit((parts.scheme or "https", "www.instagram.com", parts.path, parts.query, parts.fragment))

    if host.startswith("kkinstagram.com:"):
        return urlunsplit((parts.scheme or "https", host.replace("kkinstagram.com", "www.instagram.com", 1), parts.path, parts.query, parts.fragment))

    return url


def _try_ytdlp(url: str) -> str | None:
    """Try to extract Instagram post info via yt-dlp."""
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--dump-json",
                "--no-download",
                "--no-warnings",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
        )

        if result.returncode != 0:
            return None

        info = json.loads(result.stdout)
        title = info.get("title", "")
        description = info.get("description", "")
        uploader = info.get("uploader", info.get("channel", ""))
        subtitles = _get_subtitles(url, info)

        parts = []
        header = f"[Instagram: {url}"
        if uploader:
            header += f" - @{uploader}"
        header += "]"
        parts.append(header)

        caption = (description or title or "").strip()
        if caption:
            if len(caption) > 3000:
                caption = caption[:3000] + "..."
            parts.append(caption)
        else:
            parts.append("[Подпись пуста]")

        if subtitles:
            parts.append(f"[Субтитры / текст из видео]\n{subtitles}")
        elif "/reel/" in url.lower():
            parts.append("[Текст из самого видео недоступен: Instagram не отдал субтитры, сохранена только подпись.]")

        return "\n\n".join(parts)

    except subprocess.TimeoutExpired:
        logger.warning(f"yt-dlp timeout for Instagram {url}")
    except json.JSONDecodeError:
        logger.warning(f"yt-dlp returned invalid JSON for Instagram {url}")
    except FileNotFoundError:
        logger.error("yt-dlp not found - install it: pip install yt-dlp")
    except Exception as e:
        logger.error(f"Instagram yt-dlp error: {e}")

    return None


def _get_subtitles(url: str, info: dict) -> str | None:
    """Download and return Instagram subtitles if yt-dlp exposes them."""
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

    try:
        cmd = [
            "yt-dlp",
            "--skip-download",
            "--no-warnings",
            "--write-subs" if not use_auto else "--write-auto-subs",
            "--sub-lang", lang,
            "--sub-format", "vtt",
            "--convert-subs", "srt",
            "-o", "%(id)s",
            url,
        ]
        subprocess.run(cmd, capture_output=True, text=True, timeout=30, encoding="utf-8")

        video_id = info.get("id", "")
        matches = [f"{video_id}.{lang}.srt", f"{video_id}.{lang}-orig.srt"]
        for filename in matches:
            try:
                with open(filename, "r", encoding="utf-8", errors="replace") as fh:
                    srt = fh.read()
                return _srt_to_text(srt)
            except OSError:
                continue
        return None
    except subprocess.TimeoutExpired:
        logger.warning(f"yt-dlp subtitle timeout for Instagram {url}")
        return None
    finally:
        for suffix in (f".{lang}.srt", f".{lang}-orig.srt"):
            if lang:
                try:
                    import os
                    os.remove(f"{info.get('id', '')}{suffix}")
                except OSError:
                    pass


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
