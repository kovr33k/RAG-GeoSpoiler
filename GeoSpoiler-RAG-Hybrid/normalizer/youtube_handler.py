"""
YouTube Handler — extracts subtitles/transcript from YouTube videos via yt-dlp.

Strategy:
1. Try to get manual subtitles in: ru, uk, es, en
2. Fall back to auto-generated subtitles
3. If no subtitles available, extract video title + description
"""

import subprocess
import json
import logging
import re
from pathlib import Path

import config

logger = logging.getLogger("geospoiler.normalizer.youtube")

# Preferred subtitle languages (in priority order)
SUBTITLE_LANGS = ["ru", "uk", "es", "en"]


def extract_youtube_text(url: str) -> str:
    """
    Extract text content from a YouTube video.
    Returns formatted text with title and subtitles/description.
    """
    try:
        # First get video info (title, description, available subs)
        info = _get_video_info(url)
        if not info:
            return f'[YouTube: не удалось получить информацию — {url}]'

        title = info.get("title", "Без названия")
        description = info.get("description", "")
        channel = info.get("channel", info.get("uploader", ""))

        # Try to get subtitles
        subtitles = _get_subtitles(url, info)

        parts = [f'[YouTube: "{title}"' + (f" — {channel}" if channel else "") + "]"]

        if subtitles:
            parts.append(subtitles)
        elif description:
            # No subs — use description as fallback
            # Trim overly long descriptions (channel promos etc.)
            desc_clean = _clean_description(description)
            if desc_clean:
                parts.append(f"[Описание видео]\n{desc_clean}")
            else:
                parts.append("[Субтитры и описание недоступны]")
        else:
            parts.append("[Субтитры и описание недоступны]")

        return "\n\n".join(parts)

    except Exception as e:
        logger.error(f"YouTube extraction failed for {url}: {e}")
        return f'[YouTube: ошибка обработки — {url}]'


def _get_video_info(url: str) -> dict | None:
    """Get video metadata via yt-dlp --dump-json."""
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
        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        logger.warning(f"yt-dlp timeout for {url}")
    except json.JSONDecodeError:
        logger.warning(f"yt-dlp returned invalid JSON for {url}")
    return None


def _get_subtitles(url: str, info: dict) -> str | None:
    """Download and return subtitles text."""
    # Check which subtitle tracks are available
    available_subs = info.get("subtitles", {})
    available_auto = info.get("automatic_captions", {})

    # Determine which language to use
    lang = None
    use_auto = False

    for preferred in SUBTITLE_LANGS:
        if preferred in available_subs:
            lang = preferred
            break
    if not lang:
        for preferred in SUBTITLE_LANGS:
            if preferred in available_auto:
                lang = preferred
                use_auto = True
                break

    if not lang:
        return None

    # Download subtitles to temp file
    sub_dir = config.MEDIA_CACHE_DIR / "subs"
    sub_dir.mkdir(parents=True, exist_ok=True)
    out_template = str(sub_dir / "%(id)s")

    cmd = [
        "yt-dlp",
        "--skip-download",
        "--no-warnings",
        "--write-subs" if not use_auto else "--write-auto-subs",
        "--sub-lang", lang,
        "--sub-format", "vtt",
        "--convert-subs", "srt",
        "-o", out_template,
        url,
    ]

    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=30, encoding="utf-8")
    except subprocess.TimeoutExpired:
        return None

    # Find the downloaded .srt file
    video_id = info.get("id", "")
    srt_files = list(sub_dir.glob(f"{video_id}*.srt"))
    if not srt_files:
        return None

    srt_path = srt_files[0]
    srt_text = srt_path.read_text(encoding="utf-8", errors="replace")

    # Clean SRT to plain text
    clean = _srt_to_text(srt_text)

    # Cleanup temp file
    try:
        srt_path.unlink()
    except OSError:
        pass

    return clean if clean.strip() else None


def _srt_to_text(srt: str) -> str:
    """Convert SRT subtitle format to plain text, removing timestamps and duplicates."""
    lines = []
    prev_line = ""

    for line in srt.splitlines():
        line = line.strip()
        # Skip empty, numbering, and timestamp lines
        if not line:
            continue
        if line.isdigit():
            continue
        if re.match(r'\d{2}:\d{2}:\d{2}', line):
            continue
        # Remove HTML tags (SRT may contain <b>, <i>, etc.)
        line = re.sub(r'<[^>]+>', '', line)
        # Remove VTT positioning tags
        line = re.sub(r'\{[^}]+\}', '', line)
        # Skip duplicate consecutive lines (common in auto-subs)
        if line != prev_line:
            lines.append(line)
            prev_line = line

    return " ".join(lines)


