"""
Wiki-memory health checks.

The health pass is intentionally local and deterministic: it reads markdown
pages and JSON indexes, never calls LLMs, Telegram, LightRAG, or external APIs.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config
from retrieval import wiki_index


MAX_PAGE_CHARS = 40000
CLAIM_STATUSES = {
    "supported_by_corpus",
    "contradicted_by_corpus",
    "disputed_in_corpus",
    "unclear_in_corpus",
}
FAKE_LABEL_RE = re.compile(r"\b(fake|deepfake|false)\b|фейк|дипфейк|ложн", re.IGNORECASE)
SUMMARY_THESIS_RE = re.compile(r"\b(summary|thesis|theses)\b|summary|тезис|гипотез", re.IGNORECASE)
DIRECT_EVIDENCE_RE = re.compile(r"^\s*-\s+telegram:[^\s]+\s+-\s+(source_claim|quote):", re.MULTILINE)
CARD_PATH_RE = re.compile(r"^\s*-\s+card_path:\s*(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class WikiHealthIssue:
    severity: str
    code: str
    page_path: str
    message: str


@dataclass(frozen=True)
class WikiHealthReport:
    wiki_dir: Path
    checked_at: str
    page_count: int
    issue_count: int
    issues: list[WikiHealthIssue]

    @property
    def ok(self) -> bool:
        return self.issue_count == 0


def run_wiki_health(
    wiki_dir: Path = config.WIKI_DIR,
    index_dir: Path = config.WIKI_INDEX_DIR,
) -> WikiHealthReport:
    """Run health checks over wiki pages and indexes."""
    issues: list[WikiHealthIssue] = []
    page_paths = list(wiki_index.iter_wiki_pages(wiki_dir))
    page_to_sources = _load_json(index_dir / wiki_index.PAGE_INDEX_FILENAME)
    source_to_pages = _load_json(index_dir / wiki_index.SOURCE_INDEX_FILENAME)

    for path in page_paths:
        rel_path = path.relative_to(wiki_dir).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            issues.append(_issue("error", "page_unreadable", rel_path, str(exc)))
            continue

        if len(text) > MAX_PAGE_CHARS:
            issues.append(
                _issue(
                    "warning",
                    "page_too_large",
                    rel_path,
                    f"Page has {len(text)} chars; threshold is {MAX_PAGE_CHARS}.",
                )
            )

        if rel_path.startswith("claims/"):
            _check_claim_page(rel_path, text, page_to_sources, issues)

    _check_indexes(page_to_sources, source_to_pages, wiki_dir, issues)

    checked_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return WikiHealthReport(
        wiki_dir=wiki_dir,
        checked_at=checked_at,
        page_count=len(page_paths),
        issue_count=len(issues),
        issues=issues,
    )


def write_health_report(report: WikiHealthReport, path: Path | None = None) -> Path:
    """Write the markdown health report to output/wiki/_health.md."""
    path = path or (report.wiki_dir / "_health.md")
    path.write_text(format_health_report(report), encoding="utf-8")
    return path


def format_health_report(report: WikiHealthReport) -> str:
    lines = [
        "# Wiki Health",
        "",
        f"Checked at: {report.checked_at}",
        f"Pages checked: {report.page_count}",
        f"Issues: {report.issue_count}",
        "",
    ]

    if report.ok:
        lines.append("Status: OK")
        lines.append("")
        return "\n".join(lines)

    lines.append("## Issues")
    lines.append("")
    for issue in report.issues:
        lines.append(f"- [{issue.severity}] {issue.code} | {issue.page_path} | {issue.message}")
    lines.append("")
    return "\n".join(lines)


def _check_claim_page(
    rel_path: str,
    text: str,
    page_to_sources: dict[str, Any],
    issues: list[WikiHealthIssue],
) -> None:
    frontmatter = _parse_frontmatter(text)
    status = _claim_status(text, frontmatter)
    source_count = _int_or_none(frontmatter.get("source_count"))
    evidence = _section(text, "Evidence")
    direct_evidence = _evidence_items(evidence)
    sources = page_to_sources.get(rel_path, [])
    if not isinstance(sources, list):
        sources = []

    if not status:
        issues.append(_issue("error", "claim_missing_status", rel_path, "Claim has no status."))
    elif status not in CLAIM_STATUSES:
        issues.append(_issue("error", "claim_unknown_status", rel_path, f"Unsupported status: {status}"))

    if not sources:
        issues.append(_issue("error", "claim_without_sources", rel_path, "Claim resolves to no source ids."))

    if not evidence.strip() or not direct_evidence:
        issues.append(
            _issue("error", "claim_without_evidence", rel_path, "Claim has no source_claim or quote evidence.")
        )

    if evidence.strip() and not direct_evidence and SUMMARY_THESIS_RE.search(evidence):
        issues.append(
            _issue(
                "error",
                "claim_uses_only_summary_theses",
                rel_path,
                "Evidence appears to rely on summary/theses/hypothesis text.",
            )
        )

    if status == "supported_by_corpus" and (source_count is None or source_count < 1):
        issues.append(
            _issue(
                "error",
                "supported_claim_without_source_count",
                rel_path,
                "supported_by_corpus requires source_count >= 1.",
            )
        )

    for field in ["generated_by", "review_status", "source_count"]:
        if not str(frontmatter.get(field) or "").strip():
            issues.append(_issue("error", "missing_frontmatter", rel_path, f"Missing {field}."))

    claim_text = _without_section(text, "Guardrails")
    if FAKE_LABEL_RE.search(claim_text) and not FAKE_LABEL_RE.search(evidence):
        issues.append(
            _issue(
                "warning",
                "fake_label_without_direct_evidence",
                rel_path,
                "Fake/deepfake/false label appears outside direct evidence.",
            )
        )

    if "contradict" in rel_path or "contradicted" in text.lower():
        if status != "disputed_in_corpus" and status != "contradicted_by_corpus":
            issues.append(
                _issue(
                    "warning",
                    "possible_conflict_without_disputed_status",
                    rel_path,
                    "Page mentions contradiction but is not disputed/contradicted.",
                )
            )


def _check_indexes(
    page_to_sources: dict[str, Any],
    source_to_pages: dict[str, Any],
    wiki_dir: Path,
    issues: list[WikiHealthIssue],
) -> None:
    source_to_cards = _source_to_card_paths(wiki_dir)
    source_seen_on_claim_pages: dict[str, set[str]] = {}

    for source_id, pages in source_to_pages.items():
        if not isinstance(pages, list):
            issues.append(_issue("error", "bad_source_pages_index", str(source_id), "Pages value is not a list."))
            continue
        card_paths = source_to_cards.get(str(source_id), [])
        if not card_paths:
            issues.append(
                _issue(
                    "error",
                    "wiki_reference_unresolved",
                    str(source_id),
                    f"{source_id} has no card_path in claim evidence.",
                )
            )
            continue
        if not any(Path(card_path).exists() for card_path in card_paths):
            issues.append(
                _issue(
                    "error",
                    "source_file_missing",
                    str(source_id),
                    f"{source_id} card_path does not exist.",
                )
            )

    for page_path, sources in page_to_sources.items():
        if not isinstance(sources, list):
            issues.append(_issue("error", "bad_page_sources_index", str(page_path), "Sources value is not a list."))
            continue

        for source_id in sources:
            if source_id not in source_to_pages:
                issues.append(
                    _issue("error", "source_missing_reverse_index", str(page_path), f"{source_id} not in source_to_pages.")
                )
            source_seen_on_claim_pages.setdefault(str(source_id), set()).add(str(page_path))

    for source_id, pages in source_seen_on_claim_pages.items():
        statuses = {_claim_page_status(wiki_dir / page) for page in pages}
        if not ({"supported_by_corpus", "contradicted_by_corpus"} <= statuses):
            continue
        if "disputed_in_corpus" in statuses:
            continue
        issues.append(
            _issue(
                "warning",
                "same_source_in_contradictory_claims_without_disputed",
                str(source_id),
                f"{source_id} appears in supported and contradicted claims without disputed_in_corpus.",
            )
        )


def _source_to_card_paths(wiki_dir: Path) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for path in (wiki_dir / "claims").glob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        evidence = _section(text, "Evidence")
        for source_id, _evidence_type, card_paths in _evidence_items(evidence):
            mapping.setdefault(source_id, []).extend(card_paths)
    return mapping


def _evidence_items(evidence: str) -> list[tuple[str, str, list[str]]]:
    items: list[tuple[str, str, list[str]]] = []
    current_source_id = ""
    current_evidence_type = ""
    current_card_paths: list[str] = []

    def flush() -> None:
        if current_source_id:
            items.append((current_source_id, current_evidence_type, current_card_paths.copy()))

    for line in evidence.splitlines():
        evidence_type = _evidence_type_from_line(line)
        if evidence_type:
            flush()
            source_ids = wiki_index.extract_page_sources(line)
            current_source_id = source_ids[0] if source_ids else ""
            current_evidence_type = evidence_type
            current_card_paths = []
            continue

        if current_source_id:
            card_path = _card_path_from_line(line)
            if card_path:
                current_card_paths.append(card_path)

    flush()
    return items


def _evidence_type_from_line(line: str) -> str:
    if " - source_claim:" in line:
        return "source_claim"
    if " - quote:" in line:
        return "quote"
    return ""


def _card_path_from_line(line: str) -> str:
    match = CARD_PATH_RE.match(line)
    return match.group(1).strip() if match else ""


def _claim_page_status(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    return _claim_status(text, _parse_frontmatter(text))


def _claim_status(text: str, frontmatter: dict[str, str]) -> str:
    status = str(frontmatter.get("status") or "").strip()
    if status:
        return status
    match = re.search(r"^Status:\s*(\S+)\s*$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def _parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return {}
    data: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def _section(text: str, section_name: str) -> str:
    pattern = re.compile(rf"^##\s+{re.escape(section_name)}\s*$", flags=re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    rest = text[match.end() :]
    next_section = re.search(r"^##\s+", rest, flags=re.MULTILINE)
    return rest[: next_section.start()] if next_section else rest


def _without_section(text: str, section_name: str) -> str:
    pattern = re.compile(rf"^##\s+{re.escape(section_name)}\s*$", flags=re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return text
    before = text[: match.start()]
    rest = text[match.end() :]
    next_section = re.search(r"^##\s+", rest, flags=re.MULTILINE)
    after = rest[next_section.start() :] if next_section else ""
    return before + after


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _issue(severity: str, code: str, page_path: str, message: str) -> WikiHealthIssue:
    return WikiHealthIssue(severity=severity, code=code, page_path=page_path, message=message)
