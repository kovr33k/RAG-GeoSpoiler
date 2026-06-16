"""Cache helpers for Instagram extraction."""

import json
import logging
from datetime import UTC, datetime

import config

logger = logging.getLogger("geospoiler.normalizer.instagram")
_INSTAGRAM_CACHE_VERSION = 2

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
