"""
Reranker — интеграция с LightRAG 1.4.15 и поддержка самостоятельного вызова.

Поддерживает 3 провайдера (выбирается через RERANKER_PROVIDER в .env):
  nim          — Nvidia NIM /v1/ranking (рекомендуется)
  jina         — Jina AI Reranker API
  huggingface  — Локальный BAAI/bge-reranker-v2-m3

LightRAG API (rerank_model_func):
  async def func(query: str, documents: list[str], top_n: int)
    -> list[{"index": int, "relevance_score": float}]

Если RERANKER_ENABLED=false — функция возвращает None, LightRAG rerank не будет подключён.
"""

import logging
import asyncio
from typing import Any

import httpx

import config

logger = logging.getLogger("geospoiler.reranker")


# ──────────────────────────────────────────────────────────────────
# LightRAG-совместимая async rerank функция
# ──────────────────────────────────────────────────────────────────

async def lightrag_rerank_func(
    query: str,
    documents: list[str],
    top_n: int | None = None,
) -> list[dict]:
    """
    Async reranker совместимый с LightRAG 1.4.15 rerank_model_func API.

    Args:
        query:     Поисковый запрос пользователя.
        documents: Список текстов для ранжирования (chunk content).
        top_n:     Сколько вернуть (если None — используется config.RERANKER_TOP_N).

    Returns:
        list of {"index": int, "relevance_score": float} — отсортированный по score desc.
    """
    if not config.RERANKER_ENABLED or not documents:
        # Вернуть все документы с убывающим score (без реального rerank)
        return [{"index": i, "relevance_score": 1.0 - i * 0.01} for i in range(len(documents))]

    top_n = top_n or config.RERANKER_TOP_N
    candidates = documents[: config.RERANKER_CANDIDATE_POOL]

    try:
        provider = config.RERANKER_PROVIDER.lower()

        if provider == "nim":
            results = await _rerank_nim_async(query, candidates, top_n)
        elif provider == "jina":
            results = await _rerank_jina_async(query, candidates, top_n)
        else:
            logger.warning(f"Unknown reranker provider '{provider}', skipping.")
            return [{"index": i, "relevance_score": 1.0} for i in range(min(top_n, len(candidates)))]

        logger.info(
            f"Reranker ({provider}): {len(documents)} docs -> "
            f"{len(candidates)} candidates -> {len(results)} returned"
        )
        return results

    except Exception as e:
        logger.warning(f"Reranker failed ({e}), using original order.")
        return [{"index": i, "relevance_score": 1.0} for i in range(min(top_n or 10, len(documents)))]


# ──────────────────────────────────────────────────────────────────
# Nvidia NIM async
# ──────────────────────────────────────────────────────────────────

async def _rerank_nim_async(
    query: str,
    passages: list[str],
    top_n: int,
) -> list[dict]:
    """
    Nvidia NIM Reranking API (async).
    Full endpoint: {RERANKER_BASE_URL}/reranking
    Example: https://ai.api.nvidia.com/v1/retrieval/nvidia/llama-nemotron-rerank-1b-v2/reranking
    Response: {"rankings": [{"index": 0, "logit": 3.14}, ...]}
    """
    url = config.RERANKER_BASE_URL.rstrip("/") + "/reranking"

    payload = {
        "model": config.RERANKER_MODEL,
        "query": {"text": query},
        "passages": [{"text": p} for p in passages],
        "truncate": "END",
    }

    headers = {
        "Authorization": f"Bearer {config.RERANKER_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    # NIM returns rankings sorted by logit desc (most relevant first)
    rankings = data.get("rankings", [])

    # Normalize logit scores to [0, 1] range using sigmoid
    import math
    results = []
    for r in rankings[:top_n]:
        logit = r.get("logit", 0.0)
        score = 1.0 / (1.0 + math.exp(-logit))  # sigmoid
        results.append({"index": r["index"], "relevance_score": score})

    return results


# ──────────────────────────────────────────────────────────────────
# Jina AI async
# ──────────────────────────────────────────────────────────────────

async def _rerank_jina_async(
    query: str,
    passages: list[str],
    top_n: int,
) -> list[dict]:
    """
    Jina AI Reranker API (async).
    Endpoint: POST https://api.jina.ai/v1/rerank
    """
    url = "https://api.jina.ai/v1/rerank"

    payload = {
        "model": config.RERANKER_MODEL,
        "query": query,
        "documents": passages,
        "top_n": top_n,
    }

    headers = {
        "Authorization": f"Bearer {config.RERANKER_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    # Jina returns: {"results": [{"index": 0, "relevance_score": 0.95, ...}, ...]}
    results = data.get("results", [])
    return [
        {"index": r["index"], "relevance_score": r.get("relevance_score", 0.0)}
        for r in results
    ]


# ──────────────────────────────────────────────────────────────────
# Синхронная обёртка (для обратной совместимости / тестов)
# ──────────────────────────────────────────────────────────────────

def rerank(query: str, passages: list[str]) -> list[str]:
    """
    Синхронный вызов reranker (совместимость со старым кодом).
    Возвращает список текстов (а не индексов), обрезанный до RERANKER_TOP_N.
    """
    if not config.RERANKER_ENABLED or not passages:
        return passages

    try:
        results = asyncio.run(
            lightrag_rerank_func(query, passages, config.RERANKER_TOP_N)
        )
        return [passages[r["index"]] for r in results if r["index"] < len(passages)]
    except Exception as e:
        logger.warning(f"Sync rerank wrapper failed ({e}), using original order.")
        return passages[: config.RERANKER_TOP_N]
