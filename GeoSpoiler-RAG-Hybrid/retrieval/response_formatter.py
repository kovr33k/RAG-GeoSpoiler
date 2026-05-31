"""
Response Formatter — formats SearchPackage results into a clean markdown document.
"""

from retrieval.composer import SearchPackage

_CARDS_ONLY_MODES = {"shadow", "cards", "cards-only"}
_MAX_WIKI_PRIMARY_SOURCES = 3


def format_search_results(package: SearchPackage) -> str:
    """Render a SearchPackage into a readable markdown report."""
    
    parts = []
    
    # 1. Header
    parts.append(f"# Итоги поиска: «{package.query}»")
    parts.append(f"**Режим поиска:** {package.mode}\n")
    
    # 2. Graph/card synthesis note
    if package.mode in _CARDS_ONLY_MODES:
        parts.append("## Поиск по карточкам")
    else:
        parts.append("## Синтез графа (LightRAG)")
    if package.llm_answer:
        parts.append(package.llm_answer.strip())
    else:
        parts.append("*Нет прямого ответа от графа.*")
    parts.append("\n---\n")

    if package.wiki_results:
        parts.extend(_format_wiki_context(package))
        parts.append("\n---\n")
    
    # 3. Primary Sources
    parts.append("## Основные материалы (Прямые совпадения)")
    if package.primary_results:
        for i, res in enumerate(package.primary_results, start=1):
            parts.append(f"### {i}. {res.title}")
            parts.append(f"- **Ссылка:** {res.url}")
            parts.append(f"- **Причина:** {res.relevance_reason}")
            if res.broll_notes:
                parts.append(f"- **B-roll:** {res.broll_notes}")
            if res.snippets:
                parts.append("- **Фрагменты:**")
                for snip in res.snippets:
                    parts.append(f"  > {snip}")
            parts.append("")
    else:
        parts.append("*Прямых совпадений не найдено.*\n")
        
    # 4. Secondary Sources
    if package.secondary_results:
        parts.append("## Дополнительные материалы (BM25 / Keyword)")
        for i, res in enumerate(package.secondary_results, start=1):
            parts.append(f"### {i}. {res.title}")
            parts.append(f"- **Ссылка:** {res.url}")
            parts.append(f"- **Причина:** {res.relevance_reason}")
            if res.snippets:
                parts.append("- **Фрагменты:**")
                for snip in res.snippets:
                    # truncate long snippets
                    if len(snip) > 150:
                        snip = snip[:150] + "..."
                    parts.append(f"  > {snip}")
            parts.append("")
            
    return "\n".join(parts)


def _format_wiki_context(package: SearchPackage) -> list[str]:
    lines = [
        "## Wiki Memory Context",
        "*Local wiki pages are memory/context, not primary sources. Telegram/YouTube evidence is listed separately under each page.*",
        "",
    ]

    for i, res in enumerate(package.wiki_results, start=1):
        lines.append(f"### {i}. {res.title}")
        lines.append(f"- **Memory page:** {res.page_path}")
        lines.append(f"- **Memory score:** {res.score}")
        if res.snippet:
            lines.append("- **Memory snippet:**")
            lines.append(f"  > {_truncate(res.snippet, 260)}")
        if res.sources:
            lines.append(f"- **Referenced source ids:** {', '.join(res.sources[:5])}")

        source_refs = package.wiki_source_references.get(res.page_path, [])
        lines.extend(_format_wiki_primary_sources(source_refs))
        lines.append("")

    return lines


def _format_wiki_primary_sources(source_refs: list) -> list[str]:
    if not source_refs:
        return ["- **Primary Telegram/YouTube sources:** not resolved"]

    lines = ["- **Primary Telegram/YouTube sources:**"]
    for ref in source_refs[:_MAX_WIKI_PRIMARY_SOURCES]:
        lines.extend(_format_one_wiki_source(ref))
    if len(source_refs) > _MAX_WIKI_PRIMARY_SOURCES:
        lines.append(f"  - plus {len(source_refs) - _MAX_WIKI_PRIMARY_SOURCES} more resolved source(s)")
    return lines


def _format_one_wiki_source(ref) -> list[str]:
    lines = []
    if ref.youtube_url:
        lines.append(f"  - YouTube: {ref.youtube_url}")
        if ref.post_url:
            lines.append(f"    - Telegram post: {ref.post_url}")
    elif ref.post_url:
        lines.append(f"  - Telegram: {ref.post_url}")
    elif ref.normalized_file:
        lines.append(f"  - Normalized file: {ref.normalized_file}")
    else:
        lines.append(f"  - Source id: {ref.source_id}")

    if ref.normalized_file:
        lines.append(f"    - normalized_file: {ref.normalized_file}")
    if ref.source_id:
        lines.append(f"    - source_id: {ref.source_id}")
    if ref.date:
        lines.append(f"    - date: {ref.date}")
    return lines


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."
