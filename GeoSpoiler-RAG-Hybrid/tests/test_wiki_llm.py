import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from retrieval import wiki_llm  # noqa: E402


class WikiLlmConfigTests(unittest.TestCase):
    def test_wiki_llm_config_prefers_dedicated_values(self):
        with patch.multiple(
            wiki_llm.config,
            WIKI_LLM_API_KEY="wiki-key",
            WIKI_LLM_BASE_URL="https://wiki.example/v1",
            WIKI_LLM_MODEL="wiki-model",
            ENRICHMENT_API_KEY="enrichment-key",
            ENRICHMENT_BASE_URL="https://enrichment.example/v1",
            ENRICHMENT_MODEL="enrichment-model",
        ):
            resolved = wiki_llm.wiki_llm_config()

        self.assertEqual(resolved.api_key, "wiki-key")
        self.assertEqual(resolved.base_url, "https://wiki.example/v1")
        self.assertEqual(resolved.model, "wiki-model")

    def test_wiki_llm_config_falls_back_to_enrichment_values(self):
        with patch.multiple(
            wiki_llm.config,
            WIKI_LLM_API_KEY="",
            WIKI_LLM_BASE_URL="",
            WIKI_LLM_MODEL="",
            ENRICHMENT_API_KEY="enrichment-key",
            ENRICHMENT_BASE_URL="https://enrichment.example/v1",
            ENRICHMENT_MODEL="enrichment-model",
        ):
            resolved = wiki_llm.wiki_llm_config()

        self.assertEqual(resolved.api_key, "enrichment-key")
        self.assertEqual(resolved.base_url, "https://enrichment.example/v1")
        self.assertEqual(resolved.model, "enrichment-model")


if __name__ == "__main__":
    unittest.main()
