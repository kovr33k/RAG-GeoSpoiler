"""
Enricher Pipeline — orchestrates the conversion of normalized posts into enriched memory cards.

Scans output/normalized/ for .txt + .meta.json pairs, checks enrichment state,
and produces enriched JSON cards in output/enriched/.

Uses LLM to extract: summary, key_facts, entities, topics, theses, quotes,
events, query_aliases, and visual assessment. Long-form content is chunked
and merged. Dedup runs after all cards are created.
"""

import concurrent.futures
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import config
from enricher.chunker import chunk_text, needs_chunking
from enricher.content_classifier import classify_content
from enricher.dedup import mark_duplicates
from enricher.graph_text_builder import populate_graph_texts
from enricher.llm_enricher import (
    enrich_chunk,
    enrich_full_post,
    enrich_short_post,
    merge_chunk_results,
)
from enricher.triage import TRIAGE_KEEP, TRIAGE_REVIEW, auto_triage
from normalizer.review_queue import (
    REVIEW_TYPE_UNINFORMATIVE,
)
from normalizer.review_queue import (
    queue_item as queue_review_item,
)

logger = logging.getLogger("geospoiler.enricher")

# Header regex
_HEADER_RE = re.compile(r"^\[Канал:.*\]\s*$")

# Noise patterns — donation links, social media CTAs, disclaimers
_NOISE_PATTERNS = [
    (re.compile(r"(?:подписывайтесь|подписка|subscribe|подпишитесь).*(?:канал|channel|patreon|youtube)", re.IGNORECASE), "subscription_cta"),
    (re.compile(r"(?:patreon\.com|buymeacoffee\.com|ko-fi\.com|donationalerts)", re.IGNORECASE), "donation_link"),
    (re.compile(r"(?:QR-код|qr.code)", re.IGNORECASE), "qr_code_reference"),
    (re.compile(r"ссылки?\s+(?:на\s+)?(?:платные|в описании|внизу|ниже)", re.IGNORECASE), "paid_links_cta"),
]

# Short post threshold — posts below this body length get minimal LLM processing
_SHORT_POST_THRESHOLD = 500


@dataclass
class EnrichmentStats:
    """Aggregated stats from an enrichment run."""

    scanned: int = 0
    enriched: int = 0
    partial: int = 0  # LLM returned empty for a keep post
    skipped_up_to_date: int = 0
    skipped_no_meta: int = 0
    failed: int = 0
    duplicates_marked: int = 0
    partial_posts: list = field(default_factory=list)  # names of partial posts
    by_content_type: dict = field(default_factory=dict)
    by_triage: dict = field(default_factory=dict)


def enrich_all(
    channel_filter: str | None = None,
    force: bool = False,
) -> EnrichmentStats:
    """
    Scan normalized directory and create/update enriched memory cards.

    Args:
        channel_filter: If set, only process this channel subdirectory.
        force: If True, re-enrich all posts regardless of state.

    Returns:
        EnrichmentStats with counts of what happened.
    """
    stats = EnrichmentStats()
    progress = _load_progress()
    jobs = _collect_enrichment_jobs(
        progress=progress,
        channel_filter=channel_filter,
        force=force,
        stats=stats,
    )

    _run_enrichment_jobs(jobs, progress, stats)

    # Save progress
    _save_progress(progress)

    # Run dedup across all enriched cards
    if stats.enriched > 0:
        logger.info("Running dedup check...")
        stats.duplicates_marked = mark_duplicates()
        if stats.duplicates_marked:
            logger.info(f"  Marked {stats.duplicates_marked} duplicate(s)")

    logger.info(
        f"Enrichment complete: {stats.enriched} enriched, "
        f"{stats.skipped_up_to_date} up-to-date, "
        f"{stats.failed} failed out of {stats.scanned} scanned"
    )
    return stats


@dataclass(frozen=True)
class _EnrichmentJob:
    txt_path: Path
    meta_path: Path
    channel_name: str
    msg_id: str
    progress_key: str
    normalized_mtime: float
    out_path: Path


