"""Wiki-memory lookup, prompt formatting, and reference attachment for queries."""

from pathlib import Path
from typing import Any

import config
from loader.reference_hints import _existing_references, _merge_references
from loader.runtime import logger
from retrieval.wiki_index import WikiSearchResult, find_wiki_context
from retrieval.wiki_resolver import WikiResolvedSource, resolve_wiki_references


def _wiki_context_for_query(question: str) -> dict[str, Any] | None:
    """Return local wiki-memory matches and primary source references."""
    if not config.WIKI_ENABLED:
        return None

    try:
        results = find_wiki_context(
            question,
            wiki_dir=config.WIKI_DIR,
            top_k=config.WIKI_TOP_K,
        )
    except Exception as exc:
        logger.warning(f"Wiki context lookup failed; continuing without wiki context: {exc}")
        return None
    if not results:
        return None

    page_paths = [result.page_path for result in results]
    try:
        resolved = resolve_wiki_references(
            page_paths,
            wiki_dir=config.WIKI_DIR,
            index_dir=config.WIKI_INDEX_DIR,
            enriched_dir=config.ENRICHED_DIR,
        )
    except Exception as exc:
        logger.warning(f"Wiki reference resolution failed; continuing with unresolved wiki context: {exc}")
        resolved = {}

    wiki_pages = [_wiki_result_to_context(result, resolved.get(result.page_path, [])) for result in results]
    references = _wiki_references_from_context(wiki_pages)
    return {
        "pages": wiki_pages,
        "references": references,
    }


def _wiki_result_to_context(
    result: WikiSearchResult,
    resolved_sources: list[WikiResolvedSource],
) -> dict[str, Any]:
    return {
        "page_path": result.page_path,
        "title": result.title,
        "score": result.score,
        "snippet": result.snippet,
        "source_ids": list(result.sources),
        "resolved_sources": [
            {
                "source_id": source.source_id,
                "post_url": source.post_url,
                "youtube_url": source.youtube_url,
                "normalized_file": source.normalized_file,
                "card_path": source.card_path,
                "channel_name": source.channel_name,
                "date": source.date,
                "primary_url": source.primary_url,
            }
            for source in resolved_sources
        ],
    }


def _wiki_references_from_context(wiki_pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    for page_index, page in enumerate(wiki_pages, start=1):
        resolved_sources = page.get("resolved_sources") or []
        for source_index, source in enumerate(resolved_sources, start=1):
            normalized_file = str(source.get("normalized_file") or "").strip()
            card_path = str(source.get("card_path") or "").strip()
            references.append(
                {
                    "reference_id": f"wiki-{page_index}-{source_index}",
                    "file_path": _resolve_project_path(normalized_file) or card_path,
                    "post_url": str(source.get("post_url") or "").strip(),
                    "youtube_url": str(source.get("youtube_url") or "").strip(),
                    "source_id": str(source.get("source_id") or "").strip(),
                    "wiki_page": str(page.get("page_path") or "").strip(),
                    "channel": str(source.get("channel_name") or "").strip(),
                    "date": str(source.get("date") or "").strip(),
                }
            )
    return references


def _resolve_project_path(path_text: str) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    if path.is_absolute():
        return str(path)
    return str((config.PROJECT_ROOT / path).resolve(strict=False))


def _query_user_prompt_with_wiki(user_prompt: str, wiki_context: dict[str, Any] | None) -> str:
    if not wiki_context:
        return user_prompt
    formatted = _format_wiki_prompt_context(wiki_context)
    if not formatted:
        return user_prompt
    return f"{user_prompt}\n\n{formatted}"


def _format_wiki_prompt_context(wiki_context: dict[str, Any], max_pages: int = 5, max_sources: int = 3) -> str:
    pages = list(wiki_context.get("pages") or [])[:max_pages]
    if not pages:
        return ""

    lines = [
        "--- Local wiki memory context (read-only) ---",
        "Use this local wiki only as memory/context from the corpus, not as a primary source.",
        "When citing support, prefer the Telegram/YouTube/normalized sources listed under each wiki page.",
        "Keep source claims cautious; do not call anything fake/false/deepfake unless the listed evidence explicitly says so.",
    ]
    for page_index, page in enumerate(pages, start=1):
        lines.append("")
        lines.append(f"[wiki-{page_index}] {page.get('title', '')}")
        lines.append(f"page: {page.get('page_path', '')}")
        lines.append(f"score: {page.get('score', 0)}")
        snippet = str(page.get("snippet") or "").strip()
        if snippet:
            lines.append(f"memory_snippet: {snippet}")
        resolved_sources = list(page.get("resolved_sources") or [])[:max_sources]
        if resolved_sources:
            lines.append("primary_sources:")
            for source in resolved_sources:
                label = (
                    source.get("youtube_url")
                    or source.get("post_url")
                    or source.get("normalized_file")
                    or source.get("source_id")
                )
                parts = [str(label)]
                if source.get("source_id"):
                    parts.append(f"source_id={source['source_id']}")
                if source.get("date"):
                    parts.append(f"date={source['date']}")
                lines.append(f"- {' | '.join(parts)}")
        elif page.get("source_ids"):
            lines.append("source_ids: " + ", ".join(str(item) for item in page["source_ids"]))
    lines.append("--- End local wiki memory context ---")
    return "\n".join(lines)


def _attach_wiki_context(result: dict[str, Any], wiki_context: dict[str, Any] | None) -> dict[str, Any]:
    if not wiki_context:
        return result
    fixed = result.copy()
    data = dict(fixed.get("data") or {})
    wiki_references = list(wiki_context.get("references") or [])
    data["references"] = _merge_references(_existing_references(fixed), wiki_references)
    data["wiki_context"] = list(wiki_context.get("pages") or [])
    data["wiki_references"] = wiki_references
    fixed["data"] = data
    return fixed


def _wiki_context_from_result(result: dict[str, Any]) -> dict[str, Any] | None:
    data = result.get("data") if isinstance(result, dict) else {}
    if not isinstance(data, dict):
        return None
    pages = list(data.get("wiki_context") or [])
    if not pages:
        return None
    return {
        "pages": pages,
        "references": list(data.get("wiki_references") or []),
    }
