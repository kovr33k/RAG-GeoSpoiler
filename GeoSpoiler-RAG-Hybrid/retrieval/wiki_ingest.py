"""LLM-maintained wiki ingest from enriched cards."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import config
from retrieval import wiki_index
from retrieval.wiki_coverage import run_wiki_coverage_backfill
from retrieval.wiki_llm import call_wiki_llm
from retrieval.wiki_update import OPERATION_LOG_FILENAME, PENDING_UPDATES_FILENAME, SOURCE_HASHES_FILENAME

GENERATED_BY = "wiki_ingest_v1"
CLAIM_STATUSES = {
    "supported_by_corpus",
    "contradicted_by_corpus",
    "disputed_in_corpus",
    "unclear_in_corpus",
}
PAGE_TYPES = {"claim", "entity", "topic"}
DIRECT_EVIDENCE_TYPES = {"source_claim", "quote"}
EVIDENCE_TYPE_ALIASES = {
    "fact": "source_claim",
    "key_fact": "source_claim",
    "key_facts": "source_claim",
}


@dataclass(frozen=True)
class EnrichedCard:
    path: Path
    card: dict[str, Any]
    source: wiki_index.EnrichedSource


@dataclass(frozen=True)
class WikiIngestPending:
    reason: str
    source_id: str
    content_hash: str
    card_path: str
    post_url: str
    normalized_file: str
    date: str
    message: str


@dataclass(frozen=True)
class WikiIngestStats:
    cards_seen: int
    cards_processed: int
    pages_created: list[Path]
    pages_updated: list[Path]
    pending: list[WikiIngestPending]
    source_hashes_path: Path
    pending_updates_path: Path
    log_path: Path


def run_wiki_ingest(
    wiki_dir: Path = config.WIKI_DIR,
    enriched_dir: Path = config.ENRICHED_DIR,
    index_dir: Path = config.WIKI_INDEX_DIR,
    today: date | None = None,
    batch_size: int | None = None,
    llm_call: Callable[[str], dict[str, Any]] = call_wiki_llm,
) -> WikiIngestStats:
    """Create/update LLM-maintained wiki pages from changed enriched cards."""
    today = today or date.today()
    batch_size = batch_size or config.WIKI_INGEST_BATCH_SIZE
    for directory in [wiki_dir, wiki_dir / "claims", wiki_dir / "entities", wiki_dir / "topics", index_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    source_hashes_path = index_dir / SOURCE_HASHES_FILENAME
    pending_updates_path = wiki_dir / PENDING_UPDATES_FILENAME
    log_path = wiki_dir / OPERATION_LOG_FILENAME

    previous_hashes = _load_source_hashes(source_hashes_path)
    selected_cards = _select_cards_for_ingest(enriched_dir, previous_hashes)
    pages_created: list[Path] = []
    pages_updated: list[Path] = []
    pending: list[WikiIngestPending] = []

    for batch in _group_cards_into_batches(selected_cards, batch_size=max(1, batch_size)):
        prompt = _build_ingest_prompt(batch, wiki_dir)
        response = llm_call(prompt)
        operations = _extract_operations(response)
        if not operations:
            pending.extend(_pending_for_batch("failed_llm", batch, "Wiki LLM returned no page operations."))
            continue

        validated, errors = _validate_wiki_operations(operations, {card.source.source_id or "" for card in batch})
        if errors:
            pending.extend(_pending_for_batch("invalid_operation", batch, "; ".join(errors)))
            continue

        created, updated = _apply_wiki_operations(validated, wiki_dir, batch, today)
        pages_created.extend(created)
        pages_updated.extend(updated)

    _write_source_hashes(source_hashes_path, _current_source_hash_records(enriched_dir))
    _write_pending_updates(pending_updates_path, pending)
    wiki_index.build_wiki_indexes(wiki_dir=wiki_dir, enriched_dir=enriched_dir, index_dir=index_dir)
    run_wiki_coverage_backfill(wiki_dir=wiki_dir, enriched_dir=enriched_dir, index_dir=index_dir, today=today)
    wiki_index.build_wiki_indexes(wiki_dir=wiki_dir, enriched_dir=enriched_dir, index_dir=index_dir)

    stats = WikiIngestStats(
        cards_seen=_count_enriched_cards(enriched_dir),
        cards_processed=len(selected_cards),
        pages_created=pages_created,
        pages_updated=pages_updated,
        pending=pending,
        source_hashes_path=source_hashes_path,
        pending_updates_path=pending_updates_path,
        log_path=log_path,
    )
    _append_log(stats)
    return stats


def _select_cards_for_ingest(enriched_dir: Path, source_hashes: dict[str, str]) -> list[EnrichedCard]:
    selected: list[EnrichedCard] = []
    for path, card in wiki_index.iter_enriched_cards(enriched_dir):
        if card.get("triage") != "keep":
            continue
        source = wiki_index.get_enriched_source(path, card)
        if not source.source_id:
            continue
        if source_hashes.get(source.source_id) == source.content_hash:
            continue
        selected.append(EnrichedCard(path=path, card=card, source=source))
    return selected


def _group_cards_into_batches(cards: list[EnrichedCard], batch_size: int = 5) -> list[list[EnrichedCard]]:
    remaining = cards.copy()
    batches: list[list[EnrichedCard]] = []
    while remaining:
        seed = remaining.pop(0)
        batch = [seed]
        seed_terms = _card_terms(seed.card)
        idx = 0
        while idx < len(remaining) and len(batch) < batch_size:
            candidate = remaining[idx]
            if seed_terms & _card_terms(candidate.card):
                batch.append(candidate)
                remaining.pop(idx)
            else:
                idx += 1
        while remaining and len(batch) < batch_size:
            batch.append(remaining.pop(0))
        batches.append(batch)
    return batches


def _build_ingest_prompt(batch: list[EnrichedCard], wiki_dir: Path) -> str:
    schema = _read_text(wiki_dir / "_schema.md")
    existing_pages = _existing_page_summaries(wiki_dir)
    relevant_pages = _relevant_existing_pages(batch, wiki_dir)
    cards = [_card_prompt_payload(item) for item in batch]
    payload = {
        "instructions": [
            "Create or update wiki pages from enriched cards.",
            "Use only the provided cards and existing wiki page excerpts.",
            "Return JSON with an operations array.",
            "Each operation must include action, page_type, slug, title, and source_ids.",
            "Claim operations must include status, evidence, and guardrails.",
            "Every source_id must be copied from the input cards.",
            "Use Russian for all human-visible wiki page text when the source cards are Russian.",
            "Prefer Russian titles for claim pages; claim file names are derived from those titles.",
            "Do not translate source evidence away from the language used in enriched cards.",
        ],
        "schema": schema,
        "existing_pages": existing_pages,
        "relevant_existing_page_excerpts": relevant_pages,
        "cards": cards,
        "operation_schema": {
            "operations": [
                {
                    "action": "create|update",
                    "page_type": "claim|entity|topic",
                    "slug": "kebab-case-slug",
                    "title": "Page title",
                    "status": "supported_by_corpus|contradicted_by_corpus|disputed_in_corpus|unclear_in_corpus",
                    "source_ids": ["telegram:channel:message"],
                    "evidence": [
                        {
                            "source_id": "telegram:channel:message",
                            "evidence_type": "source_claim|quote",
                            "text": "Evidence copied or tightly paraphrased from the card.",
                        }
                    ],
                    "summary": "Entity/topic summary grounded in the cards.",
                    "guardrails": ["Caution to preserve source fidelity."],
                    "related_claims": ["claims/example.md"],
                }
            ]
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _extract_operations(response: dict[str, Any]) -> list[dict[str, Any]]:
    operations = response.get("operations") or response.get("page_operations") or []
    return [item for item in operations if isinstance(item, dict)] if isinstance(operations, list) else []


def _validate_wiki_operations(
    operations: list[dict[str, Any]],
    batch_source_ids: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    allowed_sources = {source_id for source_id in batch_source_ids if source_id}
    errors: list[str] = []
    validated: list[dict[str, Any]] = []

    for index, op in enumerate(operations, start=1):
        page_type = str(op.get("page_type") or "").strip().lower()
        if page_type not in PAGE_TYPES:
            errors.append(f"operation {index} has unsupported page_type={page_type!r}")
            continue

        slug = _slugify(op.get("slug") or op.get("title") or "")
        title = _clean_str(op.get("title"))
        if not slug or not title:
            errors.append(f"operation {index} is missing slug/title")
            continue
        if page_type == "claim":
            title_slug = _slugify(title)
            if title_slug and _has_cyrillic(title):
                slug = title_slug

        source_ids = set(_operation_source_ids(op))
        external = sorted(source_ids - allowed_sources)
        if external:
            errors.append(f"operation {index} cites sources outside the input batch: {', '.join(external)}")
            continue

        if page_type == "claim":
            status = _clean_str(op.get("status"))
            if status not in CLAIM_STATUSES:
                errors.append(f"operation {index} has unsupported claim status={status!r}")
                continue
            evidence = _normalize_claim_evidence(op.get("evidence"), allowed_sources)
            if not evidence:
                errors.append(f"operation {index} claim has no source_claim or quote evidence")
                continue
            evidence_source_ids = {item["source_id"] for item in evidence}
            if not any(source_id.startswith("telegram:") for source_id in evidence_source_ids):
                errors.append(f"operation {index} claim has no telegram source_id")
                continue
            source_ids = evidence_source_ids

        normalized = dict(op)
        normalized["page_type"] = page_type
        normalized["slug"] = slug
        normalized["title"] = title
        normalized["source_ids"] = sorted(source_ids)
        if page_type == "claim":
            normalized["evidence"] = evidence
        validated.append(normalized)

    return validated, errors


def _apply_wiki_operations(
    operations: list[dict[str, Any]],
    wiki_dir: Path,
    batch: list[EnrichedCard],
    today: date,
) -> tuple[list[Path], list[Path]]:
    created: list[Path] = []
    updated: list[Path] = []
    source_by_id = {card.source.source_id or "": card.source for card in batch}
    known_pages = _known_wiki_pages(wiki_dir, operations)

    for op in operations:
        page_type = str(op["page_type"])
        page_path = wiki_dir / _page_directory(page_type) / f"{op['slug']}.md"
        page_path.parent.mkdir(parents=True, exist_ok=True)
        text = (
            _render_claim_page(op, source_by_id, today, known_pages)
            if page_type == "claim"
            else _render_entity_topic_page(op, today, known_pages)
        )
        old_text = page_path.read_text(encoding="utf-8") if page_path.exists() else None
        if old_text == text:
            continue
        page_path.write_text(text, encoding="utf-8")
        if old_text is None:
            created.append(page_path)
        else:
            updated.append(page_path)
    return created, updated


def _render_claim_page(
    op: dict[str, Any],
    source_by_id: dict[str, wiki_index.EnrichedSource],
    today: date,
    known_pages: set[str],
) -> str:
    source_ids = [source_id for source_id in op.get("source_ids", []) if source_id]
    evidence = [item for item in op.get("evidence", []) if isinstance(item, dict)]
    source_count = len(set(source_ids))
    lines = [
        "---",
        "wiki_type: claim",
        f"status: {op.get('status')}",
        f"generated_by: {GENERATED_BY}",
        "review_status: auto",
        f"source_count: {source_count}",
        f"updated_at: {today.isoformat()}",
        "---",
        "",
        f"# {op['title']}",
        "",
        f"Статус: {op.get('status')}",
        "Статус проверки: auto",
        f"Количество источников: {source_count}",
        "",
        "## Доказательства",
        "",
    ]

    for item in evidence:
        source_id = _clean_str(item.get("source_id"))
        evidence_type = _normalize_evidence_type(item.get("evidence_type"))
        text = _one_line(item.get("text"))
        if not source_id or not text or evidence_type not in DIRECT_EVIDENCE_TYPES:
            continue
        lines.append(f"- {source_id} - {evidence_type}: {text}")
        source = source_by_id.get(source_id)
        if source:
            if source.post_url:
                lines.append(f"  - post_url: {source.post_url}")
            if source.date:
                lines.append(f"  - date: {source.date}")
            lines.append(f"  - card_path: {source.card_path}")
            lines.append(f"  - content_hash: {source.content_hash}")

    lines.extend(
        [
            "",
            "## Ограничения",
            "",
            "- Поле `status` описывает поддержку внутри корпуса, а не внешнюю фактчек-оценку.",
            "- Отвечая по этой странице, используй только процитированные доказательства.",
            "- Не используй summaries, theses или hypotheses как прямое доказательство.",
            "- Отделяй утверждения источника от интерпретации автора.",
        ]
    )
    for guardrail in op.get("guardrails") or []:
        text = _one_line(guardrail)
        if text:
            lines.append(f"- {text}")

    related_claims = _valid_related_claims(op.get("related_claims"), known_pages)
    lines.extend(["", "## Связанные страницы", ""])
    if related_claims:
        lines.extend(f"- {claim}" for claim in related_claims)
    else:
        lines.append("- indexes/page_to_sources.json")
    lines.append("")
    return "\n".join(lines)


def _render_entity_topic_page(
    op: dict[str, Any],
    today: date,
    known_pages: set[str],
) -> str:
    page_type = str(op.get("page_type"))
    source_ids = [source_id for source_id in op.get("source_ids", []) if source_id]
    related_claims = _valid_related_claims(op.get("related_claims"), known_pages)
    lines = [
        "---",
        f"wiki_type: {page_type}",
        f"generated_by: {GENERATED_BY}",
        "review_status: auto",
        f"source_count: {len(set(source_ids))}",
        f"updated_at: {today.isoformat()}",
        "---",
        "",
        f"# {op['title']}",
        "",
        _strip_source_ids(_one_line(op.get("summary"))) or "LLM-maintained wiki page grounded in enriched cards.",
        "",
        "## Связанные утверждения",
        "",
    ]
    if related_claims:
        lines.extend(f"- {claim}" for claim in related_claims)
    else:
        lines.append("- нет")

    lines.extend(["", "## Как найти источники", ""])
    lines.append("- Первичные источники открываются через доказательства в claim pages и output/wiki/indexes/page_to_sources.json.")
    lines.append("")
    return "\n".join(lines)


def _card_prompt_payload(item: EnrichedCard) -> dict[str, Any]:
    card = item.card
    return {
        "source_id": item.source.source_id,
        "content_hash": item.source.content_hash,
        "card_path": item.source.card_path,
        "post_url": item.source.post_url,
        "date": item.source.date,
        "summary": card.get("summary"),
        "key_facts": card.get("key_facts"),
        "entities": card.get("entities"),
        "topics": card.get("topics"),
        "quotes": card.get("quotes"),
        "events": card.get("events"),
        "provenance": card.get("provenance"),
    }


def _operation_source_ids(op: dict[str, Any]) -> list[str]:
    source_ids = set(_string_list(op.get("source_ids")))
    for item in op.get("evidence") or []:
        if isinstance(item, dict):
            source_id = _clean_str(item.get("source_id"))
            if source_id:
                source_ids.add(source_id)
    return sorted(source_ids)


def _normalize_claim_evidence(value: Any, allowed_sources: set[str]) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        source_id = _clean_str(item.get("source_id"))
        evidence_type = _normalize_evidence_type(item.get("evidence_type"))
        text = _one_line(item.get("text"))
        if (
            not source_id
            or source_id not in allowed_sources
            or evidence_type not in DIRECT_EVIDENCE_TYPES
            or not text
        ):
            continue
        normalized.append({"source_id": source_id, "evidence_type": evidence_type, "text": text})
    return normalized


def _normalize_evidence_type(value: object) -> str:
    text = _clean_str(value).casefold().replace("-", "_").replace(" ", "_")
    if not text:
        return "source_claim"
    return EVIDENCE_TYPE_ALIASES.get(text, text)


def _known_wiki_pages(wiki_dir: Path, operations: list[dict[str, Any]]) -> set[str]:
    pages = {path.relative_to(wiki_dir).as_posix() for path in wiki_index.iter_wiki_pages(wiki_dir)}
    for op in operations:
        page_type = str(op.get("page_type") or "")
        slug = _clean_str(op.get("slug"))
        if page_type in PAGE_TYPES and slug:
            pages.add(f"{_page_directory(page_type)}/{slug}.md")
    return pages


def _valid_related_claims(value: Any, known_pages: set[str]) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for item in _string_list(value):
        ref = _claim_ref_from_text(item)
        if not ref or ref not in known_pages or ref in seen:
            continue
        refs.append(ref)
        seen.add(ref)
    return refs


def _claim_ref_from_text(value: object) -> str:
    text = _clean_str(value).replace("\\", "/")
    match = re.search(r"\bclaims/[\w.-]+\.md\b", text, flags=re.UNICODE)
    return match.group(0) if match else ""


def _strip_source_ids(text: str) -> str:
    text = re.sub(r"\s*\(\s*telegram:[^)]+\)", "", text)
    text = re.sub(r"\btelegram:[^\s\]\),;]+?:[^\s\r\n\]\),.;]+", "", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def _pending_for_batch(reason: str, batch: list[EnrichedCard], message: str) -> list[WikiIngestPending]:
    return [
        WikiIngestPending(
            reason=reason,
            source_id=card.source.source_id or "",
            content_hash=card.source.content_hash,
            card_path=card.source.card_path,
            post_url=card.source.post_url,
            normalized_file=card.source.normalized_file,
            date=card.source.date,
            message=message,
        )
        for card in batch
    ]


def _load_source_hashes(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    hashes: dict[str, str] = {}
    if not isinstance(data, dict):
        return hashes
    for source_id, value in data.items():
        if isinstance(value, str):
            hashes[str(source_id)] = value
        elif isinstance(value, dict) and value.get("content_hash"):
            hashes[str(source_id)] = str(value["content_hash"])
    return hashes


def _current_source_hash_records(enriched_dir: Path) -> dict[str, dict[str, str]]:
    records: dict[str, dict[str, str]] = {}
    for source in wiki_index.collect_enriched_sources(enriched_dir):
        if not source.source_id:
            continue
        records[source.source_id] = {
            "source_id": source.source_id,
            "content_hash": source.content_hash,
            "card_path": source.card_path,
            "post_url": source.post_url,
            "normalized_file": source.normalized_file,
            "date": source.date,
        }
    return dict(sorted(records.items()))


def _write_source_hashes(path: Path, records: dict[str, dict[str, str]]) -> None:
    _write_json(path, records)


def _write_pending_updates(path: Path, pending: list[WikiIngestPending]) -> None:
    _write_json(path, [asdict(item) for item in pending])


def _append_log(stats: WikiIngestStats) -> None:
    stats.log_path.parent.mkdir(parents=True, exist_ok=True)
    if not stats.log_path.exists():
        stats.log_path.write_text("# Wiki Operation Log\n\n", encoding="utf-8")
    event = {
        "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "event": "wiki_ingest",
        "cards_seen": stats.cards_seen,
        "cards_processed": stats.cards_processed,
        "pages_created": [path.as_posix() for path in stats.pages_created],
        "pages_updated": [path.as_posix() for path in stats.pages_updated],
        "pending_updates": len(stats.pending),
    }
    header = (
        f"## [{event['timestamp'][:10]}] {event['event']} | "
        f"processed={event['cards_processed']} created={len(stats.pages_created)} "
        f"updated={len(stats.pages_updated)} pending={len(stats.pending)}"
    )
    with stats.log_path.open("a", encoding="utf-8") as handle:
        handle.write(header + "\n")
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def _existing_page_summaries(wiki_dir: Path) -> list[dict[str, str]]:
    summaries = []
    for path in wiki_index.iter_wiki_pages(wiki_dir):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        rel_path = path.relative_to(wiki_dir).as_posix()
        summaries.append({"page_path": rel_path, "title": _page_title(text, rel_path)})
    return summaries


def _relevant_existing_pages(batch: list[EnrichedCard], wiki_dir: Path, limit: int = 5) -> list[dict[str, str]]:
    batch_terms = set()
    for item in batch:
        batch_terms.update(_card_terms(item.card))
    if not batch_terms:
        return []

    matches: list[tuple[int, dict[str, str]]] = []
    for path in wiki_index.iter_wiki_pages(wiki_dir):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        text_terms = {token.casefold() for token in re.findall(r"[\w-]{3,}", text)}
        score = len(batch_terms & text_terms)
        if score <= 0:
            continue
        rel_path = path.relative_to(wiki_dir).as_posix()
        matches.append(
            (
                score,
                {
                    "page_path": rel_path,
                    "title": _page_title(text, rel_path),
                    "excerpt": _truncate(" ".join(text.split()), 1000),
                },
            )
        )
    matches.sort(key=lambda item: (-item[0], item[1]["page_path"]))
    return [item[1] for item in matches[:limit]]


def _card_terms(card: dict[str, Any]) -> set[str]:
    terms = set()
    for value in _flatten_entities(card.get("entities")) + _string_list(card.get("topics")):
        terms.update(token.casefold() for token in re.findall(r"[\w-]{3,}", value))
    return terms


def _flatten_entities(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    items: list[str] = []
    for group in value.values():
        if isinstance(group, list):
            items.extend(str(item) for item in group if str(item).strip())
        elif str(group).strip():
            items.append(str(group))
    return items


def _page_directory(page_type: str) -> str:
    if page_type == "claim":
        return "claims"
    if page_type == "entity":
        return "entities"
    return "topics"


def _page_title(text: str, rel_path: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return Path(rel_path).stem.replace("-", " ")


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _count_enriched_cards(enriched_dir: Path) -> int:
    if not enriched_dir.exists():
        return 0
    return sum(1 for _ in enriched_dir.rglob("*.enriched.json"))


def _slugify(value: object) -> str:
    text = _clean_str(value).casefold()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text, flags=re.UNICODE).strip("-")
    return text[:120]


def _has_cyrillic(value: object) -> bool:
    return bool(re.search(r"[а-яё]", _clean_str(value), flags=re.IGNORECASE))


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_clean_str(item) for item in value if _clean_str(item)]
    text = _clean_str(value)
    return [text] if text else []


def _one_line(value: object) -> str:
    return " ".join(str(value).split()) if value is not None else ""


def _clean_str(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _truncate(text: str, max_chars: int) -> str:
    return text if len(text) <= max_chars else text[: max_chars - 3].rstrip() + "..."
