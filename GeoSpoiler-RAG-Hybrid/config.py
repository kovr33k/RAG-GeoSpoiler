"""
GeoSpoiler-RAG Configuration
Loads settings from .env file. All API providers use OpenAI-compatible format
so you can swap between OpenAI, Nvidia NIM, Together AI, etc. by changing URL and key.
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).parent
load_dotenv(PROJECT_ROOT / ".env")


# ───────────────────────── Telegram ─────────────────────────
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE", "")
TELEGRAM_FOLDER = os.getenv("TELEGRAM_FOLDER", "GeoSpoiler")  # Telegram folder name to read from

# ───────────────────────── LLM ─────────────────────────
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "120"))
LLM_MAX_ASYNC = int(os.getenv("LLM_MAX_ASYNC", "1"))
LLM_DELAY_SECONDS = float(os.getenv("LLM_DELAY_SECONDS", "2.0"))
RAG_BUILD_DELAY_SECONDS = float(os.getenv("RAG_BUILD_DELAY_SECONDS", str(LLM_DELAY_SECONDS)))
QUERY_DELAY_SECONDS = float(os.getenv("QUERY_DELAY_SECONDS", "0"))
RAG_INSERT_TIMEOUT_SECONDS = float(os.getenv("RAG_INSERT_TIMEOUT_SECONDS", "600"))
RAG_DELETE_TIMEOUT_SECONDS = float(os.getenv("RAG_DELETE_TIMEOUT_SECONDS", "120"))
QUERY_TIMEOUT_SECONDS = float(os.getenv("QUERY_TIMEOUT_SECONDS", "240"))
FALLBACK_SYNTH_TIMEOUT_SECONDS = float(os.getenv("FALLBACK_SYNTH_TIMEOUT_SECONDS", "45"))
RAG_FINALIZE_TIMEOUT_SECONDS = float(os.getenv("RAG_FINALIZE_TIMEOUT_SECONDS", "30"))
HYBRID_QUERY_CARDS_ENABLED = os.getenv("HYBRID_QUERY_CARDS_ENABLED", "true").lower() == "true"
HYBRID_SYNTH_ENABLED = os.getenv("HYBRID_SYNTH_ENABLED", "true").lower() == "true"
HYBRID_QUERY_CARDS_TOP_K = int(os.getenv("HYBRID_QUERY_CARDS_TOP_K", "3"))

# Role-specific chat models. Each role falls back to the main LLM_* settings.
RAG_BUILD_API_KEY = os.getenv("RAG_BUILD_API_KEY", "") or LLM_API_KEY
RAG_BUILD_BASE_URL = os.getenv("RAG_BUILD_BASE_URL", "") or LLM_BASE_URL
RAG_BUILD_MODEL = os.getenv("RAG_BUILD_MODEL", "") or LLM_MODEL

QUERY_API_KEY = os.getenv("QUERY_API_KEY", "") or LLM_API_KEY
QUERY_BASE_URL = os.getenv("QUERY_BASE_URL", "") or LLM_BASE_URL
QUERY_MODEL = os.getenv("QUERY_MODEL", "") or LLM_MODEL

FALLBACK_SYNTH_API_KEY = os.getenv("FALLBACK_SYNTH_API_KEY", "") or QUERY_API_KEY
FALLBACK_SYNTH_BASE_URL = os.getenv("FALLBACK_SYNTH_BASE_URL", "") or QUERY_BASE_URL
FALLBACK_SYNTH_MODEL = os.getenv("FALLBACK_SYNTH_MODEL", "") or QUERY_MODEL

TRANSLATION_API_KEY = os.getenv("TRANSLATION_API_KEY", "") or LLM_API_KEY
TRANSLATION_BASE_URL = os.getenv("TRANSLATION_BASE_URL", "") or LLM_BASE_URL
TRANSLATION_MODEL = os.getenv("TRANSLATION_MODEL", "") or LLM_MODEL

# ───────────────────────── Embedding ─────────────────────────
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "https://api.openai.com/v1")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "3072"))
EMBEDDING_TIMEOUT_SECONDS = float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "120"))
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "8"))
EMBEDDING_MAX_ATTEMPTS = int(os.getenv("EMBEDDING_MAX_ATTEMPTS", "6"))
EMBEDDING_CONCURRENCY = int(os.getenv("EMBEDDING_CONCURRENCY", "1"))

# ───────────────────────── Vision ─────────────────────────
VISION_API_KEY = os.getenv("VISION_API_KEY", "")
VISION_BASE_URL = os.getenv("VISION_BASE_URL", "https://api.openai.com/v1")
VISION_MODEL = os.getenv("VISION_MODEL", "gpt-4o")

# ───────────────────────── Reranker ─────────────────────────
# Set RERANKER_ENABLED=true to activate. Recommended after corpus reaches ~500 docs.
# Provider options:
#   nim          — Nvidia NIM /v1/ranking  (recommended, no GPU needed)
#   huggingface  — local BAAI/bge-reranker-v2-m3 via FlagEmbedding
#   jina         — Jina AI reranker API
RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "false").lower() == "true"
RERANKER_PROVIDER = os.getenv("RERANKER_PROVIDER", "nim")
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "nvidia/llama-nemotron-rerank-1b-v2")
RERANKER_API_KEY = os.getenv("RERANKER_API_KEY", "")
RERANKER_BASE_URL = os.getenv("RERANKER_BASE_URL", "https://integrate.api.nvidia.com/v1")
RERANKER_TOP_N = int(os.getenv("RERANKER_TOP_N", "10"))           # Final passages shown to LLM
RERANKER_CANDIDATE_POOL = int(os.getenv("RERANKER_CANDIDATE_POOL", "50"))  # Candidate pool before reranking

# ───────────────────────── Paths ─────────────────────────
OUTPUT_DIR = PROJECT_ROOT / os.getenv("OUTPUT_DIR", "./output")
NORMALIZED_DIR = OUTPUT_DIR / "normalized"
ENRICHED_DIR = OUTPUT_DIR / "enriched"
REVIEW_QUEUE_DIR = OUTPUT_DIR / "review_queue"
RAG_STORAGE_DIR = PROJECT_ROOT / os.getenv("RAG_STORAGE_DIR", "./rag_storage")
STATE_DIR = PROJECT_ROOT / os.getenv("STATE_DIR", "./state")
MEDIA_CACHE_DIR = PROJECT_ROOT / os.getenv("MEDIA_CACHE_DIR", "./media_cache")
LOG_DIR = PROJECT_ROOT / os.getenv("LOG_DIR", "./logs")

# Ensure all directories exist
for d in [NORMALIZED_DIR, ENRICHED_DIR, REVIEW_QUEUE_DIR, RAG_STORAGE_DIR, STATE_DIR, MEDIA_CACHE_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ───────────────────────── Enrichment ─────────────────────────
# Optional separate model for enrichment (defaults to main LLM_MODEL).
# Use a more capable model here if budget allows (e.g. Claude Opus for reasoning).
ENRICHMENT_API_KEY = os.getenv("ENRICHMENT_API_KEY", "") or LLM_API_KEY
ENRICHMENT_BASE_URL = os.getenv("ENRICHMENT_BASE_URL", "") or LLM_BASE_URL
ENRICHMENT_MODEL = os.getenv("ENRICHMENT_MODEL", "") or LLM_MODEL
ENRICHMENT_SCHEMA_VERSION = int(os.getenv("ENRICHMENT_SCHEMA_VERSION", "1"))

# ───────────────────────── LightRAG ─────────────────────────
LIGHTRAG_ENTITY_TYPES = [
    "person",           # Политики, военные, журналисты
    "organization",     # НАТО, ООН, ЧВК Вагнер, СБУ, Reuters
    "country",          # Россия, Украина, США, Венгрия
    "military_unit",    # 47-я ОМБр, 1-я танковая армия, батальон Азов
    "event",            # Выборы в США, Курская операция, Саммит мира
    "location",         # Авдеевка, Закарпатье, Сувалкский коридор
    "conflict",         # Российско-украинская война, Конфликт в Газе
    "document",         # Законы, договора, соглашения, санкционные пакеты
                        # (Будапештский меморандум, Минские соглашения,
                        #  Закон о мобилизации, 13-й пакет санкций ЕС)
    "other",            # Fallback for real entities outside the core ontology
]

LIGHTRAG_LANGUAGE = "English"  # Граф строится на английском
RELATION_EXTRACTION_MODE = os.getenv("RELATION_EXTRACTION_MODE", "interpretive").strip().lower()

LIGHTRAG_ENTITY_TYPE_REMAP = {
    "concept": "other",
    "group": "organization",
    "platform": "organization",
    "website": "organization",
    "technology": "other",
    "equipment": "other",
    "artifact": "other",
    "content": "document",
    "data": "document",
    "method": "document",
    "policy": "document",
    "product": "other",
    "category": "other",
    "unknown": "other",
}

_default_aliases = {
    "сша": "United States",
    "usa": "United States",
    "united states": "United States",
    "украина": "Ukraine",
    "ukraine": "Ukraine",
    "россия": "Russia",
    "росія": "Russia",
    "russia": "Russia",
    "германия": "Germany",
    "germany": "Germany",
    "адг": "AfD",
    "afd": "AfD",
    "трамп": "Donald Trump",
    "donald trump": "Donald Trump",
    "дональд трамп": "Donald Trump",
    "ес": "European Union",
    "єс": "European Union",
    "eu": "European Union",
    "european union": "European Union",
    "кремль": "Kremlin",
}

LIGHTRAG_ENTITY_ALIASES = _default_aliases.copy()
_alias_json = os.getenv("LIGHTRAG_ENTITY_ALIASES_JSON", "").strip()
if _alias_json:
    try:
        LIGHTRAG_ENTITY_ALIASES.update(json.loads(_alias_json))
    except json.JSONDecodeError:
        pass

# ───────────────────────── URL Patterns ─────────────────────────
import re

YOUTUBE_PATTERN = re.compile(
    r'(?:https?://)?(?:www\.)?(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)[\w-]+',
    re.IGNORECASE,
)
INSTAGRAM_PATTERN = re.compile(
    r'(?:https?://)?(?:www\.)?instagram\.com/(?:reel|p)/[\w-]+',
    re.IGNORECASE,
)
AI_CHAT_PATTERNS = [
    re.compile(r'(?:https?://)?(?:chat\.openai\.com|chatgpt\.com)/(?:share|c)/[\w-]+', re.IGNORECASE),
    re.compile(r'(?:https?://)?gemini\.google\.com/(?:app|share)/[\w-]+', re.IGNORECASE),
    re.compile(r'(?:https?://)?claude\.ai/(?:chat|share)/[\w-]+', re.IGNORECASE),
]
WEB_URL_PATTERN = re.compile(
    r'https?://[^\s<>"\']+',
    re.IGNORECASE,
)
