"""
Lightweight wiki-memory indexes.

This module intentionally stays file-based: no embeddings, no vector DB, and no
LightRAG calls. It builds service indexes around existing wiki pages and can read
enriched cards to derive stable source metadata for later wiki build steps.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import config


SOURCE_INDEX_FILENAME = "source_to_pages.json"
PAGE_INDEX_FILENAME = "page_to_sources.json"
CLAIM_INDEX_FILENAME = "claim_to_sources.json"

_SOURCE_ID_RE = re.compile(r"telegram:[^\r\n\]\),;]+?:[^\s\r\n\]\),.;]+")
_TOKEN_RE = re.compile(r"[\w-]+", re.UNICODE)
_QUERY_TERM_PREFIX_ALIASES = {
    "трамп": ("trump", "donald"),
    "орбан": ("orban", "viktor"),
    "венгр": ("hungary", "hungarian"),
    "куб": ("cuba", "cuban"),
    "росс": ("russia", "russian"),
    "сша": ("usa", "united", "states"),
    "америк": ("usa", "united", "states"),
    "украин": ("ukraine", "ukrainian"),
    "ультралев": ("ultraleft", "left"),
    "ультраправ": ("ultraright", "right"),
    "адг": ("afd",),
    "балти": ("baltic",),
    "эстон": ("estonia", "estonian"),
    "нарв": ("narva",),
    "слова": ("slovakia", "slovak"),
    "фицо": ("fico",),
    "стармер": ("starmer",),
    "британ": ("britain", "uk", "united", "kingdom"),
    "северокор": ("north", "korea", "korean"),
}
_CONTENT_HASH_FIELDS = (
    "provenance",
    "content_type",
    "triage",
    "language",
    "summary",
    "key_facts",
    "entities",
    "topics",
    "quotes",
    "events",
    "source_chain",
    "graph_text",
    "search_text",
)


@dataclass(frozen=True)
class EnrichedSource:
    source_id: str | None
    content_hash: str
    card_path: str
    post_url: str
    normalized_file: str
    channel_name: str
    channel_id: str
    message_id: str
    date: str


@dataclass(frozen=True)
class WikiSearchResult:
    page_path: str
    score: int
    title: str
    snippet: str
    sources: list[str]


@dataclass(frozen=True)
class WikiIndexBuildResult:
    source_to_pages_path: Path
    page_to_sources_path: Path
    claim_to_sources_path: Path
    page_count: int
    source_count: int
    claim_count: int
    enriched_source_count: int


def load_enriched_card(path: Path) -> dict[str, Any]:
    """Read one enriched card JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def iter_enriched_cards(enriched_dir: Path = config.ENRICHED_DIR) -> Iterable[tuple[Path, dict[str, Any]]]:
    """Yield readable enriched cards under output/enriched."""
    if not enriched_dir.exists():
        return
    for path in sorted(enriched_dir.rglob("*.enriched.json")):
        try:
            yield path, load_enriched_card(path)
        except (OSError, json.JSONDecodeError):
            continue


def extract_source_id(card_or_provenance: dict[str, Any]) -> str | None:
    """Build a stable source id from Telegram provenance.

    Preferred form: telegram:{channel_id}:{message_id}
    Fallback form:  telegram:{channel_name}:{message_id}
    """
    provenance = card_or_provenance.get("provenance")
    if not isinstance(provenance, dict):
        provenance = card_or_provenance

    existing = _clean_str(provenance.get("source_id"))
    if existing:
        return existing

    message_id = _clean_str(provenance.get("message_id"))
    if not message_id:
        return None

    channel_id = _clean_str(provenance.get("channel_id"))
    if channel_id:
        return f"telegram:{channel_id}:{message_id}"

    channel_name = _clean_str(provenance.get("channel_name"))
    if channel_name:
        return f"telegram:{channel_name}:{message_id}"

    return None


def compute_content_hash(card: dict[str, Any]) -> str:
    """Compute a stable hash for source-relevant enriched card content."""
    payload = {key: card.get(key) for key in _CONTENT_HASH_FIELDS if key in card}
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def get_enriched_source(path: Path, card: dict[str, Any]) -> EnrichedSource:
    """Derive source metadata from an enriched card."""
    provenance = card.get("provenance") if isinstance(card.get("provenance"), dict) else {}
    return EnrichedSource(
        source_id=extract_source_id(card),
        content_hash=compute_content_hash(card),
        card_path=str(path),
        post_url=_clean_str(provenance.get("post_url")),
        normalized_file=_clean_str(provenance.get("normalized_file")),
        channel_name=_clean_str(provenance.get("channel_name")),
        channel_id=_clean_str(provenance.get("channel_id")),
        message_id=_clean_str(provenance.get("message_id")),
        date=_clean_str(provenance.get("date")),
    )


def collect_enriched_sources(enriched_dir: Path = config.ENRICHED_DIR) -> list[EnrichedSource]:
    """Read enriched cards and return source metadata for cards that parse."""
    return [get_enriched_source(path, card) for path, card in iter_enriched_cards(enriched_dir)]


def extract_page_sources(text: str) -> list[str]:
    """Extract source ids referenced by a wiki page."""
    sources = []
    seen = set()
    for match in _SOURCE_ID_RE.finditer(text):
        source_id = match.group(0).strip().rstrip(".;:")
        if source_id and source_id not in seen:
            seen.add(source_id)
            sources.append(source_id)
    return sources


