import asyncio
import contextvars
import json
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from lightrag import LightRAG, QueryParam
from lightrag.prompt import PROMPTS
from lightrag.utils import EmbeddingFunc, compute_mdhash_id

import config
from loader.answer_postprocess import (
    _FALLBACK_TECHNICAL_MARKERS,
    _NO_CONTEXT_MARKERS,
    _answer_looks_corrupt,
    _is_funding_question,
    _postprocess_answer_text,
    _question_requests_visuals,
    _response_has_no_context,
    _response_looks_corrupt,
)
from loader.clients import (
    _chat_completion_options,
    _chat_settings_for_role,
    _embed_texts,
    _openai_client,
)
from loader.reference_hints import (
    _attach_reference_hints,
    _existing_references,
    _merge_references,
    _resolve_match_source_path,
)
from reranker import lightrag_rerank_func
from retrieval.wiki_index import WikiSearchResult, find_wiki_context
from retrieval.wiki_resolver import WikiResolvedSource, resolve_wiki_references

logger = logging.getLogger("geospoiler.loader")
_LLM_ROLE = contextvars.ContextVar("geospoiler_lightrag_llm_role", default="query")

_TUPLE_DELIMITER = PROMPTS["DEFAULT_TUPLE_DELIMITER"]
_COMPLETION_DELIMITER = PROMPTS["DEFAULT_COMPLETION_DELIMITER"]
_ALLOWED_ENTITY_TYPES = {entity_type.casefold() for entity_type in config.LIGHTRAG_ENTITY_TYPES}
_ENTITY_TYPE_REMAP = {
    key.casefold(): value.casefold()
    for key, value in config.LIGHTRAG_ENTITY_TYPE_REMAP.items()
}
_ENTITY_ALIAS_MAP = {
    key.casefold(): value.strip()
    for key, value in config.LIGHTRAG_ENTITY_ALIASES.items()
    if value.strip()
}
_HEADER_LINE_RE = re.compile(r"^\[(?=.*(?:Канал:|Дата:|Пост:)).*\]\s*$")
_URL_ENTITY_RE = re.compile(r"^(?:https?://|www\.)", re.IGNORECASE)
_DATE_ENTITY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2})?$")
_POSTHOLDER_LINE_RE = re.compile(
    r"^\[(?:Видео:|Аудио:|Transcript|Voice transcript|Video transcript|AI-диалог:|Отправлено в очередь на ручной просмотр:|Уже обработано:).*\]$"
)

_QUERY_USER_PROMPT = (
    "Use only the context that directly answers the specific question asked. "
    "STRICTLY ignore tangential references, background information, or adjacent topics even if they share entities, countries, or people with the query. "
    "Do not broaden a narrow question into a general ideological or geopolitical essay, but if the context contains indirect or circumstantial evidence, answer with clear separation between direct evidence and broader context. "
    "For questions asking who funds or finances an actor, answer only if the context directly names a funder; do not infer financing from influence, sympathy, corruption, travel, leaks, or ideological alignment. "
    "If a funding question has no directly named funder, say in Russian: 'В базе отсутствует прямое указание; по имеющимся данным это нельзя определить.' "
    "Use careful attribution language: if the context says something is suspected, alleged, reported, or claimed, keep that qualification. "
    "Do not turn allegations, suspicions, or interpretations into established facts. "
    "If the answer is only indirectly supported, explicitly say so instead of claiming there is no information. "
    "If the provided context truly does not support an answer, clearly state that the base does not contain the answer. "
    "ВСЕГДА ОТВЕЧАЙ НА РУССКОМ ЯЗЫКЕ."
)
_SOURCE_QUERY_USER_PROMPT = (
    "The user is asking for provenance. Prioritize concrete source attribution over synthesis. "
    "Restate the claim using the user's wording before giving links; keep compounds such as 'ультралевые' and 'ультраправые' unhyphenated when the user writes them that way. "
    "Use only retrieved context and references. Name the specific post, file, or document that supports the claim. "
    "Prefer Telegram post URLs or source file references when available in the context. "
    "If the retrieved context does not contain a concrete source for the claim, say that the base contains the claim but the source link was not recovered. "
    "Do not add broad background or adjacent political analysis. "
    "ВСЕГДА ОТВЕЧАЙ НА РУССКОМ ЯЗЫКЕ."
)
_OVERVIEW_QUERY_USER_PROMPT = (
    "Answer as a broad overview, but still use only the provided context. "
    "Group repeated evidence by theme and avoid listing weakly related entities as if they were central. "
    "Clearly separate direct evidence from broader patterns inferred from multiple retrieved posts. "
    "If the context is thin or mixed, state that limitation. "
    "ВСЕГДА ОТВЕЧАЙ НА РУССКОМ ЯЗЫКЕ."
)
_QUERY_RESPONSE_TYPE = "Short factual answer in a few paragraphs"
_DEFAULT_QUERY_TOP_K = 15
_DEFAULT_QUERY_CHUNK_TOP_K = 10
_QUERY_PROFILES: dict[str, dict[str, Any]] = {
    "answer": {
        "top_k": 15,
        "chunk_top_k": _DEFAULT_QUERY_CHUNK_TOP_K,
        "user_prompt": _QUERY_USER_PROMPT,
    },
    "source": {
        "top_k": 15,
        "chunk_top_k": _DEFAULT_QUERY_CHUNK_TOP_K,
        "user_prompt": _SOURCE_QUERY_USER_PROMPT,
    },
    "overview": {
        "top_k": 30,
        "chunk_top_k": _DEFAULT_QUERY_CHUNK_TOP_K,
        "user_prompt": _OVERVIEW_QUERY_USER_PROMPT,
    },
}


def get_query_profile(profile: str | None = None) -> dict[str, Any]:
    """Return retrieval and prompt settings for a named query profile."""
    name = (profile or "answer").strip().lower()
    if name not in _QUERY_PROFILES:
        raise ValueError(f"unknown query profile: {profile}")
    return _QUERY_PROFILES[name].copy()


def _configure_lightrag_prompts() -> None:
    """Override inconsistent upstream examples with a project-specific one."""
    PROMPTS["entity_extraction_examples"] = [
        """<Entity_types>
["person","organization","country","military_unit","event","location","conflict","document","other"]

<Input Text>
```
[Канал: Example Channel | Дата: 2026-01-01 10:00 | Пост: https://t.me/example/1]

Robert Fico formed a coalition with the Slovak National Party.
```

<Output>
entity{tuple_delimiter}Robert Fico{tuple_delimiter}person{tuple_delimiter}Robert Fico is a politician who formed a coalition described in the source text.
entity{tuple_delimiter}Slovak National Party{tuple_delimiter}organization{tuple_delimiter}Slovak National Party is a political organization that formed a coalition with Robert Fico.
relation{tuple_delimiter}Robert Fico{tuple_delimiter}Slovak National Party{tuple_delimiter}coalition,political alliance{tuple_delimiter}Robert Fico formed a coalition with the Slovak National Party.
{completion_delimiter}
"""
    ]


