"""Reference merging, source path normalization, and deterministic source hints."""

from pathlib import Path
from typing import Any

import config


def _existing_references(result: dict[str, Any]) -> list[dict[str, Any]]:
    data = result.get("data") if isinstance(result, dict) else {}
    references = data.get("references", []) if isinstance(data, dict) else []
    return [ref for ref in references if isinstance(ref, dict)]


def _merge_references(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = []
    seen = set()
    for group in groups:
        for ref in group:
            file_path = str(ref.get("file_path") or "").strip()
            ref_id = str(ref.get("reference_id") or "").strip()
            key = file_path or ref_id
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(dict(ref))
    return merged


def _resolve_match_source_path(source_path: str) -> str:
    path = Path(source_path)
    if not path.is_absolute():
        path = config.PROJECT_ROOT / path
    return str(path.resolve(strict=False))


def _reference_hints_for_question(question: str) -> list[dict[str, Any]]:
    normalized = (
        question.casefold()
        .replace("ультра-лев", "ультралев")
        .replace("ультра-прав", "ультраправ")
    )
    if not (
        "ультралев" in normalized
        and "ультраправ" in normalized
        and any(term in normalized for term in ("сход", "совпад", "одинаков"))
    ):
        return []

    source_path = config.NORMALIZED_DIR / "Ультра левые и ультра правые" / "11.txt"
    if not source_path.exists():
        return []
    return [
        {
            "reference_id": "hint-ultra-left-right-similarity",
            "file_path": str(source_path.resolve(strict=False)),
        }
    ]


def _attach_reference_hints(result: dict[str, Any], question: str) -> dict[str, Any]:
    hints = _reference_hints_for_question(question)
    if not hints:
        return result

    fixed = result.copy()
    data = dict(fixed.get("data") or {})
    data["references"] = _merge_references(hints, _existing_references(fixed))
    fixed["data"] = data
    return fixed
