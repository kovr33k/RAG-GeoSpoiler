"""
Graph Text Builder — converts enriched memory cards into texts
optimised for LightRAG ingestion and keyword search.

Two outputs per card:
  graph_text  — compact, fact-dense text that LightRAG will parse
                into entities and relationships.
  search_text — expanded text with aliases and bilingual terms
                for BM25 / keyword retrieval.
"""

import json
import logging
from pathlib import Path

import config

logger = logging.getLogger("geospoiler.enricher.graph_text")

TRIAGE_KEEP = "keep"


# ── Public API ──────────────────────────────────────────────────────────────

def build_graph_text(card: dict) -> str:
    """
    Build a compact, LightRAG-optimised text from an enriched card.

    Structure:
        [Header: channel, date, post_url]
        SUMMARY: ...
        KEY FACTS:
          - fact 1 [fact]
          - fact 2 [source_claim]
        ENTITIES: person1, org1, country1, ...
        THESES:
          - thesis 1
        QUOTES:
          - Speaker: "quote" (context)
        EVENTS:
          - Event Name (date, location): description
    """
    if card.get("triage") != TRIAGE_KEEP:
        return ""

    prov = card.get("provenance", {})
    parts = []

    # Header
    header = (
        f"[Канал: {prov.get('channel_name', '?')} | "
        f"Дата: {_format_date(prov.get('date', ''))} | "
        f"Пост: {prov.get('post_url', '')}]"
    )
    parts.append(header)

    # Summary
    summary = card.get("summary", "").strip()
    if summary:
        parts.append(f"\n{summary}")

    # Key facts
    facts = card.get("key_facts", [])
    if facts:
        lines = ["Ключевые факты:"]
        for f in facts:
            text = f.get("text", "") if isinstance(f, dict) else str(f)
            claim = f.get("claim_type", "fact") if isinstance(f, dict) else "fact"
            if text:
                lines.append(f"- {text} [{claim}]")
        if len(lines) > 1:
            parts.append("\n".join(lines))

    # Entities (flat line for graph extraction)
    entities = card.get("entities", {})
    entity_tokens = []
    for category in ["people", "organizations", "countries", "locations",
                      "military_units", "equipment"]:
        for e in entities.get(category, []):
            if e:
                entity_tokens.append(str(e))
    if entity_tokens:
        parts.append(f"Сущности: {', '.join(entity_tokens)}")

    # Theses
    theses = card.get("theses", [])
    if theses:
        lines = ["Тезисы:"]
        for t in theses:
            if t:
                lines.append(f"- {t}")
        if len(lines) > 1:
            parts.append("\n".join(lines))

    # Quotes (top 5)
    quotes = card.get("quotes", [])[:5]
    if quotes:
        lines = ["Цитаты:"]
        for q in quotes:
            speaker = q.get("speaker", "?")
            text = q.get("text", "")
            context = q.get("context", "")
            if text:
                line = f'- {speaker}: «{text}»'
                if context:
                    line += f" ({context})"
                lines.append(line)
        if len(lines) > 1:
            parts.append("\n".join(lines))

    # Events
    events = card.get("events", [])
    if events:
        lines = ["События:"]
        for ev in events:
            name = ev.get("name", "")
            date = ev.get("date", "")
            location = ev.get("location", "")
            desc = ev.get("description", "")
            if name or desc:
                meta = ", ".join(filter(None, [date, location]))
                label = f"{name} ({meta})" if meta else name
                line = f"- {label}"
                if desc:
                    line += f": {desc}"
                lines.append(line)
        if len(lines) > 1:
            parts.append("\n".join(lines))

    # Source chain
    source = card.get("source_chain", {})
    original = source.get("original_source", "")
    youtube = source.get("youtube_url", "")
    if original:
        parts.append(f"Источник: {original}")
    if youtube:
        parts.append(f"YouTube: {youtube}")

    return "\n\n".join(parts)


def build_search_text(card: dict) -> str:
    """
    Build an expanded search text with aliases and bilingual terms.

    Includes graph_text + query_aliases + topics + content_type.
    Designed for BM25/keyword matching.
    """
    if card.get("triage") != TRIAGE_KEEP:
        return ""

    parts = []

    # Start with graph_text as base
    graph_text = card.get("graph_text", "")
    if not graph_text:
        graph_text = build_graph_text(card)
    parts.append(graph_text)

    # Query aliases (bilingual)
    aliases = card.get("query_aliases", [])
    if aliases:
        parts.append("Синонимы для поиска: " + " | ".join(aliases))

    # Topics
    topics = card.get("topics", [])
    if topics:
        parts.append("Темы: " + ", ".join(topics))

    visual = card.get("visual", {})
    if isinstance(visual, dict):
        broll = str(visual.get("broll_notes") or "").strip()
        if broll and visual.get("broll_potential") in ("high", "medium"):
            parts.append("Визуалы для поиска: " + broll)

    # Content type
    ct = card.get("content_type", "")
    if ct:
        parts.append(f"Тип контента: {ct}")

    return "\n\n".join(parts)


def populate_graph_texts(card: dict) -> dict:
    """
    Fill graph_text and search_text fields in a card.
    Returns the modified card.
    """
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

                if card.get("triage") != TRIAGE_KEEP:
                    stats["skipped"] += 1
                    continue

                old_gt = card.get("graph_text", "")
                populate_graph_texts(card)

                # Only write if changed
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

def _format_date(date_str: str) -> str:
    """Format ISO date to compact 'YYYY-MM-DD HH:MM' format."""
    if not date_str:
        return "?"
    # Handle ISO format: "2026-04-18T16:14:14+00:00"
    try:
        return date_str[:16].replace("T", " ")
    except Exception:
        return date_str
