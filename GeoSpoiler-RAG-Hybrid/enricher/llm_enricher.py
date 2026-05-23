"""
LLM Enricher — calls the LLM to extract structured data from normalized posts.

Single LLM call extracts: summary, key_facts, entities, topics, theses,
quotes, events, query_aliases, visual assessment, and claim types.
"""

import json
import logging
import re

import requests

import config

logger = logging.getLogger("geospoiler.enricher.llm")

# ── Header regex to strip before sending to LLM ──
_HEADER_RE = re.compile(r"^\[Канал:.*\]\s*$")
_EXPLICIT_FAKE_RE = re.compile(
    r"(фейк\w*|фальшив\w*|подделк\w*|поддельн\w*|сфабрикован\w*|"
    r"дезинформац\w*|сатир\w*|пароди\w*|fake\w*|false\w*|"
    r"fabricated|forged|disinformation|satire|parody|not real|"
    r"не\s+явля\w+\s+реальн\w*|не\s+настоящ\w*)",
    re.IGNORECASE,
)
_UNSUPPORTED_VERDICT_RE = re.compile(
    r"(фейк\w*|фальшив\w*|подделк\w*|поддельн\w*|сфабрикован\w*|"
    r"дезинформац\w*|сатир\w*|пароди\w*|fake\w*|false\w*|"
    r"fabricated|forged|disinformation|satire|parody|not real|"
    r"не\s+явля\w+\s+реальн\w*|не\s+настоящ\w*)",
    re.IGNORECASE,
)


# ── System prompts ──────────────────────────────────────────────────────────

_SYSTEM_PROMPT_FULL = """Ты — аналитик для OSINT-базы знаний по геополитике (проект GeoSpoiler).
CRITICAL SOURCE-FIDELITY RULES:
- Do not fact-check claims against your outside knowledge.
- If the source presents a statement as real, preserve it as a source_claim.
- Do not label a claim as fake, false, satire, parody, fabricated, disinformation, or imitation unless the source text explicitly says that.
- Sarcasm, emojis, all-caps style, political disagreement, or hostile commentary are not enough to call a statement fake.
- Do not add hedging words such as "якобы" unless the source itself uses them.
- When uncertain about truth status, write "в посте утверждается" and use claim_type=source_claim.

Тебе дают нормализованный текст поста из Telegram. Пост может содержать:
- текст автора
- транскрипт YouTube видео
- описание изображений (через Vision API)
- контент из Instagram
- внешние статьи

Твоя задача — извлечь структурированную информацию и вернуть JSON.

ВАЖНЫЕ ПРАВИЛА:
- Пиши summary и key_facts на РУССКОМ языке.
- key_facts — это АТОМАРНЫЕ утверждения. Каждый факт = одно предложение. Сохраняй конкретику: имена, цифры, даты, названия.
- НЕ выдумывай факты. Если в тексте нет информации — оставь поле пустым.
- НЕ превращай мнения автора в проверенные факты. Используй claim_type.
- query_aliases — синонимы/переводы для поиска (русский + английский).
- Для quotes сохраняй ОРИГИНАЛЬНЫЙ текст цитаты.
- broll_potential: high = есть конкретные визуальные кадры, medium = возможно полезно, low = только текст, none = ничего визуально.

Верни ТОЛЬКО JSON, без markdown-обёртки."""

