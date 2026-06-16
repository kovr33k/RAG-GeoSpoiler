"""LightRAG storage paths, document ids, metadata, and rebuild helpers."""

import asyncio
import json
import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from lightrag import LightRAG
from lightrag.utils import compute_mdhash_id

import config
from loader.runtime import logger

_HEADER_LINE_RE = re.compile(r"^\[(?=.*(?:Канал:|Дата:|Пост:)).*\]\s*$")

def _source_index_path() -> Path:
    """Resolve the SQLite metadata index path from the current config at runtime."""
    return config.RAG_STORAGE_DIR / "doc_metadata_index.sqlite"


def _legacy_source_index_path() -> Path:
    """Resolve the retired JSON metadata index path for one-way migration."""
    return config.RAG_STORAGE_DIR / "doc_metadata_index.json"


def _skipped_insert_report_path() -> Path:
    """Resolve the per-load skipped insert report path."""
    return config.PROJECT_ROOT / "artifacts" / "rag_insert_skipped.md"


def load_source_metadata_index() -> dict[str, dict[str, Any]]:
    """Load the persisted source metadata lookup as a dict for compatibility."""
    _migrate_legacy_source_metadata_index()
    index_path = _source_index_path()
    if not index_path.exists():
        return {}
    conn = _connect_source_metadata_index()
    try:
        rows = conn.execute(
            "SELECT source_path, metadata_json FROM source_metadata ORDER BY source_path"
        ).fetchall()
    except sqlite3.Error:
        return {}
    finally:
        conn.close()

    data: dict[str, dict[str, Any]] = {}
    for source_path, metadata_json in rows:
        try:
            metadata = json.loads(metadata_json)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(metadata, dict):
            data[str(source_path)] = metadata
    return data if isinstance(data, dict) else {}


def _connect_source_metadata_index() -> sqlite3.Connection:
    """Open the SQLite metadata index and ensure the schema exists."""
    index_path = _source_index_path()
    index_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(index_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS source_metadata (
            source_path TEXT PRIMARY KEY,
            metadata_json TEXT NOT NULL
        )
        """
    )
    return conn


def _migrate_legacy_source_metadata_index() -> None:
    """Import the retired JSON index into SQLite once when SQLite is absent."""
    index_path = _source_index_path()
    if index_path.exists():
        return
    legacy_path = _legacy_source_index_path()
    if not legacy_path.exists():
        return
    try:
        legacy_data = json.loads(legacy_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    if not isinstance(legacy_data, dict):
        return

    conn = _connect_source_metadata_index()
    try:
        for source_path, metadata in legacy_data.items():
            if not isinstance(metadata, dict):
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO source_metadata (source_path, metadata_json)
                VALUES (?, ?)
                """,
                (str(source_path), json.dumps(metadata, ensure_ascii=False)),
            )
        conn.commit()
    finally:
        conn.close()

def _parse_header_metadata(text: str) -> dict:
    """Best-effort metadata extraction from the first line of a normalized document."""
    first_line = text.splitlines()[0].strip() if text.splitlines() else ""
    if not _HEADER_LINE_RE.match(first_line):
        return {}
    inner = first_line.strip()[1:-1]
    metadata: dict[str, str] = {}
    for part in inner.split(" | "):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        metadata[key.strip().lower()] = value.strip()
    return metadata


