"""LightRAG document ingestion from enriched card graph_text."""

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from lightrag import LightRAG

import config
from loader.runtime import LLM_ROLE as _LLM_ROLE
from loader.runtime import logger
from loader.storage import (
    _HEADER_LINE_RE,
    _canonical_source_path,
    _cleanup_skipped_doc,
    _doc_status_field,
    _doc_status_value,
    _load_document_metadata,
    _rag_file_path,
    _remove_source_metadata_index,
    _skipped_insert_report_path,
    _source_doc_id,
    _sync_source_metadata_index,
    _wait_for_doc_terminal_status,
    _write_skipped_insert_report,
)

_POSTHOLDER_LINE_RE = re.compile(
    r"^\[(?:Видео:|Аудио:|Transcript|Voice transcript|Video transcript|AI-диалог:|"
    r"Внешняя ссылка:|Малоинформативный пост:|Instagram Reel:.*очередь|"
    r"Отправлено в очередь на ручной просмотр:|Уже обработано:).*\]$"
)
_INSTAGRAM_REEL_WRAPPER_RE = re.compile(
    "^\\[(?:Instagram Reel:|\u0414\u043b\u0438\u043d\u043d\u044b\u0439 Instagram Reel:).*\\]$",
    re.IGNORECASE,
)

def _prepare_text_for_rag(text: str) -> str:
    """Remove metadata wrappers and placeholders before graph extraction."""
    lines = text.splitlines()
    if lines and _HEADER_LINE_RE.match(lines[0].strip()):
        lines = lines[1:]

    kept_lines = []
    for line in lines:
        stripped = line.strip()
        if _POSTHOLDER_LINE_RE.match(stripped) or _INSTAGRAM_REEL_WRAPPER_RE.match(stripped):
            continue
        kept_lines.append(line)

    cleaned = "\n".join(kept_lines).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned

async def _upsert_text(rag: LightRAG, source_path: str, text: str) -> None:
    """
    Replace an existing LightRAG document for this source path, then insert the new text.

    LightRAG's default doc_id is content-based, which duplicates logical documents when the
    same file is reloaded after edits. We instead key documents by source path.
    """
    canonical_path = _canonical_source_path(source_path)
    doc_id = _source_doc_id(canonical_path)
    rag_file_path = _rag_file_path(canonical_path)
    metadata = _load_document_metadata(source_path, text)
    metadata["canonical_path"] = canonical_path
    _sync_source_metadata_index(source_path, metadata)
    if rag_file_path != canonical_path:
        _sync_source_metadata_index(rag_file_path, metadata)

    rag_text = _prepare_text_for_rag(text)
    if not rag_text.strip():
        raise RuntimeError(f"document became empty after RAG cleanup: {canonical_path}")

    existing_doc = await rag.doc_status.get_by_id(doc_id)
    if existing_doc:
        deletion = await rag.adelete_by_doc_id(doc_id)
        if deletion.status != "success":
            raise RuntimeError(
                f"failed to replace existing doc_id={doc_id} for {canonical_path}: {deletion.message}"
            )

    token = _LLM_ROLE.set("build")
    try:
        await rag.ainsert([rag_text], ids=[doc_id], file_paths=[rag_file_path])
    finally:
        _LLM_ROLE.reset(token)


