"""Deterministic overview page for local wiki memory."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import config
from retrieval import wiki_index
from retrieval.wiki_coverage import coverage_gaps


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


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _rel(path: Path, wiki_dir: Path) -> str:
    return path.relative_to(wiki_dir).as_posix()
