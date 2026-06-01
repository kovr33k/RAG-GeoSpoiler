"""OpenAI-compatible client helpers for LightRAG queries and embeddings."""

import asyncio
import logging
from typing import Any

import numpy as np
from openai import APIConnectionError, APITimeoutError, AsyncOpenAI

import config
from llm_auth import get_openai_api_key

logger = logging.getLogger("geospoiler.loader")


def _client_api_key(api_key: str, base_url: str) -> str:
    return get_openai_api_key(api_key, base_url) or "geospoiler-missing-api-key"


def _chat_settings_for_role(role: str) -> tuple[str, str, str]:
    if role == "build":
        return config.RAG_BUILD_API_KEY, config.RAG_BUILD_BASE_URL, config.RAG_BUILD_MODEL
    if role == "fallback":
        return config.FALLBACK_SYNTH_API_KEY, config.FALLBACK_SYNTH_BASE_URL, config.FALLBACK_SYNTH_MODEL
    return config.QUERY_API_KEY, config.QUERY_BASE_URL, config.QUERY_MODEL


def _openai_client(api_key: str, base_url: str, **kwargs) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=_client_api_key(api_key, base_url),
        base_url=base_url,
        **kwargs,
    )


def _uses_deepseek_v4() -> bool:
    values = (
        config.LLM_BASE_URL,
        config.LLM_MODEL,
        config.RAG_BUILD_BASE_URL,
        config.RAG_BUILD_MODEL,
        config.QUERY_BASE_URL,
        config.QUERY_MODEL,
        config.FALLBACK_SYNTH_BASE_URL,
        config.FALLBACK_SYNTH_MODEL,
    )
    text = " ".join(str(value).casefold() for value in values)
    return "api.deepseek.com" in text or "deepseek-v4" in text


def _chat_completion_options(max_tokens: int | None = None, **kwargs) -> dict[str, Any]:
    """Build OpenAI-compatible chat options from explicit args plus local config."""
    options = {key: value for key, value in kwargs.items() if value is not None}
    if max_tokens is not None and max_tokens > 0:
        options["max_tokens"] = max_tokens
    if config.LLM_REASONING_EFFORT:
        options["reasoning_effort"] = config.LLM_REASONING_EFFORT
    if _uses_deepseek_v4() and not config.LLM_REASONING_EFFORT:
        extra_body = dict(options.get("extra_body") or {})
        extra_body.setdefault("thinking", {"type": "disabled"})
        options["extra_body"] = extra_body
    return options


_embed_client = AsyncOpenAI(
    api_key=_client_api_key(config.EMBEDDING_API_KEY, config.EMBEDDING_BASE_URL),
    base_url=config.EMBEDDING_BASE_URL,
    timeout=config.EMBEDDING_TIMEOUT_SECONDS,
)
_embed_semaphore = asyncio.Semaphore(max(1, config.EMBEDDING_CONCURRENCY))

_NIM_ASYMMETRIC_MODELS = {
    "nvidia/nv-embedqa-e5-v5",
    "nvidia/nv-embedqa-mistral-7b-v2",
    "nvidia/llama-3.2-nv-embedqa-1b-v2",
}

_needs_input_type = config.EMBEDDING_MODEL in _NIM_ASYMMETRIC_MODELS


async def _embed_texts(texts: list[str], input_type: str = "passage") -> np.ndarray:
    """Call NIM embedding API. Returns numpy array as required by LightRAG."""
    if not texts:
        return np.empty((0, config.EMBEDDING_DIM), dtype=np.float32)

    all_vectors: list[list[float]] = []
    batch_size = max(1, config.EMBEDDING_BATCH_SIZE)

    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        kwargs: dict = {
            "model": config.EMBEDDING_MODEL,
            "input": batch,
        }
        if _needs_input_type:
            kwargs["extra_body"] = {"input_type": input_type, "truncate": "END"}

        for attempt in range(1, max(1, config.EMBEDDING_MAX_ATTEMPTS) + 1):
            try:
                async with _embed_semaphore:
                    response = await _embed_client.embeddings.create(**kwargs)
                all_vectors.extend(item.embedding for item in response.data)
                break
            except (APIConnectionError, APITimeoutError) as exc:
                if attempt >= config.EMBEDDING_MAX_ATTEMPTS:
                    raise
                delay = min(12, 1.5 * attempt)
                logger.warning(
                    "Embedding request failed for batch %s-%s/%s on attempt %s/%s: %s. Retrying in %.1fs.",
                    start + 1,
                    start + len(batch),
                    len(texts),
                    attempt,
                    config.EMBEDDING_MAX_ATTEMPTS,
                    exc.__class__.__name__,
                    delay,
                )
                await asyncio.sleep(delay)

    return np.array(all_vectors, dtype=np.float32)