_USER_PROMPT_FULL = """Извлеки из этого поста структурированную информацию.

Пост (content_type: {content_type}):
---
{text}
---

Верни JSON с ТОЧНО такой структурой:
{{
  "summary": "2-4 предложения: о чём пост",
  "key_facts": [
    {{"text": "атомарный факт", "claim_type": "fact|source_claim|hypothesis"}}
  ],
  "entities": {{
    "people": ["Имя (уточнение)"],
    "organizations": ["Название"],
    "countries": ["Страна"],
    "locations": ["Место"],
    "military_units": ["Подразделение"],
    "equipment": ["Техника/системы"]
  }},
  "topics": ["тег темы 1", "тег темы 2"],
  "theses": ["авторский тезис/вывод 1"],
  "quotes": [
    {{"speaker": "кто", "text": "дословная цитата", "context": "контекст"}}
  ],
  "events": [
    {{"name": "название", "date": "YYYY-MM-DD или null", "location": "где", "description": "что произошло"}}
  ],
  "query_aliases": ["синоним 1 (ru)", "synonym 2 (en)"],
  "broll_potential": "high|medium|low|none",
  "broll_notes": "описание визуального материала для b-roll, если есть"
}}"""

_SYSTEM_PROMPT_SHORT = """Ты — аналитик для OSINT-базы знаний. Извлеки минимальную структуру из короткого поста.
CRITICAL SOURCE-FIDELITY RULES:
- Do not fact-check claims against your outside knowledge.
- If the source presents a statement as real, preserve it as a source_claim.
- Do not label a claim as fake, false, satire, parody, fabricated, disinformation, or imitation unless the source text explicitly says that.
- Do not add hedging words such as "якобы" unless the source itself uses them.

Пиши summary и key_facts на РУССКОМ языке, даже если исходный текст на другом языке.
Верни ТОЛЬКО JSON, без markdown-обёртки."""

_USER_PROMPT_SHORT = """Короткий пост (content_type: {content_type}):
---
{text}
---

Верни JSON:
{{
  "summary": "1-2 предложения",
  "key_facts": [{{"text": "факт", "claim_type": "fact|source_claim|hypothesis"}}],
  "entities": {{
    "people": [], "organizations": [], "countries": [],
    "locations": [], "military_units": [], "equipment": []
  }},
  "topics": [],
  "theses": [],
  "quotes": [],
  "events": [],
  "query_aliases": [],
  "broll_potential": "none",
  "broll_notes": ""
}}"""

_SYSTEM_PROMPT_CHUNK = """Ты — аналитик. Перед тобой ФРАГМЕНТ длинного транскрипта видео.
Извлеки структурированную информацию из этого фрагмента.
Пиши summary и key_facts на РУССКОМ языке, даже если исходный текст на другом языке.
Верни ТОЛЬКО JSON, без markdown-обёртки."""

_USER_PROMPT_CHUNK = """Фрагмент #{chunk_index} (из {total_chunks}):
---
{text}
---

Верни JSON:
{{
  "summary": "2-3 предложения: о чём этот фрагмент",
  "key_facts": [{{"text": "атомарный факт", "claim_type": "fact|source_claim|hypothesis"}}],
  "entities": {{
    "people": [], "organizations": [], "countries": [],
    "locations": [], "military_units": [], "equipment": []
  }},
  "quotes": [{{"speaker": "кто", "text": "цитата", "context": "контекст"}}],
  "broll_notes": "визуальные описания, если упоминаются"
}}"""

_SYSTEM_PROMPT_MERGE = """Ты — аналитик. Перед тобой summaries и key_facts из ВСЕХ фрагментов длинного видео.
Объедини их в единую карточку. Дедуплицируй факты, сохрани ВСЕ уникальные.
Пиши summary, key_facts, topics, theses, events, query_aliases и broll_notes на РУССКОМ языке, кроме дословных цитат.
Верни ТОЛЬКО JSON, без markdown-обёртки."""

_USER_PROMPT_MERGE = """Заголовок поста: {header}

Данные по фрагментам:
{chunks_data}

Верни единый JSON:
{{
  "summary": "3-5 предложений — общее summary всего видео",
  "key_facts": [{{"text": "факт", "claim_type": "fact|source_claim|hypothesis"}}],
  "entities": {{
    "people": [], "organizations": [], "countries": [],
    "locations": [], "military_units": [], "equipment": []
  }},
  "topics": ["тег 1", "тег 2"],
  "theses": ["авторский тезис 1"],
  "quotes": [{{"speaker": "кто", "text": "цитата", "context": "контекст"}}],
  "events": [{{"name": "", "date": null, "location": "", "description": ""}}],
  "query_aliases": ["синоним (ru)", "synonym (en)"],
  "broll_potential": "high|medium|low|none",
  "broll_notes": "описание визуала для монтажа"
}}"""


