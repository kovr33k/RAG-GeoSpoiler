"""
Retrieval Composer — orchestrates multi-index search across LightRAG and Enriched Cards.
Supports multiple retrieval modes optimized for different analytical tasks.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from lightrag import LightRAG
from loader.lightrag_loader import query_rag_result
from retrieval import shadow_search
from retrieval.card_fts import CardFtsMatch, search_card_index
from retrieval.wiki_index import WikiSearchResult, find_wiki_context
from retrieval.wiki_resolver import WikiResolvedSource, resolve_wiki_references
import config

logger = logging.getLogger("geospoiler.retrieval.composer")


@dataclass
class SearchResult:
    source_path: str
    card_path: str | None
    title: str
    url: str
    relevance_reason: str
    snippets: list[str] = field(default_factory=list)
    broll_notes: str = ""
    is_primary: bool = True


@dataclass
class SearchPackage:
    query: str
    mode: str
    llm_answer: str
    primary_results: list[SearchResult]
    secondary_results: list[SearchResult]
    wiki_results: list[WikiSearchResult] = field(default_factory=list)
    wiki_source_references: dict[str, list[WikiResolvedSource]] = field(default_factory=dict)


@dataclass(frozen=True)
class CardSearchHit:
    source_path: str
    card_path: str | None
    title: str
    url: str
    score: float
    snippet: str
    backend: str


def _load_all_cards() -> list[dict]:
    cards = []
    enriched_dir = config.ENRICHED_DIR
    if not enriched_dir.exists():
        return cards
        
    for channel_dir in enriched_dir.iterdir():
        if not channel_dir.is_dir():
            continue
        for card_path in channel_dir.glob("*.enriched.json"):
            try:
                card = json.loads(card_path.read_text(encoding="utf-8"))
                if card.get("triage") == "keep":
                    card["_path"] = str(card_path)
                    cards.append(card)
            except Exception:
                pass
    return cards


_CARDS_ONLY_MODES = {"shadow", "cards", "cards-only"}


async def search(rag: LightRAG | None, query: str, mode: str = "recall") -> SearchPackage:
    """
    Execute a multi-index search based on the specified mode.
    Modes:
      - recall: Broadest search (LightRAG mix + shadow keyword)
      - broll: Visual-focused search
      - thesis: Focus on high-level analytical claims
      - entity: Focus on specific actors/locations
      - shadow/cards/cards-only: Fast enriched-card keyword search without LightRAG/LLM
    """
    mode = mode.strip().lower()
    logger.info(f"Composer executing search (mode={mode}) for: {query}")
    
    llm_answer = ""
    primary = {}
    secondary = {}
    wiki_results = _find_wiki_results(query)
    wiki_source_references = _resolve_wiki_references(wiki_results)

    cards_only = mode in _CARDS_ONLY_MODES

    # 1. Run LightRAG unless this is an explicit cards-only diagnostic search.
    lightrag_mode_map = {
        "recall": "mix" if config.RERANKER_ENABLED else "hybrid",
        "broll": "hybrid",
        "thesis": "global",
        "entity": "local"
    }
    lr_mode = lightrag_mode_map.get(mode, "hybrid")
    
    # We use "source" profile to get concrete citations if possible
    lr_profile = "source" if mode in ["recall", "entity"] else "overview"
    
    if cards_only:
        llm_answer = "Cards-only search: LightRAG/LLM query was not run."
    else:
        if rag is None:
            raise ValueError("rag is required unless mode is shadow/cards/cards-only")
        lr_result = await query_rag_result(rag, query, mode=lr_mode, query_profile=lr_profile)
        llm_answer = lr_result.get("response", "No answer from LightRAG.")
    
    cards = _load_all_cards()
    path_to_card = _index_cards_by_path(cards)

    # Process LightRAG references
    # references is usually a list of dicts from LightRAG if we enabled it, 
    # but currently our lightrag_loader just returns the result dict which might have 'references' depending on version.
    # We will also use shadow search as a strong backup.

    # 2. Run local card search. G2 prefers SQLite FTS5 and keeps shadow_search as fallback.
    card_hits = _search_card_hits(query, top_k=20)
    
    # 3. Mode-specific filtering on cards
    query_lower = query.lower()
    
    if mode == "broll":
        # Look for broll potential
        for card in cards:
            v = card.get("visual", {})
            if v.get("broll_potential") in ("high", "medium") and query_lower in v.get("broll_notes", "").lower():
                path = card.get("provenance", {}).get("normalized_file", card["_path"])
                if path not in primary:
                    primary[path] = _card_to_result(card, "B-roll Match")
                    primary[path].snippets.append(v.get("broll_notes", ""))

    elif mode == "thesis":
        for card in cards:
            theses = card.get("theses", [])
            for t in theses:
                if query_lower in t.lower():
                    path = card.get("provenance", {}).get("normalized_file", card["_path"])
                    if path not in primary:
                        primary[path] = _card_to_result(card, "Thesis Match")
                    primary[path].snippets.append(t)

    elif mode == "entity":
        for card in cards:
            entities = card.get("entities", {})
            found = False
            for cat, ents in entities.items():
                for e in ents:
                    if query_lower in str(e).lower():
                        found = True
                        break
            if found:
                path = card.get("provenance", {}).get("normalized_file", card["_path"])
                if path not in primary:
                    primary[path] = _card_to_result(card, "Entity Match")

    # 4. Integrate local card-search results
    for hit in card_hits:
        # If it's not already in primary, add it to secondary (or primary for broad/card-only modes).
        key = hit.source_path or hit.card_path or hit.title
        if key not in primary:
            card = _lookup_card_for_hit(path_to_card, hit)
            res = (
                _card_to_result(card, _card_search_reason(hit))
                if card
                else _hit_to_result(hit, _card_search_reason(hit))
            )
            if hit.snippet:
                res.snippets.append(hit.snippet)

            if (mode == "recall" and len(primary) < 5) or cards_only:
                primary[key] = res
            else:
                if key not in secondary:
                    secondary[key] = res

    # Convert to lists
    primary_list = list(primary.values())
    secondary_list = list(secondary.values())

    return SearchPackage(
        query=query,
        mode=mode,
        llm_answer=llm_answer,
        primary_results=primary_list,
        secondary_results=secondary_list,
        wiki_results=wiki_results,
        wiki_source_references=wiki_source_references,
    )


def _card_to_result(card: dict, reason: str) -> SearchResult:
    prov = card.get("provenance", {})
    return SearchResult(
        source_path=prov.get("normalized_file", card.get("_path", "")),
        card_path=card.get("_path"),
        title=f"{prov.get('channel_name', '?')} - {prov.get('date', '?')[:10]}",
        url=prov.get("post_url", ""),
        relevance_reason=reason,
        snippets=[],
        broll_notes=card.get("visual", {}).get("broll_notes", "")
    )


def _index_cards_by_path(cards: list[dict]) -> dict[str, dict]:
    indexed = {}
    for card in cards:
        provenance = card.get("provenance", {}) if isinstance(card.get("provenance"), dict) else {}
        for key in (provenance.get("normalized_file"), card.get("_path")):
            if key:
                indexed[str(key)] = card
    return indexed


def _search_card_hits(query: str, top_k: int = 20) -> list[CardSearchHit]:
    try:
        fts_matches = search_card_index(query, top_k=top_k, db_path=config.CARD_FTS_DB_PATH)
    except Exception as exc:
        logger.warning("Card FTS search failed; falling back to shadow_search: %s", exc)
        fts_matches = []

    if fts_matches:
        return [_fts_match_to_hit(match) for match in fts_matches]

    return [_shadow_match_to_hit(match) for match in shadow_search.search(query, top_k=top_k)]


def _fts_match_to_hit(match: CardFtsMatch) -> CardSearchHit:
    return CardSearchHit(
        source_path=match.normalized_file,
        card_path=match.card_path or None,
        title=match.title,
        url=match.post_url,
        score=match.score,
        snippet=match.snippet,
        backend="fts",
    )


def _shadow_match_to_hit(match: shadow_search.ShadowMatch) -> CardSearchHit:
    return CardSearchHit(
        source_path=match.source_path,
        card_path=match.card_path,
        title=match.title,
        url="",
        score=match.score,
        snippet=match.snippet,
        backend="shadow",
    )


def _lookup_card_for_hit(path_to_card: dict[str, dict], hit: CardSearchHit) -> dict | None:
    for key in (hit.source_path, hit.card_path or ""):
        if key and key in path_to_card:
            return path_to_card[key]
    return None


def _hit_to_result(hit: CardSearchHit, reason: str) -> SearchResult:
    return SearchResult(
        source_path=hit.source_path,
        card_path=hit.card_path,
        title=hit.title,
        url=hit.url,
        relevance_reason=reason,
        snippets=[],
    )


def _card_search_reason(hit: CardSearchHit) -> str:
    if hit.backend == "fts":
        return f"FTS Match (BM25 score: {hit.score:.3g})"
    return f"Shadow fallback match (score: {hit.score:.1f})"


def _find_wiki_results(query: str) -> list[WikiSearchResult]:
    if not config.WIKI_ENABLED:
        return []
    try:
        return find_wiki_context(query, wiki_dir=config.WIKI_DIR, top_k=config.WIKI_TOP_K)
    except OSError as exc:
        logger.warning("Wiki context search failed: %s", exc)
        return []


def _resolve_wiki_references(results: list[WikiSearchResult]) -> dict[str, list[WikiResolvedSource]]:
    if not config.WIKI_ENABLED or not results:
        return {}
    try:
        return resolve_wiki_references(
            [result.page_path for result in results],
            wiki_dir=config.WIKI_DIR,
            index_dir=config.WIKI_INDEX_DIR,
            enriched_dir=config.ENRICHED_DIR,
        )
    except OSError as exc:
        logger.warning("Wiki source resolution failed: %s", exc)
        return {}
