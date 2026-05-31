"""
Seed minimal entity and topic wiki pages linked to existing claim pages.

These pages do not carry primary source evidence directly. They point to claim
pages, and claim pages resolve to source ids via page_to_sources/source_to_pages.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

import config


GENERATED_BY = "wiki_entity_topic_seed_v1"
AUTO_START = "<!-- WIKI_MASTER_INDEX_AUTO_START -->"
AUTO_END = "<!-- WIKI_MASTER_INDEX_AUTO_END -->"


@dataclass(frozen=True)
class WikiPageSpec:
    page_type: str
    slug: str
    title: str
    summary: str
    claims: tuple[str, ...]


@dataclass(frozen=True)
class EntityTopicSeedStats:
    created: list[Path]
    existing: list[Path]
    skipped: list[str]
    master_index_path: Path


ENTITY_SPECS: tuple[WikiPageSpec, ...] = (
    WikiPageSpec(
        page_type="entity",
        slug="viktor-orban",
        title="Viktor Orban",
        summary="Hungarian prime minister connected to the seeded Hungary election and Russia-Hungary claim pages.",
        claims=(
            "trump-supported-orban-2026",
            "trump-jr-supported-orban",
            "vance-supported-orban",
            "orban-russia-energy-sanctions",
            "tisza-defeated-orban",
            "russia-hungary-relations",
            "fake-deepfake-separation",
        ),
    ),
    WikiPageSpec(
        page_type="entity",
        slug="donald-trump",
        title="Donald Trump",
        summary="US political figure referenced in support claims involving Viktor Orban.",
        claims=("trump-supported-orban-2026", "vance-supported-orban"),
    ),
    WikiPageSpec(
        page_type="entity",
        slug="donald-trump-jr",
        title="Donald Trump Jr.",
        summary="Referenced separately from Donald Trump in the Orban support claim ledger.",
        claims=("trump-jr-supported-orban",),
    ),
    WikiPageSpec(
        page_type="entity",
        slug="jd-vance",
        title="JD Vance",
        summary="Referenced in source claims about support for Viktor Orban and Hungarian election messaging.",
        claims=("vance-supported-orban", "trump-supported-orban-2026"),
    ),
    WikiPageSpec(
        page_type="entity",
        slug="peter-magyar",
        title="Peter Magyar",
        summary="Opposition figure connected to TISZA and claims about challenging Orban.",
        claims=("tisza-defeated-orban", "fake-deepfake-separation"),
    ),
    WikiPageSpec(
        page_type="entity",
        slug="tisza",
        title="TISZA",
        summary="Hungarian opposition party/topic linked to claims about Orban, Magyar, and election competition.",
        claims=("tisza-defeated-orban", "fake-deepfake-separation"),
    ),
    WikiPageSpec(
        page_type="entity",
        slug="russia",
        title="Russia",
        summary="State actor linked to Hungary energy, sanctions, influence, and disinformation claims.",
        claims=("orban-russia-energy-sanctions", "russia-hungary-relations", "fake-deepfake-separation"),
    ),
    WikiPageSpec(
        page_type="entity",
        slug="hungary",
        title="Hungary",
        summary="Country context for the seeded Orban, TISZA, energy, Russia, and election claim pages.",
        claims=(
            "trump-supported-orban-2026",
            "trump-jr-supported-orban",
            "vance-supported-orban",
            "orban-russia-energy-sanctions",
            "tisza-defeated-orban",
            "russia-hungary-relations",
            "fake-deepfake-separation",
        ),
    ),
)


TOPIC_SPECS: tuple[WikiPageSpec, ...] = (
    WikiPageSpec(
        page_type="topic",
        slug="trump-orban-support",
        title="Trump-Orban Support",
        summary="Claims that Trump, Trump Jr., and Vance supported or signaled support for Viktor Orban.",
        claims=("trump-supported-orban-2026", "trump-jr-supported-orban", "vance-supported-orban"),
    ),
    WikiPageSpec(
        page_type="topic",
        slug="hungary-election-2026",
        title="Hungary Election 2026",
        summary="Election-related claim pages around Orban, TISZA, outside support, and disinformation.",
        claims=(
            "trump-supported-orban-2026",
            "trump-jr-supported-orban",
            "vance-supported-orban",
            "tisza-defeated-orban",
            "fake-deepfake-separation",
            "russia-hungary-relations",
        ),
    ),
    WikiPageSpec(
        page_type="topic",
        slug="russia-hungary-relations",
        title="Russia-Hungary Relations",
        summary="Claims about Russia-Hungary political contact, influence, energy, and sanctions.",
        claims=("russia-hungary-relations", "orban-russia-energy-sanctions"),
    ),
    WikiPageSpec(
        page_type="topic",
        slug="orban-russia-energy-sanctions",
        title="Orban, Russia, Energy, and Sanctions",
        summary="Corpus claims about sanctions, Russian energy dependence, and Hungarian policy.",
        claims=("orban-russia-energy-sanctions", "russia-hungary-relations"),
    ),
    WikiPageSpec(
        page_type="topic",
        slug="tisza-orban-election",
        title="TISZA and Orban Election Competition",
        summary="Claims about TISZA, Peter Magyar, and challenges to Viktor Orban.",
        claims=("tisza-defeated-orban", "fake-deepfake-separation"),
    ),
    WikiPageSpec(
        page_type="topic",
        slug="hungary-election-disinformation",
        title="Hungary Election Disinformation",
        summary="Claims about fake/deepfake separation and disinformation around Hungarian politics.",
        claims=("fake-deepfake-separation", "russia-hungary-relations"),
    ),
    WikiPageSpec(
        page_type="topic",
        slug="fake-deepfake-separation",
        title="Fake and Deepfake Separation",
        summary="Guardrail topic for keeping fake/deepfake evidence separate from real political support claims.",
        claims=("fake-deepfake-separation", "trump-supported-orban-2026", "vance-supported-orban"),
    ),
)


def seed_entity_topic_pages(
    wiki_dir: Path = config.WIKI_DIR,
    specs: Iterable[WikiPageSpec] = ENTITY_SPECS + TOPIC_SPECS,
    today: date | None = None,
) -> EntityTopicSeedStats:
    """Create missing entity/topic pages and update the generated master index block."""
    today = today or date.today()
    created: list[Path] = []
    existing: list[Path] = []
    skipped: list[str] = []

    for directory in [wiki_dir / "entities", wiki_dir / "topics"]:
        directory.mkdir(parents=True, exist_ok=True)

    for spec in specs:
        _validate_spec(spec)
        related_claims = _existing_claim_paths(wiki_dir, spec.claims)
        if not related_claims:
            skipped.append(spec.slug)
            continue

        page_path = _page_path(wiki_dir, spec)
        if page_path.exists():
            existing.append(page_path)
            continue

        page_path.write_text(render_entity_topic_page(spec, related_claims, today), encoding="utf-8")
        created.append(page_path)

    master_index_path = update_master_index(wiki_dir)
    return EntityTopicSeedStats(
        created=created,
        existing=existing,
        skipped=skipped,
        master_index_path=master_index_path,
    )


def render_entity_topic_page(spec: WikiPageSpec, related_claims: list[str], today: date) -> str:
    lines = [
        "---",
        f"wiki_type: {spec.page_type}",
        f"generated_by: {GENERATED_BY}",
        "review_status: auto",
        f"related_claim_count: {len(related_claims)}",
        f"updated_at: {today.isoformat()}",
        "---",
        "",
        f"# {spec.title}",
        "",
        spec.summary,
        "",
        "## Related Claims",
        "",
    ]
    lines.extend(f"- {claim}" for claim in related_claims)
    lines.extend(
        [
            "",
            "## Source Resolution",
            "",
            "- This page links to claim pages only.",
            "- Resolve primary sources through claim evidence and output/wiki/indexes/page_to_sources.json.",
            "",
        ]
    )
    return "\n".join(lines)


def update_master_index(wiki_dir: Path = config.WIKI_DIR) -> Path:
    """Refresh only the generated page-list block in _master_index.md."""
    master_index_path = wiki_dir / "_master_index.md"
    existing = master_index_path.read_text(encoding="utf-8") if master_index_path.exists() else "# Wiki Memory\n"
    generated = render_master_index_block(wiki_dir)

    if AUTO_START in existing and AUTO_END in existing:
        before = existing.split(AUTO_START, 1)[0].rstrip()
        after = existing.split(AUTO_END, 1)[1].lstrip()
        content = f"{before}\n\n{generated}\n\n{after}".rstrip() + "\n"
    else:
        content = existing.rstrip() + "\n\n" + generated + "\n"

    master_index_path.write_text(content, encoding="utf-8")
    return master_index_path


def render_master_index_block(wiki_dir: Path = config.WIKI_DIR) -> str:
    sections = [
        ("Claims", "claims"),
        ("Entities", "entities"),
        ("Topics", "topics"),
    ]
    lines = [AUTO_START, "## Generated Page Index", ""]
    for title, directory_name in sections:
        lines.extend([f"### {title}", ""])
        paths = sorted((wiki_dir / directory_name).glob("*.md"))
        if not paths:
            lines.append("- none")
        else:
            for path in paths:
                rel_path = path.relative_to(wiki_dir).as_posix()
                lines.append(f"- {rel_path}")
        lines.append("")
    lines.append(AUTO_END)
    return "\n".join(lines)


def _existing_claim_paths(wiki_dir: Path, claim_slugs: Iterable[str]) -> list[str]:
    claims = []
    for slug in claim_slugs:
        rel_path = f"claims/{slug}.md"
        if (wiki_dir / rel_path).exists():
            claims.append(rel_path)
    return claims


def _page_path(wiki_dir: Path, spec: WikiPageSpec) -> Path:
    directory = "entities" if spec.page_type == "entity" else "topics"
    return wiki_dir / directory / f"{spec.slug}.md"


def _validate_spec(spec: WikiPageSpec) -> None:
    if spec.page_type not in {"entity", "topic"}:
        raise ValueError(f"Unsupported wiki page type for {spec.slug}: {spec.page_type}")