def _collect_enrichment_jobs(
    *,
    progress: dict,
    channel_filter: str | None,
    force: bool,
    stats: EnrichmentStats,
) -> list[_EnrichmentJob]:
    normalized_dir = config.NORMALIZED_DIR
    enriched_dir = config.ENRICHED_DIR

    if channel_filter:
        channel_dirs = [normalized_dir / channel_filter]
        if not channel_dirs[0].exists():
            logger.error(f"Channel directory not found: {channel_dirs[0]}")
            return []
    else:
        channel_dirs = sorted(d for d in normalized_dir.iterdir() if d.is_dir())

    jobs: list[_EnrichmentJob] = []
    for channel_dir in channel_dirs:
        channel_name = channel_dir.name
        txt_files = sorted(channel_dir.glob("*.txt"))

        for txt_path in txt_files:
            stats.scanned += 1
            msg_id = txt_path.stem
            meta_path = txt_path.with_suffix(".meta.json")
            progress_key = f"{channel_name}/{msg_id}"

            if not meta_path.exists():
                logger.warning(f"No meta.json for {progress_key} ? skipping")
                stats.skipped_no_meta += 1
                continue

            normalized_mtime = txt_path.stat().st_mtime
            out_path = enriched_dir / channel_name / f"{msg_id}.enriched.json"
            if (
                not force
                and not _needs_enrichment(progress, progress_key, normalized_mtime)
                and not _is_existing_partial_card(out_path, txt_path)
            ):
                stats.skipped_up_to_date += 1
                continue

            jobs.append(
                _EnrichmentJob(
                    txt_path=txt_path,
                    meta_path=meta_path,
                    channel_name=channel_name,
                    msg_id=msg_id,
                    progress_key=progress_key,
                    normalized_mtime=normalized_mtime,
                    out_path=out_path,
                )
            )

    return jobs


def _run_enrichment_jobs(
    jobs: list[_EnrichmentJob],
    progress: dict,
    stats: EnrichmentStats,
) -> None:
    if not jobs:
        return

    concurrency = min(_enrichment_concurrency(), len(jobs))
    if concurrency <= 1:
        for job in jobs:
            try:
                card = _run_enrichment_job(job)
                _handle_enriched_card(job, card, progress, stats)
            except Exception as exc:
                _record_enrichment_failure(job, exc, stats)
        return

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_to_job = {executor.submit(_run_enrichment_job, job): job for job in jobs}
        for future in concurrent.futures.as_completed(future_to_job):
            job = future_to_job[future]
            try:
                card = future.result()
                _handle_enriched_card(job, card, progress, stats)
            except Exception as exc:
                _record_enrichment_failure(job, exc, stats)


def _run_enrichment_job(job: _EnrichmentJob) -> dict:
    return _enrich_single_post(
        txt_path=job.txt_path,
        meta_path=job.meta_path,
        channel_name=job.channel_name,
        msg_id=job.msg_id,
    )


