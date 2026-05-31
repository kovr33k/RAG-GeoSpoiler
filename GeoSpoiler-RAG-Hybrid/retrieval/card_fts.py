import json
import logging
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import config
from retrieval.wiki_index import extract_source_id

logger = logging.getLogger("geospoiler.retrieval.card_fts")

_TOKEN_RE = re.compile(r"\w{3,}", re.UNICODE)


@dataclass(frozen=True)
class CardFtsRecord:
    source_id: str
    card_path: str
    normalized_file: str
    post_url: str
    title: str
    search_text: str
    entities: str
    topics: str
    claim_types: str


@dataclass(frozen=True)
class CardFtsBuildStats:
    db_path: Path
    cards_seen: int
    cards_indexed: int
    cards_skipped: int


@dataclass(frozen=True)
class CardFtsMatch:
    source_id: str
    card_path: str
    normalized_file: str
    post_url: str
    title: str
    score: float
    snippet: str


def rebuild_card_index(
    enriched_dir: Path = config.ENRICHED_DIR,
    db_path: Path = config.CARD_FTS_DB_PATH,
) -> CardFtsBuildStats:
    """Rebuild the local SQLite FTS5 index for enriched cards."""
    records = list(iter_card_records(enriched_dir))
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(db_path)) as conn:
        _create_schema(conn)
        conn.execute("DELETE FROM cards_fts")
        conn.executemany(
            """
            INSERT INTO cards_fts (
                source_id,
                card_path,
                normalized_file,
                post_url,
                title,
                search_text,
                entities,
                topics,
                claim_types
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    record.source_id,
                    record.card_path,
                    record.normalized_file,
                    record.post_url,
                    record.title,
                    record.search_text,
                    record.entities,
                    record.topics,
                    record.claim_types,
                )
                for record in records
            ],
        )
        conn.commit()

    seen = _count_enriched_cards(enriched_dir)
    indexed = len(records)
    return CardFtsBuildStats(
        db_path=db_path,
        cards_seen=seen,
        cards_indexed=indexed,
        cards_skipped=max(0, seen - indexed),
    )


def search_card_index(
    query: str,
    top_k: int = 10,
    db_path: Path = config.CARD_FTS_DB_PATH,
) -> list[CardFtsMatch]:
    """Search the local card FTS index without calling LightRAG or an LLM."""
    match_query = _to_fts_query(query)
    if not match_query or not db_path.exists():
        return []

    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        _create_schema(conn)
        rows = conn.execute(
            """
            SELECT
                source_id,
                card_path,
                normalized_file,
                post_url,
                title,
                bm25(cards_fts) AS rank,
                snippet(cards_fts, 5, '...', '...', ' ', 24) AS snippet
            FROM cards_fts
            WHERE cards_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (match_query, max(1, top_k)),
        ).fetchall()
        return [
            CardFtsMatch(
                source_id=row["source_id"],
                card_path=row["card_path"],
                normalized_file=row["normalized_file"],
                post_url=row["post_url"],
                title=row["title"],
                score=round(-float(row["rank"]), 6),
                snippet=_clean_snippet(row["snippet"]),
            )
            for row in rows
        ]


def iter_card_records(enriched_dir: Path = config.ENRICHED_DIR) -> Iterable[CardFtsRecord]:
    if not enriched_dir.exists():
        return

    for card_path in sorted(enriched_dir.rglob("*.enriched.json")):
        try:
            card = json.loads(card_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.debug("Card FTS could not read %s: %s", card_path, exc)
            continue
        record = card_to_fts_record(card, card_path)
        if record:
            yield record


def card_to_fts_record(card: dict[str, Any], card_path: Path) -> CardFtsRecord | None:
    if card.get("triage") != "keep":
        return None

    provenance = card.get("provenance") if isinstance(card.get("provenance"), dict) else {}
    search_text = _first_text(
        card.get("search_text"),
        card.get("graph_text"),
        card.get("summary"),
    )
    if not search_text:
        return None

    normalized_file = _clean_str(provenance.get("normalized_file")) or str(card_path)
    channel_name = _clean_str(provenance.get("channel_name")) or "?"
    date = _clean_str(provenance.get("date"))
    title = f"{channel_name} - {date[:10] if date else '?'}"

    return CardFtsRecord(
        source_id=extract_source_id(card) or "",
        card_path=str(card_path),
        normalized_file=normalized_file,
        post_url=_clean_str(provenance.get("post_url")),
        title=title,
        search_text=search_text,
        entities=_flatten_entities(card.get("entities")),
        topics=_join_texts(card.get("topics")),
        claim_types=_claim_types(card),
    )


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS cards_fts USING fts5(
            source_id UNINDEXED,
            card_path UNINDEXED,
            normalized_file UNINDEXED,
            post_url UNINDEXED,
            title,
            search_text,
            entities,
            topics,
            claim_types,
            tokenize='unicode61'
        )
        """
    )


def _to_fts_query(query: str) -> str:
    terms = []
    seen = set()
    for term in _TOKEN_RE.findall(query.casefold()):
        if term in seen:
            continue
        seen.add(term)
        terms.append(f"{term}*")
    return " OR ".join(terms)


def _count_enriched_cards(enriched_dir: Path) -> int:
    if not enriched_dir.exists():
        return 0
    return sum(1 for _ in enriched_dir.rglob("*.enriched.json"))


def _flatten_entities(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    items: list[str] = []
    for group in value.values():
        if isinstance(group, list):
            items.extend(str(item) for item in group if str(item).strip())
        elif str(group).strip():
            items.append(str(group))
    return " ".join(items)


def _claim_types(card: dict[str, Any]) -> str:
    values = []
    for fact in card.get("key_facts") or []:
        if isinstance(fact, dict):
            claim_type = _clean_str(fact.get("claim_type"))
            if claim_type:
                values.append(claim_type)
    return " ".join(sorted(set(values)))


def _join_texts(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value if str(item).strip())
    if str(value).strip():
        return str(value)
    return ""


def _first_text(*values: Any) -> str:
    for value in values:
        text = _clean_str(value)
        if text:
            return text
    return ""


def _clean_str(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _clean_snippet(value: Any) -> str:
    text = _clean_str(value).replace("\n", " ")
    return re.sub(r"\s+", " ", text)
