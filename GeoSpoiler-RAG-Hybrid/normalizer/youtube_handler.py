"""
YouTube Handler — extracts subtitles/transcript from YouTube videos via yt-dlp.

Strategy:
1. Try to get manual subtitles in: ru, uk, es, en
2. Fall back to auto-generated subtitles
3. Fall back to Whisper transcription (if TRANSCRIPTION_ENABLED)
4. If nothing works, extract video title + description
"""

import subprocess
import json
import logging
import re
from pathlib import Path

import requests

import config
from llm_auth import get_openai_api_key

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
        else:
            # No subs — try Whisper transcription
            transcript = _transcribe_audio(url, info)
            if transcript:
                parts.append(transcript)
            elif description:
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


CHUNK_DURATION_SEC = 600  # 10-minute chunks for Whisper


def _transcribe_audio(url: str, info: dict) -> str | None:
    """Download audio, split into chunks, transcribe via Whisper API."""
    if not config.TRANSCRIPTION_ENABLED:
        return None

    api_key = config.TRANSCRIPTION_API_KEY
    if not api_key or api_key == "your-api-key-here":
        return None

    audio_dir = config.MEDIA_CACHE_DIR / "youtube_audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    video_id = info.get("id", "unknown")
    raw_path = audio_dir / f"{video_id}_raw.%(ext)s"

    # Step 1: download audio
    try:
        subprocess.run(
            [
                "yt-dlp",
                "-x",
                "--no-warnings",
                "-o", str(raw_path),
                url,
            ],
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
        )
    except subprocess.TimeoutExpired:
        logger.warning(f"yt-dlp audio download timeout for {url}")
        return None

    raw_files = list(audio_dir.glob(f"{video_id}_raw.*"))
    if not raw_files:
        return None
    raw_file = raw_files[0]

    # Step 2: split into 10-min chunks as low-bitrate mp3
    chunks = _split_audio(raw_file, audio_dir, video_id)
    raw_file.unlink(missing_ok=True)

    if not chunks:
        return None

    # Step 3: transcribe each chunk
    texts = []
    try:
        for chunk_path in chunks:
            text = _call_whisper(chunk_path)
            if text:
                texts.append(text)
    finally:
        for chunk_path in chunks:
            chunk_path.unlink(missing_ok=True)

    return " ".join(texts) if texts else None


def _split_audio(input_path: Path, out_dir: Path, prefix: str) -> list[Path]:
    """Split audio into 10-minute mono 48kbps mp3 chunks."""
    pattern = out_dir / f"{prefix}_chunk_%03d.mp3"
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(input_path),
                "-ac", "1",
                "-b:a", "48k",
                "-f", "segment",
                "-segment_time", str(CHUNK_DURATION_SEC),
                "-reset_timestamps", "1",
                str(pattern),
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        logger.warning(f"ffmpeg split timeout for {input_path}")
        return []

    chunks = sorted(out_dir.glob(f"{prefix}_chunk_*.mp3"))
    return chunks


def _call_whisper(audio_path: Path) -> str | None:
    """Transcribe audio via configured API (supports chat-completions and STT endpoints)."""
    import base64

    api_key = get_openai_api_key(config.TRANSCRIPTION_API_KEY, config.TRANSCRIPTION_BASE_URL)
    audio_b64 = base64.b64encode(audio_path.read_bytes()).decode("utf-8")
    base_url = config.TRANSCRIPTION_BASE_URL.rstrip("/")

    # Use chat completions for LLM-based transcription (Gemini, etc.)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    lang = config.TRANSCRIPTION_LANGUAGE or "ru"

    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json={
                "model": config.TRANSCRIPTION_MODEL,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "input_audio", "input_audio": {"data": audio_b64, "format": "mp3"}},
                        {"type": "text", "text": f"Транскрибируй это аудио дословно на русском языке. Верни только текст транскрипции, без комментариев."},
                    ],
                }],
                "max_tokens": 16000,
            },
            timeout=config.TRANSCRIPTION_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        text = str(payload["choices"][0]["message"].get("content") or "").strip()
        return text if text else None
    except requests.Timeout:
        logger.warning(f"Transcription API timeout for {audio_path}")
        return None
    except Exception as exc:
        logger.warning(f"Transcription failed for {audio_path}: {exc}")
        return None


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