def _load_document_metadata(source_path: str, text: str) -> dict:
    """Load sidecar metadata when available, falling back to parsed header metadata."""
    source_file = Path(source_path)
    metadata_path = source_file.with_suffix(".meta.json")
    if metadata_path.exists():
        try:
            return json.loads(metadata_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning(f"  Failed to read metadata sidecar for {source_path}")
    return _parse_header_metadata(text)


def _sync_source_metadata_index(source_path: str, metadata: dict) -> None:
    """Persist source metadata in the SQLite lookup index inside rag_storage."""
    _migrate_legacy_source_metadata_index()
    conn = _connect_source_metadata_index()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO source_metadata (source_path, metadata_json)
            VALUES (?, ?)
            """,
            (
                _canonical_source_path(source_path),
                json.dumps(metadata, ensure_ascii=False),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _remove_source_metadata_index(source_path: str) -> None:
    """Remove metadata for a document that did not finish insertion."""
    _migrate_legacy_source_metadata_index()
    index_path = _source_index_path()
    if not index_path.exists():
        return
    conn = _connect_source_metadata_index()
    try:
        conn.execute(
            "DELETE FROM source_metadata WHERE source_path = ?",
            (_canonical_source_path(source_path),),
        )
        conn.commit()
    finally:
        conn.close()


def _write_skipped_insert_report(skipped: list[dict[str, Any]]) -> None:
    """Persist the final list of documents skipped during RAG insertion."""
    report_path = _skipped_insert_report_path()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Skipped RAG Inserts",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Skipped: {len(skipped)}",
        "",
    ]

    if not skipped:
        lines.append("No documents were skipped during the last load.")
    else:
        lines.extend(
            [
                "| # | Reason | Length | Source |",
                "|---:|---|---:|---|",
            ]
        )
        for idx, item in enumerate(skipped, start=1):
            reason = str(item.get("reason", "")).replace("|", "\\|")
            source_path = str(item.get("source_path", "")).replace("|", "\\|")
            content_length = item.get("content_length", "")
            lines.append(f"| {idx} | {reason} | {content_length} | `{source_path}` |")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _cleanup_skipped_doc(rag: LightRAG, doc_id: str) -> None:
    """Remove a timed-out document from active LightRAG queues before continuing."""
    try:
        deletion = await asyncio.wait_for(
            rag.adelete_by_doc_id(doc_id),
            timeout=config.RAG_DELETE_TIMEOUT_SECONDS,
        )
        if getattr(deletion, "status", "") in {"success", "not_found"}:
            return
        logger.warning(
            "  Cleanup for skipped doc_id=%s returned %s: %s",
            doc_id,
            getattr(deletion, "status", "unknown"),
            getattr(deletion, "message", ""),
        )
    except Exception as exc:
        logger.warning(f"  Cleanup via adelete_by_doc_id failed for {doc_id}: {exc}")

    # Last-resort cleanup prevents a PROCESSING/FAILED status from being picked up
    # again by the next insert. Rebuild starts from empty storage, so any partial
    # graph data from this document stays isolated to the failed insert attempt.
    for storage_name in ("doc_status", "full_docs"):
        storage = getattr(rag, storage_name, None)
        delete = getattr(storage, "delete", None)
        if delete is None:
            continue
        try:
            await delete([doc_id])
        except Exception as exc:
            logger.warning(f"  Direct cleanup failed for {storage_name}/{doc_id}: {exc}")


def _doc_status_value(status_doc: Any) -> str:
    if not status_doc:
        return ""
    if isinstance(status_doc, dict):
        return str(status_doc.get("status", ""))
    return str(getattr(status_doc, "status", ""))


def _doc_status_field(status_doc: Any, field_name: str, default: Any = "") -> Any:
    if not status_doc:
        return default
    if isinstance(status_doc, dict):
        return status_doc.get(field_name, default)
    return getattr(status_doc, field_name, default)


async def _wait_for_doc_terminal_status(
    rag: LightRAG,
    doc_id: str,
    timeout_seconds: float,
) -> Any:
    """Wait until LightRAG has actually finished processing the inserted doc."""
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    last_status_doc: Any = None
    pending_statuses = {"pending", "processing", "preprocessed"}

    while True:
        last_status_doc = await rag.doc_status.get_by_id(doc_id)
        status = _doc_status_value(last_status_doc).lower()
        if status in {"processed", "failed"}:
            return last_status_doc
        if status and status not in pending_statuses:
            return last_status_doc
        if not status:
            return last_status_doc

        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError
        await asyncio.sleep(1.0)

def rebuild_rag_storage(preserve_llm_cache: bool = False) -> Path | None:
    """
    Archive the current LightRAG storage directory and recreate it empty.

    Args:
        preserve_llm_cache: If True, copies the LLM response cache back to the fresh storage.

    Returns:
        Path to the created backup directory, or None if there was nothing to back up.
    """
    storage_dir = config.RAG_STORAGE_DIR
    backup_root = config.PROJECT_ROOT / "rag_storage_backups"
    backup_root.mkdir(parents=True, exist_ok=True)

    if not storage_dir.exists() or not any(storage_dir.iterdir()):
        storage_dir.mkdir(parents=True, exist_ok=True)
        logger.info("RAG storage is already empty; nothing to back up.")
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_root / f"{storage_dir.name}_{timestamp}"
    suffix = 1
    while backup_path.exists():
        backup_path = backup_root / f"{storage_dir.name}_{timestamp}_{suffix}"
        suffix += 1

    shutil.move(str(storage_dir), str(backup_path))
    storage_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Archived RAG storage to: {backup_path}")

    if preserve_llm_cache:
        cache_name = "kv_store_llm_response_cache.json"
        cache_source = backup_path / cache_name
        if cache_source.exists():
            shutil.copy2(str(cache_source), str(storage_dir / cache_name))
            logger.info("Preserved LLM response cache for embedding rebuild.")

    return backup_path


def _canonical_source_path(source_path: str) -> str:
    """Normalize a source path so one logical source maps to one LightRAG doc_id."""
    return str(Path(source_path).resolve(strict=False))


def _source_doc_id(source_path: str) -> str:
    """Build a stable document ID from the normalized source path."""
    return compute_mdhash_id(_canonical_source_path(source_path), prefix="doc-")
