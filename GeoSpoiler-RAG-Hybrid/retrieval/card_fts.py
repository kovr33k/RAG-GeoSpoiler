import json
import logging
import re
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import config
from retrieval.card_text import card_search_text, strip_metadata_lines
from retrieval.query_terms import add_compound_terms, expand_query_terms, matches_term
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
class WikiFtsBuildStats:
    db_path: Path
    pages_seen: int
    pages_indexed: int
    pages_skipped: int


@dataclass(frozen=True)
class CardFtsMatch:
    source_id: str
    card_path: str
    normalized_file: str
    post_url: str
    title: str
    score: float
    snippet: str


@dataclass(frozen=True)
class WikiFtsMatch:
    page_path: str
    page_type: str
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


def rebuild_wiki_index(
    wiki_dir: Path = config.WIKI_DIR,
    db_path: Path = config.CARD_FTS_DB_PATH,
) -> WikiFtsBuildStats:
    """Rebuild the local SQLite FTS5 index for wiki pages."""
    records = list(iter_wiki_records(wiki_dir))
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(db_path)) as conn:
        _create_wiki_schema(conn)
        conn.execute("DELETE FROM wiki_fts")
        conn.executemany(
            """
            INSERT INTO wiki_fts (
                page_path,
                page_type,
                title,
                content,
                entities,
                topics
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            records,
        )
        conn.commit()

    seen = _count_wiki_pages(wiki_dir)
    indexed = len(records)
    return WikiFtsBuildStats(
        db_path=db_path,
        pages_seen=seen,
        pages_indexed=indexed,
        pages_skipped=max(0, seen - indexed),
    )


def search_card_index(
    query: str,
    top_k: int = 10,
    db_path: Path = config.CARD_FTS_DB_PATH,
) -> list[CardFtsMatch]:
    """Search the local card FTS index without calling LightRAG or an LLM."""
    query_terms = _query_terms(query)
    match_query = _to_fts_query(query)
    if not match_query or not db_path.exists():
        return []

    limit = max(1, top_k)
    fetch_limit = max(limit, min(100, limit * 5))
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
                search_text,
                bm25(cards_fts) AS rank,
                snippet(cards_fts, 5, '...', '...', ' ', 24) AS snippet
            FROM cards_fts
            WHERE cards_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (match_query, fetch_limit),
        ).fetchall()
        ranked = [
            (
                _coverage_score(str(row["search_text"] or ""), query_terms),
                -float(row["rank"]),
                CardFtsMatch(
                    source_id=row["source_id"],
                    card_path=row["card_path"],
                    normalized_file=row["normalized_file"],
                    post_url=row["post_url"],
                    title=row["title"],
                    score=round(-float(row["rank"]), 6),
                    snippet=_clean_snippet(row["snippet"]),
                ),
            )
            for row in rows
        ]
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in ranked[:limit]]


def search_wiki_index(
    query: str,
    top_k: int = 10,
    db_path: Path = config.CARD_FTS_DB_PATH,
) -> list[WikiFtsMatch]:
    """Search the local wiki FTS table without mixing card results."""
    query_terms = _query_terms(query)
    match_query = _to_fts_query(query)
    if not match_query or not db_path.exists():
        return []

    limit = max(1, top_k)
    fetch_limit = max(limit, min(100, limit * 5))
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        _create_wiki_schema(conn)
        rows = conn.execute(
            """
            SELECT
                page_path,
                page_type,
                title,
                content,
                bm25(wiki_fts) AS rank,
                snippet(wiki_fts, 3, '...', '...', ' ', 24) AS snippet
            FROM wiki_fts
            WHERE wiki_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (match_query, fetch_limit),
        ).fetchall()
        ranked = [
            (
                _coverage_score(str(row["content"] or ""), query_terms),
                -float(row["rank"]),
                WikiFtsMatch(
                    page_path=row["page_path"],
                    page_type=row["page_type"],
                    title=row["title"],
                    score=round(-float(row["rank"]), 6),
                    snippet=_clean_snippet(row["snippet"]),
                ),
            )
            for row in rows
        ]
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in ranked[:limit]]


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


def iter_wiki_records(wiki_dir: Path = config.WIKI_DIR) -> Iterable[tuple[str, str, str, str, str, str]]:
    if not wiki_dir.exists():
        return

    from retrieval import wiki_index

    for page_path in wiki_index.iter_wiki_pages(wiki_dir):
        try:
            text = page_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.debug("Wiki FTS could not read %s: %s", page_path, exc)
            continue
        rel_path = page_path.relative_to(wiki_dir).as_posix()
        title = _wiki_title(text, rel_path)
        page_type = _wiki_page_type(rel_path, text)
        yield (
            rel_path,
            page_type,
            title,
            text,
            _wiki_section_terms(text, "Entities"),
            _wiki_section_terms(text, "Topics"),
        )


def card_to_fts_record(card: dict[str, Any], card_path: Path) -> CardFtsRecord | None:
    if card.get("triage") != "keep":
        return None

    provenance = card.get("provenance") if isinstance(card.get("provenance"), dict) else {}
    search_text = card_search_text(card, card_path)
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


def _create_wiki_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts USING fts5(
            page_path UNINDEXED,
            page_type UNINDEXED,
            title,
            content,
            entities,
            topics,
            tokenize='unicode61'
        )
        """
    )


def _to_fts_query(query: str) -> str:
    terms = _query_terms(query)
    return " OR ".join(f"{term}*" for term in terms)


def _query_terms(query: str) -> list[str]:
    terms = []
    seen = set()
    for term in expand_query_terms(_TOKEN_RE.findall(query.casefold())):
        if term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return terms


def _coverage_score(search_text: str, query_terms: list[str]) -> int:
    ranking_text = strip_metadata_lines(search_text)
    text_tokens = add_compound_terms(_TOKEN_RE.findall(ranking_text.casefold()))
    return sum(
        1
        for term in query_terms
        if any(_matches_term(token, term) for token in text_tokens)
    )


def _matches_term(token: str, term: str) -> bool:
    return matches_term(token, term)


def _count_enriched_cards(enriched_dir: Path) -> int:
    if not enriched_dir.exists():
        return 0
    return sum(1 for _ in enriched_dir.rglob("*.enriched.json"))


def _count_wiki_pages(wiki_dir: Path) -> int:
    if not wiki_dir.exists():
        return 0
    from retrieval import wiki_index

    return sum(1 for _ in wiki_index.iter_wiki_pages(wiki_dir))


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


def _clean_str(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _clean_snippet(value: Any) -> str:
    text = _clean_str(value).replace("\n", " ")
    return re.sub(r"\s+", " ", text)


def _wiki_title(text: str, rel_path: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return Path(rel_path).stem.replace("-", " ")


def _wiki_page_type(rel_path: str, text: str) -> str:
    frontmatter = _parse_frontmatter(text)
    wiki_type = str(frontmatter.get("wiki_type") or "").strip()
    if wiki_type:
        return wiki_type
    if rel_path.startswith("claims/"):
        return "claim"
    if rel_path.startswith("entities/"):
        return "entity"
    if rel_path.startswith("topics/"):
        return "topic"
    return "wiki"


def _wiki_section_terms(text: str, section_name: str) -> str:
    pattern = re.compile(rf"^##\s+{re.escape(section_name)}\s*$", flags=re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    rest = text[match.end() :]
    next_section = re.search(r"^##\s+", rest, flags=re.MULTILINE)
    section = rest[: next_section.start()] if next_section else rest
    return _clean_snippet(section)


def _parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return {}
    data: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()
    return data