async def load_texts(
    rag: LightRAG,
    texts_with_paths: list[tuple[str, str]],
    batch_size: int = 5,
) -> int:
    """
    Load normalized texts into LightRAG.

    Args:
        rag: Initialized LightRAG instance
        texts_with_paths: List of (filepath, text_content) tuples
        batch_size: How many texts to insert at once

    Returns:
        Number of successfully inserted texts
    """
    total = len(texts_with_paths)
    inserted = 0
    skipped: list[dict[str, Any]] = []
    skipped_doc_ids: set[str] = set()
    attempted_docs: dict[str, dict[str, Any]] = {}
    insert_timeout = max(1.0, config.RAG_INSERT_TIMEOUT_SECONDS)

    for i, (path, text) in enumerate(texts_with_paths, start=1):
        canonical_path = _canonical_source_path(path)
        doc_id = _source_doc_id(canonical_path)
        attempted_docs[doc_id] = {
            "source_path": canonical_path,
            "content_length": len(text),
        }
        try:
            await asyncio.wait_for(
                _upsert_text(rag, path, text),
                timeout=insert_timeout,
            )
            status_doc = await _wait_for_doc_terminal_status(
                rag,
                doc_id,
                timeout_seconds=insert_timeout,
            )
            if _doc_status_value(status_doc) == "failed":
                reason = "LightRAG marked document as failed"
                skipped.append(
                    {
                        "source_path": canonical_path,
                        "doc_id": doc_id,
                        "reason": reason,
                        "content_length": len(text),
                    }
                )
                skipped_doc_ids.add(doc_id)
                logger.error(f"  Skipped failed insert for {canonical_path}: {reason}")
                await _cleanup_skipped_doc(rag, doc_id)
                _remove_source_metadata_index(canonical_path)
                continue
            inserted += 1
        except TimeoutError:
            reason = f"insert timeout after {insert_timeout:.0f}s"
            skipped.append(
                {
                    "source_path": canonical_path,
                    "doc_id": doc_id,
                    "reason": reason,
                    "content_length": len(text),
                }
            )
            skipped_doc_ids.add(doc_id)
            logger.error(f"  Skipped timed-out insert for {canonical_path}: {reason}")
            await _cleanup_skipped_doc(rag, doc_id)
            _remove_source_metadata_index(canonical_path)
        except Exception as e:
            reason = f"insert error: {e}"
            skipped.append(
                {
                    "source_path": canonical_path,
                    "doc_id": doc_id,
                    "reason": reason,
                    "content_length": len(text),
                }
            )
            skipped_doc_ids.add(doc_id)
            logger.error(f"  Skipped failed insert for {path}: {reason}")
            await _cleanup_skipped_doc(rag, doc_id)
            _remove_source_metadata_index(canonical_path)

        if i % batch_size == 0 or i == total:
            logger.info(f"  Inserted progress: {inserted}/{total} ({len(skipped)} skipped)")

    for doc_id, doc_info in attempted_docs.items():
        if doc_id in skipped_doc_ids:
            continue
        status_doc = await rag.doc_status.get_by_id(doc_id)
        if _doc_status_value(status_doc).lower() == "failed":
            source_path = str(_doc_status_field(status_doc, "file_path") or doc_info["source_path"])
            content_length = _doc_status_field(status_doc, "content_length", doc_info["content_length"])
            reason = "LightRAG marked document as failed after insert returned"
            skipped.append(
                {
                    "source_path": source_path,
                    "doc_id": doc_id,
                    "reason": reason,
                    "content_length": content_length,
                }
            )
            skipped_doc_ids.add(doc_id)
            inserted = max(0, inserted - 1)
            logger.error(f"  Late failed insert for {source_path}: {reason}")
            await _cleanup_skipped_doc(rag, doc_id)
            _remove_source_metadata_index(source_path)

    _write_skipped_insert_report(skipped)
    if skipped:
        logger.warning("Skipped %s RAG insert(s):", len(skipped))
        for item in skipped:
            logger.warning(
                "  %s (%s, len=%s)",
                item["source_path"],
                item["reason"],
                item["content_length"],
            )
        logger.warning("Skipped insert report: %s", _skipped_insert_report_path())

    logger.info(
        f"Loading complete: {inserted}/{total} texts inserted into LightRAG "
        f"({len(skipped)} skipped)."
    )
    return inserted


async def load_from_directory(rag: LightRAG, directory: Path | None = None) -> int:
    """
    Load all .txt files from the normalized output directory into LightRAG.

    Args:
        rag: Initialized LightRAG instance
        directory: Directory to scan (defaults to config.NORMALIZED_DIR)

    Returns:
        Number of inserted texts
    """
    directory = directory or config.NORMALIZED_DIR

    texts_with_paths = []
    for txt_file in sorted(directory.rglob("*.txt")):
        try:
            text = txt_file.read_text(encoding="utf-8")
            if text.strip():
                texts_with_paths.append((str(txt_file), text))
        except Exception as e:
            logger.warning(f"  Cannot read {txt_file}: {e}")

    if not texts_with_paths:
        logger.warning("No normalized texts found to load.")
        return 0

    logger.info(f"Found {len(texts_with_paths)} normalized texts to load.")
    return await load_texts(rag, texts_with_paths)


async def load_from_enriched(rag: LightRAG, enriched_dir: Path | None = None) -> int:
    """
    Load graph_text from enriched cards into LightRAG.

    Uses the structured graph_text field which is purpose-built for knowledge graph
    extraction — contains entities, events, theses, and quotes in a format optimized
    for LightRAG's entity/relationship extraction.

    Only cards with schema_version=enriched_v2 and non-empty graph_text are loaded.
    Missing graph_text is skipped; normalized source text is never substituted.

    Returns:
        Number of inserted texts
    """
    enriched_dir = enriched_dir or config.ENRICHED_DIR

    if not enriched_dir.exists():
        logger.warning("Enriched directory does not exist: %s", enriched_dir)
        return 0

    texts_with_paths: list[tuple[str, str]] = []
    skipped_non_v2 = 0
    skipped_no_graph_text = 0

    for card_path in sorted(enriched_dir.rglob("*.enriched.json")):
        try:
            card = json.loads(card_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.debug("Cannot read enriched card %s: %s", card_path, exc)
            continue

        if card.get("schema_version") != "enriched_v2":
            skipped_non_v2 += 1
            continue

        quality_flags = card.get("quality_flags") or []
        if {"extraction_unstable", "partial_segment_failure"} & set(quality_flags):
            logger.info("Skipping unstable enriched card from LightRAG: %s", card_path)
            continue

        graph_text = (card.get("graph_text") or "").strip()
        if not graph_text:
            skipped_no_graph_text += 1
            continue

        provenance = card.get("provenance") if isinstance(card.get("provenance"), dict) else {}
        source_path = provenance.get("normalized_path") or ""
        if not source_path:
            logger.warning("Skipping v2 card without provenance.normalized_path: %s", card_path)
            continue
        texts_with_paths.append((source_path, graph_text))

    if not texts_with_paths:
        logger.warning("No enriched cards with graph_text found to load.")
        return 0

    if skipped_non_v2:
        logger.info("  Skipped %d non-v2 enriched card(s)", skipped_non_v2)
    if skipped_no_graph_text:
        logger.info("  Skipped %d enriched_v2 card(s) without graph_text", skipped_no_graph_text)

    logger.info(f"Found {len(texts_with_paths)} enriched texts to load into LightRAG.")
    return await load_texts(rag, texts_with_paths)
