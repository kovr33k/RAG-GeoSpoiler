"""
Web Handler — extracts article text from web URLs using trafilatura.
"""

import logging
import requests
import trafilatura

logger = logging.getLogger("geospoiler.normalizer.web")

# Timeout for web requests
REQUEST_TIMEOUT = 15

# User-Agent to avoid bot blocks
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def extract_web_text(url: str) -> str:
    """
    Extract article text from a web page.
    Returns formatted text with title and content.
    """
    try:
        # Download the page
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        # Extract text with trafilatura
        text = trafilatura.extract(
            response.text,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
            favor_recall=True,  # Get more content rather than less
            url=url,
        )

        if not text or len(text.strip()) < 50:
            # trafilatura failed — try to get at least the title
            metadata = trafilatura.extract_metadata(response.text)
            title = metadata.title if metadata else ""
            if title:
                return f'[Веб: {url} — "{title}"]\n[Содержание не удалось извлечь]'
            return f'[Веб: {url}]\n[Содержание не удалось извлечь]'

        # Get metadata for title
        metadata = trafilatura.extract_metadata(response.text)
        title = metadata.title if metadata and metadata.title else ""

        header = f'[Веб: {url}' + (f' — "{title}"' if title else "") + "]"

        # Limit very long articles
        if len(text) > 5000:
            text = text[:5000] + "\n[...текст обрезан]"

        return f"{header}\n{text}"

    except requests.Timeout:
        logger.warning(f"Timeout fetching {url}")
        return f'[Веб: {url} — таймаут]'
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return f'[Веб: {url} — ошибка загрузки]'
    except Exception as e:
        logger.error(f"Web extraction error for {url}: {e}")
        return f'[Веб: {url} — ошибка обработки]'
