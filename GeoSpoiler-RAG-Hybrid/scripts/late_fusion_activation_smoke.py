"""Live activation smoke for the active Late-Fusion runtime configuration."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402
from cli_runtime import _finalize_rag_safely  # noqa: E402
from loader.factory import create_rag  # noqa: E402
from loader.query import query_rag_result  # noqa: E402
from scripts.late_fusion_ab import _result_artifact, _valid_http_url  # noqa: E402

CASES = (
    (
        "SMOKE_ANSWER",
        "Что в базе говорится о сходстве ультралевых и ультраправых?",
        "answer",
    ),
    (
        "SMOKE_SOURCE",
        "Трамп реально поддерживал Орбана? Дай ссылки на конкретные материалы.",
        "source",
    ),
    (
        "SMOKE_YOUTUBE",
        "Что в длинном видео говорится о проекте «Восточный щит», роли Starlink и применимости российского боевого опыта против НАТО? Собери несколько разных тезисов и дай таймкоды.",
        "source",
    ),
    ("SMOKE_LF10", "Кто финансирует AfD?", "answer"),
)
_CITATION_RE = re.compile(r"\[(S\d+)\]")


async def run_smoke(output_path: Path) -> dict[str, Any]:
    if not config.LATE_FUSION_ENABLED:
        raise RuntimeError("Active Late-Fusion flag is disabled")
    if config.RERANKER_ENABLED:
        raise RuntimeError("Reranker must remain disabled for this activation")

    rag = await create_rag()
    cases: list[dict[str, Any]] = []
    try:
        for case_id, question, profile in CASES:
            result = await query_rag_result(rag, question, mode="mix", query_profile=profile)
            artifact = _result_artifact(result)
            answer = artifact["answer"]
            references = artifact["references"]
            trace = artifact["late_fusion"]
            reference_ids = {str(item.get("reference_id") or "") for item in references}
            citations = set(_CITATION_RE.findall(answer))
            errors: list[str] = []
            if trace.get("pipeline") != "late_fusion":
                errors.append("pipeline_not_late_fusion")
            if artifact["fallback"]:
                errors.append("fallback_present")
            if not references:
                errors.append("references_empty")
            if not citations:
                errors.append("citations_empty")
            if citations - reference_ids:
                errors.append("unknown_citations")
            if any(not _valid_http_url(str(item.get("url") or "")) for item in references):
                errors.append("invalid_reference_url")
            if case_id == "SMOKE_YOUTUBE" and not any(item.get("start_url") for item in references):
                errors.append("youtube_start_url_missing")
            cases.append(
                {
                    "id": case_id,
                    "question": question,
                    "profile": profile,
                    "answer": answer,
                    "reference_count": len(references),
                    "citation_count": len(citations),
                    "youtube_start_url_count": sum(bool(item.get("start_url")) for item in references),
                    "pipeline": trace.get("pipeline"),
                    "fallback": artifact["fallback"],
                    "channel_statuses": trace.get("channel_statuses"),
                    "errors": errors,
                }
            )
    finally:
        await _finalize_rag_safely(rag)

    report = {
        "late_fusion_enabled": config.LATE_FUSION_ENABLED,
        "reranker_enabled": config.RERANKER_ENABLED,
        "wiki_enabled": config.WIKI_ENABLED,
        "cases": cases,
        "passed": all(not case["errors"] for case in cases),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = asyncio.run(run_smoke(args.output))
    for case in report["cases"]:
        print(
            f"{case['id']}: pipeline={case['pipeline']} refs={case['reference_count']} "
            f"citations={case['citation_count']} fallback={bool(case['fallback'])} errors={case['errors']}"
        )
    print(f"activation_smoke_passed={report['passed']}")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
