"""
Resolve wiki-memory references back to primary source metadata.

The resolver follows the D2 chain:
wiki page -> page_to_sources.json -> source_id -> enriched card -> post_url /
normalized_file. It is local-only and does not call LightRAG or any LLM.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import config
from retrieval import wiki_index
from retrieval.source_registry import SourcePassport, resolve_source

logger = logging.getLogger("geospoiler.retrieval.wiki_resolver")


@dataclass(frozen=True)
class WikiResolvedSource:
    page_path: str
    source_id: str
    post_url: str
    normalized_file: str
    card_path: str
    youtube_url: str
    channel_name: str
    date: str

    @property
    def primary_url(self) -> str:
        return self.youtube_url or self.post_url


def resolve_wiki_references(
    page_paths: Iterable[str],
    wiki_dir: Path = config.WIKI_DIR,
    index_dir: Path = config.WIKI_INDEX_DIR,
    enriched_dir: Path = config.ENRICHED_DIR,
    registry_db_path: Path | None = None,
    limit_per_page: int = 5,
) -> dict[str, list[WikiResolvedSource]]:
    """Resolve wiki page paths to original source metadata."""
    page_to_sources = _load_page_to_sources(wiki_dir, index_dir)
    source_cards: dict[str, dict] | None = None
    registry_db_path = registry_db_path or config.SOURCE_REGISTRY_DB_PATH
    resolved: dict[str, list[WikiResolvedSource]] = {}

    for page_path in page_paths:
        page_sources = page_to_sources.get(page_path, [])
        if not page_sources:
            page_sources = _related_claim_sources(page_path, wiki_dir, page_to_sources)

        page_results: list[WikiResolvedSource] = []
        seen_sources: set[str] = set()
        for source_id in page_sources:
            if source_id in seen_sources:
                continue
            seen_sources.add(source_id)
            source = _resolved_source_from_registry(page_path, source_id, registry_db_path)
            if source is None:
                if source_cards is None:
                    source_cards = _load_source_cards(enriched_dir)
                card = source_cards.get(source_id)
                if not card:
                    continue
                source = _resolved_source_from_card(page_path, source_id, card)
            page_results.append(source)
            if len(page_results) >= limit_per_page:
                break
        resolved[page_path] = page_results

    return resolved


def _load_page_to_sources(wiki_dir: Path, index_dir: Path) -> dict[str, list[str]]:
    path = index_dir / wiki_index.PAGE_INDEX_FILENAME
    data = _load_json(path)
    if not data:
        data, _source_to_pages = wiki_index.build_page_source_indexes(wiki_dir)
    return {
        str(page_path): [str(source_id) for source_id in sources]
        for page_path, sources in data.items()
        if isinstance(sources, list)
    }


def _load_source_cards(enriched_dir: Path) -> dict[str, dict]:
    cards: dict[str, dict] = {}
    for card_path, card in wiki_index.iter_enriched_cards(enriched_dir):
        source_id = wiki_index.extract_source_id(card)
        if not source_id:
            continue
        card = dict(card)
        card["_path"] = str(card_path)
        cards[source_id] = card
    return cards


def _related_claim_sources(
    page_path: str,
    wiki_dir: Path,
    page_to_sources: dict[str, list[str]],
) -> list[str]:
    path = wiki_dir / page_path
    if not path.exists() or not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []

    sources: list[str] = []
    seen: set[str] = set()
    for claim_path in _extract_related_claim_paths(text):
        for source_id in page_to_sources.get(claim_path, []):
            if source_id in seen:
                continue
            seen.add(source_id)
            sources.append(source_id)
    return sources


def _extract_related_claim_paths(text: str) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip().lstrip("-").strip()
        if not stripped.startswith("claims/") or not stripped.endswith(".md"):
            continue
        claim_path = stripped.split()[0]
        if claim_path in seen:
            continue
        seen.add(claim_path)
        paths.append(claim_path)
    return paths


def _resolved_source_from_registry(
    page_path: str,
    source_id: str,
    registry_db_path: Path,
) -> WikiResolvedSource | None:
    try:
        passport = resolve_source(source_id, db_path=registry_db_path)
    except Exception as exc:
        logger.debug("Source registry lookup failed for %s: %s", source_id, exc)
        return None
    if passport is None:
        return None
    return _resolved_source_from_passport(page_path, passport)


def _resolved_source_from_passport(page_path: str, passport: SourcePassport) -> WikiResolvedSource:
    return WikiResolvedSource(
        page_path=page_path,
        source_id=passport.source_id,
        post_url=passport.post_url,
        normalized_file=passport.normalized_file,
        card_path=passport.card_path,
        youtube_url=passport.youtube_url,
        channel_name=passport.channel_name,
        date=passport.date,
    )


def _resolved_source_from_card(page_path: str, source_id: str, card: dict) -> WikiResolvedSource:
    provenance = card.get("provenance") if isinstance(card.get("provenance"), dict) else {}
    source_chain = card.get("source_chain") if isinstance(card.get("source_chain"), dict) else {}
    youtube_url = _clean_str(source_chain.get("youtube_url"))
    return WikiResolvedSource(
        page_path=page_path,
        source_id=source_id,
        post_url=_clean_str(provenance.get("post_url")),
        normalized_file=_clean_str(provenance.get("normalized_file")),
        card_path=_clean_str(card.get("_path")),
        youtube_url=youtube_url,
        channel_name=_clean_str(provenance.get("channel_name")),
        date=_clean_str(provenance.get("date")),
    )


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _clean_str(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()