def _clean_description(desc: str) -> str:
    """Clean YouTube description: remove promo links, social media blocks, etc."""
    lines = desc.splitlines()
    clean_lines = []
    for line in lines:
        # Stop at common "promo block" markers
        line_lower = line.lower().strip()
        line = _strip_leading_subscribe_prompt(line)
        if not line.strip():
            continue
        line_lower = line.lower().strip()
        normalized = re.sub(r"[^0-9a-zа-яёіїєґ]+", " ", line_lower).strip()
        stop_idx = _find_description_stop_index(line)
        if stop_idx is not None:
            prefix = line[:stop_idx].strip(" \t\r\n—–-«»\"'👉📣")
            if prefix:
                clean_lines.append(prefix)
            break
        if _looks_like_timeline_marker(line_lower):
            break
        if any(marker in normalized for marker in [
            "subscribe", "подписывайтесь", "подписаться",
            "follow us", "наши соцсети", "наши социальные сети",
            "социальные сети", "поддержать", "поддержать канал",
            "донат", "donate", "patreon", "boosty", "monobank",
            "рекламных интеграций", "по вопросам рекламы",
            "содержание", "таймкоды", "chapters",
        ]):
            break
        if _is_description_link_farm_line(line_lower):
            break
        clean_lines.append(line)

    result = "\n".join(clean_lines).strip()
    # Limit length
    if len(result) > 2000:
        result = result[:2000] + "..."
    return result


def _strip_leading_subscribe_prompt(line: str) -> str:
    """Remove a leading subscription CTA while preserving the useful description."""
    if re.match(r"^\s*еще\s+не\s+подписаны", line, flags=re.IGNORECASE):
        useful_start = re.search(r"\b(почему|зачем|как|кто|что)\b", line, flags=re.IGNORECASE)
        if useful_start:
            return line[useful_start.start():]
    return re.sub(
        r"^\s*(?:еще\s+не\s+)?подписан[^\?!.]{0,120}(?:[ᐅᐊ>]+|\s{2,})\s*",
        "",
        line,
        flags=re.IGNORECASE,
    )


def _find_description_stop_index(line: str) -> int | None:
    """Find the earliest promo/timeline marker inside a YouTube description line."""
    stop_patterns = [
        r"[🧡💛❤️]?\s*поддержать(?:\s+канал)?",
        r"по\s+вопросам\s+реклам",
        r"социальные\s+сети",
        r"единозбор",
        r"содержание\s*:",
        r"таймкоды\s*:",
        r"chapters\s*:",
        r"\b\d{1,2}:\d{2}(?::\d{2})?\s*[—–-]",
        r"\b\d{1,2}:\d{2}(?::\d{2})?\s+",
        r"стрим\s+тут",
        r"мой\s+телеграм",
        r"https?://(?:send|base)\.monobank\.ua/\S+",
        r"https?://(?:www\.)?(?:instagram|facebook|twitter|x|tiktok)\.com/\S+",
        r"https?://t\.me/\S+",
    ]
    matches = [
        match.start()
        for pattern in stop_patterns
        if (match := re.search(pattern, line, flags=re.IGNORECASE))
    ]
    return min(matches) if matches else None


def _looks_like_timeline_marker(line: str) -> bool:
    """Return True for YouTube chapter/timeline rows like '0:00 - Intro'."""
    return bool(re.match(r"^\s*\d{1,2}:\d{2}(?::\d{2})?\s*[-—:]", line))


def _is_description_link_farm_line(line: str) -> bool:
    """Return True for promo-only link blocks in YouTube descriptions."""
    promo_hosts = (
        "send.monobank.ua",
        "base.monobank.ua",
        "instagram.com",
        "facebook.com",
        "twitter.com",
        "x.com/",
        "t.me/",
        "tiktok.com",
        "discord.gg",
    )
    return line.startswith(("http://", "https://")) and any(host in line for host in promo_hosts)
