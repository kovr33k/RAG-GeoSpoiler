"""
Graph Text Builder v2 — converts enriched_v2 cards into texts
for LightRAG ingestion and FTS search.

Two outputs per card:
  graph_text  — compact 3-10 sentence text for LightRAG graph extraction.
                Focuses on relationships between entities and events.
  search_text — dense flat text for BM25/FTS retrieval combining all
                card fields into a searchable representation.
"""

import json
import logging

import config

logger = logging.getLogger("geospoiler.enricher.graph_text")


# ── Public API ──────────────────────────────────────────────────────────────

def build_graph_text(card: dict) -> str:
    """
    Build a compact LightRAG-optimised graph text from a v2 enriched card.

    Structure: short relational sentences that help LightRAG extract
    entity-relationship triples. No dump of all fields.
    """
    parts = []

    prov = card.get("provenance", {})
    channel = prov.get("channel", "?")
    date = _format_date(prov.get("date", ""))
    source = prov.get("forwarded_from") or channel

    # Header for context
    parts.append(f"Документ из канала {channel} ({date}), источник: {source}.")

    # Summary as main relationship anchor
    summary = (card.get("summary") or "").strip()
    if summary:
        parts.append(summary)

    # Key entities as relationship nodes
    entity_tokens = _extract_entity_texts(card.get("entities", {}))
    if entity_tokens:
        parts.append(f"Упоминаются: {', '.join(entity_tokens[:15])}.")

    # Events as relationship edges
    events = card.get("events", [])
    for ev in events[:5]:
        if isinstance(ev, dict):
            desc = ev.get("description", "")
            actors = ev.get("actors", [])
            location = ev.get("location", "")
            if desc:
                actor_text = f" ({', '.join(actors)})" if actors else ""
                loc_text = f" в {location}" if location else ""
                parts.append(f"Событие{loc_text}{actor_text}: {desc}")

    # Theses as relationship context
    theses = card.get("theses", [])
    for th in theses[:3]:
        if isinstance(th, dict) and th.get("text"):
            speaker = th.get("speaker", "")
            speaker_prefix = f"{speaker}: " if speaker else ""
            parts.append(f"Позиция — {speaker_prefix}{th['text']}")

    # Top quotes (max 2 for graph density)
    quotes = card.get("quotes", [])[:2]
    for q in quotes:
        if isinstance(q, dict) and q.get("text"):
            speaker = q.get("speaker", "?")
            parts.append(f'{speaker}: «{q["text"]}»')

    return "\n".join(parts)


def build_search_text(card: dict) -> str:
    """
    Build a dense FTS/search text combining all card fields.

    Designed for BM25/keyword matching — includes all searchable tokens.
    """
    parts = []

    prov = card.get("provenance", {})
    content_type = card.get("content_type", "")
    channel = prov.get("channel", "")
    date = _format_date(prov.get("date", ""))

    # Metadata line
    meta_parts = [p for p in [content_type, channel, date] if p]
    if meta_parts:
        parts.append(" ".join(meta_parts))

    # Summary
    summary = (card.get("summary") or "").strip()
    if summary:
        parts.append(summary)

    # Key points
    key_points = card.get("key_points", [])
    if key_points:
        kp_texts = []
        for kp in key_points:
            if isinstance(kp, dict):
                kp_texts.append(kp.get("text", ""))
            elif isinstance(kp, str):
                kp_texts.append(kp)
        kp_text = "; ".join(t for t in kp_texts if t)
        if kp_text:
            parts.append(f"Ключевые пункты: {kp_text}")

    # Entities
    entity_tokens = _extract_entity_texts(card.get("entities", {}))
    if entity_tokens:
        parts.append(f"Сущности: {', '.join(entity_tokens)}")

    # Topics
    topics = card.get("topics", [])
    if topics:
        topic_labels = []
        for t in topics:
            if isinstance(t, dict):
                topic_labels.append(t.get("label", ""))
            elif isinstance(t, str):
                topic_labels.append(t)
        topic_text = ", ".join(t for t in topic_labels if t)
        if topic_text:
            parts.append(f"Темы: {topic_text}")

    # Theses
    theses = card.get("theses", [])
    if theses:
        thesis_texts = []
        for th in theses:
            if isinstance(th, dict):
                thesis_texts.append(th.get("text", ""))
            elif isinstance(th, str):
                thesis_texts.append(th)
        th_text = "; ".join(t for t in thesis_texts if t)
        if th_text:
            parts.append(f"Тезисы: {th_text}")

    # Quotes (condensed)
    quotes = card.get("quotes", [])[:5]
    if quotes:
        q_parts = []
        for q in quotes:
            if isinstance(q, dict) and q.get("text"):
                speaker = q.get("speaker", "?")
                q_parts.append(f'{speaker}: «{q["text"]}»')
        if q_parts:
            parts.append("Цитаты: " + " | ".join(q_parts))

    # Events
    events = card.get("events", [])
    if events:
        ev_parts = []
        for ev in events:
            if isinstance(ev, dict):
                desc = ev.get("description", "")
                if desc:
                    ev_parts.append(desc)
        if ev_parts:
            parts.append("События: " + "; ".join(ev_parts))

    # Search phrases
    phrases = card.get("search_phrases", [])
    if phrases:
        phrase_texts = []
        for a in phrases:
            if isinstance(a, dict):
                phrase_texts.append(a.get("text", ""))
            elif isinstance(a, str):
                phrase_texts.append(a)
        phrase_text = " | ".join(t for t in phrase_texts if t)
        if phrase_text:
            parts.append(f"Поиск: {phrase_text}")

    # Source chain
    source_chain = card.get("source_chain", {})
    original = source_chain.get("original_source", "")
    if original:
        parts.append(f"Источник: {original}")

    return "\n".join(parts)


