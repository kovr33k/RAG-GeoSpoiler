"""Run model bakeoff suites and write stable artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

import config
from eval.model_bakeoff.aggregate_report import write_reports
from eval.model_bakeoff.config_loader import ModelConfig, load_model_registry
from eval.model_bakeoff.scoring import score_political_risk, score_quality
from llm_auth import auth_headers

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODELS_PATH = Path(__file__).with_name("models.yaml")
DEFAULT_SUITES_DIR = Path(__file__).with_name("suites")
DEFAULT_PROMPTS_DIR = Path(__file__).with_name("prompts")
DEFAULT_ARTIFACT_ROOT = PROJECT_ROOT / "artifacts" / "model_bakeoff"

_TASK_PROMPTS = {
    "direct_qa": "direct_qa_system.txt",
    "source_preservation": "source_preservation_system.txt",
    "translation_fidelity": "translation_fidelity_system.txt",
    "enrichment_json": "enrichment_json_system.txt",
    "rag_build_extraction": "rag_build_extraction_system.txt",
    "rag_build_tuple_extraction": "rag_build_tuple_extraction_system.txt",
    "fixed_context_synthesis": "fixed_context_synthesis_system.txt",
    "fallback_synth": "fallback_synth_system.txt",
    "script_pack": "fixed_context_synthesis_system.txt",
}


def estimate_cost_usd(model: ModelConfig, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost from per-million token registry prices."""
    cost = (
        (max(0, input_tokens) * model.input_price_per_m)
        + (max(0, output_tokens) * model.output_price_per_m)
    ) / 1_000_000
    return round(cost, 8)


def build_output_record(
    *,
    run_id: str,
    model: ModelConfig,
    role: str,
    suite: str,
    case_id: str,
    prompt_text: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    raw_response: str,
    parsed_response: Any,
    errors: list[str],
    retries: int,
    cache_buster: str,
) -> dict[str, Any]:
    """Build the canonical per-model output record."""
    return {
        "run_id": run_id,
        "timestamp": _utc_now(),
        "model_id": model.id,
        "provider": model.provider,
        "role": role,
        "suite": suite,
        "case_id": case_id,
        "prompt_hash": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": latency_ms,
        "estimated_cost_usd": estimate_cost_usd(model, input_tokens, output_tokens),
        "raw_response": raw_response,
        "parsed_response": parsed_response,
        "errors": list(errors),
        "retries": retries,
        "cache_buster": cache_buster,
    }


def load_suite(path: Path) -> list[dict[str, Any]]:
    """Load JSONL suite cases."""
    cases: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        cases.append(json.loads(line))
    return cases


