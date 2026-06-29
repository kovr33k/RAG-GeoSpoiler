"""Coverage backfill for entity/topic wiki hub pages."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import config
from retrieval import wiki_index

GENERATED_BY = "wiki_coverage_backfill_v1"
AUTO_GENERATORS = {
    GENERATED_BY,
    "wiki_ingest_v1",
    "wiki_entity_topic_seed_v1",
}


@dataclass(frozen=True)
class WikiCoverageBackfillStats:
    pages_created: list[Path]
    pages_updated: list[Path]
    pages_skipped: list[Path]
    pages_deleted: list[Path]
    entities_considered: int
    topics_considered: int
    entities_created_or_updated: int
    topics_created_or_updated: int


ENTITY_ALIASES = {
    "рф": "Россия",
    "российская федерация": "Россия",
    "russia": "Россия",
    "ес": "Европа",
    "єс": "Европа",
    "eu": "Европа",
    "european union": "Европа",
    "евросоюз": "Европа",
    "европейский союз": "Европа",
    "страны европы": "Европа",
    "кндр": "Северная Корея",
    "north korea": "Северная Корея",
    "трамп": "Дональд Трамп",
    "donald trump": "Дональд Трамп",
}

SOURCE_LIKE_ENTITY_NAMES = {
    "24 канал",
    "ateo breaking",
    "bloomberg",
    "clash report",
    "financial times",
    "ft",
    "in factum",
    "reuters",
    "the moscow times",
    "the wall street journal",
    "unrealpolitik",
    "wall street journal",
    "wsj",
    "yep",
    "yigal levin",
    "yigal levin @yigallevin",
    "yigal levin yigallevin",
    "игаль левин",
    "радио свобода",
    "рбк україна",
}


@dataclass(frozen=True)
class CoverageCandidate:
    page_type: str
    name: str
    count: int
    related_claims: list[str]
    existing_path: Path | None = None


def run_wiki_coverage_backfill(
    wiki_dir: Path = config.WIKI_DIR,
    enriched_dir: Path = config.ENRICHED_DIR,
    index_dir: Path | None = None,
    today: date | None = None,
    threshold: int | None = None,
    limit: int | None = None,
) -> WikiCoverageBackfillStats:
    """Create/update missing entity and topic hub pages from claim pages."""
    today = today or date.today()
    threshold = threshold if threshold is not None else config.WIKI_COVERAGE_THRESHOLD
    limit = limit if limit is not None else config.WIKI_COVERAGE_LIMIT
    index_dir = index_dir or (wiki_dir / "indexes")
    for directory in [wiki_dir / "entities", wiki_dir / "topics", index_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    wiki_index.build_wiki_indexes(wiki_dir=wiki_dir, enriched_dir=enriched_dir, index_dir=index_dir)
    page_to_sources = _load_json(index_dir / wiki_index.PAGE_INDEX_FILENAME)
    source_to_claims = _source_to_claims(page_to_sources)
    cards = list(wiki_index.iter_enriched_cards(enriched_dir))

    entity_candidates = _coverage_candidates(
        cards=cards,
        page_type="entity",
        existing_paths=_existing_page_name_paths(wiki_dir / "entities"),
        source_to_claims=source_to_claims,
        threshold=threshold,
        limit=limit,
    )
    topic_candidates = _coverage_candidates(
        cards=cards,
        page_type="topic",
        existing_paths=_existing_page_name_paths(wiki_dir / "topics"),
        source_to_claims=source_to_claims,
        threshold=threshold,
        limit=limit,
    )

    deleted = _cleanup_stale_entity_pages(wiki_dir, entity_candidates)
    created: list[Path] = []
    updated: list[Path] = []
    skipped: list[Path] = []
    for candidate in entity_candidates + topic_candidates:
        path = candidate.existing_path or _candidate_path(wiki_dir, candidate)
        if path.exists() and not _can_update_page(path):
            skipped.append(path)
            continue
        text = _render_hub_page(candidate, today)
        old_text = path.read_text(encoding="utf-8") if path.exists() else None
        if old_text == text:
            continue
        path.write_text(text, encoding="utf-8")
        if old_text is None:
            created.append(path)
        else:
            updated.append(path)

    wiki_index.build_wiki_indexes(wiki_dir=wiki_dir, enriched_dir=enriched_dir, index_dir=index_dir)
    entity_changes = sum(1 for path in created + updated if path.parent.name == "entities")
    topic_changes = sum(1 for path in created + updated if path.parent.name == "topics")
    return WikiCoverageBackfillStats(
        pages_created=created,
        pages_updated=updated,
        pages_skipped=skipped,
        pages_deleted=deleted,
        entities_considered=len(entity_candidates),
        topics_considered=len(topic_candidates),
        entities_created_or_updated=entity_changes,
        topics_created_or_updated=topic_changes,
    )


def coverage_gaps(
    wiki_dir: Path = config.WIKI_DIR,
    enriched_dir: Path = config.ENRICHED_DIR,
    threshold: int | None = None,
    limit: int | None = None,
) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """Return frequent enriched-card entities/topics without wiki hub pages."""
    threshold = threshold if threshold is not None else config.WIKI_COVERAGE_THRESHOLD
    limit = limit if limit is not None else config.WIKI_COVERAGE_LIMIT
    cards = list(wiki_index.iter_enriched_cards(enriched_dir))
    existing_entities = _existing_coverage_names(wiki_dir / "entities", "entity")
    existing_topics = set(_existing_page_name_paths(wiki_dir / "topics"))
    return (
        _missing_counts(_mention_counts(cards, "entity"), existing_entities, threshold, limit),
        _missing_counts(_mention_counts(cards, "topic"), existing_topics, threshold, limit),
    )


def _coverage_candidates(
    *,
    cards: list[tuple[Path, dict[str, Any]]],
    page_type: str,
    existing_paths: dict[str, Path],
    source_to_claims: dict[str, list[str]],
    threshold: int,
    limit: int,
) -> list[CoverageCandidate]:
    counts: Counter[str] = Counter()
    related: dict[str, set[str]] = defaultdict(set)
    for _path, card in cards:
        if card.get("triage") != "keep":
            continue
        source_id = wiki_index.extract_source_id(card)
        names = _coverage_names(card, page_type)
        for name in names:
            counts[name] += 1
            for claim in source_to_claims.get(source_id or "", []):
                related[name].add(claim)

    missing: list[CoverageCandidate] = []
    existing: list[CoverageCandidate] = []
    for name, count in counts.items():
        if count < threshold:
            continue
        normalized = _normalize_name(name)
        candidate = CoverageCandidate(
            page_type=page_type,
            name=name,
            count=count,
            related_claims=sorted(related[name]),
            existing_path=existing_paths.get(normalized),
        )
        if candidate.existing_path:
            existing.append(candidate)
        else:
            missing.append(candidate)

    missing.sort(key=lambda item: (-item.count, item.name.casefold()))
    existing.sort(key=lambda item: (-item.count, item.name.casefold()))
    return missing[:limit] + existing


def _mention_counts(cards: list[tuple[Path, dict[str, Any]]], page_type: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for _path, card in cards:
        if card.get("triage") != "keep":
            continue
        for name in _coverage_names(card, page_type):
            counts[name] += 1
    return counts


def _missing_counts(
    counts: Counter[str],
    existing_names: set[str],
    threshold: int,
    limit: int,
) -> list[tuple[str, int]]:
    missing = []
    for name, count in counts.items():
        if count < threshold:
            continue
        if _normalize_name(name) in existing_names:
            continue
        missing.append((name, count))
    missing.sort(key=lambda item: (-item[1], item[0].casefold()))
    return missing[:limit]


def _coverage_names(card: dict[str, Any], page_type: str) -> list[str]:
    raw_names = _entity_or_topic_names(card, page_type)
    names: list[str] = []
    seen: set[str] = set()
    for raw_name in raw_names:
        name = _canonical_entity_name(raw_name) if page_type == "entity" else raw_name.strip()
        if not name:
            continue
        normalized = _normalize_name(name)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        names.append(name)
    return names


def _canonical_entity_name(name: str) -> str | None:
    text = str(name).strip()
    if not text:
        return None
    normalized = _normalize_name(text)
    if not normalized or normalized in _SOURCE_ENTITY_KEYS:
        return None
    return _ENTITY_ALIAS_BY_KEY.get(normalized, text)


def _existing_coverage_names(directory: Path, page_type: str) -> set[str]:
    names = set(_existing_page_name_paths(directory))
    if page_type != "entity" or not directory.exists():
        return names
    for path in directory.glob("*.md"):
        title = _page_title(path) or path.stem.replace("-", " ")
        canonical = _canonical_entity_name(title)
        if canonical:
            names.add(_normalize_name(canonical))
    return names


def _cleanup_stale_entity_pages(wiki_dir: Path, entity_candidates: list[CoverageCandidate]) -> list[Path]:
    entity_dir = wiki_dir / "entities"
    if not entity_dir.exists():
        return []
    canonical_names = {_normalize_name(candidate.name) for candidate in entity_candidates}
    deleted: list[Path] = []
    for path in sorted(entity_dir.glob("*.md")):
        if not _can_update_page(path):
            continue
        title = _page_title(path) or path.stem.replace("-", " ")
        canonical = _canonical_entity_name(title)
        if canonical is None:
            path.unlink()
            deleted.append(path)
            continue
        canonical_key = _normalize_name(canonical)
        title_key = _normalize_name(title)
        canonical_path = entity_dir / f"{_slugify(canonical)}.md"
        if canonical_key != title_key and (canonical_path.exists() or canonical_key in canonical_names):
            path.unlink()
            deleted.append(path)
            continue
        if canonical_key not in canonical_names and not _page_has_claim_refs(path):
            path.unlink()
            deleted.append(path)
    return deleted


def _render_hub_page(candidate: CoverageCandidate, today: date) -> str:
    lines = [
        "---",
        f"wiki_type: {candidate.page_type}",
        f"generated_by: {GENERATED_BY}",
        "review_status: auto",
        f"coverage_count: {candidate.count}",
        f"related_claim_count: {len(candidate.related_claims)}",
        f"updated_at: {today.isoformat()}",
        "---",
        "",
        f"# {candidate.name}",
        "",
        _hub_summary(candidate.page_type),
        "",
        "## Связанные утверждения",
        "",
    ]
    if candidate.related_claims:
        lines.extend(f"- {claim}" for claim in candidate.related_claims)
    else:
        lines.append("- нет")
    lines.extend(
        [
            "",
            "## Как найти источники",
            "",
            "- Первичные источники открываются через доказательства в claim pages и output/wiki/indexes/page_to_sources.json.",
            "- Эта страница не добавляет прямых доказательств сверх связанных страниц-утверждений.",
            "",
        ]
    )
    return "\n".join(lines)


def _hub_summary(page_type: str) -> str:
    if page_type == "entity":
        return "Эта страница-сводка по сущности автоматически собрана из упоминаний в enriched cards."
    if page_type == "topic":
        return "Эта страница-сводка по теме автоматически собрана из упоминаний в enriched cards."
    return "Эта страница-сводка автоматически собрана из упоминаний в enriched cards."


def _source_to_claims(page_to_sources: dict[str, Any]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = defaultdict(list)
    for page, sources in page_to_sources.items():
        if not str(page).startswith("claims/") or not isinstance(sources, list):
            continue
        for source_id in sources:
            mapping[str(source_id)].append(str(page))
    return {source_id: sorted(set(claims)) for source_id, claims in mapping.items()}


def _existing_page_name_paths(directory: Path) -> dict[str, Path]:
    names: dict[str, Path] = {}
    if not directory.exists():
        return names
    for path in directory.glob("*.md"):
        names.setdefault(_normalize_name(path.stem.replace("-", " ")), path)
        title = _page_title(path)
        if title:
            names.setdefault(_normalize_name(title), path)
    return names


def _page_title(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _page_has_claim_refs(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return bool(re.search(r"\bclaims/[^\s)]+\.md", text))


def _can_update_page(path: Path) -> bool:
    try:
        frontmatter = _parse_frontmatter(path.read_text(encoding="utf-8"))
    except OSError:
        return False
    generated_by = str(frontmatter.get("generated_by") or "").strip()
    review_status = str(frontmatter.get("review_status") or "").strip()
    return generated_by in AUTO_GENERATORS and (not review_status or review_status == "auto")


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


def _entity_or_topic_names(card: dict[str, Any], page_type: str) -> list[str]:
    return _flatten_entities(card.get("entities")) if page_type == "entity" else _string_list(card.get("topics"))


def _flatten_entities(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    items: list[str] = []
    for group in value.values():
        if isinstance(group, list):
            items.extend(str(item).strip() for item in group if str(item).strip())
        elif str(group).strip():
            items.append(str(group).strip())
    return items


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip() if value is not None else ""
    return [text] if text else []


def _candidate_path(wiki_dir: Path, candidate: CoverageCandidate) -> Path:
    directory = "entities" if candidate.page_type == "entity" else "topics"
    return wiki_dir / directory / f"{_slugify(candidate.name)}.md"


def _slugify(value: str) -> str:
    text = value.casefold()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text, flags=re.UNICODE).strip("-")
    return text[:120]


def _normalize_name(value: str) -> str:
    return " ".join(re.findall(r"[\w-]+", value.casefold()))


_ENTITY_ALIAS_BY_KEY = {_normalize_name(alias): canonical for alias, canonical in ENTITY_ALIASES.items()}
_SOURCE_ENTITY_KEYS = {_normalize_name(name) for name in SOURCE_LIKE_ENTITY_NAMES}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}
