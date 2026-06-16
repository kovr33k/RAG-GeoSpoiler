"""Instagram URL, yt-dlp, download, and subtitle helpers."""

import json
import logging
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import config

logger = logging.getLogger("geospoiler.normalizer.instagram")

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

def _extract_post_id(url: str) -> str | None:
    """Extract the post/reel ID from an Instagram URL."""
    match = re.search(r"instagram\.com/(?:reel|p)/([A-Za-z0-9_-]+)", url)
    return match.group(1) if match else None