def run_bakeoff(
    *,
    models_path: Path = DEFAULT_MODELS_PATH,
    suite_paths: list[Path],
    roles: set[str] | None = None,
    families: set[str] | None = None,
    model_ids: set[str] | None = None,
    limit: int | None = None,
    run_id: str | None = None,
    dry_run: bool = False,
    cache_buster: str = "",
) -> Path:
    """Run selected suites against selected models and return the run directory."""
    load_dotenv(config.PROJECT_ROOT / ".env")
    run_id = run_id or datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    run_dir = DEFAULT_ARTIFACT_ROOT / run_id
    output_dir = run_dir / "model_outputs"
    scores_dir = run_dir / "scores"
    output_dir.mkdir(parents=True, exist_ok=True)
    scores_dir.mkdir(parents=True, exist_ok=True)

    models = _filter_models(load_model_registry(models_path), roles, families, model_ids)
    config_snapshot = {
        "run_id": run_id,
        "created_at": _utc_now(),
        "dry_run": dry_run,
        "roles": sorted(roles or []),
        "families": sorted(families or []),
        "model_ids": sorted(model_ids or []),
        "suites": [str(path) for path in suite_paths],
        "models": [asdict(model) for model in models],
        "flags": {
            "RERANKER_ENABLED": config.RERANKER_ENABLED,
            "HYBRID_SYNTH_ENABLED": config.HYBRID_SYNTH_ENABLED,
            "WIKI_ENABLED": config.WIKI_ENABLED,
        },
    }
    (run_dir / "config_snapshot.json").write_text(
        json.dumps(config_snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    score_records: list[dict[str, Any]] = []
    for suite_path in suite_paths:
        suite_cases = load_suite(suite_path)
        if limit is not None:
            suite_cases = suite_cases[:limit]
        for case in suite_cases:
            for model in models:
                role = _role_for_case(model, case)
                if role is None:
                    continue
                record = _run_case(
                    run_id=run_id,
                    model=model,
                    role=role,
                    suite=suite_path.stem,
                    case=case,
                    dry_run=dry_run,
                    cache_buster=cache_buster,
                )
                model_dir = output_dir / _safe_model_dir(model.id)
                model_dir.mkdir(parents=True, exist_ok=True)
                (model_dir / f"{case['id']}.json").write_text(
                    json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                score_records.append(_score_record(record, model, case))

    _write_score_csvs(scores_dir, score_records)
    write_reports(run_dir, score_records)
    return run_dir


def _run_case(
    *,
    run_id: str,
    model: ModelConfig,
    role: str,
    suite: str,
    case: dict[str, Any],
    dry_run: bool,
    cache_buster: str,
) -> dict[str, Any]:
    messages, prompt_text = _messages_for_case(case)
    started = time.perf_counter()
    errors: list[str] = []
    retries = 0
    raw_response = ""
    parsed_response: Any = None
    input_tokens = _rough_tokens(prompt_text)
    output_tokens = 0

    if dry_run:
        raw_response = _dry_run_response(case)
        parsed_response = _parse_json(raw_response)
        output_tokens = _rough_tokens(raw_response)
    else:
        try:
            raw_response, usage = _call_chat_completion(model, messages, force_json=_case_requires_json(case))
            parsed_response = _parse_json(raw_response)
            input_tokens = int(usage.get("prompt_tokens") or input_tokens)
            output_tokens = int(usage.get("completion_tokens") or _rough_tokens(raw_response))
        except Exception as exc:
            errors.append(str(exc))

    latency_ms = int((time.perf_counter() - started) * 1000)
    return build_output_record(
        run_id=run_id,
        model=model,
        role=role,
        suite=suite,
        case_id=str(case["id"]),
        prompt_text=prompt_text,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        raw_response=raw_response,
        parsed_response=parsed_response,
        errors=errors,
        retries=retries,
        cache_buster=cache_buster,
    )


def _score_record(record: dict[str, Any], model: ModelConfig, case: dict[str, Any]) -> dict[str, Any]:
    scored = {
        "model_id": model.id,
        "provider": model.provider,
        "family": model.family,
        "role": record["role"],
        "suite": record["suite"],
        "case_id": record["case_id"],
        "estimated_cost_usd": record["estimated_cost_usd"],
        "latency_ms": record["latency_ms"],
    }
    if record.get("errors"):
        scored["quality"] = {
            "score": 0,
            "passed": False,
            "schema_valid": False,
            "missing": [],
            "forbidden": ["api_error"],
        }
        return scored
    if case.get("expected_behavior") or "political" in record["suite"] or case.get("suite") == "chinese_political_risk":
        scored["political_risk"] = asdict(score_political_risk(case, record))
    scored["quality"] = asdict(score_quality(case, record))
    return scored


def _write_score_csvs(scores_dir: Path, records: list[dict[str, Any]]) -> None:
    political_path = scores_dir / "political_risk_scores.csv"
    quality_path = scores_dir / "quality_scores.csv"
    with political_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["model_id", "role", "suite", "case_id", "risk_level", "score", "flags"])
        writer.writeheader()
        for record in records:
            risk = record.get("political_risk")
            if not risk:
                continue
            writer.writerow({
                "model_id": record["model_id"],
                "role": record["role"],
                "suite": record["suite"],
                "case_id": record["case_id"],
                "risk_level": risk["risk_level"],
                "score": risk["score"],
                "flags": ",".join(risk.get("flags") or []),
            })
    with quality_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["model_id", "role", "suite", "case_id", "passed", "score", "missing", "forbidden"])
        writer.writeheader()
        for record in records:
            quality = record.get("quality")
            if not quality:
                continue
            writer.writerow({
                "model_id": record["model_id"],
                "role": record["role"],
                "suite": record["suite"],
                "case_id": record["case_id"],
                "passed": quality["passed"],
                "score": quality["score"],
                "missing": ",".join(quality.get("missing") or []),
                "forbidden": ",".join(quality.get("forbidden") or []),
            })


def _filter_models(
    models: list[ModelConfig],
    roles: set[str] | None,
    families: set[str] | None,
    model_ids: set[str] | None,
) -> list[ModelConfig]:
    filtered = []
    for model in models:
        if families and model.family not in families:
            continue
        if model_ids and model.id not in model_ids:
            continue
        if roles and not roles.intersection(model.roles):
            continue
        filtered.append(model)
    return filtered


def _role_for_case(model: ModelConfig, case: dict[str, Any]) -> str | None:
    preferred = case.get("role")
    if preferred:
        return str(preferred)
    task_type = str(case.get("task_type", ""))
    role_map = {
        "translation_fidelity": "translation",
        "enrichment_json": "enrichment",
        "rag_build_extraction": "rag_build",
        "rag_build_tuple_extraction": "rag_build",
        "fixed_context_synthesis": "query",
        "fallback_synth": "fallback_synth",
        "source_preservation": "high_risk_enrichment",
        "direct_qa": "query",
        "script_pack": "script_pack",
    }
    role = role_map.get(task_type)
    if role:
        return role
    return model.roles[0] if model.roles else None


def _messages_for_case(case: dict[str, Any]) -> tuple[list[dict[str, str]], str]:
    task_type = str(case.get("task_type", "direct_qa"))
    system_path = DEFAULT_PROMPTS_DIR / _TASK_PROMPTS.get(task_type, "direct_qa_system.txt")
    system = system_path.read_text(encoding="utf-8")
    user = _case_user_prompt(case)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], f"{system}\n\n{user}"


