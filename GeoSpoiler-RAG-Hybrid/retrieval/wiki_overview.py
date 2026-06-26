"""Deterministic overview page for local wiki memory."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import config
from retrieval import wiki_index


@dataclass(frozen=True)
class WikiOverview:
    wiki_dir: Path
    generated_on: date
    claim_count: int
    entity_count: int
    topic_count: int
    status_counts: dict[str, int]
    recent_updates: list[str]
    pending_count: int
    missing_entities: list[tuple[str, int]] = field(default_factory=list)
    missing_topics: list[tuple[str, int]] = field(default_factory=list)


def build_wiki_overview(
    wiki_dir: Path = config.WIKI_DIR,
    enriched_dir: Path = config.ENRICHED_DIR,
    today: date | None = None,
) -> WikiOverview:
    """Collect wiki counts, recent updates, pending queue size, and coverage gaps."""
    today = today or date.today()
    page_paths = list(wiki_index.iter_wiki_pages(wiki_dir))
    claims = [path for path in page_paths if _rel(path, wiki_dir).startswith("claims/")]
    entities = [path for path in page_paths if _rel(path, wiki_dir).startswith("entities/")]
    topics = [path for path in page_paths if _rel(path, wiki_dir).startswith("topics/")]

    status_counts: Counter[str] = Counter()
    updates: list[tuple[str, str]] = []
    for path in claims:
        text = _read_text(path)
        frontmatter = _parse_frontmatter(text)
        status = str(frontmatter.get("status") or "unknown").strip() or "unknown"
        status_counts[status] += 1
        updated_at = str(frontmatter.get("updated_at") or "").strip()
        if updated_at:
            updates.append((updated_at, _rel(path, wiki_dir)))

    updates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    pending_count = len(_load_pending(wiki_dir / "_pending_updates.json"))
    missing_entities, missing_topics = coverage_gaps(wiki_dir=wiki_dir, enriched_dir=enriched_dir)

    return WikiOverview(
        wiki_dir=wiki_dir,
        generated_on=today,
        claim_count=len(claims),
        entity_count=len(entities),
        topic_count=len(topics),
        status_counts=dict(sorted(status_counts.items())),
        recent_updates=[f"{updated}: {page}" for updated, page in updates[:10]],
        pending_count=pending_count,
        missing_entities=missing_entities,
        missing_topics=missing_topics,
    )


def format_wiki_overview(overview: WikiOverview) -> str:
    lines = [
        "# Wiki Overview",
        "",
        f"Generated: {overview.generated_on.isoformat()}",
        "",
        "## Counts",
        "",
        f"- Claims: {overview.claim_count}",
        f"- Entities: {overview.entity_count}",
        f"- Topics: {overview.topic_count}",
        "",
        "## Claim Statuses",
        "",
    ]
    if overview.status_counts:
        lines.extend(f"- {status}: {count}" for status, count in overview.status_counts.items())
    else:
        lines.append("- none")

    lines.extend(["", "## Recent Updates", ""])
    if overview.recent_updates:
        lines.extend(f"- {item}" for item in overview.recent_updates)
    else:
        lines.append("- none")

    lines.extend(["", "## Pending Sources", "", f"- {overview.pending_count} source(s) awaiting fallback review"])

    lines.extend(["", "## Coverage", ""])
    lines.append("Important entities in enriched cards without wiki page:")
    if overview.missing_entities:
        lines.extend(f"- {name}: {count}" for name, count in overview.missing_entities)
    else:
        lines.append("- none")
    lines.append("")
    lines.append("Important topics in enriched cards without wiki page:")
    if overview.missing_topics:
        lines.extend(f"- {name}: {count}" for name, count in overview.missing_topics)
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def write_wiki_overview(overview: WikiOverview, path: Path | None = None) -> Path:
    path = path or (overview.wiki_dir / "_overview.md")
    path.write_text(format_wiki_overview(overview), encoding="utf-8")
    return path


def coverage_gaps(
    wiki_dir: Path = config.WIKI_DIR,
    enriched_dir: Path = config.ENRICHED_DIR,
    threshold: int = 3,
    limit: int = 20,
) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    existing_entities = _existing_page_names(wiki_dir / "entities")
    existing_topics = _existing_page_names(wiki_dir / "topics")
    entity_counts: Counter[str] = Counter()
    topic_counts: Counter[str] = Counter()

    for _path, card in wiki_index.iter_enriched_cards(enriched_dir):
        if card.get("triage") != "keep":
            continue
        for entity in _flatten_entities(card.get("entities")):
            entity_counts[entity] += 1
        for topic in _string_list(card.get("topics")):
            topic_counts[topic] += 1

    missing_entities = _missing_counts(entity_counts, existing_entities, threshold, limit)
    missing_topics = _missing_counts(topic_counts, existing_topics, threshold, limit)
    return missing_entities, missing_topics


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


def _existing_page_names(directory: Path) -> set[str]:
    names: set[str] = set()
    if not directory.exists():
        return names
    for path in directory.glob("*.md"):
        names.add(_normalize_name(path.stem.replace("-", " ")))
        text = _read_text(path)
        for line in text.splitlines():
            if line.startswith("# "):
                names.add(_normalize_name(line[2:].strip()))
                break
    return names


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


def _load_pending(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return {}
    data: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()
    return data


def _normalize_name(value: str) -> str:
    return " ".join(re.findall(r"[\w-]+", value.casefold()))


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _rel(path: Path, wiki_dir: Path) -> str:
    return path.relative_to(wiki_dir).as_posix()
