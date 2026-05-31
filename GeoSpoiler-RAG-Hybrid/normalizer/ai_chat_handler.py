"""
AI Chat Handler - routes AI conversation links to a manual review queue.

Links to ChatGPT and Claude conversations are saved as review items.
The user must manually extract the relevant text and place it in the normalized output.
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import config

logger = logging.getLogger("geospoiler.normalizer.ai_chat")


@dataclass
class AIReviewResult:
    """Result of routing an AI chat URL into the manual review queue."""

    placeholder_text: str
    action: str  # queued | already_reviewed
    filepath: str


def queue_for_review(
    url: str,
    channel_name: str,
    message_id: int,
    message_text: str = "",
    message_date: datetime | None = None,
) -> AIReviewResult:
    """
    Save an AI chat link to the review queue for manual processing.

    Creates a .json file in output/review_queue/ with all context.
    Returns queue metadata plus a placeholder text for the normalized output.
    """
    review_item = {
        "url": url,
        "channel": channel_name,
        "message_id": message_id,
        "message_text": message_text,
        "message_date": message_date.isoformat() if message_date else None,
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",  # pending | processed | skipped
        "extracted_text": None,  # User fills this in
    }

    # Build a filename that is unique per (channel, message, url).
    # Without the URL hash, two chat links in one post would silently overwrite each other.
    url_hash = hashlib.sha1(url.encode()).hexdigest()[:8]
    filename = f"{channel_name}_{message_id}_{url_hash}.json"
    filepath = config.REVIEW_QUEUE_DIR / _sanitize(filename)

    # Guard: do NOT overwrite files that have already been reviewed.
    # Re-normalizing the same message must not reset a processed/skipped item
    # back to pending (which would erase the extracted_text).
    if filepath.exists():
        try:
            existing = json.loads(filepath.read_text(encoding="utf-8"))
            if existing.get("status") in ("processed", "skipped"):
                logger.info(
                    f"  AI chat link already reviewed ({existing['status']}), skipping: {filepath.name}"
                )
                return AIReviewResult(
                    placeholder_text=f"[AI-диалог: {url}]\n[Уже обработано: {filepath.name}]",
                    action="already_reviewed",
                    filepath=str(filepath),
                )
        except (json.JSONDecodeError, OSError):
            pass  # Corrupted file - overwrite is fine

    filepath.write_text(
        json.dumps(review_item, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    logger.info(f"  AI chat link queued for review: {url} -> {filepath}")

    return AIReviewResult(
        placeholder_text=f"[AI-диалог: {url}]\n[Отправлено в очередь на ручной просмотр: {filepath.name}]",
        action="queued",
        filepath=str(filepath),
    )


def get_pending_reviews() -> list[dict]:
    """List all pending review items."""
    items = []
    for f in config.REVIEW_QUEUE_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("status") == "pending":
                data["_filepath"] = str(f)
                items.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return items


def mark_reviewed(filepath: str, extracted_text: str | None = None, skip: bool = False) -> None:
    """
    Mark a review item as processed or skipped.

    Args:
        filepath: Path to the review .json file
        extracted_text: The text to use (if processed)
        skip: If True, mark as skipped (no text extracted)
    """
    path = Path(filepath)
    if not path.exists():
        logger.warning(f"Review file not found: {filepath}")
        return

    data = json.loads(path.read_text(encoding="utf-8"))
    data["status"] = "skipped" if skip else "processed"
    data["extracted_text"] = extracted_text
    data["reviewed_at"] = datetime.now(timezone.utc).isoformat()

    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _sanitize(name: str) -> str:
    """Sanitize filename."""
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in name).strip("_")