def _case_user_prompt(case: dict[str, Any]) -> str:
    if "prompt" in case:
        return str(case["prompt"])
    if case.get("task_type") == "translation_fidelity":
        payload = {
            "language": case.get("language", ""),
            "text": case.get("input", ""),
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)
    if "input" in case:
        return json.dumps(case["input"], ensure_ascii=False, indent=2)
    if "context" in case:
        payload = {"question": case.get("question", ""), "context": case.get("context", [])}
        return json.dumps(payload, ensure_ascii=False, indent=2)
    return json.dumps(case, ensure_ascii=False, indent=2)


def _call_chat_completion(
    model: ModelConfig,
    messages: list[dict[str, str]],
    force_json: bool | None = None,
) -> tuple[str, dict[str, Any]]:
    base_url = _base_url_for(model)
    api_key = _api_key_for(model)
    if not api_key:
        raise RuntimeError(f"No API key configured for provider {model.provider}.")
    payload = {
        "model": getattr(model, "api_id", "") or model.id,
        "messages": messages,
        "temperature": 0,
    }
    payload.update(_provider_options(model, base_url))
    json_requested = force_json if force_json is not None else any("json" in message["content"].casefold() for message in messages)
    if json_requested:
        payload["response_format"] = {"type": "json_object"}
    response = _post_chat_completion(base_url, api_key, payload)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        if response.status_code == 400 and "response_format" in payload:
            fallback_payload = dict(payload)
            fallback_payload.pop("response_format", None)
            response = _post_chat_completion(base_url, api_key, fallback_payload)
            response.raise_for_status()
        else:
            raise exc
    data = response.json()
    return str(data["choices"][0]["message"]["content"] or "").strip(), data.get("usage") or {}


