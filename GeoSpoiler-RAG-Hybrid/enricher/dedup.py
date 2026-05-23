"""
Dedup — detects duplicate posts based on shared YouTube URLs or high text similarity.

Rules:
- YouTube URL exact match: same video_id → is_duplicate=True
- The FIRST post chronologically with a given YouTube URL is the canonical one
- Text similarity is NOT implemented yet (Phase 2+)
- Dedup does NOT delete anything — it marks the card and sets canonical_memory_id
"""

import json
import logging
from pathlib import Path

import config

logger = logging.getLogger("geospoiler.enricher.dedup")

# ── YouTube video ID extraction ──
import re

_YT_VIDEO_ID_RE = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|v/|shorts/))([a-zA-Z0-9_-]{11})"
)


def build_youtube_index(enriched_dir: Path | None = None) -> dict[str, list[dict]]:
    """
    Scan all enriched cards and build an index of YouTube video IDs → posts.

    Returns:
        Dict mapping video_id → list of {channel, msg_id, date, card_path}
        sorted by date (earliest first).
    """
    enriched_dir = enriched_dir or config.ENRICHED_DIR
    index: dict[str, list[dict]] = {}

    for card_path in enriched_dir.rglob("*.enriched.json"):
        try:
            card = json.loads(card_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        yt_url = card.get("source_chain", {}).get("youtube_url")
        if not yt_url:
            continue

        video_id = _extract_video_id(yt_url)
        if not video_id:
            continue

        channel = card.get("provenance", {}).get("channel_name", "")
        msg_id = card.get("provenance", {}).get("message_id", "")
        date = card.get("provenance", {}).get("date", "")

        entry = {
            "channel": channel,
            "msg_id": str(msg_id),
            "date": date,
            "card_path": str(card_path),
            "memory_id": f"{channel}/{msg_id}",
        }

        if video_id not in index:
            index[video_id] = []
        index[video_id].append(entry)

    # Sort each group by date
    for video_id in index:
        index[video_id].sort(key=lambda x: x.get("date", ""))

    return index


def mark_duplicates(enriched_dir: Path | None = None) -> int:
    """
    Scan enriched cards and mark duplicates based on shared YouTube URLs.

    The first post (by date) with a given YouTube URL is canonical.
    All subsequent posts with the same URL get dedup.is_duplicate=True.

    Returns:
        Number of duplicates marked.
    """
    yt_index = build_youtube_index(enriched_dir)
    marked = 0

    for video_id, entries in yt_index.items():
        if len(entries) < 2:
            continue

        canonical = entries[0]  # Earliest by date
        for dup in entries[1:]:
            card_path = Path(dup["card_path"])
            try:
                card = json.loads(card_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            if card.get("dedup", {}).get("is_duplicate"):
                continue  # Already marked

            card["dedup"] = {
                "is_duplicate": True,
                "duplicate_group_id": video_id,
                "canonical_memory_id": canonical["memory_id"],
                "duplicate_reason": f"Same YouTube video: {video_id}",
            }

            card_path.write_text(
                json.dumps(card, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            marked += 1
            logger.info(
                f"  Dedup: {dup['memory_id']} → duplicate of {canonical['memory_id']} "
                f"(YouTube: {video_id})"
            )

    return marked


def _extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from URL."""
    match = _YT_VIDEO_ID_RE.search(url)
    return match.group(1) if match else None
