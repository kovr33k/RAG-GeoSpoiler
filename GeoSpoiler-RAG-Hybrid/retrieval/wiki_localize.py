"""Localize generated wiki markdown filenames and UI labels."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import config
from retrieval import wiki_index

AUTO_GENERATORS = {"wiki_ingest_v1", "wiki_coverage_backfill_v1", "wiki_entity_topic_seed_v1"}


@dataclass(frozen=True)
class WikiLocalizationStats:
    claims_renamed: int
    pages_rewritten: int
    indexed_pages: int
    indexed_sources: int


def localize_wiki_pages(
    wiki_dir: Path = config.WIKI_DIR,
    enriched_dir: Path = config.ENRICHED_DIR,
    index_dir: Path = config.WIKI_INDEX_DIR,
) -> WikiLocalizationStats:
    """Rename generated claim pages to Russian title slugs and localize labels."""
    wiki_dir.mkdir(parents=True, exist_ok=True)
    (wiki_dir / "claims").mkdir(parents=True, exist_ok=True)
    index_dir.mkdir(parents=True, exist_ok=True)

    renames = _rename_generated_claims(wiki_dir)
    pages_rewritten = _rewrite_markdown_pages(wiki_dir, renames)
    index_stats = wiki_index.build_wiki_indexes(wiki_dir=wiki_dir, enriched_dir=enriched_dir, index_dir=index_dir)
    return WikiLocalizationStats(
        claims_renamed=len(renames),
        pages_rewritten=pages_rewritten,
        indexed_pages=index_stats.page_count,
        indexed_sources=index_stats.source_count,
    )


def _rename_generated_claims(wiki_dir: Path) -> dict[str, str]:
    renames: dict[str, str] = {}
    claims_dir = wiki_dir / "claims"
    if not claims_dir.exists():
        return renames

    for path in sorted(claims_dir.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if not _is_auto_generated(text):
            continue
        title = _page_title(text)
        if not title or not _has_cyrillic(title):
            continue
        slug = _slugify(title)
        if not slug or slug == path.stem:
            continue
        target = _unique_path(claims_dir / f"{slug}.md")
        old_rel = _relative_path(path, wiki_dir)
        new_rel = _relative_path(target, wiki_dir)
        path.rename(target)
        renames[old_rel] = new_rel
    return renames


def _rewrite_markdown_pages(wiki_dir: Path, renames: dict[str, str]) -> int:
    rewritten = 0
    for path in sorted(wiki_dir.rglob("*.md")):
        if path.name.startswith("_"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        new_text = _replace_claim_refs(text, renames)
        new_text = _localize_labels(new_text)
        if new_text == text:
            continue
        path.write_text(new_text, encoding="utf-8")
        rewritten += 1
    return rewritten


def _replace_claim_refs(text: str, renames: dict[str, str]) -> str:
    for old_ref, new_ref in sorted(renames.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace(old_ref, new_ref)
    return text


def _localize_labels(text: str) -> str:
    replacements = {
        "## Evidence": "## Доказательства",
        "## Guardrails": "## Ограничения",
        "## Related Claims": "## Связанные утверждения",
        "## Source Resolution": "## Как найти источники",
        "## Related": "## Связанные страницы",
        "Review status:": "Статус проверки:",
        "Source count:": "Количество источников:",
        "Status:": "Статус:",
        "This entity page is a coverage hub generated from enriched-card mentions.": (
            "Эта страница-сводка по сущности автоматически собрана из упоминаний в enriched cards."
        ),
        "This topic page is a coverage hub generated from enriched-card mentions.": (
            "Эта страница-сводка по теме автоматически собрана из упоминаний в enriched cards."
        ),
        "- Resolve primary sources through claim evidence and output/wiki/indexes/page_to_sources.json.": (
            "- Первичные источники открываются через доказательства в claim pages и output/wiki/indexes/page_to_sources.json."
        ),
        "- This page does not add direct evidence beyond its related claim pages.": (
            "- Эта страница не добавляет прямых доказательств сверх связанных страниц-утверждений."
        ),
        "- Treat Status as corpus status, not external fact-check status.": (
            "- Поле `status` описывает поддержку внутри корпуса, а не внешнюю фактчек-оценку."
        ),
        "- Use only cited evidence items when answering from this page.": (
            "- Отвечая по этой странице, используй только процитированные доказательства."
        ),
        "- Do not use summaries, theses, or hypotheses as direct evidence.": (
            "- Не используй summaries, theses или hypotheses как прямое доказательство."
        ),
        "- Do not use summaries, theses, hypotheses, or interpretations as the only direct evidence for a claim.": (
            "- Не используй summaries, theses, hypotheses или interpretations как единственное прямое доказательство."
        ),
        "- Separate source claims from author interpretation.": (
            "- Отделяй утверждения источника от интерпретации автора."
        ),
        "- none": "- нет",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _is_auto_generated(text: str) -> bool:
    frontmatter = _parse_frontmatter(text)
    generated_by = frontmatter.get("generated_by", "")
    review_status = frontmatter.get("review_status", "")
    return generated_by in AUTO_GENERATORS and review_status in {"", "auto"}


def _parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return {}
    data: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def _page_title(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    index = 2
    while True:
        candidate = parent / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _relative_path(path: Path, wiki_dir: Path) -> str:
    return path.relative_to(wiki_dir).as_posix()


def _slugify(value: object) -> str:
    text = _clean_str(value).casefold()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text, flags=re.UNICODE).strip("-")
    return text[:120]


def _has_cyrillic(value: object) -> bool:
    return bool(re.search(r"[а-яё]", _clean_str(value), flags=re.IGNORECASE))


def _clean_str(value: object) -> str:
    return str(value).strip() if value is not None else ""