def _handle_enriched_card(
    job: _EnrichmentJob,
    card: dict,
    progress: dict,
    stats: EnrichmentStats,
) -> None:
    is_partial = (
        card.get("triage") == TRIAGE_KEEP
        and not card.get("summary")
        and len(_strip_header(job.txt_path.read_text(encoding="utf-8")).strip()) >= 20
    )

    ct = card.get("content_type", "unknown")
    tr = card.get("triage", "unknown")

    if tr == TRIAGE_REVIEW:
        _queue_uninformative_review(
            card=card,
            txt_path=job.txt_path,
            channel_name=job.channel_name,
            msg_id=job.msg_id,
        )

    if is_partial:
        stats.partial += 1
        stats.partial_posts.append(job.progress_key)
        logger.warning(
            f"  Partial: {job.progress_key} -> {ct} / {tr} "
            "(LLM returned empty result, will retry)"
        )
    else:
        out_dir = job.out_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        job.out_path.write_text(
            json.dumps(card, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        progress["enriched"][job.progress_key] = {
            "enriched_at": datetime.now(UTC).isoformat(),
            "normalized_mtime": job.normalized_mtime,
            "version": config.ENRICHMENT_SCHEMA_VERSION,
        }
        stats.enriched += 1
        logger.info(f"  Enriched: {job.progress_key} -> {ct} / {tr}")

    stats.by_content_type[ct] = stats.by_content_type.get(ct, 0) + 1
    stats.by_triage[tr] = stats.by_triage.get(tr, 0) + 1


def _record_enrichment_failure(
    job: _EnrichmentJob,
    exc: Exception,
    stats: EnrichmentStats,
) -> None:
    stats.failed += 1
    logger.error(
        f"  Failed to enrich {job.progress_key}: {exc}",
        exc_info=True,
    )


def _enrichment_concurrency() -> int:
    try:
        return max(1, int(config.ENRICHMENT_CONCURRENCY))
    except (TypeError, ValueError):
        return 1

def _enrich_single_post(
    txt_path: Path,
    meta_path: Path,
    channel_name: str,
    msg_id: str,
) -> dict:
    """
    Create an enriched memory card for a single normalized post.

    Flow:
    1. Classify content type
    2. Auto-triage
    3. If triage != keep → skeleton card (no LLM)
    4. If short text → short LLM extraction
    5. If long text → chunk + per-chunk LLM + merge
    6. If regular → full LLM extraction
    7. Extract noise patterns
    """
    normalized_text = txt_path.read_text(encoding="utf-8")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    # Classify content type
    content_type = classify_content(meta, normalized_text)

    # Auto-triage
    triage_status, triage_reason = auto_triage(content_type, meta, normalized_text)

    # Build provenance
    provenance = {
        "channel_name": meta.get("channel_name", channel_name),
        "channel_id": meta.get("channel_id"),
        "message_id": meta.get("message_id", int(msg_id) if msg_id.isdigit() else msg_id),
        "date": meta.get("date"),
        "post_url": meta.get("post_url", ""),
        "normalized_file": str(txt_path.relative_to(config.PROJECT_ROOT)),
        "meta_file": str(meta_path.relative_to(config.PROJECT_ROOT)),
        "is_forward": meta.get("is_forward", False),
        "forward_from": meta.get("forward_from_name"),
    }

    # Detect language (default Russian for this pipeline)
    language = "ru"

    # ── LLM enrichment ──
    llm_data = {}
    chunks_data = []

    if triage_status == TRIAGE_KEEP:
        body = _strip_header(normalized_text)
        body_len = len(body.strip())

        if body_len < 20:
            # Too short even for minimal LLM
            pass
        elif body_len < _SHORT_POST_THRESHOLD:
            # Short post — minimal extraction
            llm_data = enrich_short_post(normalized_text, content_type)
        elif needs_chunking(normalized_text):
            # Long-form — chunk + merge
            header_line = _extract_header(normalized_text)
            text_chunks = chunk_text(normalized_text)
            chunk_results = []
            for chunk in text_chunks:
                cr = enrich_chunk(chunk["text"], chunk["index"], len(text_chunks))
                cr["char_range"] = chunk["char_range"]
                chunk_results.append(cr)

            llm_data = merge_chunk_results(header_line, chunk_results)
            chunks_data = [
                {
                    "index": i,
                    "summary": cr.get("summary", ""),
                    "key_facts": cr.get("key_facts", []),
                    "char_range": cr.get("char_range", []),
                }
                for i, cr in enumerate(chunk_results)
            ]
        else:
            # Regular post — full extraction
            llm_data = enrich_full_post(normalized_text, content_type)

    # ── Extract noise ──
    noise = _extract_noise(normalized_text)

    # ── Build card ──
    card = {
        "version": config.ENRICHMENT_SCHEMA_VERSION,
        "enriched_at": datetime.now(UTC).isoformat(),
        "provenance": provenance,
        "content_type": content_type,
        "triage": triage_status,
        "triage_reason": triage_reason,
        "language": language,

        # LLM-populated fields
        "summary": llm_data.get("summary", ""),
        "key_facts": llm_data.get("key_facts", []),
        "entities": llm_data.get("entities", {
            "people": [],
            "organizations": [],
            "countries": [],
            "locations": [],
            "military_units": [],
            "equipment": [],
        }),
        "topics": llm_data.get("topics", []),
        "theses": llm_data.get("theses", []),
        "quotes": llm_data.get("quotes", []),
        "events": llm_data.get("events", []),
        "query_aliases": llm_data.get("query_aliases", []),

        # Visual assessment
        "visual": {
            "has_images": meta.get("has_images", False),
            "has_video": meta.get("has_video", False) or bool(meta.get("youtube_urls")),
            "video_type": _detect_video_type(meta),
            "broll_potential": llm_data.get("broll_potential", "unknown"),
            "broll_notes": llm_data.get("broll_notes", ""),
            "image_descriptions": [],
        },

        # Source chain
        "source_chain": {
            "original_source": _detect_original_source(meta),
            "cited_sources": [],
            "youtube_url": (meta.get("youtube_urls") or [None])[0],
        },

        # Chunks for long content
        "chunks": chunks_data,

        # Noise
        "noise": noise,

        # Dedup (filled by mark_duplicates after all cards are created)
        "dedup": {
            "is_duplicate": False,
            "duplicate_group_id": None,
            "canonical_memory_id": None,
            "duplicate_reason": None,
        },

        # Graph/search texts
        "graph_text": "",
        "search_text": "",
    }

    # Populate graph_text and search_text from the card data
    populate_graph_texts(card)

    return card


def _detect_video_type(meta: dict) -> str | None:
    """Determine video type from metadata."""
    if meta.get("youtube_urls"):
        return "youtube"
    if meta.get("has_video"):
        return "telegram_native"
    return None


def _detect_original_source(meta: dict) -> str:
    """Determine original source attribution."""
    if meta.get("is_forward") and meta.get("forward_from_name"):
        return meta["forward_from_name"]
    return meta.get("channel_name", "unknown")


def _strip_header(text: str) -> str:
    """Remove the metadata header line from normalized text."""
    lines = text.split("\n")
    body_lines = [ln for ln in lines if not _HEADER_RE.match(ln.strip())]
    return "\n".join(body_lines).strip()


def _extract_header(text: str) -> str:
    """Extract the metadata header line."""
    for line in text.split("\n"):
        if _HEADER_RE.match(line.strip()):
            return line.strip()
    return ""


def _extract_noise(text: str) -> list[dict]:
    """Detect noise patterns (donation links, CTAs) in text."""
    noise = []
    for pattern, kind in _NOISE_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            noise.append({
                "kind": kind,
                "matched": matches[0] if len(matches) == 1 else matches[:3],
                "action": "exclude_from_graph",
            })
    return noise


def _queue_uninformative_review(
    card: dict,
    txt_path: Path,
    channel_name: str,
    msg_id: str,
) -> None:
    """Create a review queue item for a post flagged as uninformative by auto_triage."""
    provenance = card.get("provenance", {})
    triage_reason = card.get("triage_reason", "Uninformative post")

    # Read a preview of the normalized text for context
    try:
        message_text = txt_path.read_text(encoding="utf-8")[:500]
    except OSError:
        message_text = ""

    # Parse message_id as int if possible
    try:
        mid = int(msg_id)
    except ValueError:
        mid = 0

    # Parse date
    date_str = provenance.get("date")
    message_date = None
    if date_str:
        try:
            from datetime import datetime
            message_date = datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            pass

    queue_review_item(
        review_type=REVIEW_TYPE_UNINFORMATIVE,
        channel_name=channel_name,
        message_id=mid,
        message_text=message_text,
        message_date=message_date,
        reason=triage_reason,
        normalized_filepath=str(txt_path),
    )


def _card_has_extracted_content(card: dict) -> bool:
    if str(card.get("summary") or "").strip():
        return True

    for content_field in ("key_facts", "topics", "theses", "quotes", "events", "chunks"):
        if card.get(content_field):
            return True

    entities = card.get("entities", {})
    if isinstance(entities, dict):
        return any(bool(items) for items in entities.values())

    visual = card.get("visual", {})
    if isinstance(visual, dict) and str(visual.get("broll_notes") or "").strip():
        return True

    return False


def _is_existing_partial_card(card_path: Path, txt_path: Path) -> bool:
    if not card_path.exists():
        return False

    try:
        card = json.loads(card_path.read_text(encoding="utf-8"))
        if card.get("triage") != TRIAGE_KEEP:
            return False
        if _card_has_extracted_content(card):
            return False

        body = _strip_header(txt_path.read_text(encoding="utf-8")).strip()
        if len(body) >= 20:
            logger.warning(
                f"  Partial enriched card will be retried: {card_path.parent.name}/{card_path.stem}"
            )
            return True
    except Exception as e:
        logger.warning(f"Cannot inspect enriched card {card_path}: {e}")

    return False


# ── Progress tracking ──────────────────────────────────────────────────────

_PROGRESS_FILE = config.STATE_DIR / "enrichment_progress.json"


def _load_progress() -> dict:
    """Load enrichment progress state."""
    if _PROGRESS_FILE.exists():
        try:
            return json.loads(_PROGRESS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load enrichment progress: {e}")
    return {"last_run": None, "enriched": {}}


def _save_progress(progress: dict) -> None:
    """Save enrichment progress state."""
    progress["last_run"] = datetime.now(UTC).isoformat()
    _PROGRESS_FILE.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _needs_enrichment(
    progress: dict,
    key: str,
    normalized_mtime: float,
) -> bool:
    """Check if a post needs (re-)enrichment."""
    prev = progress.get("enriched", {}).get(key)
    if prev is None:
        return True  # Never enriched
    if prev.get("normalized_mtime", 0) < normalized_mtime:
        return True  # Normalized file was updated
    if prev.get("version", 0) < config.ENRICHMENT_SCHEMA_VERSION:
        return True  # Schema/prompt version bumped
    return False
