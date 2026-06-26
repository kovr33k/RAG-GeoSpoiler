"""OpenAI-compatible client helpers for LLM-maintained wiki pages."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import requests

import config
from llm_auth import auth_headers

logger = logging.getLogger("geospoiler.retrieval.wiki_llm")


@dataclass(frozen=True)
class WikiLlmConfig:
    api_key: str
    base_url: str
    model: str
    timeout_seconds: float


def wiki_llm_config() -> WikiLlmConfig:
    """Resolve dedicated wiki LLM settings, falling back to enrichment settings."""
    return WikiLlmConfig(
        api_key=str(config.WIKI_LLM_API_KEY or config.ENRICHMENT_API_KEY or ""),
        base_url=str(config.WIKI_LLM_BASE_URL or config.ENRICHMENT_BASE_URL or ""),
        model=str(config.WIKI_LLM_MODEL or config.ENRICHMENT_MODEL or ""),
        timeout_seconds=float(config.WIKI_INGEST_TIMEOUT_SECONDS),
    )


def call_wiki_llm(prompt: str, system: str | None = None) -> dict[str, Any]:
    """Call the configured wiki LLM and return parsed JSON, or empty dict on failure."""
    resolved = wiki_llm_config()
    if not resolved.api_key or resolved.api_key == "your-api-key-here":
        logger.warning("No WIKI_LLM_API_KEY/ENRICHMENT_API_KEY configured; wiki ingest will queue pending sources.")
        return {}
    if not resolved.base_url or not resolved.model:
        logger.warning("Wiki LLM base URL or model is missing; wiki ingest will queue pending sources.")
        return {}

    system_prompt = system or (
        "You are a wiki maintainer. Use ONLY the provided source data. "
        "Every claim must cite source_ids. Do not invent facts. Return only JSON."
    )
    payload = {
        "model": resolved.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    return _post_json(payload, resolved, allow_fallback=True)


def _post_json(payload: dict[str, Any], resolved: WikiLlmConfig, allow_fallback: bool) -> dict[str, Any]:
    try:
        response = requests.post(
            f"{resolved.base_url.rstrip('/')}/chat/completions",
            headers=auth_headers(resolved.api_key, resolved.base_url),
            json=payload,
            timeout=resolved.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        content = str(data["choices"][0]["message"]["content"]).strip()
        return _parse_json_response(content)
    except requests.HTTPError as exc:
        if allow_fallback and exc.response is not None and exc.response.status_code == 400:
            fallback_payload = dict(payload)
            fallback_payload.pop("response_format", None)
            return _post_json(fallback_payload, resolved, allow_fallback=False)
        logger.warning("Wiki LLM HTTP error: %s", exc)
        return {}
    except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
        logger.warning("Wiki LLM call failed: %s", exc)
        return {}


def _parse_json_response(content: str) -> dict[str, Any]:
    content = content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines).strip()
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        logger.warning("Wiki LLM returned invalid JSON: %s", exc)
        return {}
    return data if isinstance(data, dict) else {}
