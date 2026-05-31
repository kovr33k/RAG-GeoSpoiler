"""Soft validation for local GeoSpoiler artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

import config
from models import ALLOWED_CLAIM_TYPES, EnrichedCard
from retrieval.wiki_index import compute_content_hash


@dataclass(frozen=True)
class ContractIssue:
    severity: str
    code: str
    path: str
    message: str
    field: str = ""


@dataclass
class EnrichedValidationReport:
    cards_seen: int = 0
    cards_valid: int = 0
    cards_invalid: int = 0
    errors: list[ContractIssue] = field(default_factory=list)
    warnings: list[ContractIssue] = field(default_factory=list)
    report_path: Path | None = None

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)


def validate_enriched_card(data: dict[str, Any], path: Path | str = "") -> tuple[EnrichedCard | None, list[ContractIssue]]:
    """Validate one enriched card and return non-fatal contract issues."""
    path_text = str(path)
    issues: list[ContractIssue] = []
    try:
        card = EnrichedCard.model_validate(data)
    except ValidationError as exc:
        for err in exc.errors():
            field = ".".join(str(part) for part in err.get("loc", ()))
            issues.append(
                ContractIssue(
                    severity="error",
                    code="schema_error",
                    path=path_text,
                    field=field,
                    message=str(err.get("msg", "validation error")),
                )
            )
        return None, issues

    if card.source_id is None:
        issues.append(
            ContractIssue(
                severity="warning",
                code="missing_source_id",
                path=path_text,
                field="provenance",
                message="Could not derive stable source_id from provenance.",
            )
        )

    if card.triage == "keep" and not card.summary.strip() and not card.key_facts:
        issues.append(
            ContractIssue(
                severity="warning",
                code="empty_evidence_summary",
                path=path_text,
                field="summary,key_facts",
                message="Kept card has neither summary nor key_facts.",
            )
        )

    for idx, fact in enumerate(card.key_facts):
        if fact.claim_type not in ALLOWED_CLAIM_TYPES:
            issues.append(
                ContractIssue(
                    severity="warning",
                    code="unknown_claim_type",
                    path=path_text,
                    field=f"key_facts.{idx}.claim_type",
                    message=(
                        f"Unknown claim_type '{fact.claim_type}'. "
                        f"Allowed: {', '.join(sorted(ALLOWED_CLAIM_TYPES))}."
                    ),
                )
            )

    return card, issues


def scan_enriched_cards(enriched_dir: Path = config.ENRICHED_DIR) -> EnrichedValidationReport:
    """Scan output/enriched without mutating cards or stopping on bad files."""
    report = EnrichedValidationReport()
    if not enriched_dir.exists():
        report.errors.append(
            ContractIssue(
                severity="error",
                code="missing_enriched_dir",
                path=str(enriched_dir),
                message="Enriched directory does not exist.",
            )
        )
        return report

    for path in sorted(enriched_dir.rglob("*.enriched.json")):
        report.cards_seen += 1
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            report.cards_invalid += 1
            report.errors.append(
                ContractIssue(
                    severity="error",
                    code="invalid_json",
                    path=str(path),
                    message=str(exc),
                )
            )
            continue
        except OSError as exc:
            report.cards_invalid += 1
            report.errors.append(
                ContractIssue(
                    severity="error",
                    code="read_error",
                    path=str(path),
                    message=str(exc),
                )
            )
            continue

        if not isinstance(data, dict):
            report.cards_invalid += 1
            report.errors.append(
                ContractIssue(
                    severity="error",
                    code="schema_error",
                    path=str(path),
                    message="Enriched card root must be a JSON object.",
                )
            )
            continue

        card, issues = validate_enriched_card(data, path)
        report.errors.extend(issue for issue in issues if issue.severity == "error")
        report.warnings.extend(issue for issue in issues if issue.severity != "error")
        if card is None or any(issue.severity == "error" for issue in issues):
            report.cards_invalid += 1
        else:
            report.cards_valid += 1

    return report


def write_enriched_validation_report(
    report: EnrichedValidationReport,
    output_path: Path | None = None,
) -> Path:
    """Write a compact Markdown validation report."""
    if output_path is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = config.PROJECT_ROOT / "artifacts" / f"enriched_validation_{stamp}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Enriched Card Validation Report",
        "",
        f"- generated_at: {datetime.now(timezone.utc).replace(microsecond=0).isoformat()}",
        f"- cards_seen: {report.cards_seen}",
        f"- cards_valid: {report.cards_valid}",
        f"- cards_invalid: {report.cards_invalid}",
        f"- errors: {report.error_count}",
        f"- warnings: {report.warning_count}",
        "",
    ]

    if report.errors:
        lines.extend(["## Errors", ""])
        lines.extend(_issue_lines(report.errors))
        lines.append("")

    if report.warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(_issue_lines(report.warnings))
        lines.append("")

    if not report.errors and not report.warnings:
        lines.extend(["No contract issues found.", ""])

    output_path.write_text("\n".join(lines), encoding="utf-8")
    report.report_path = output_path
    return output_path


def compute_card_content_hash(card: EnrichedCard) -> str:
    """Compute the existing wiki/source-registry content hash for a parsed card."""
    return compute_content_hash(card.model_dump(mode="json"))


def _issue_lines(issues: list[ContractIssue], limit: int = 100) -> list[str]:
    rows = []
    for issue in issues[:limit]:
        field = f" `{issue.field}`" if issue.field else ""
        rows.append(f"- `{issue.code}`{field}: {issue.path} - {issue.message}")
    if len(issues) > limit:
        rows.append(f"- ... {len(issues) - limit} more issue(s) omitted")
    return rows
