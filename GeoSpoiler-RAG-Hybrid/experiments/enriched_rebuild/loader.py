"""Retired enriched-card graph loading experiment.

The supported main graph source is normalized text. This module keeps the old
enriched-card graph loading path available for historical comparisons without
keeping it in the main loader implementation.
"""

import json
import re
from pathlib import Path

from lightrag import LightRAG

import config
from loader.ingest import _INSTAGRAM_REEL_WRAPPER_RE, load_from_directory, load_texts
from loader.runtime import logger

_NORMALIZED_HEADER_RE = re.compile(r"^\[Канал:.*\]\s*$")
_PLACEHOLDER_CONTENT_RE = re.compile(
    r"^\[(?:Видео:|Аудио:|AI-диалог:|Внешняя ссылка:|Малоинформативный пост:|"
    r"Instagram Reel:.*очередь|Отправлено в очередь|Уже обработано:|Веб-страница:.*ошибка).*\]$",
    re.IGNORECASE,
)


def _strip_normalized_header(text: str) -> str:
    lines = text.split("\n")
    body_lines = [ln for ln in lines if not _NORMALIZED_HEADER_RE.match(ln.strip())]
    return "\n".join(body_lines).strip()


def _has_meaningful_normalized_body(text: str) -> bool:
    body = _strip_normalized_header(text)
    lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
    if not lines:
        return False
    return any(
        not _PLACEHOLDER_CONTENT_RE.match(ln) and not _INSTAGRAM_REEL_WRAPPER_RE.match(ln)
        for ln in lines
    )


def _card_has_extracted_content(card: dict) -> bool:
    if str(card.get("summary") or "").strip():
        return True

    for field in ("key_facts", "topics", "theses", "quotes", "events", "chunks"):
        if card.get(field):
            return True

    entities = card.get("entities", {})
    if isinstance(entities, dict):
        return any(bool(items) for items in entities.values())

    visual = card.get("visual", {})
    if isinstance(visual, dict) and str(visual.get("broll_notes") or "").strip():
        return True

    return False


def _read_normalized_fallback(card: dict) -> tuple[str, str] | None:
    norm_file = card.get("provenance", {}).get("normalized_file", "")
    if not norm_file:
        return None

    norm_path = Path(norm_file)
    if not norm_path.is_absolute():
        norm_path = config.PROJECT_ROOT / norm_path
    if not norm_path.exists():
        return None

    raw_text = norm_path.read_text(encoding="utf-8").strip()
    if not raw_text:
        return None
    return str(norm_path), raw_text


def _read_all_normalized_texts() -> dict[str, str]:
    """Return all normalized texts keyed by resolved absolute file path."""
    normalized_texts: dict[str, str] = {}
    for txt_file in sorted(config.NORMALIZED_DIR.rglob("*.txt")):
        try:
            text = txt_file.read_text(encoding="utf-8").strip()
        except Exception as e:
            logger.warning(f"  Cannot read normalized fallback {txt_file}: {e}")
            continue
        if text:
            normalized_texts[str(txt_file.resolve())] = text
    return normalized_texts


async def load_from_enriched(rag: LightRAG) -> dict:
    """
    Retired experimental graph-load path for enriched cards.

    The supported v1.1 LightRAG graph source is normalized text. Keep this
    helper only for historical/experimental investigation outside the main CLI.
    It loads enriched memory cards using graph_text, without losing curated
    normalized posts.

    For each enriched card:
      - is_duplicate → skip
      - keep + usable graph_text → load graph_text
      - review/partial/empty graph_text → fallback to normalized .txt file
      - missing enriched card → fallback to normalized .txt file

    Returns:
        dict with stats: loaded, skipped_triage, skipped_dedup,
        fallback_normalized, missing_enriched, errors
    """
    enriched_dir = config.ENRICHED_DIR
    stats = {
        "loaded": 0,
        "normalized_found": 0,
        "skipped_triage": 0,
        "skipped_dedup": 0,
        "fallback_normalized": 0,
        "missing_enriched": 0,
        "errors": 0,
    }

    if not enriched_dir.exists():
        logger.warning("No enriched directory found; falling back to normalized.")
        loaded = await load_from_directory(rag)
        stats["fallback_normalized"] = loaded
        return stats

    normalized_texts = _read_all_normalized_texts()
    stats["normalized_found"] = len(normalized_texts)
    texts_with_paths = []
    loaded_normalized_paths: set[str] = set()
    excluded_normalized_paths: set[str] = set()

    for channel_dir in sorted(d for d in enriched_dir.iterdir() if d.is_dir()):
        for card_path in sorted(channel_dir.glob("*.enriched.json")):
            try:
                card = json.loads(card_path.read_text(encoding="utf-8"))
                fallback = _read_normalized_fallback(card)
                fallback_path = str(Path(fallback[0]).resolve()) if fallback else None

                # Skip duplicates, but mark their source as intentionally accounted for.
                dedup = card.get("dedup", {})
                if dedup.get("is_duplicate"):
                    stats["skipped_dedup"] += 1
                    if fallback_path:
                        excluded_normalized_paths.add(fallback_path)
                    continue

                try:
                    from enricher.graph_text_builder import build_graph_text

                    graph_text = build_graph_text(card).strip()
                except Exception as exc:
                    logger.debug(f"  Could not rebuild graph_text for {card_path}: {exc}")
                    graph_text = card.get("graph_text", "").strip()
                raw_body = _strip_normalized_header(fallback[1]) if fallback else ""

                if card.get("triage") == "keep" and graph_text and (
                    _card_has_extracted_content(card) or len(raw_body.strip()) < 20
                ):
                    # Use enriched graph_text only when it contains actual extraction.
                    source_path = card.get("provenance", {}).get(
                        "normalized_file", str(card_path)
                    )
                    texts_with_paths.append((source_path, graph_text))
                    if fallback_path:
                        loaded_normalized_paths.add(fallback_path)
                elif fallback:
                    # Fallback: load raw normalized file for review/empty/partial cards.
                    if _has_meaningful_normalized_body(fallback[1]):
                        texts_with_paths.append(fallback)
                        loaded_normalized_paths.add(fallback_path)
                        stats["fallback_normalized"] += 1
                        if card.get("triage") != "keep":
                            stats["skipped_triage"] += 1
                    else:
                        stats["skipped_triage"] += 1
                        logger.info(
                            f"  Review-only placeholder not loaded: "
                            f"{channel_dir.name}/{card_path.stem}"
                        )
                else:
                    logger.warning(
                        f"  No usable graph_text and no normalized file for "
                        f"{channel_dir.name}/{card_path.stem}"
                    )

            except Exception as e:
                stats["errors"] += 1
                logger.error(f"  Error reading {card_path}: {e}")

    for norm_path, raw_text in normalized_texts.items():
        if norm_path in loaded_normalized_paths or norm_path in excluded_normalized_paths:
            continue
        if not _has_meaningful_normalized_body(raw_text):
            continue

        texts_with_paths.append((norm_path, raw_text))
        loaded_normalized_paths.add(norm_path)
        stats["fallback_normalized"] += 1
        stats["missing_enriched"] += 1

    if not texts_with_paths:
        logger.warning("No enriched texts to load.")
        return stats

    logger.info(
        f"Loading {len(texts_with_paths)} enriched texts into LightRAG "
        f"(skipped: {stats['skipped_triage']} triage, "
        f"{stats['skipped_dedup']} dedup, "
        f"{stats['fallback_normalized']} fallback, "
        f"{stats['missing_enriched']} missing enriched)."
    )
    stats["loaded"] = await load_texts(rag, texts_with_paths)
    return stats