# ── Public API ──────────────────────────────────────────────────────────────

def enrich_short_post(text: str, content_type: str) -> dict:
    """Enrich a short post (<500 chars body) with minimal LLM extraction."""
    body = _strip_header(text)
    if len(body.strip()) < 20:
        return _empty_enrichment()

    result = _normalize_result(_call_llm(
        system=_SYSTEM_PROMPT_SHORT,
        user=_USER_PROMPT_SHORT.format(content_type=content_type, text=body),
    ))
    return _remove_unsupported_fake_labels(result, body)


def enrich_full_post(text: str, content_type: str) -> dict:
    """Enrich a regular post with full LLM extraction."""
    body = _strip_header(text)
    result = _normalize_result(_call_llm(
        system=_SYSTEM_PROMPT_FULL,
        user=_USER_PROMPT_FULL.format(content_type=content_type, text=body),
    ))
    return _remove_unsupported_fake_labels(result, body)


def enrich_chunk(text: str, chunk_index: int, total_chunks: int) -> dict:
    """Enrich a single chunk of a long-form post."""
    result = _normalize_result(_call_llm(
        system=_SYSTEM_PROMPT_CHUNK,
        user=_USER_PROMPT_CHUNK.format(
            chunk_index=chunk_index + 1,
            total_chunks=total_chunks,
            text=text,
        ),
    ))
    return _remove_unsupported_fake_labels(result, text)


def merge_chunk_results(header: str, chunk_results: list[dict]) -> dict:
    """Merge multiple chunk results into a single enrichment."""
    chunks_data = ""
    for i, cr in enumerate(chunk_results):
        chunks_data += f"\n--- Фрагмент {i+1} ---\n"
        chunks_data += f"Summary: {cr.get('summary', '')}\n"
        facts = cr.get("key_facts", [])
        if facts:
            chunks_data += "Key facts:\n"
            for f in facts:
                if isinstance(f, dict):
                    chunks_data += f"  - {f.get('text', '')} [{f.get('claim_type', 'fact')}]\n"
                else:
                    chunks_data += f"  - {f}\n"
        quotes = cr.get("quotes", [])
        if quotes:
            chunks_data += "Quotes:\n"
            for q in quotes:
                if isinstance(q, dict):
                    chunks_data += f"  - {q.get('speaker', '?')}: «{q.get('text', '')}»\n"
        broll = cr.get("broll_notes", "")
        if broll:
            chunks_data += f"B-roll: {broll}\n"

    result = _call_llm(
        system=_SYSTEM_PROMPT_MERGE,
        user=_USER_PROMPT_MERGE.format(header=header, chunks_data=chunks_data),
    )
    return _normalize_result(result)


# ── LLM call ───────────────────────────────────────────────────────────────

