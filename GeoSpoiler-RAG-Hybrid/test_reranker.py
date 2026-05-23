import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

import reranker  # noqa: E402


class RerankerTests(unittest.TestCase):
    def test_sync_wrapper_returns_model_order(self):
        async def fake_rerank(query, passages, top_n):
            return [
                {"index": 1, "relevance_score": 0.9},
                {"index": 0, "relevance_score": 0.8},
            ]

        with patch.object(reranker.config, "RERANKER_ENABLED", True):
            with patch.object(reranker, "lightrag_rerank_func", fake_rerank):
                result = reranker.rerank("q", ["a", "b"])

        self.assertEqual(result, ["b", "a"])

    def test_sync_wrapper_returns_original_passages_when_disabled(self):
        with patch.object(reranker.config, "RERANKER_ENABLED", False):
            result = reranker.rerank("q", ["a", "b"])

        self.assertEqual(result, ["a", "b"])
