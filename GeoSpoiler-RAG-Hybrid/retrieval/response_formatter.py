"""
Response Formatter — formats SearchPackage results into a clean markdown document.
"""

from retrieval.composer import SearchPackage

_CARDS_ONLY_MODES = {"shadow", "cards", "cards-only"}


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