def _source_index_path() -> Path:
    """Resolve the metadata index path from the current config at runtime."""
    return config.RAG_STORAGE_DIR / "doc_metadata_index.json"


def _skipped_insert_report_path() -> Path:
    """Resolve the per-load skipped insert report path."""
    return config.PROJECT_ROOT / "artifacts" / "rag_insert_skipped.md"


def load_source_metadata_index() -> dict[str, dict[str, Any]]:
    """Load the persisted source metadata lookup file."""
    index_path = _source_index_path()
    if not index_path.exists():
        return {}
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _build_extraction_policy() -> str:
    """Project-specific extraction guidance layered on top of LightRAG prompts."""
    relation_policy = (
        "Prefer only explicitly stated relationships. Do not add speculative links."
        if config.RELATION_EXTRACTION_MODE == "explicit"
        else "Interpretive relationships are allowed only when the source text itself frames them as a clear alignment, backing, or strategic connection."
    )
    alias_lines = "\n".join(
        f"- `{alias}` -> `{canonical}`"
        for alias, canonical in sorted(_ENTITY_ALIAS_MAP.items())
    )
    return (
        "Ignore metadata headers and technical wrappers.\n"
        "Do not extract channel names, dates, URLs, post numbers, filenames, or placeholder media/review notes as entities.\n"
        "Use only the provided entity types. If a type does not fit exactly, map it to `other`.\n"
        f"{relation_policy}\n"
        "Canonicalize frequent aliases to these preferred names:\n"
        f"{alias_lines}"
    )


def _is_extraction_prompt(prompt: str, system_prompt: str | None) -> bool:
    """Detect LightRAG extraction prompts so we can constrain and sanitize them."""
    if not system_prompt:
        return False
    if "Knowledge Graph Specialist" not in system_prompt:
        return False
    return (
        "Data to be Processed" in prompt
        or "last extraction task" in prompt
        or "Completion Signal" in prompt
    )


def _canonicalize_entity_name(name: str) -> str:
    """Map common aliases to one canonical node label."""
    stripped = name.strip()
    return _ENTITY_ALIAS_MAP.get(stripped.casefold(), stripped)


def _sanitize_extraction_field(value: str) -> str:
    """Strip control delimiters so LightRAG can parse a stable tuple shape."""
    cleaned = str(value).replace(_TUPLE_DELIMITER, " ").replace(_COMPLETION_DELIMITER, " ")
    cleaned = cleaned.replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s{2,}", " ", cleaned).strip()


def _normalize_entity_type(entity_type: str) -> str:
    """Map model-produced types back into the local ontology."""
    normalized = entity_type.strip().casefold()
    if normalized in _ALLOWED_ENTITY_TYPES:
        return normalized
    remapped = _ENTITY_TYPE_REMAP.get(normalized, "other")
    return remapped if remapped in _ALLOWED_ENTITY_TYPES else "other"


def _is_noise_entity(entity_name: str) -> bool:
    """Reject technical artifacts that should never become graph nodes."""
    normalized = entity_name.strip()
    if not normalized:
        return True
    if _URL_ENTITY_RE.match(normalized):
        return True
    if _DATE_ENTITY_RE.match(normalized):
        return True
    if normalized.startswith("[") and normalized.endswith("]"):
        return True
    if "t.me/" in normalized.lower():
        return True
    return False


