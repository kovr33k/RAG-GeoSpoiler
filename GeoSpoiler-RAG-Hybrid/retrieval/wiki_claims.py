"""
Seed a small, source-grounded claim ledger without LLM calls.

The first claim pages are intentionally rule-based. Evidence comes only from
triage=keep enriched cards and only from key_facts[source_claim] or quotes.
Summaries, theses, and hypotheses are not promoted into evidence here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

import config
from retrieval import wiki_index


CLAIM_STATUSES = {
    "supported_by_corpus",
    "contradicted_by_corpus",
    "disputed_in_corpus",
    "unclear_in_corpus",
}
GENERATED_BY = "wiki_claim_seed_v1"
MAX_EVIDENCE_PER_CLAIM = 10


@dataclass(frozen=True)
class ClaimSpec:
    slug: str
    title: str
    status: str
    match_groups: tuple[tuple[str, ...], ...]
    guardrails: tuple[str, ...] = ()


@dataclass(frozen=True)
class ClaimEvidence:
    source_id: str
    evidence_type: str
    text: str
    post_url: str
    card_path: str
    content_hash: str
    date: str


@dataclass(frozen=True)
class ClaimSeedStats:
    created: list[Path]
    existing: list[Path]
    skipped: list[str]


_RU = {
    "ai_video": "\u0438\u0438-\u0432\u0438\u0434\u0435\u043e",
    "defeat": "\u043f\u043e\u0431\u0435\u0434",
    "disinfo": "\u0434\u0435\u0437\u0438\u043d\u0444\u043e\u0440\u043c\u0430\u0446",
    "energy": "\u044d\u043d\u0435\u0440\u0433",
    "fake": "\u0444\u0435\u0439\u043a",
    "gas": "\u0433\u0430\u0437",
    "help": "\u043f\u043e\u043c\u043e\u0447",
    "hungary": "\u0432\u0435\u043d\u0433\u0440",
    "jd": "\u0434\u0436\u0435\u0439 \u0434\u0438",
    "kremlin": "\u043a\u0440\u0435\u043c\u043b",
    "lavrov": "\u043b\u0430\u0432\u0440\u043e\u0432",
    "magyar": "\u043c\u0430\u0434\u044f\u0440",
    "magyar_soft": "\u043c\u0430\u0434\u044c\u044f\u0440",
    "moscow": "\u043c\u043e\u0441\u043a\u0432",
    "oil": "\u043d\u0435\u0444\u0442",
    "orban": "\u043e\u0440\u0431\u0430\u043d",
    "poll": "\u043e\u043f\u0440\u043e\u0441",
    "russia": "\u0440\u043e\u0441\u0441\u0438",
    "sanctions": "\u0441\u0430\u043d\u043a\u0446",
    "support": "\u043f\u043e\u0434\u0434\u0435\u0440\u0436",
    "tisza": "\u0442\u0438\u0441\u0430",
    "trump": "\u0442\u0440\u0430\u043c\u043f",
    "trump_jr": "\u0442\u0440\u0430\u043c\u043f-\u043c\u043b\u0430\u0434",
    "vance": "\u0432\u0435\u043d\u0441",
    "vance_alt": "\u0432\u044d\u043d\u0441",
}


DEFAULT_CLAIM_SPECS: tuple[ClaimSpec, ...] = (
    ClaimSpec(
        slug="trump-supported-orban-2026",
        title="Trump supported Orban before the 2026 Hungarian election",
        status="supported_by_corpus",
        match_groups=(
            (_RU["trump"], "trump"),
            (_RU["orban"], "orban"),
            (_RU["support"], "support", _RU["help"], "help"),
        ),
        guardrails=(
            "Do not describe this support claim as fake unless a cited source explicitly says it is fake.",
            "Keep Trump support claims separate from fake/deepfake election-manipulation claims.",
        ),
    ),
    ClaimSpec(
        slug="trump-jr-supported-orban",
        title="Trump Jr. supported Orban",
        status="supported_by_corpus",
        match_groups=(
            (_RU["trump_jr"], "trump jr", "donald trump jr"),
            (_RU["orban"], "orban"),
            (_RU["support"], "support", _RU["help"], "help"),
        ),
        guardrails=(
            "Do not merge Donald Trump Jr. evidence into Donald Trump evidence without saying who spoke.",
        ),
    ),
    ClaimSpec(
        slug="vance-supported-orban",
        title="Vance supported Orban",
        status="supported_by_corpus",
        match_groups=(
            (_RU["vance"], _RU["vance_alt"], _RU["jd"], "vance"),
            (_RU["orban"], "orban"),
            (_RU["support"], "support", _RU["help"], "help"),
        ),
        guardrails=(
            "Preserve whether the evidence says direct electoral support or broader political support.",
        ),
    ),
    ClaimSpec(
        slug="orban-russia-energy-sanctions",
        title="Orban, Russia, energy, and sanctions",
        status="supported_by_corpus",
        match_groups=(
            (_RU["orban"], "orban", _RU["hungary"], "hungary"),
            (_RU["russia"], "russia", _RU["lavrov"]),
            (_RU["energy"], "energy", _RU["sanctions"], _RU["oil"], _RU["gas"], _RU["lavrov"]),
        ),
        guardrails=(
            "Separate energy dependence, sanctions policy, and Russia-contact evidence when answering.",
        ),
    ),
    ClaimSpec(
        slug="tisza-defeated-orban",
        title="TISZA and Magyar challenged or defeated Orban",
        status="supported_by_corpus",
        match_groups=(
            (_RU["tisza"], "tisza", _RU["magyar"], _RU["magyar_soft"], "magyar"),
            (_RU["orban"], "orban", "fidesz"),
            (_RU["defeat"], "defeat", _RU["poll"], "election"),
        ),
        guardrails=(
            "Distinguish polling leads from confirmed election results.",
        ),
    ),
    ClaimSpec(
        slug="russia-hungary-relations",
        title="Russia-Hungary relations and influence claims",
        status="supported_by_corpus",
        match_groups=(
            (_RU["russia"], "russia", _RU["moscow"], _RU["kremlin"]),
            (_RU["hungary"], "hungary", _RU["orban"], "orban"),
        ),
        guardrails=(
            "Separate documented source claims from broad interpretations about influence.",
        ),
    ),
    ClaimSpec(
        slug="fake-deepfake-separation",
        title="Fake and deepfake claims must stay separate from real support claims",
        status="supported_by_corpus",
        match_groups=(
            (_RU["fake"], "fake", "deepfake", _RU["ai_video"], _RU["disinfo"]),
            (_RU["hungary"], "hungary", _RU["orban"], "orban", "gurzo"),
        ),
        guardrails=(
            "Do not let fake/deepfake evidence cancel separate source claims of political support.",
            "Only call a specific support claim fake if the evidence explicitly identifies that claim as fake.",
        ),
    ),
)


def seed_claim_pages(
    wiki_dir: Path = config.WIKI_DIR,
    enriched_dir: Path = config.ENRICHED_DIR,
    specs: Iterable[ClaimSpec] = DEFAULT_CLAIM_SPECS,
    today: date | None = None,
) -> ClaimSeedStats:
    """Create missing seed claim pages from source-grounded enriched evidence."""
    today = today or date.today()
    claims_dir = wiki_dir / "claims"
    claims_dir.mkdir(parents=True, exist_ok=True)

    created: list[Path] = []
    existing: list[Path] = []
    skipped: list[str] = []

    cards = list(wiki_index.iter_enriched_cards(enriched_dir))
    for spec in specs:
        _validate_spec(spec)
        page_path = claims_dir / f"{spec.slug}.md"
        if page_path.exists():
            existing.append(page_path)
            continue

        evidence = collect_claim_evidence(spec, cards)
        if not evidence:
            skipped.append(spec.slug)
            continue

        page_path.write_text(render_claim_page(spec, evidence, today), encoding="utf-8")
        created.append(page_path)

    return ClaimSeedStats(created=created, existing=existing, skipped=skipped)


def collect_claim_evidence(
    spec: ClaimSpec,
    cards: Iterable[tuple[Path, dict]],
    max_items: int = MAX_EVIDENCE_PER_CLAIM,
) -> list[ClaimEvidence]:
    """Collect matching source_claim and quote evidence for one claim spec."""
    evidence: list[ClaimEvidence] = []
    seen: set[tuple[str, str, str]] = set()

    for card_path, card in cards:
        if card.get("triage") != "keep":
            continue
        source = wiki_index.get_enriched_source(card_path, card)
        if not source.source_id:
            continue

        for item in _iter_source_claim_items(card):
            if not _matches_spec(item, spec):
                continue
            key = (source.source_id, "source_claim", item)
            if key in seen:
                continue
            seen.add(key)
            evidence.append(_to_evidence(source, "source_claim", item))
            if len(evidence) >= max_items:
                return evidence

        for item in _iter_quote_items(card):
            if not _matches_spec(item, spec):
                continue
            key = (source.source_id, "quote", item)
            if key in seen:
                continue
            seen.add(key)
            evidence.append(_to_evidence(source, "quote", item))
            if len(evidence) >= max_items:
                return evidence

    return evidence


def render_claim_page(spec: ClaimSpec, evidence: list[ClaimEvidence], today: date) -> str:
    source_count = len({item.source_id for item in evidence})
    lines = [
        "---",
        "wiki_type: claim",
        f"status: {spec.status}",
        f"generated_by: {GENERATED_BY}",
        "review_status: auto",
        f"source_count: {source_count}",
        f"updated_at: {today.isoformat()}",
        "---",
        "",
        f"# {spec.title}",
        "",
        f"Status: {spec.status}",
        "Review status: auto",
        f"Source count: {source_count}",
        "",
        "## Evidence",
        "",
    ]

    for item in evidence:
        lines.append(f"- {item.source_id} - {item.evidence_type}: {item.text}")
        if item.post_url:
            lines.append(f"  - post_url: {item.post_url}")
        if item.date:
            lines.append(f"  - date: {item.date}")
        lines.append(f"  - card_path: {item.card_path}")
        lines.append(f"  - content_hash: {item.content_hash}")

    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- Treat Status as corpus status, not external fact-check status.",
            "- Use only cited evidence items when answering from this page.",
            "- Do not use summaries, theses, or hypotheses as direct evidence.",
            "- Separate source claims from author interpretation.",
        ]
    )
    for guardrail in spec.guardrails:
        lines.append(f"- {guardrail}")

    lines.extend(
        [
            "",
            "## Related",
            "",
            "- indexes/page_to_sources.json",
            "- indexes/source_to_pages.json",
            "",
        ]
    )
    return "\n".join(lines)


def _iter_source_claim_items(card: dict) -> Iterable[str]:
    for fact in card.get("key_facts", []) or []:
        if not isinstance(fact, dict):
            continue
        if fact.get("claim_type") != "source_claim":
            continue
        text = _one_line(fact.get("text"))
        if text:
            yield text


def _iter_quote_items(card: dict) -> Iterable[str]:
    for quote in card.get("quotes", []) or []:
        if not isinstance(quote, dict):
            continue
        speaker = _one_line(quote.get("speaker"))
        text = _one_line(quote.get("text"))
        context = _one_line(quote.get("context"))
        if not text:
            continue
        if speaker and context:
            yield f"{speaker}: {text} ({context})"
        elif speaker:
            yield f"{speaker}: {text}"
        else:
            yield text


def _to_evidence(source: wiki_index.EnrichedSource, evidence_type: str, text: str) -> ClaimEvidence:
    return ClaimEvidence(
        source_id=source.source_id or "",
        evidence_type=evidence_type,
        text=text,
        post_url=source.post_url,
        card_path=source.card_path,
        content_hash=source.content_hash,
        date=source.date,
    )


def _matches_spec(text: str, spec: ClaimSpec) -> bool:
    text_lower = text.lower()
    return all(any(term.lower() in text_lower for term in group) for group in spec.match_groups)


def _validate_spec(spec: ClaimSpec) -> None:
    if spec.status not in CLAIM_STATUSES:
        raise ValueError(f"Unsupported claim status for {spec.slug}: {spec.status}")


def _one_line(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())