def _post_chat_completion(base_url: str, api_key: str, payload: dict[str, Any]) -> requests.Response:
    return requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers=auth_headers(api_key, base_url),
        json=payload,
        timeout=120,
    )


def _case_requires_json(case: dict[str, Any]) -> bool:
    return str(case.get("task_type", "")) in {"enrichment_json", "rag_build_extraction"}


def _provider_options(model: ModelConfig, base_url: str) -> dict[str, Any]:
    text = f"{model.provider} {model.id} {getattr(model, 'api_id', '') or ''} {base_url}".casefold()
    if config.LLM_REASONING_EFFORT and model.provider.casefold() == "openrouter":
        return {"reasoning_effort": config.LLM_REASONING_EFFORT}
    if config.LLM_REASONING_EFFORT:
        return {}
    if "deepseek-v4" not in text and "api.deepseek.com" not in text:
        return {}
    return {"thinking": {"type": "disabled"}}


def _base_url_for(model: ModelConfig) -> str:
    if model.base_url_env and os.getenv(model.base_url_env):
        return str(os.getenv(model.base_url_env))
    provider = model.provider.casefold()
    if provider == "openrouter":
        return os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    if provider == "deepseek":
        return os.getenv("DEEPSEEK_BASE_URL") or config.LLM_BASE_URL
    if provider == "google":
        return os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai")
    if provider == "mistral":
        return os.getenv("MISTRAL_BASE_URL", "https://api.mistral.ai/v1")
    return config.LLM_BASE_URL


def _api_key_for(model: ModelConfig) -> str:
    if model.api_key_env and os.getenv(model.api_key_env):
        return str(os.getenv(model.api_key_env))
    provider = model.provider.casefold()
    if provider == "openrouter":
        return os.getenv("OPENROUTER_API_KEY", "")
    if provider == "deepseek":
        return os.getenv("DEEPSEEK_API_KEY") or config.LLM_API_KEY
    if provider == "google":
        return os.getenv("GEMINI_API_KEY", "")
    if provider == "mistral":
        return os.getenv("MISTRAL_API_KEY", "")
    return config.LLM_API_KEY


def _dry_run_response(case: dict[str, Any]) -> str:
    expected = case.get("expected_behavior") or case.get("expected") or {}
    if case.get("task_type") == "enrichment_json":
        return json.dumps({
            "summary": "Dry run response.",
            "key_facts": [{"text": "Dry run fact.", "claim_type": "source_claim"}],
            "entities": {},
            "quotes": [],
            "expected": expected,
        }, ensure_ascii=False)
    return json.dumps({"dry_run": True, "expected": expected}, ensure_ascii=False)


def _parse_json(text: str) -> Any:
    stripped = str(text or "").strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None


def _rough_tokens(text: str) -> int:
    return max(1, int(len(text) / 4))


def _safe_model_dir(model_id: str) -> str:
    return model_id.replace("/", "__").replace(":", "_")


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _parse_csv_set(value: str) -> set[str] | None:
    items = {item.strip() for item in value.split(",") if item.strip()}
    return items or None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run GeoSpoiler model bakeoff suites.")
    parser.add_argument("--models", type=Path, default=DEFAULT_MODELS_PATH)
    parser.add_argument("--suite", action="append", type=Path, required=True)
    parser.add_argument("--roles", default="")
    parser.add_argument("--families", default="")
    parser.add_argument("--model-ids", default="")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--run-id")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--cache-buster", default="")
    args = parser.parse_args(argv)

    run_dir = run_bakeoff(
        models_path=args.models,
        suite_paths=args.suite,
        roles=_parse_csv_set(args.roles),
        families=_parse_csv_set(args.families),
        model_ids=_parse_csv_set(args.model_ids),
        limit=args.limit,
        run_id=args.run_id,
        dry_run=args.dry_run,
        cache_buster=args.cache_buster,
    )
    print(f"Model bakeoff artifacts: {run_dir}")


if __name__ == "__main__":
    main()
