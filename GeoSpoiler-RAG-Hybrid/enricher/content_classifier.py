"""
Content Classifier — determines content_type from meta.json + normalized text.

Reads the sidecar .meta.json produced by the normalizer and the body text
to classify a post into one of the 15 content types.
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger("geospoiler.enricher.classifier")

# ── Content types ──────────────────────────────────────────────────────────
CONTENT_TYPES = [
    "text",              # Plain text post, no media
    "news",              # News repost (forwarded from news channel)
    "analysis",          # Long-form analysis / opinion
    "youtube_longform",  # YouTube video with long transcript (>3000 chars)
    "youtube_short",     # YouTube Shorts or short video (<3000 chars transcript)
    "instagram_reel",    # Instagram Reel
    "instagram_post",    # Instagram photo/carousel post
    "image",             # Post with image(s) — infographic, map, photo
    "screenshot",        # Screenshot of social media / chat
    "quote",             # Short quote (<200 chars body)
    "video_native",      # Telegram native video (not YouTube)
    "ai_chat",           # AI chat link (ChatGPT, Claude)
    "web_article",       # External web article
    "broll_candidate",   # Visual-only content for b-roll
    "mixed",             # Combination of text + video + images
]

# YouTube marker left by the normalizer's youtube_handler
_YOUTUBE_MARKER_RE = re.compile(r"\[YouTube:", re.IGNORECASE)
# Vision API description marker from image_handler
_IMAGE_DESC_RE = re.compile(r"\[Изображение(?:\s+\d+)?:", re.IGNORECASE)
# Native media placeholders from normalizer
_MEDIA_PLACEHOLDER_RE = re.compile(r"\[(?:Видео:|Аудио:).*не обработано.*\]", re.IGNORECASE)
# AI-chat placeholder from normalizer
_AI_CHAT_PLACEHOLDER_RE = re.compile(
    r"\[(?:AI-диалог:|Отправлено в очередь на ручной просмотр:)", re.IGNORECASE
)
# Instagram marker
_INSTAGRAM_MARKER_RE = re.compile(r"\[Instagram", re.IGNORECASE)
# Web article marker from web_handler
_WEB_MARKER_RE = re.compile(r"\[Веб-страница:", re.IGNORECASE)
# Header line
_HEADER_RE = re.compile(r"^\[Канал:.*\]\s*$")


def classify_content(meta: dict, normalized_text: str) -> str:
    """
    Determine the content_type of a post based on its metadata and normalized text.

    Args:
        meta: Parsed contents of the .meta.json sidecar file.
        normalized_text: Full text from the .txt normalized file.

    Returns:
        One of the CONTENT_TYPES strings.
    """
    # Strip header line for body analysis
    lines = normalized_text.split("\n")
    body_lines = [ln for ln in lines if not _HEADER_RE.match(ln.strip())]
    body = "\n".join(body_lines).strip()

    has_youtube = bool(meta.get("youtube_urls"))
    has_instagram = bool(meta.get("instagram_urls"))
    has_ai_chat = bool(meta.get("ai_chat_urls"))
    has_web = bool(meta.get("web_urls"))
    has_images = meta.get("has_images", False)
    has_video = meta.get("has_video", False)
    has_text = meta.get("has_text", False)
    is_forward = meta.get("is_forward", False)

    # Count how many content signals are present
    media_signals = sum([has_youtube, has_instagram, has_images, has_video, has_web])

    # ── Priority 1: AI chat ──
    if has_ai_chat:
        return "ai_chat"

    # ── Priority 2: YouTube ──
    if has_youtube:
        # Estimate transcript length from the YouTube section in normalized text
        yt_section_len = _estimate_youtube_section_length(body)
        if yt_section_len > 3000:
            return "youtube_longform"
        return "youtube_short"

    # ── Priority 3: Instagram ──
    if has_instagram:
        for url in meta.get("instagram_urls", []):
            if "/reel/" in url.lower():
                return "instagram_reel"
        return "instagram_post"

    # ── Priority 4: Native video ──
    if has_video and not has_youtube:
        # If there's meaningful text alongside, it's mixed
        if has_text and _body_text_length(body) > 200:
            return "mixed"
        return "video_native"

    # ── Priority 5: Web article ──
    if has_web and _WEB_MARKER_RE.search(body):
        return "web_article"

    # ── Priority 6: Image-based ──
    if has_images:
        text_len = _body_text_length(body)
        if text_len < 50:
            # Image with no/minimal text → b-roll or pure image
            return "broll_candidate"
        if text_len < 200 and not has_text:
            # Only image descriptions, no original text
            return "image"
        if has_text and text_len > 200:
            # Text + images
            if media_signals > 1:
                return "mixed"
            # Determine if the text is analysis or news
            return _classify_text_post(body, is_forward)
        return "image"

    # ── Priority 7: Text-only posts ──
    if has_text:
        return _classify_text_post(body, is_forward)

    # ── Fallback ──
    return "text"


def _classify_text_post(body: str, is_forward: bool) -> str:
    """Sub-classify a text-only post into text / news / analysis / quote."""
    text_len = _body_text_length(body)

    # Very short text → quote
    if text_len < 200:
        return "quote"

    # Forwarded posts under 800 chars are typically news
    if is_forward and text_len < 800:
        return "news"

    # Long text (>1500 chars) is usually analysis
    if text_len > 1500:
        return "analysis"

    # Medium-length forwarded → news
    if is_forward:
        return "news"

    # Medium-length original → text
    return "text"


def _body_text_length(body: str) -> int:
    """
    Length of body text excluding markers, placeholders, and image descriptions.
    Gives a rough measure of 'real' textual content.
    """
    clean_lines = []
    for line in body.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        # Skip normalized markers
        if any(pattern.match(stripped) for pattern in [
            _YOUTUBE_MARKER_RE, _IMAGE_DESC_RE, _MEDIA_PLACEHOLDER_RE,
            _AI_CHAT_PLACEHOLDER_RE, _INSTAGRAM_MARKER_RE, _WEB_MARKER_RE,
        ]):
            continue
        clean_lines.append(stripped)
    return sum(len(ln) for ln in clean_lines)


def _estimate_youtube_section_length(body: str) -> int:
    """
    Estimate the length of YouTube transcript/content in the body.
    Everything after the [YouTube: ...] marker until end or next marker.
    """
    match = _YOUTUBE_MARKER_RE.search(body)
    if not match:
        return 0
    # Find the end of the YouTube marker line
    start = body.find("\n", match.start())
    if start == -1:
        return 0
    # Text from after the marker to end of body
    yt_section = body[start:]
    return len(yt_section.strip())
