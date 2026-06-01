"""
Shadow Search — a fast keyword fallback search over memory cards.
Returns (file_path, score, snippet) for exact/partial term matches.
"""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import config

logger = logging.getLogger("geospoiler.retrieval.shadow")

_STOPWORDS = {
    "что",
    "как",
    "какой",
    "где",
    "кто",
    "это",
    "или",
    "для",
    "про",
    "при",
    "под",
    "над",
    "без",
    "базе",
    "говорится",
    "главный",
    "тезис",
    "тезисы",
    "автор",
    "продвигает",
}


@dataclass
class ShadowMatch:
    source_path: str
    card_path: str | None
    score: float
    snippet: str
    title: str


def _tokenize(text: str) -> list[str]:
    """Extract lowercase words >= 3 chars."""
    words = re.findall(r"\w{3,}", text.lower())
    return [word for word in words if word not in _STOPWORDS]


def _matches_term(token: str, term: str) -> bool:
    """Match exact words plus simple Slavic inflection variants by prefix."""
    if token == term:
        return True
    if len(token) < 4 or len(term) < 4:
        return False
    prefix_len = min(len(token), len(term), 6)
    if token[:prefix_len] == term[:prefix_len]:
        return True
    if min(len(token), len(term)) <= 5:
        return token[:4] == term[:4]
    return False


def _extract_snippet(text: str, query_terms: list[str], context_chars: int = 100) -> str:
    """Find the best window of text containing query terms."""
    text_lower = text.lower()
    best_pos = -1
    best_score = 0

    for term in query_terms:
        pos = text_lower.find(term)
        if pos != -1:
            # We found a match. To be simple, just return the first good window.
            start = max(0, pos - context_chars)
            end = min(len(text), pos + len(term) + context_chars)
            return "..." + text[start:end].replace("\n", " ").strip() + "..."
            
    return text[:context_chars*2].replace("\n", " ").strip() + "..."


def search(query: str, top_k: int = 10) -> list[ShadowMatch]:
    """
    Perform a keyword search over all enriched cards (fallback to normalized).
    """
    query_terms = set(_tokenize(query))
    if not query_terms:
        return []

    enriched_dir = config.ENRICHED_DIR
    matches = []

    # 1. Search in enriched cards
    if enriched_dir.exists():
        for channel_dir in enriched_dir.iterdir():
            if not channel_dir.is_dir():
                continue
            for card_path in channel_dir.glob("*.enriched.json"):
                try:
                    card = json.loads(card_path.read_text(encoding="utf-8"))
                    
                    if card.get("triage") != "keep":
                        continue
                        
                    # Use search_text if available, else graph_text, else summary
                    search_text = card.get("search_text", "")
                    if not search_text:
                        search_text = card.get("graph_text", "")
                    if not search_text:
                        search_text = card.get("summary", "")
                        
                    text_tokens = _tokenize(search_text)
                    
                    score = 0.0
                    for term in query_terms:
                        score += sum(1 for token in text_tokens if _matches_term(token, term))
                        
                    if score > 0:
                        source_path = card.get("provenance", {}).get("normalized_file", str(card_path))
                        prov = card.get("provenance", {})
                        title = f"{prov.get('channel_name', '?')} - {prov.get('date', '?')[:10]}"
                        
                        snippet = _extract_snippet(search_text, list(query_terms))
                        
                        matches.append(
                            ShadowMatch(
                                source_path=source_path,
                                card_path=str(card_path),
                                score=score,
                                snippet=snippet,
                                title=title,
                            )
                        )
                except Exception as e:
                    logger.debug(f"Shadow search failed to read {card_path}: {e}")

    # 2. (Optional) Search in normalized if we don't have enough enriched yet?
    # For now, relying on enriched is better since we will backfill anyway.

    # Sort by score descending
    matches.sort(key=lambda x: x.score, reverse=True)
    return matches[:top_k]
