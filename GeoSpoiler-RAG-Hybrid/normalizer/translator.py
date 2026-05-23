import logging
import requests

import config

logger = logging.getLogger("geospoiler.normalizer.translator")

TRANSLATOR_SYSTEM_PROMPT = """You are an expert translator and OSINT analyst. 
Your task is to ensure the provided text is in Russian. 
If the text is already entirely or predominantly in Russian, return it exactly as is, without any modifications. 
If it is in Ukrainian, English, or any other language, translate it to Russian accurately.
Preserve all original meaning, entities, quotes, formatting, and tone. 
DO NOT add any conversational filler like 'Here is the translation'. Output ONLY the final Russian text."""


def translate_to_russian_if_needed(text: str) -> str:
    """
    Translates the text to Russian using the configured LLM, 
    or leaves it unchanged if it is already in Russian.
    """
    if not text or not text.strip():
        return text

    api_key = config.TRANSLATION_API_KEY
    if not api_key or api_key == "your-api-key-here":
        logger.warning("No TRANSLATION_API_KEY configured; skipping translation.")
        return text

    payload = {
        "model": config.TRANSLATION_MODEL,
        "messages": [
            {"role": "system", "content": TRANSLATOR_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0.1,  # Low temperature for accurate translation
    }

    try:
        response = requests.post(
            f"{config.TRANSLATION_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        translated_text = data["choices"][0]["message"]["content"].strip()
        return translated_text
    except requests.Timeout:
        logger.warning("LLM translation timeout. Returning original text.")
        return text
    except Exception as e:
        logger.error(f"LLM translation error: {e}")
        return text
