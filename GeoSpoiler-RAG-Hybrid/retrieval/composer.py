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
    path_to_card = {c.get("provenance", {}).get("normalized_file", c["_path"]): c for c in cards}

    # Process LightRAG references
    # references is usually a list of dicts from LightRAG if we enabled it, 
    # but currently our lightrag_loader just returns the result dict which might have 'references' depending on version.
    # We will also use shadow search as a strong backup.

    # 2. Run Shadow Search
    shadow_results = shadow_search.search(query, top_k=20)
    
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

    # 4. Integrate shadow results
    for sr in shadow_results:
        # If it's not already in primary, add it to secondary (or primary for broad/card-only modes).
        if sr.source_path not in primary:
            card = path_to_card.get(sr.source_path)
            if card:
                res = _card_to_result(card, f"Keyword Match (Score: {sr.score:.1f})")
                res.snippets.append(sr.snippet)
                
                if (mode == "recall" and len(primary) < 5) or cards_only:
                    primary[sr.source_path] = res
                else:
                    if sr.source_path not in secondary:
                        secondary[sr.source_path] = res

    # Convert to lists
    primary_list = list(primary.values())
    secondary_list = list(secondary.values())

    return SearchPackage(
        query=query,
        mode=mode,
        llm_answer=llm_answer,
        primary_results=primary_list,
        secondary_results=secondary_list
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