def iter_wiki_pages(wiki_dir: Path = config.WIKI_DIR) -> Iterable[Path]:
    """Yield content pages under the wiki directory, excluding operational files."""
    if not wiki_dir.exists():
        return
    for path in sorted(wiki_dir.rglob("*.md")):
        if path.name.startswith("_"):
            continue
        yield path


def build_page_source_indexes(wiki_dir: Path = config.WIKI_DIR) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Build page_to_sources and source_to_pages from existing markdown pages."""
    page_to_sources: dict[str, list[str]] = {}
    source_to_pages: dict[str, list[str]] = {}

    for page_path in iter_wiki_pages(wiki_dir):
        rel_path = _relative_page_path(page_path, wiki_dir)
        try:
            sources = extract_page_sources(page_path.read_text(encoding="utf-8"))
        except OSError:
            continue
        page_to_sources[rel_path] = sources
        for source_id in sources:
            source_to_pages.setdefault(source_id, []).append(rel_path)

    for pages in source_to_pages.values():
        pages.sort()

    return page_to_sources, dict(sorted(source_to_pages.items()))


def build_claim_to_sources(page_to_sources: dict[str, list[str]]) -> dict[str, list[str]]:
    """Build a claim-page to sources mapping."""
    return {
        page_path: sources
        for page_path, sources in sorted(page_to_sources.items())
        if page_path.startswith("claims/")
    }


def build_wiki_indexes(
    wiki_dir: Path = config.WIKI_DIR,
    enriched_dir: Path = config.ENRICHED_DIR,
    index_dir: Path | None = None,
) -> WikiIndexBuildResult:
    """Build JSON indexes for current wiki pages."""
    index_dir = index_dir or (wiki_dir / "indexes")
    index_dir.mkdir(parents=True, exist_ok=True)

    page_to_sources, source_to_pages = build_page_source_indexes(wiki_dir)
    claim_to_sources = build_claim_to_sources(page_to_sources)
    enriched_sources = collect_enriched_sources(enriched_dir)

    source_to_pages_path = index_dir / SOURCE_INDEX_FILENAME
    page_to_sources_path = index_dir / PAGE_INDEX_FILENAME
    claim_to_sources_path = index_dir / CLAIM_INDEX_FILENAME

    _write_json(source_to_pages_path, source_to_pages)
    _write_json(page_to_sources_path, page_to_sources)
    _write_json(claim_to_sources_path, claim_to_sources)

    return WikiIndexBuildResult(
        source_to_pages_path=source_to_pages_path,
        page_to_sources_path=page_to_sources_path,
        claim_to_sources_path=claim_to_sources_path,
        page_count=len(page_to_sources),
        source_count=len(source_to_pages),
        claim_count=len(claim_to_sources),
        enriched_source_count=sum(1 for source in enriched_sources if source.source_id),
    )


def find_wiki_context(
    question: str,
    wiki_dir: Path = config.WIKI_DIR,
    top_k: int = config.WIKI_TOP_K,
) -> list[WikiSearchResult]:
    """Return ranked wiki pages for a question using simple keyword matching."""
    query_terms = _expand_query_terms(question)
    if not query_terms:
        return []

    results: list[WikiSearchResult] = []
    page_to_sources, _ = build_page_source_indexes(wiki_dir)

    for page_path in iter_wiki_pages(wiki_dir):
        try:
            text = page_path.read_text(encoding="utf-8")
        except OSError:
            continue
        rel_path = _relative_page_path(page_path, wiki_dir)
        score = _score_page(query_terms, rel_path, text)
        if score <= 0:
            continue
        results.append(
            WikiSearchResult(
                page_path=rel_path,
                score=score,
                title=_page_title(text, rel_path),
                snippet=_page_snippet(text, query_terms),
                sources=page_to_sources.get(rel_path, []),
            )
        )

    results.sort(key=lambda item: (-item.score, item.page_path))
    return results[:top_k]


def wiki_context_to_dicts(results: Iterable[WikiSearchResult]) -> list[dict[str, Any]]:
    """Convert ranked wiki context to JSON-serializable dictionaries."""
    return [asdict(result) for result in results]


def _score_page(query_terms: set[str], rel_path: str, text: str) -> int:
    path_terms = _tokenize(rel_path.replace("/", " ").replace("-", " "))
    text_terms = _tokenize(text)
    path_hits = len(query_terms & path_terms)
    text_hits = len(query_terms & text_terms)
    if path_hits == 0 and text_hits == 0:
        return 0

    type_boost = 10 if rel_path.startswith("claims/") else 3 if rel_path.startswith(("topics/", "entities/")) else 0
    return path_hits * 5 + text_hits + type_boost


def _page_title(text: str, rel_path: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return Path(rel_path).stem.replace("-", " ")


def _page_snippet(text: str, query_terms: set[str], max_chars: int = 240) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        line_terms = _tokenize(stripped)
        if query_terms & line_terms:
            return _truncate(stripped, max_chars)
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return _truncate(stripped, max_chars)
    return ""


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _tokenize(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(text) if len(token) > 1}


def _expand_query_terms(text: str) -> set[str]:
    terms = _tokenize(text)
    expanded = set(terms)

    for token in terms:
        for prefix, aliases in _QUERY_TERM_PREFIX_ALIASES.items():
            if token.startswith(prefix):
                expanded.update(aliases)

    for alias, canonical in config.LIGHTRAG_ENTITY_ALIASES.items():
        alias_terms = _tokenize(alias)
        if alias_terms and alias_terms <= terms:
            expanded.update(_tokenize(canonical))

    return expanded


def _relative_page_path(path: Path, wiki_dir: Path) -> str:
    return path.relative_to(wiki_dir).as_posix()


def _write_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _clean_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