def populate_graph_texts(card: dict) -> dict:
    """Fill graph_text and search_text fields in a card. Returns the modified card."""
    card["graph_text"] = build_graph_text(card)
    card["search_text"] = build_search_text(card)
    return card


def populate_all_cards(channel_filter: str | None = None) -> dict:
    """
    Scan all enriched cards and populate graph_text + search_text fields.

    Returns stats dict: {updated: int, skipped: int, errors: int}
    """
    enriched_dir = config.ENRICHED_DIR
    if not enriched_dir.exists():
        logger.warning("No enriched directory found.")
        return {"updated": 0, "skipped": 0, "errors": 0}

    stats = {"updated": 0, "skipped": 0, "errors": 0}

    channel_dirs = sorted(
        [d for d in enriched_dir.iterdir() if d.is_dir()]
    )
    if channel_filter:
        channel_dirs = [d for d in channel_dirs if d.name == channel_filter]

    for channel_dir in channel_dirs:
        for card_path in sorted(channel_dir.glob("*.enriched.json")):
            try:
                card = json.loads(card_path.read_text(encoding="utf-8"))

                old_gt = card.get("graph_text", "")
                populate_graph_texts(card)

                if card["graph_text"] != old_gt or not old_gt:
                    card_path.write_text(
                        json.dumps(card, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    stats["updated"] += 1
                    logger.debug(
                        f"  Updated graph_text: {channel_dir.name}/{card_path.stem}"
                    )
                else:
                    stats["skipped"] += 1

            except Exception as e:
                stats["errors"] += 1
                logger.error(f"  Error processing {card_path}: {e}")

    logger.info(
        f"Graph text build: {stats['updated']} updated, "
        f"{stats['skipped']} skipped, {stats['errors']} errors"
    )
    return stats


# ── Helpers ─────────────────────────────────────────────────────────────────

def _extract_entity_texts(entities: dict) -> list[str]:
    """Extract flat list of entity text strings from v2 structured entities."""
    tokens = []
    for category in ["people", "organizations", "countries", "locations",
                     "military_units", "equipment", "weapons",
                     "programs_projects", "media_sources", "other"]:
        for item in entities.get(category, []):
            if isinstance(item, dict):
                text = item.get("text", "")
            else:
                text = str(item)
            if text.strip():
                tokens.append(text.strip())
    return tokens


def _format_date(date_str: str) -> str:
    """Format ISO date to compact 'YYYY-MM-DD HH:MM' format."""
    if not date_str:
        return "?"
    try:
        return date_str[:16].replace("T", " ")
    except Exception:
        return date_str
