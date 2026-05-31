"""
Incremental wiki-memory updates.

This module compares enriched-card content hashes against the previous wiki
source snapshot, updates only pages linked through source_to_pages.json, and
queues unlinked changed/new sources for later review. It is local-only and does
not call LLMs, Telegram, LightRAG, or external APIs.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import config
from retrieval import wiki_index


SOURCE_HASHES_FILENAME = "source_hashes.json"
PENDING_UPDATES_FILENAME = "_pending_updates.json"
OPERATION_LOG_FILENAME = "_log.md"

_EVIDENCE_START_RE = re.compile(r"^\s*-\s+telegram:[^\s]+\s+-\s+")
_METADATA_RE = re.compile(r"^(\s*-\s+)(post_url|date|card_path|content_hash):")
_UPDATED_AT_RE = re.compile(r"^updated_at:\s*.*$", re.MULTILINE)


@dataclass(frozen=True)
class WikiSourceSnapshot:
    source_id: str
    content_hash: str
    card_path: str
    post_url: str
    normalized_file: str
    date: str


@dataclass(frozen=True)
class WikiPendingUpdate:
    reason: str
    source_id: str
    content_hash: str
    card_path: str
    post_url: str
    normalized_file: str
    date: str
    pages: list[str]
    message: str


@dataclass(frozen=True)
class WikiIncrementalUpdateStats:
    initialized: bool
    current_sources: int
    new_sources: list[str]
    changed_sources: list[str]
    removed_sources: list[str]
    pages_updated: list[Path]
    pending_updates: list[WikiPendingUpdate]
    source_hashes_path: Path
    pending_updates_path: Path
    log_path: Path


def run_wiki_incremental_update(
    wiki_dir: Path = config.WIKI_DIR,
    enriched_dir: Path = config.ENRICHED_DIR,
    index_dir: Path = config.WIKI_INDEX_DIR,
    today: date | None = None,
) -> WikiIncrementalUpdateStats:
    """Update linked wiki pages from changed enriched sources only."""
    today = today or date.today()
    wiki_dir.mkdir(parents=True, exist_ok=True)
    index_dir.mkdir(parents=True, exist_ok=True)

    source_hashes_path = index_dir / SOURCE_HASHES_FILENAME
    pending_updates_path = wiki_dir / PENDING_UPDATES_FILENAME
    log_path = wiki_dir / OPERATION_LOG_FILENAME

    current_sources = _current_source_snapshots(enriched_dir)
    previous_sources = _load_source_snapshots(source_hashes_path)
    source_to_pages = _load_source_to_pages(wiki_dir, index_dir)

    if not previous_sources:
        _write_source_snapshots(source_hashes_path, current_sources)
        _write_pending_updates(pending_updates_path, [])
        stats = WikiIncrementalUpdateStats(
            initialized=True,
            current_sources=len(current_sources),
            new_sources=[],
            changed_sources=[],
            removed_sources=[],
            pages_updated=[],
            pending_updates=[],
            source_hashes_path=source_hashes_path,
            pending_updates_path=pending_updates_path,
            log_path=log_path,
        )
        _append_log(stats)
        return stats

    new_sources = sorted(source_id for source_id in current_sources if source_id not in previous_sources)
    changed_sources = sorted(
        source_id
        for source_id, source in current_sources.items()
        if source_id in previous_sources and previous_sources[source_id].content_hash != source.content_hash
    )
    removed_sources = sorted(source_id for source_id in previous_sources if source_id not in current_sources)

    pending_updates: list[WikiPendingUpdate] = []
    pages_to_sources: dict[str, list[WikiSourceSnapshot]] = {}

    for source_id in new_sources + changed_sources:
        source = current_sources[source_id]
        pages = list(source_to_pages.get(source_id, []))
        if not pages:
            reason = "new_unlinked_source" if source_id in new_sources else "changed_unlinked_source"
            pending_updates.append(_pending_update(reason, source, pages))
            continue
        for page in pages:
            pages_to_sources.setdefault(page, []).append(source)

    pages_updated = _update_linked_pages(wiki_dir, pages_to_sources, today)

    _write_source_snapshots(source_hashes_path, current_sources)
    _write_pending_updates(pending_updates_path, pending_updates)

    stats = WikiIncrementalUpdateStats(
        initialized=False,
        current_sources=len(current_sources),
        new_sources=new_sources,
        changed_sources=changed_sources,
        removed_sources=removed_sources,
        pages_updated=pages_updated,
        pending_updates=pending_updates,
        source_hashes_path=source_hashes_path,
        pending_updates_path=pending_updates_path,
        log_path=log_path,
    )
    _append_log(stats)
    return stats


def _current_source_snapshots(enriched_dir: Path) -> dict[str, WikiSourceSnapshot]:
    snapshots: dict[str, WikiSourceSnapshot] = {}
    for source in wiki_index.collect_enriched_sources(enriched_dir):
        if not source.source_id:
            continue
        snapshots[source.source_id] = WikiSourceSnapshot(
            source_id=source.source_id,
            content_hash=source.content_hash,
            card_path=source.card_path,
            post_url=source.post_url,
            normalized_file=source.normalized_file,
            date=source.date,
        )
    return dict(sorted(snapshots.items()))


def _load_source_to_pages(wiki_dir: Path, index_dir: Path) -> dict[str, list[str]]:
    data = _load_json(index_dir / wiki_index.SOURCE_INDEX_FILENAME)
    if not data:
        _page_to_sources, data = wiki_index.build_page_source_indexes(wiki_dir)
    return {
        str(source_id): [str(page) for page in pages]
        for source_id, pages in data.items()
        if isinstance(pages, list)
    }


def _load_source_snapshots(path: Path) -> dict[str, WikiSourceSnapshot]:
    data = _load_json(path)
    snapshots: dict[str, WikiSourceSnapshot] = {}
    for source_id, value in data.items():
        if isinstance(value, str):
            content_hash = value
            payload: dict[str, Any] = {}
        elif isinstance(value, dict):
            content_hash = str(value.get("content_hash") or "")
            payload = value
        else:
            continue
        if not content_hash:
            continue
        snapshots[str(source_id)] = WikiSourceSnapshot(
            source_id=str(source_id),
            content_hash=content_hash,
            card_path=str(payload.get("card_path") or ""),
            post_url=str(payload.get("post_url") or ""),
            normalized_file=str(payload.get("normalized_file") or ""),
            date=str(payload.get("date") or ""),
        )
    return snapshots


def _write_source_snapshots(path: Path, snapshots: dict[str, WikiSourceSnapshot]) -> None:
    _write_json(path, {source_id: asdict(source) for source_id, source in sorted(snapshots.items())})


def _write_pending_updates(path: Path, pending_updates: list[WikiPendingUpdate]) -> None:
    _write_json(path, [asdict(item) for item in pending_updates])


def _pending_update(reason: str, source: WikiSourceSnapshot, pages: list[str]) -> WikiPendingUpdate:
    return WikiPendingUpdate(
        reason=reason,
        source_id=source.source_id,
        content_hash=source.content_hash,
        card_path=source.card_path,
        post_url=source.post_url,
        normalized_file=source.normalized_file,
        date=source.date,
        pages=pages,
        message="Source is not linked from any wiki page; review whether a claim, entity, or topic page should include it.",
    )


def _update_linked_pages(
    wiki_dir: Path,
    pages_to_sources: dict[str, list[WikiSourceSnapshot]],
    today: date,
) -> list[Path]:
    updated: list[Path] = []
    for rel_page, sources in sorted(pages_to_sources.items()):
        page_path = wiki_dir / rel_page
        if not page_path.exists() or not page_path.is_file():
            continue
        try:
            text = page_path.read_text(encoding="utf-8")
        except OSError:
            continue
        source_by_id = {source.source_id: source for source in sources}
        new_text = _update_page_text(text, source_by_id, today)
        if new_text == text:
            continue
        page_path.write_text(new_text, encoding="utf-8")
        updated.append(page_path)
    return updated


def _update_page_text(text: str, source_by_id: dict[str, WikiSourceSnapshot], today: date) -> str:
    evidence = _section(text, "Evidence")
    if not evidence:
        return text

    updated_evidence = _update_evidence_section(evidence, source_by_id)
    if updated_evidence == evidence:
        return text

    start, end = _section_bounds(text, "Evidence")
    updated_text = text[:start] + updated_evidence + text[end:]
    return _set_updated_at(updated_text, today)


def _update_evidence_section(evidence: str, source_by_id: dict[str, WikiSourceSnapshot]) -> str:
    lines = evidence.splitlines()
    updated_lines: list[str] = []
    block: list[str] = []

    def flush_block() -> None:
        if not block:
            return
        updated_lines.extend(_update_evidence_block(block, source_by_id))
        block.clear()

    for line in lines:
        if _EVIDENCE_START_RE.match(line):
            flush_block()
            block.append(line)
            continue
        if block:
            block.append(line)
        else:
            updated_lines.append(line)

    flush_block()
    suffix = "\n" if evidence.endswith("\n") else ""
    return "\n".join(updated_lines) + suffix


def _update_evidence_block(
    lines: list[str],
    source_by_id: dict[str, WikiSourceSnapshot],
) -> list[str]:
    source_ids = wiki_index.extract_page_sources(lines[0])
    if not source_ids:
        return lines.copy()
    source = source_by_id.get(source_ids[0])
    if source is None:
        return lines.copy()

    replacements = {
        "post_url": source.post_url,
        "date": source.date,
        "card_path": source.card_path,
        "content_hash": source.content_hash,
    }
    seen: set[str] = set()
    updated = []
    for line in lines:
        match = _METADATA_RE.match(line)
        if not match:
            updated.append(line)
            continue
        field = match.group(2)
        seen.add(field)
        value = replacements.get(field, "")
        updated.append(f"{match.group(1)}{field}: {value}" if value else line)

    for field in ("post_url", "date", "card_path", "content_hash"):
        value = replacements[field]
        if value and field not in seen:
            updated.append(f"  - {field}: {value}")

    return updated


def _set_updated_at(text: str, today: date) -> str:
    value = f"updated_at: {today.isoformat()}"
    if _UPDATED_AT_RE.search(text):
        return _UPDATED_AT_RE.sub(value, text, count=1)

    lines = text.splitlines()
    if len(lines) >= 2 and lines[0].strip() == "---":
        for idx, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                lines.insert(idx, value)
                return "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    return text


def _section(text: str, section_name: str) -> str:
    start, end = _section_bounds(text, section_name)
    return text[start:end]


def _section_bounds(text: str, section_name: str) -> tuple[int, int]:
    pattern = re.compile(rf"^##\s+{re.escape(section_name)}\s*$", flags=re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return 0, 0
    start = match.end()
    rest = text[start:]
    next_section = re.search(r"^##\s+", rest, flags=re.MULTILINE)
    end = start + next_section.start() if next_section else len(text)
    return start, end


def _append_log(stats: WikiIncrementalUpdateStats) -> None:
    stats.log_path.parent.mkdir(parents=True, exist_ok=True)
    if not stats.log_path.exists():
        stats.log_path.write_text("# Wiki Operation Log\n\n", encoding="utf-8")

    event = {
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "event": "wiki_incremental_update",
        "initialized": stats.initialized,
        "current_sources": stats.current_sources,
        "new_sources": len(stats.new_sources),
        "changed_sources": len(stats.changed_sources),
        "removed_sources": len(stats.removed_sources),
        "pages_updated": [path.as_posix() for path in stats.pages_updated],
        "pending_updates": len(stats.pending_updates),
    }
    with stats.log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