def _call_llm(system: str, user: str) -> dict:
    """Call the LLM API and parse JSON response with hard total timeout."""
    api_key = config.ENRICHMENT_API_KEY
    if not api_key or api_key == "your-api-key-here":
        logger.warning("No ENRICHMENT_API_KEY configured; returning empty enrichment.")
        return {}

    payload = {
        "model": config.ENRICHMENT_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

    try:
        content = _post_with_hard_timeout(payload)
        return _parse_json_response(content)

    except _HardTimeoutError:
        logger.warning(
            f"LLM enrichment hard timeout ({config.LLM_TIMEOUT_SECONDS}s). "
            "API was streaming but took too long overall."
        )
        return {}
    except requests.Timeout:
        logger.warning("LLM enrichment timeout (no bytes received).")
        return {}
    except requests.HTTPError as e:
        logger.error(f"LLM enrichment HTTP error: {e}")
        if e.response is not None:
            if e.response.status_code == 429:
                logger.warning("Rate limited (429). Returning empty (will be marked partial and retried later).")
                return {}
            # If the model doesn't support json_object mode, retry without it
            if e.response.status_code == 400:
                return _call_llm_fallback(system, user)
        return {}
    except Exception as e:
        logger.error(f"LLM enrichment error: {e}")
        return {}


class _HardTimeoutError(Exception):
    """Raised when the total request time exceeds the hard limit."""


def _post_with_hard_timeout(payload: dict) -> str:
    """
    POST to LLM API with a hard total timeout.

    requests.post(timeout=N) only limits time between bytes — if the API
    streams tokens slowly, the request can hang forever. This wraps the
    call in a thread and kills it after LLM_TIMEOUT_SECONDS total.
    """
    import concurrent.futures
    import time

    def _do_request():
        if config.LLM_DELAY_SECONDS > 0:
            time.sleep(config.LLM_DELAY_SECONDS)
            
        response = requests.post(
            f"{config.ENRICHMENT_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {config.ENRICHMENT_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=config.LLM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_do_request)
        try:
            return future.result(timeout=config.LLM_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise _HardTimeoutError()


def _call_llm_fallback(system: str, user: str) -> dict:
    """Fallback LLM call without response_format (for models that don't support it)."""
    api_key = config.ENRICHMENT_API_KEY
    payload = {
        "model": config.ENRICHMENT_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
    }

    try:
        response = requests.post(
            f"{config.ENRICHMENT_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=config.LLM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()
        return _parse_json_response(content)
    except Exception as e:
        logger.error(f"LLM enrichment fallback error: {e}")
        return {}


# ── Helpers ─────────────────────────────────────────────────────────────────

def _parse_json_response(content: str) -> dict:
    """Parse JSON from LLM response, handling markdown code blocks."""
    # Strip markdown code fences if present
    content = content.strip()
    if content.startswith("```"):
        # Remove opening ```json or ``` and closing ```
        lines = content.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM JSON: {e}")
        logger.debug(f"Raw content: {content[:500]}")
        return {}


def _strip_header(text: str) -> str:
    """Remove the metadata header line from normalized text."""
    lines = text.split("\n")
    body_lines = [ln for ln in lines if not _HEADER_RE.match(ln.strip())]
    return "\n".join(body_lines).strip()


def _normalize_result(raw: dict) -> dict:
    """Normalize LLM output into a consistent structure."""
    result = _empty_enrichment()

    result["summary"] = raw.get("summary", "")

    # Key facts: support both list[str] and list[dict]
    raw_facts = raw.get("key_facts", [])
    for f in raw_facts:
        if isinstance(f, str):
            result["key_facts"].append({"text": f, "claim_type": "fact"})
        elif isinstance(f, dict) and f.get("text"):
            result["key_facts"].append({
                "text": f["text"],
                "claim_type": f.get("claim_type", "fact"),
            })

    # Entities
    raw_entities = raw.get("entities", {})
    for key in result["entities"]:
        vals = raw_entities.get(key, [])
        if isinstance(vals, list):
            result["entities"][key] = [str(v) for v in vals if v]

    result["topics"] = [str(t) for t in raw.get("topics", []) if t]
    result["theses"] = [str(t) for t in raw.get("theses", []) if t]

    # Quotes
    raw_quotes = raw.get("quotes", [])
    for q in raw_quotes:
        if isinstance(q, dict) and q.get("text"):
            result["quotes"].append({
                "speaker": q.get("speaker", "unknown"),
                "text": q["text"],
                "context": q.get("context", ""),
            })

    # Events
    raw_events = raw.get("events", [])
    for e in raw_events:
        if isinstance(e, dict) and (e.get("name") or e.get("description")):
            result["events"].append({
                "name": e.get("name", ""),
                "date": e.get("date"),
                "location": e.get("location", ""),
                "description": e.get("description", ""),
            })

    result["query_aliases"] = [str(a) for a in raw.get("query_aliases", []) if a]
    result["broll_potential"] = raw.get("broll_potential", "unknown")
    result["broll_notes"] = raw.get("broll_notes", "")

    return result


def _remove_unsupported_fake_labels(result: dict, source_text: str) -> dict:
    """
    Remove model-inferred fake/satire/disinformation verdicts.

    The enricher extracts what the source says; it is not a fact-checker.
    If the source itself does not explicitly call something fake, generated
    verdict labels are unsafe and should not enter graph_text/search_text.
    """
    if _EXPLICIT_FAKE_RE.search(source_text or ""):
        return result

    strip_unsupported_hedges = "якобы" not in (source_text or "").casefold()
    result["summary"] = _sanitize_unsupported_verdict_text(
        result.get("summary", ""),
        strip_unsupported_hedges=strip_unsupported_hedges,
    )

    cleaned_facts = []
    for fact in result.get("key_facts", []):
        if not isinstance(fact, dict):
            continue
        text = _sanitize_unsupported_verdict_text(
            fact.get("text", ""),
            strip_unsupported_hedges=strip_unsupported_hedges,
        )
        if text:
            cleaned_facts.append({**fact, "text": text})
    result["key_facts"] = cleaned_facts

    result["topics"] = [
        topic for topic in result.get("topics", [])
        if not _UNSUPPORTED_VERDICT_RE.search(str(topic))
    ]
    result["theses"] = [
        _sanitize_unsupported_verdict_text(
            thesis,
            strip_unsupported_hedges=strip_unsupported_hedges,
        )
        for thesis in result.get("theses", [])
        if not _UNSUPPORTED_VERDICT_RE.search(str(thesis))
    ]
    result["theses"] = [thesis for thesis in result["theses"] if thesis]

    for quote in result.get("quotes", []):
        if isinstance(quote, dict):
            quote["speaker"] = _sanitize_unsupported_verdict_text(
                quote.get("speaker", ""),
                strip_unsupported_hedges=strip_unsupported_hedges,
            )
            quote["context"] = _sanitize_unsupported_verdict_text(
                quote.get("context", ""),
                strip_unsupported_hedges=strip_unsupported_hedges,
            )

    for event in result.get("events", []):
        if isinstance(event, dict):
            event["description"] = _sanitize_unsupported_verdict_text(
                event.get("description", ""),
                strip_unsupported_hedges=strip_unsupported_hedges,
            )

    return result


def _sanitize_unsupported_verdict_text(
    text: str,
    strip_unsupported_hedges: bool = False,
) -> str:
    """Strip unsupported verdict wording while keeping the source claim."""
    if not text:
        return ""

    cleaned = str(text)
    cleaned = re.sub(
        r"Текст\s+имитирует[^.]*\.\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"(?:,\s*)?(?:но|хотя)?\s*не\s+явля\w+\s+реальн\w*\.?",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\bфальшив\w*\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(фейков\w*|поддельн\w*|сфабрикованн\w*)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    if strip_unsupported_hedges:
        cleaned = re.sub(
            r"\bякобы\s+",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"\s*\(якобы\)",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = cleaned.replace("заявление, от", "заявление от")
    cleaned = re.sub(
        r"\s{2,}",
        " ",
        cleaned,
    ).strip()
    return cleaned


def _empty_enrichment() -> dict:
    """Return an empty enrichment structure."""
    return {
        "summary": "",
        "key_facts": [],
        "entities": {
            "people": [],
            "organizations": [],
            "countries": [],
            "locations": [],
            "military_units": [],
            "equipment": [],
        },
        "topics": [],
        "theses": [],
        "quotes": [],
        "events": [],
        "query_aliases": [],
        "broll_potential": "unknown",
        "broll_notes": "",
    }