def _postprocess_extraction_response(response_text: str) -> str:
    """Normalize raw extraction output before LightRAG parses it."""
    entities: dict[str, tuple[str, str, str]] = {}
    relations: dict[tuple[str, str, str], tuple[str, str, str, str]] = {}

    for raw_line in str(response_text).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == _COMPLETION_DELIMITER:
            continue
        if line.startswith(f"entity{_TUPLE_DELIMITER}"):
            parts = line.split(_TUPLE_DELIMITER)
            if len(parts) < 4:
                continue
            name = _canonicalize_entity_name(_sanitize_extraction_field(parts[1]))
            if _is_noise_entity(name):
                continue
            entity_type = _normalize_entity_type(_sanitize_extraction_field(parts[2]))
            description = _sanitize_extraction_field(_TUPLE_DELIMITER.join(parts[3:]))
            key = name.casefold()
            current = entities.get(key)
            if current is None or len(description) > len(current[2]):
                entities[key] = (name, entity_type, description)
            continue

        if line.startswith(f"relation{_TUPLE_DELIMITER}"):
            parts = line.split(_TUPLE_DELIMITER)
            if len(parts) < 5:
                continue
            source = _canonicalize_entity_name(_sanitize_extraction_field(parts[1]))
            target = _canonicalize_entity_name(_sanitize_extraction_field(parts[2]))
            if _is_noise_entity(source) or _is_noise_entity(target):
                continue
            keywords = _sanitize_extraction_field(parts[3])
            description = _sanitize_extraction_field(_TUPLE_DELIMITER.join(parts[4:]))
            relation_key = tuple(sorted((source.casefold(), target.casefold()))) + (keywords.casefold(),)
            current = relations.get(relation_key)
            if current is None or len(description) > len(current[3]):
                relations[relation_key] = (source, target, keywords, description)

    output_lines = [
        f"entity{_TUPLE_DELIMITER}{name}{_TUPLE_DELIMITER}{entity_type}{_TUPLE_DELIMITER}{description}"
        for name, entity_type, description in entities.values()
    ]
    output_lines.extend(
        f"relation{_TUPLE_DELIMITER}{source}{_TUPLE_DELIMITER}{target}{_TUPLE_DELIMITER}{keywords}{_TUPLE_DELIMITER}{description}"
        for source, target, keywords, description in relations.values()
        if source.casefold() in entities and target.casefold() in entities
    )
    output_lines.append(_COMPLETION_DELIMITER)
    return "\n".join(output_lines)


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
    """Persist source metadata in one lookup file inside rag_storage."""
    index_path = _source_index_path()
    index_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if index_path.exists():
            current = json.loads(index_path.read_text(encoding="utf-8"))
        else:
            current = {}
    except (json.JSONDecodeError, OSError):
        current = {}

    current[_canonical_source_path(source_path)] = metadata
    index_path.write_text(
        json.dumps(current, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _remove_source_metadata_index(source_path: str) -> None:
    """Remove metadata for a document that did not finish insertion."""
    index_path = _source_index_path()
    if not index_path.exists():
        return
    try:
        current = json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    if current.pop(_canonical_source_path(source_path), None) is not None:
        index_path.write_text(
            json.dumps(current, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


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
            raise asyncio.TimeoutError
        await asyncio.sleep(1.0)


def _prepare_text_for_rag(text: str) -> str:
    """Remove metadata wrappers and placeholders before graph extraction."""
    lines = text.splitlines()
    if lines and _HEADER_LINE_RE.match(lines[0].strip()):
        lines = lines[1:]

    kept_lines = []
    for line in lines:
        stripped = line.strip()
        if _POSTHOLDER_LINE_RE.match(stripped):
            continue
        kept_lines.append(line)

    cleaned = "\n".join(kept_lines).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


async def create_rag() -> LightRAG:
    """Initialize a LightRAG instance with configured LLM and Embedding."""
    _configure_lightrag_prompts()

    async def llm_func(prompt, system_prompt=None, history_messages=[], **kwargs):
        is_extraction = _is_extraction_prompt(prompt, system_prompt)
        role = _LLM_ROLE.get()
        chat_role = "build" if role == "build" else "query"
        api_key, base_url, model = _chat_settings_for_role(chat_role)
        llm_client = _openai_client(
            api_key,
            base_url,
            timeout=config.LLM_TIMEOUT_SECONDS,
        )
        messages = []
        if system_prompt:
            system_content = system_prompt
            if is_extraction:
                system_content = f"{system_prompt}\n\n---Project-Specific Rules---\n{_build_extraction_policy()}"
            messages.append({"role": "system", "content": system_content})
        for m in (history_messages or []):
            messages.append(m)
        messages.append({"role": "user", "content": prompt})

        delay_seconds = (
            config.RAG_BUILD_DELAY_SECONDS if chat_role == "build" else config.QUERY_DELAY_SECONDS
        )
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

        response = await llm_client.chat.completions.create(
            model=model,
            messages=messages,
            **_chat_completion_options(
                max_tokens=kwargs.get("max_tokens") or config.QUERY_MAX_TOKENS,
                temperature=kwargs.get("temperature"),
                top_p=kwargs.get("top_p"),
            ),
        )
        content = response.choices[0].message.content or ""
        if is_extraction:
            content = _postprocess_extraction_response(content)
        return content

    # ── Embedding function ──
    # Using our custom _embed_texts which adds input_type for NIM asymmetric models
    embedding_func = EmbeddingFunc(
        embedding_dim=config.EMBEDDING_DIM,
        max_token_size=8192,
        func=_embed_texts,
    )

    # ── Create LightRAG ──
    # rerank_model_func: LightRAG calls this BEFORE sending chunks to LLM.
    # Signature: async (query, documents, top_n) -> [{"index": int, "relevance_score": float}]
    rag = LightRAG(
        working_dir=str(config.RAG_STORAGE_DIR),
        llm_model_func=llm_func,
        llm_model_max_async=config.LLM_MAX_ASYNC,
        embedding_func=embedding_func,
        rerank_model_func=lightrag_rerank_func if config.RERANKER_ENABLED else None,
        addon_params={
            "language": config.LIGHTRAG_LANGUAGE,
            "entity_types": config.LIGHTRAG_ENTITY_TYPES,
        },
    )

    await rag.initialize_storages()
    logger.info("LightRAG initialized.")
    return rag


def rebuild_rag_storage() -> Path | None:
    """
    Archive the current LightRAG storage directory and recreate it empty.

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
    return backup_path


def _canonical_source_path(source_path: str) -> str:
    """Normalize a source path so one logical source maps to one LightRAG doc_id."""
    return str(Path(source_path).resolve(strict=False))


def _source_doc_id(source_path: str) -> str:
    """Build a stable document ID from the normalized source path."""
    return compute_mdhash_id(_canonical_source_path(source_path), prefix="doc-")


def _entity_names_index_path() -> Path:
    """Path to the doc -> entity name index created by LightRAG."""
    return config.RAG_STORAGE_DIR / "kv_store_full_entities.json"


def _load_all_entity_names() -> list[str]:
    """Collect the unique entity labels currently present in the active graph."""
    path = _entity_names_index_path()
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    names: dict[str, None] = {}
    for entry in data.values():
        if not isinstance(entry, dict):
            continue
        for name in entry.get("entity_names", []):
            if isinstance(name, str) and name.strip():
                names[name.strip()] = None
    return list(names.keys())


def _entity_name_preference_key(name: str) -> tuple[int, int, str]:
    """Prefer human-readable casing when auto-choosing a canonical label."""
    stripped = name.strip()
    is_all_caps = stripped.isupper() and any(ch.isalpha() for ch in stripped)
    starts_lower = bool(stripped) and stripped[0].islower()
    return (
        1 if is_all_caps and len(stripped) > 4 else 0,
        1 if starts_lower else 0,
        stripped.casefold(),
    )


def plan_safe_entity_merges(entity_names: list[str]) -> list[dict[str, Any]]:
    """
    Plan only the merges that are considered safe enough for automatic cleanup.

    Safe groups currently include:
    - exact case-only variants of the same entity label
    - explicit alias mappings declared in config and normalized by _canonicalize_entity_name()
    """
    merge_groups: dict[str, set[str]] = {}

    # Safe case-only duplicates, e.g. HAMAS -> Hamas, al-Qaeda -> Al-Qaeda
    casefold_groups: dict[str, list[str]] = {}
    for name in entity_names:
        casefold_groups.setdefault(name.casefold(), []).append(name)
    for variants in casefold_groups.values():
        deduped = sorted(set(variants))
        if len(deduped) < 2:
            continue
        target = sorted(deduped, key=_entity_name_preference_key)[0]
        sources = {name for name in deduped if name != target}
        if sources:
            merge_groups.setdefault(target, set()).update(sources)

    # Explicit alias-based merges from project config, e.g. USA -> United States
    for name in entity_names:
        canonical = _canonicalize_entity_name(name)
        if canonical == name:
            continue
        merge_groups.setdefault(canonical, set()).add(name)

    planned = []
    already_sources: set[str] = set()
    for target in sorted(merge_groups):
        sources = sorted(
            src
            for src in merge_groups[target]
            if src != target and src not in already_sources
        )
        if not sources:
            continue
        planned.append({"target": target, "sources": sources})
        already_sources.update(sources)
    return planned


async def auto_fix_safe_entity_merges(rag: LightRAG) -> list[dict[str, Any]]:
    """Apply safe entity merges directly to the active LightRAG graph."""
    plans = plan_safe_entity_merges(_load_all_entity_names())
    applied: list[dict[str, Any]] = []

    for plan in plans:
        try:
            await rag.amerge_entities(plan["sources"], plan["target"])
            applied.append(plan)
            logger.info(
                "Auto-fixed entity aliases: %s -> %s",
                ", ".join(plan["sources"]),
                plan["target"],
            )
        except Exception as exc:
            logger.warning(
                "Failed to auto-merge entities into %s (%s): %s",
                plan["target"],
                ", ".join(plan["sources"]),
                exc,
            )

    return applied


async def _upsert_text(rag: LightRAG, source_path: str, text: str) -> None:
    """
    Replace an existing LightRAG document for this source path, then insert the new text.

    LightRAG's default doc_id is content-based, which duplicates logical documents when the
    same file is reloaded after edits. We instead key documents by source path.
    """
    canonical_path = _canonical_source_path(source_path)
    doc_id = _source_doc_id(canonical_path)
    metadata = _load_document_metadata(source_path, text)
    metadata["canonical_path"] = canonical_path
    _sync_source_metadata_index(source_path, metadata)

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
        await rag.ainsert([rag_text], ids=[doc_id], file_paths=[canonical_path])
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
        except asyncio.TimeoutError:
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
            logger.error(f"  Failed to insert {path}: {e}")

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

    if skipped:
        _write_skipped_insert_report(skipped)
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


_NORMALIZED_HEADER_RE = re.compile(r"^\[Канал:.*\]\s*$")
_PLACEHOLDER_CONTENT_RE = re.compile(
    r"^\[(?:Видео:|Аудио:|AI-диалог:|Отправлено в очередь|Уже обработано:|Веб-страница:.*ошибка).*\]$",
    re.IGNORECASE,
)


def _strip_normalized_header(text: str) -> str:
    lines = text.split("\n")
    body_lines = [ln for ln in lines if not _NORMALIZED_HEADER_RE.match(ln.strip())]
    return "\n".join(body_lines).strip()


def _has_meaningful_normalized_body(text: str) -> bool:
    body = _strip_normalized_header(text)
    lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
    if not lines:
        return False
    return any(not _PLACEHOLDER_CONTENT_RE.match(ln) for ln in lines)


def _card_has_extracted_content(card: dict) -> bool:
    if str(card.get("summary") or "").strip():
        return True

    for field in ("key_facts", "topics", "theses", "quotes", "events", "chunks"):
        if card.get(field):
            return True

    entities = card.get("entities", {})
    if isinstance(entities, dict):
        return any(bool(items) for items in entities.values())

    visual = card.get("visual", {})
    if isinstance(visual, dict) and str(visual.get("broll_notes") or "").strip():
        return True

    return False


def _read_normalized_fallback(card: dict) -> tuple[str, str] | None:
    norm_file = card.get("provenance", {}).get("normalized_file", "")
    if not norm_file:
        return None

    norm_path = Path(norm_file)
    if not norm_path.is_absolute():
        norm_path = config.PROJECT_ROOT / norm_path
    if not norm_path.exists():
        return None

    raw_text = norm_path.read_text(encoding="utf-8").strip()
    if not raw_text:
        return None
    return str(norm_path), raw_text


def _read_all_normalized_texts() -> dict[str, str]:
    """Return all normalized texts keyed by resolved absolute file path."""
    normalized_texts: dict[str, str] = {}
    for txt_file in sorted(config.NORMALIZED_DIR.rglob("*.txt")):
        try:
            text = txt_file.read_text(encoding="utf-8").strip()
        except Exception as e:
            logger.warning(f"  Cannot read normalized fallback {txt_file}: {e}")
            continue
        if text:
            normalized_texts[str(txt_file.resolve())] = text
    return normalized_texts


async def load_from_enriched(rag: LightRAG) -> dict:
    """
    Retired experimental graph-load path for enriched cards.

    The supported v1.1 LightRAG graph source is normalized text. Keep this
    helper only for historical/experimental investigation outside the main CLI.
    It loads enriched memory cards using graph_text, without losing curated
    normalized posts.

    For each enriched card:
      - is_duplicate → skip
      - keep + usable graph_text → load graph_text
      - review/partial/empty graph_text → fallback to normalized .txt file
      - missing enriched card → fallback to normalized .txt file

    Returns:
        dict with stats: loaded, skipped_triage, skipped_dedup,
        fallback_normalized, missing_enriched, errors
    """
    enriched_dir = config.ENRICHED_DIR
    stats = {
        "loaded": 0,
        "normalized_found": 0,
        "skipped_triage": 0,
        "skipped_dedup": 0,
        "fallback_normalized": 0,
        "missing_enriched": 0,
        "errors": 0,
    }

    if not enriched_dir.exists():
        logger.warning("No enriched directory found; falling back to normalized.")
        loaded = await load_from_directory(rag)
        stats["fallback_normalized"] = loaded
        return stats

    normalized_texts = _read_all_normalized_texts()
    stats["normalized_found"] = len(normalized_texts)
    texts_with_paths = []
    loaded_normalized_paths: set[str] = set()
    excluded_normalized_paths: set[str] = set()

    for channel_dir in sorted(d for d in enriched_dir.iterdir() if d.is_dir()):
        for card_path in sorted(channel_dir.glob("*.enriched.json")):
            try:
                card = json.loads(card_path.read_text(encoding="utf-8"))
                fallback = _read_normalized_fallback(card)
                fallback_path = str(Path(fallback[0]).resolve()) if fallback else None

                # Skip duplicates, but mark their source as intentionally accounted for.
                dedup = card.get("dedup", {})
                if dedup.get("is_duplicate"):
                    stats["skipped_dedup"] += 1
                    if fallback_path:
                        excluded_normalized_paths.add(fallback_path)
                    continue

                try:
                    from enricher.graph_text_builder import build_graph_text

                    graph_text = build_graph_text(card).strip()
                except Exception as exc:
                    logger.debug(f"  Could not rebuild graph_text for {card_path}: {exc}")
                    graph_text = card.get("graph_text", "").strip()
                raw_body = _strip_normalized_header(fallback[1]) if fallback else ""

                if card.get("triage") == "keep" and graph_text and (
                    _card_has_extracted_content(card) or len(raw_body.strip()) < 20
                ):
                    # Use enriched graph_text only when it contains actual extraction.
                    source_path = card.get("provenance", {}).get(
                        "normalized_file", str(card_path)
                    )
                    texts_with_paths.append((source_path, graph_text))
                    if fallback_path:
                        loaded_normalized_paths.add(fallback_path)
                elif fallback:
                    # Fallback: load raw normalized file for review/empty/partial cards.
                    if _has_meaningful_normalized_body(fallback[1]):
                        texts_with_paths.append(fallback)
                        loaded_normalized_paths.add(fallback_path)
                        stats["fallback_normalized"] += 1
                        if card.get("triage") != "keep":
                            stats["skipped_triage"] += 1
                    else:
                        stats["skipped_triage"] += 1
                        logger.info(
                            f"  Review-only placeholder not loaded: "
                            f"{channel_dir.name}/{card_path.stem}"
                        )
                else:
                    logger.warning(
                        f"  No usable graph_text and no normalized file for "
                        f"{channel_dir.name}/{card_path.stem}"
                    )

            except Exception as e:
                stats["errors"] += 1
                logger.error(f"  Error reading {card_path}: {e}")

    for norm_path, raw_text in normalized_texts.items():
        if norm_path in loaded_normalized_paths or norm_path in excluded_normalized_paths:
            continue
        if not _has_meaningful_normalized_body(raw_text):
            continue

        texts_with_paths.append((norm_path, raw_text))
        loaded_normalized_paths.add(norm_path)
        stats["fallback_normalized"] += 1
        stats["missing_enriched"] += 1

    if not texts_with_paths:
        logger.warning("No enriched texts to load.")
        return stats

    logger.info(
        f"Loading {len(texts_with_paths)} enriched texts into LightRAG "
        f"(skipped: {stats['skipped_triage']} triage, "
        f"{stats['skipped_dedup']} dedup, "
        f"{stats['fallback_normalized']} fallback, "
        f"{stats['missing_enriched']} missing enriched)."
    )
    stats["loaded"] = await load_texts(rag, texts_with_paths)
    return stats


async def query_rag(
    rag: LightRAG,
    question: str,
    mode: str | None = None,
    query_profile: str | None = None,
) -> str:
    """
    Query the LightRAG knowledge graph.

    Reranking happens INSIDE LightRAG at the chunk retrieval stage (before LLM),
    via rerank_model_func passed to the LightRAG constructor.

    Args:
        rag:      Initialized LightRAG instance
        question: The question to ask
        mode:     Query mode — "local", "global", "hybrid", "naive", "mix".
                  Defaults to "mix" when reranker is enabled, otherwise "hybrid".
        query_profile: Answer behavior profile — "answer", "source", or "overview".

    Returns:
        The answer from LightRAG
    """
    if mode is None:
        # "mix" mode gives LightRAG the most candidates to rerank from
        mode = "mix" if config.RERANKER_ENABLED else "hybrid"
    profile = get_query_profile(query_profile)
    wiki_context = _wiki_context_for_query(question)
    user_prompt = _query_user_prompt_with_wiki(profile["user_prompt"], wiki_context)

    logger.info(
        f"Querying LightRAG (mode={mode}, profile={query_profile or 'answer'}, rerank={'enabled' if config.RERANKER_ENABLED else 'disabled'})"
    )

    # enable_rerank=True tells LightRAG to call our rerank_model_func on retrieved chunks
    try:
        token = _LLM_ROLE.set("query")
        result = await asyncio.wait_for(
            rag.aquery(
                question,
                param=QueryParam(
                    mode=mode,
                    enable_rerank=config.RERANKER_ENABLED,
                    top_k=profile["top_k"],
                    chunk_top_k=profile["chunk_top_k"],
                    response_type=_QUERY_RESPONSE_TYPE,
                    user_prompt=user_prompt,
                ),
            ),
            timeout=config.QUERY_TIMEOUT_SECONDS,
        )
        _LLM_ROLE.reset(token)
    except asyncio.TimeoutError:
        _LLM_ROLE.reset(token)
        logger.warning(
            "LightRAG query timed out after %ss; trying shadow-search fallback.",
            config.QUERY_TIMEOUT_SECONDS,
        )
        if not _is_funding_question(question):
            fallback = _shadow_fallback_result(question, query_profile)
            if fallback:
                fallback = await _synthesize_shadow_fallback_result(question, query_profile, fallback)
                return str(fallback["llm_response"]["content"])
        return "В базе не удалось получить ответ за отведённое время."
    except Exception as exc:
        _LLM_ROLE.reset(token)
        logger.warning(f"LightRAG query failed; trying shadow-search fallback: {exc}")
        if not _is_funding_question(question):
            fallback = _shadow_fallback_result(question, query_profile)
            if fallback:
                fallback = await _synthesize_shadow_fallback_result(question, query_profile, fallback)
                return str(fallback["llm_response"]["content"])
        return "В базе не удалось получить ответ."
    if (
        isinstance(result, str)
        and not _is_funding_question(question)
        and any(marker in result.casefold() for marker in _NO_CONTEXT_MARKERS)
    ):
        fallback = _shadow_fallback_result(question, query_profile)
        if fallback:
            logger.info("Using shadow-search fallback after no-context LightRAG answer.")
            fallback = await _synthesize_shadow_fallback_result(question, query_profile, fallback)
            return str(fallback["llm_response"]["content"])
    if isinstance(result, str) and not _is_funding_question(question) and _answer_looks_corrupt(result):
        fallback = _shadow_fallback_result(question, query_profile)
        if fallback:
            logger.info("Using shadow-search fallback after corrupt LightRAG answer.")
            fallback = await _synthesize_shadow_fallback_result(question, query_profile, fallback)
            return str(fallback["llm_response"]["content"])
    if isinstance(result, str):
        return _postprocess_answer_text(result, question, query_profile)
    return result


def _card_fact_lines(
    card: dict[str, Any],
    limit: int = 4,
    *,
    include_visual: bool = False,
) -> list[str]:
    lines = []
    summary = str(card.get("summary") or "").strip()
    if summary:
        lines.append(summary)
    for fact in card.get("key_facts", []) or []:
        if not isinstance(fact, dict):
            continue
        text = str(fact.get("text") or "").strip()
        if text:
            lines.append(text)
        if len(lines) >= limit:
            break
    if include_visual:
        visual = card.get("visual", {})
        if isinstance(visual, dict):
            broll_notes = str(visual.get("broll_notes") or "").strip()
            if broll_notes:
                lines.append(f"Визуалы: {broll_notes}")
    return lines[:limit]


def _load_shadow_card(card_path: str | None) -> dict[str, Any]:
    if not card_path:
        return {}
    try:
        card = json.loads(Path(card_path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return card if isinstance(card, dict) else {}


def _shadow_match_text(match: Any, card: dict[str, Any]) -> str:
    parts = [str(match.title), str(match.source_path), str(match.snippet)]
    for key in ("search_text", "graph_text", "summary"):
        value = str(card.get(key) or "").strip()
        if value:
            parts.append(value)
    for fact in card.get("key_facts", []) or []:
        if isinstance(fact, dict) and fact.get("text"):
            parts.append(str(fact["text"]))
    return "\n".join(parts)


_GENERIC_CONTEXT_QUERY_TERMS = (
    "какие",
    "какой",
    "какая",
    "какую",
    "какими",
    "база",
    "описывает",
    "можно",
    "использовать",
    "используй",
    "кадр",
    "кадры",
    "визуал",
    "визуалы",
    "ролик",
    "ролика",
    "отношение",
    "попытку",
    "видео",
    "broll",
    "source",
    "sources",
    "источник",
    "источники",
)


def _content_query_terms(query_terms: list[str], shadow_search_module: Any) -> list[str]:
    """Keep topic/entity terms separate from generic task wording for card ranking."""
    content_terms = []
    for term in query_terms:
        if any(
            shadow_search_module._matches_term(term, generic)
            or shadow_search_module._matches_term(generic, term)
            for generic in _GENERIC_CONTEXT_QUERY_TERMS
        ):
            continue
        content_terms.append(term)
    return content_terms or query_terms


def _shadow_fallback_result(question: str, query_profile: str | None) -> dict[str, Any] | None:
    """Build a deterministic lexical fallback when vector/graph retrieval misses exact cards."""
    try:
        from retrieval import shadow_search
    except Exception as exc:
        logger.debug(f"Shadow fallback unavailable: {exc}")
        return None

    query_terms = list(dict.fromkeys(shadow_search._tokenize(question)))
    required_terms = 1 if len(query_terms) <= 1 else 2
    content_terms = _content_query_terms(query_terms, shadow_search)
    include_visual = _question_requests_visuals(question)
    candidates = []
    for match in shadow_search.search(question, top_k=8):
        card = _load_shadow_card(match.card_path)
        text_tokens = shadow_search._tokenize(_shadow_match_text(match, card))
        path_title_tokens = shadow_search._tokenize(f"{match.title} {match.source_path}")
        matched_terms = {
            term
            for term in query_terms
            if any(shadow_search._matches_term(token, term) for token in text_tokens)
        }
        path_title_terms = {
            term
            for term in query_terms
            if any(shadow_search._matches_term(token, term) for token in path_title_tokens)
        }
        content_matched_terms = {
            term
            for term in content_terms
            if any(shadow_search._matches_term(token, term) for token in text_tokens)
        }
        if len(matched_terms) >= required_terms:
            candidates.append((match, card, matched_terms, path_title_terms, content_matched_terms))

    if not candidates:
        return None

    content_term_counts = {
        term: sum(1 for item in candidates if term in item[4])
        for term in content_terms
    }

    def specificity_score(item: tuple[Any, dict[str, Any], set[str], set[str], set[str]]) -> float:
        return sum(1.0 / content_term_counts[term] for term in item[4] if content_term_counts.get(term))

    if include_visual:
        candidates.sort(
            key=lambda item: (len(item[4]), item[0].score, specificity_score(item), len(item[2]), len(item[3])),
            reverse=True,
        )
    else:
        candidates.sort(
            key=lambda item: (len(item[4]), len(item[3]), item[0].score, specificity_score(item), len(item[2])),
            reverse=True,
        )
    top_parent = Path(_resolve_match_source_path(candidates[0][0].source_path)).parent
    max_context_matches = 1 if include_visual else 3
    strong_matches = [
        item
        for item in candidates
        if Path(_resolve_match_source_path(item[0].source_path)).parent == top_parent
    ][:max_context_matches]
    if not strong_matches:
        return None

    references = []
    sections = []
    context_items = []
    for idx, (match, card, _matched_terms, _path_title_terms, _content_matched_terms) in enumerate(strong_matches, start=1):
        source_path = _resolve_match_source_path(match.source_path)
        references.append({"reference_id": str(idx), "file_path": source_path})

        facts = _card_fact_lines(card, include_visual=include_visual)
        if facts:
            body = "\n".join(f"- {fact}" for fact in facts)
        else:
            body = f"- {match.snippet.strip()}"
            facts = [match.snippet.strip()]
        sections.append(f"[{idx}] Источник: {source_path}\n{body}")
        context_items.append(
            {
                "reference_id": str(idx),
                "file_path": source_path,
                "facts": facts,
                "snippet": str(match.snippet or "").strip(),
                "title": str(match.title or "").strip(),
            }
        )

    if query_profile == "source":
        intro = "Найденные источники по этому тезису:"
    elif include_visual:
        intro = "По найденным карточкам можно использовать такие кадры и визуалы:"
    else:
        intro = "По найденным релевантным карточкам:"

    answer = intro + "\n\n" + "\n\n".join(sections)
    if "тезис" in question.casefold() and "тезис" not in answer.casefold():
        answer = "Главный тезис по найденным карточкам:\n\n" + answer
    answer += "\n\n### References\n"
    for ref in references:
        answer += f"- [{ref['reference_id']}] {ref['file_path']}\n"
    answer = _postprocess_answer_text(answer, question, query_profile)

    return {
        "response": answer,
        "llm_response": {"content": answer},
        "data": {"references": references, "shadow_context": context_items},
        "fallback": "shadow_search",
    }


def _format_shadow_context(context_items: list[dict[str, Any]]) -> str:
    blocks = []
    for item in context_items:
        facts = [str(fact).strip() for fact in item.get("facts", []) if str(fact).strip()]
        fact_text = "\n".join(f"- {fact}" for fact in facts)
        blocks.append(
            f"[{item.get('reference_id')}] {item.get('file_path')}\n"
            f"{fact_text}"
        )
    return "\n\n".join(blocks)


async def _synthesize_shadow_fallback_result(
    question: str,
    query_profile: str | None,
    fallback: dict[str, Any],
) -> dict[str, Any]:
    """Turn shadow-search matches into a normal user-facing answer."""
    data = dict(fallback.get("data") or {})
    context_items = data.get("shadow_context") or []
    if not context_items or not config.FALLBACK_SYNTH_API_KEY or not config.HYBRID_SYNTH_ENABLED:
        return fallback

    include_visual = _question_requests_visuals(question)
    profile = query_profile or "answer"
    context = _format_shadow_context(context_items)
    if not context.strip():
        return fallback

    system = (
        "Ты пишешь финальный ответ RAG-системы на русском языке. "
        "Используй только предоставленный контекст карточек. "
        "Не упоминай LightRAG, shadow search, fallback, точный поиск по карточкам или технические детали системы. "
        "Не копируй сырые поля карточки как дамп; сделай связный ответ. "
        "Сохраняй осторожные формулировки: подозрения остаются подозрениями, заявления источника остаются заявлениями источника. "
        "Не называй утверждения фальшивыми, ложными, дезинформацией или имитацией, если это явно не сказано в контексте."
    )
    if include_visual:
        system += " Вопрос просит визуалы, поэтому можно использовать визуальные заметки и кадры."
    else:
        system += " Не включай B-roll, визуальные заметки или предложения кадров, если они случайно попали в контекст."
    if profile == "source":
        system += " Так как пользователь просит источник, укажи конкретные файлы/ссылки из контекста."

    user = (
        f"Вопрос:\n{question}\n\n"
        f"Контекст карточек:\n{context}\n\n"
        "Ответь в 2-4 абзацах. Для source-вопроса можно использовать короткий список источников."
    )

    try:
        if config.QUERY_DELAY_SECONDS > 0:
            await asyncio.sleep(config.QUERY_DELAY_SECONDS)
        client = _openai_client(
            config.FALLBACK_SYNTH_API_KEY,
            config.FALLBACK_SYNTH_BASE_URL,
            timeout=min(config.LLM_TIMEOUT_SECONDS, config.FALLBACK_SYNTH_TIMEOUT_SECONDS),
            max_retries=0,
        )
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=config.FALLBACK_SYNTH_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                **_chat_completion_options(
                    max_tokens=config.FALLBACK_SYNTH_MAX_TOKENS,
                    temperature=0,
                ),
            ),
            timeout=config.FALLBACK_SYNTH_TIMEOUT_SECONDS + 5,
        )
        answer = (response.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.warning(f"Shadow fallback synthesis failed; using deterministic answer: {exc}")
        return fallback

    if not answer:
        return fallback
    if _answer_looks_corrupt(answer):
        logger.warning("Shadow fallback synthesis looked corrupt; using deterministic card fallback.")
        return fallback
    answer = _postprocess_answer_text(answer, question, query_profile)

    fixed = fallback.copy()
    fixed["response"] = answer
    fixed["llm_response"] = {"content": answer}
    fixed["fallback"] = "shadow_search_llm"
    return fixed


def _card_context_for_query(question: str, query_profile: str | None) -> dict[str, Any] | None:
    """Return strong enriched-card matches as context for normal hybrid answers."""
    if not config.HYBRID_QUERY_CARDS_ENABLED:
        return None
    fallback = _shadow_fallback_result(question, query_profile)
    if not fallback:
        return None

    data = dict(fallback.get("data") or {})
    context_items = list(data.get("shadow_context") or [])[: max(1, config.HYBRID_QUERY_CARDS_TOP_K)]
    if not context_items:
        return None

    references = []
    for idx, item in enumerate(context_items, start=1):
        item["reference_id"] = f"card-{idx}"
        file_path = str(item.get("file_path") or "").strip()
        if file_path:
            references.append({"reference_id": f"card-{idx}", "file_path": file_path})
    if not references:
        return None

    return {"references": references, "shadow_context": context_items}


def _attach_card_context(
    result: dict[str, Any],
    card_context: dict[str, Any],
    *,
    prefer_card_references: bool = False,
) -> dict[str, Any]:
    fixed = result.copy()
    data = dict(fixed.get("data") or {})
    card_references = list(card_context.get("references") or [])
    existing_references = _existing_references(fixed)
    if prefer_card_references:
        data["references"] = _merge_references(card_references, existing_references)
    else:
        data["references"] = _merge_references(existing_references, card_references)
    data["shadow_context"] = list(card_context.get("shadow_context") or [])
    fixed["data"] = data
    return fixed


def _should_prefer_card_references(question: str, query_profile: str | None) -> bool:
    return True


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


async def _synthesize_hybrid_result(
    question: str,
    query_profile: str | None,
    result: dict[str, Any],
    card_context: dict[str, Any],
) -> dict[str, Any]:
    """Compose LightRAG answer with enriched-card facts into one user-facing answer."""
    prefer_card_references = _should_prefer_card_references(question, query_profile)
    if not config.HYBRID_SYNTH_ENABLED or not config.FALLBACK_SYNTH_API_KEY:
        return _attach_card_context(result, card_context, prefer_card_references=prefer_card_references)

    graph_answer = str(result.get("llm_response", {}).get("content") or result.get("response") or "").strip()
    context = _format_shadow_context(list(card_context.get("shadow_context") or []))
    if not graph_answer or not context.strip():
        return _attach_card_context(result, card_context, prefer_card_references=prefer_card_references)

    wiki_context = _wiki_context_from_result(result)
    wiki_prompt_context = (
        _format_wiki_prompt_context(wiki_context, max_pages=3, max_sources=2)
        if wiki_context
        else ""
    )
    include_visual = _question_requests_visuals(question)
    profile = query_profile or "answer"
    system = (
        "Ты пишешь финальный ответ RAG-системы на русском языке. "
        "У тебя есть черновой ответ графа, дополнительные карточки источников и, возможно, локальная wiki-память. "
        "Собери один связный ответ, используя только эти данные. "
        "Не упоминай LightRAG, shadow search, fallback, wiki-память, карточки, технические детали системы или внутренние режимы поиска. "
        "Не копируй сырые поля как дамп. "
        "Сохраняй осторожные формулировки: подозрения остаются подозрениями, заявления источника остаются заявлениями источника. "
        "Не называй утверждения фальшивыми, ложными, дезинформацией или имитацией, если это явно не сказано в данных. "
        "Если дополнительные данные только дублируют или слабо связаны с вопросом, не раздувай ответ."
    )
    if include_visual:
        system += " Вопрос просит визуалы, поэтому можно использовать визуальные заметки и кадры."
    else:
        system += " Не включай B-roll, визуальные заметки или предложения кадров."
    if profile == "source":
        system += " Так как пользователь просит источник, укажи конкретные файлы/ссылки из контекста."

    wiki_block = f"\n\nЛокальная wiki-память:\n{wiki_prompt_context}" if wiki_prompt_context else ""
    user = (
        f"Вопрос:\n{question}\n\n"
        f"Черновой ответ графа:\n{graph_answer}\n\n"
        f"Дополнительный контекст источников:\n{context}"
        f"{wiki_block}\n\n"
        "Ответь в 2-5 абзацах. Не добавляй факты вне предоставленных данных."
    )

    try:
        if config.QUERY_DELAY_SECONDS > 0:
            await asyncio.sleep(config.QUERY_DELAY_SECONDS)
        client = _openai_client(
            config.FALLBACK_SYNTH_API_KEY,
            config.FALLBACK_SYNTH_BASE_URL,
            timeout=min(config.LLM_TIMEOUT_SECONDS, config.FALLBACK_SYNTH_TIMEOUT_SECONDS),
            max_retries=0,
        )
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=config.FALLBACK_SYNTH_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                **_chat_completion_options(
                    max_tokens=config.FALLBACK_SYNTH_MAX_TOKENS,
                    temperature=0,
                ),
            ),
            timeout=config.FALLBACK_SYNTH_TIMEOUT_SECONDS + 5,
        )
        answer = (response.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.warning(f"Hybrid synthesis failed; keeping LightRAG answer with card references: {exc}")
        return _attach_card_context(result, card_context, prefer_card_references=prefer_card_references)

    if not answer:
        return _attach_card_context(result, card_context, prefer_card_references=prefer_card_references)
    if _answer_looks_corrupt(answer):
        logger.warning("Hybrid synthesis looked corrupt; keeping LightRAG answer with card references.")
        return _attach_card_context(result, card_context, prefer_card_references=prefer_card_references)

    answer = _postprocess_answer_text(answer, question, query_profile)
    fixed = _attach_card_context(result, card_context, prefer_card_references=prefer_card_references)
    llm_response = dict(fixed.get("llm_response") or {})
    llm_response["content"] = answer
    fixed["llm_response"] = llm_response
    fixed["response"] = answer
    fixed["hybrid_context"] = "cards"
    return fixed


async def query_rag_result(
    rag: LightRAG,
    question: str,
    mode: str | None = None,
    query_profile: str | None = None,
) -> dict[str, Any]:
    """Query LightRAG once and return both the answer and structured retrieval data."""
    if mode is None:
        mode = "mix" if config.RERANKER_ENABLED else "hybrid"
    profile = get_query_profile(query_profile)
    wiki_context = _wiki_context_for_query(question)
    user_prompt = _query_user_prompt_with_wiki(profile["user_prompt"], wiki_context)

    logger.info(
        f"Querying LightRAG with retrieval payload (mode={mode}, profile={query_profile or 'answer'}, rerank={'enabled' if config.RERANKER_ENABLED else 'disabled'})"
    )

    try:
        token = _LLM_ROLE.set("query")
        result = await asyncio.wait_for(
            rag.aquery_llm(
                question,
                param=QueryParam(
                    mode=mode,
                    enable_rerank=config.RERANKER_ENABLED,
                    include_references=True,
                    top_k=profile["top_k"],
                    chunk_top_k=profile["chunk_top_k"],
                    response_type=_QUERY_RESPONSE_TYPE,
                    user_prompt=user_prompt,
                ),
            ),
            timeout=config.QUERY_TIMEOUT_SECONDS,
        )
        _LLM_ROLE.reset(token)
    except asyncio.TimeoutError:
        _LLM_ROLE.reset(token)
        logger.warning(
            "LightRAG query timed out after %ss; trying shadow-search fallback.",
            config.QUERY_TIMEOUT_SECONDS,
        )
        if not _is_funding_question(question):
            fallback = _shadow_fallback_result(question, query_profile)
            if fallback:
                fallback = await _synthesize_shadow_fallback_result(question, query_profile, fallback)
                return _attach_wiki_context(fallback, wiki_context)
        return _attach_wiki_context({
            "response": "В базе не удалось получить ответ за отведённое время.",
            "llm_response": {"content": "В базе не удалось получить ответ за отведённое время."},
            "data": {"references": []},
            "fallback": "timeout_no_context",
        }, wiki_context)
    except Exception as exc:
        _LLM_ROLE.reset(token)
        logger.warning(f"LightRAG query failed; trying shadow-search fallback: {exc}")
        if not _is_funding_question(question):
            fallback = _shadow_fallback_result(question, query_profile)
            if fallback:
                fallback = await _synthesize_shadow_fallback_result(question, query_profile, fallback)
                return _attach_wiki_context(fallback, wiki_context)
        return _attach_wiki_context({
            "response": "В базе не удалось получить ответ.",
            "llm_response": {"content": "В базе не удалось получить ответ."},
            "data": {"references": []},
            "fallback": "error_no_context",
        }, wiki_context)
    if isinstance(result, dict) and not _is_funding_question(question) and _response_has_no_context(result):
        fallback = _shadow_fallback_result(question, query_profile)
        if fallback:
            logger.info("Using shadow-search fallback after no-context LightRAG answer.")
            fallback = await _synthesize_shadow_fallback_result(question, query_profile, fallback)
            return _attach_wiki_context(fallback, wiki_context)
    if isinstance(result, dict) and not _is_funding_question(question) and _response_looks_corrupt(result):
        fallback = _shadow_fallback_result(question, query_profile)
        if fallback:
            logger.info("Using shadow-search fallback after corrupt LightRAG answer.")
            fallback = await _synthesize_shadow_fallback_result(question, query_profile, fallback)
            return _attach_wiki_context(fallback, wiki_context)
    if isinstance(result, dict):
        answer = str(result.get("llm_response", {}).get("content") or result.get("response") or "")
        fixed_answer = _postprocess_answer_text(answer, question, query_profile)
        if fixed_answer != answer:
            result = result.copy()
            llm_response = dict(result.get("llm_response") or {})
            llm_response["content"] = fixed_answer
            result["llm_response"] = llm_response
            result["response"] = fixed_answer
        result = _attach_wiki_context(result, wiki_context)
        if not _is_funding_question(question):
            card_context = _card_context_for_query(question, query_profile)
            if card_context:
                logger.info("Adding enriched-card context to LightRAG answer.")
                result = await _synthesize_hybrid_result(
                    question,
                    query_profile,
                    result,
                    card_context,
                )
        result = _attach_reference_hints(result, question)
    return result
