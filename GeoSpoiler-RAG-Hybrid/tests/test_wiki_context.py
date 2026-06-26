import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loader import wiki_context  # noqa: E402


class WikiPromptContextTests(unittest.TestCase):
    def test_claim_guardrails_are_included_in_prompt_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            (wiki_dir / "claims").mkdir(parents=True)
            (wiki_dir / "claims" / "claim.md").write_text(
                "# Claim\n\n"
                "## Evidence\n\n"
                "- telegram:1:10 - source_claim: Evidence.\n\n"
                "## Guardrails\n\n"
                "- Use only cited evidence.\n"
                "- Separate fake/deepfake evidence from support claims.\n\n"
                "## Related\n\n"
                "- topics/example.md\n",
                encoding="utf-8",
            )
            context = {
                "pages": [
                    {
                        "page_path": "claims/claim.md",
                        "title": "Claim",
                        "score": 10,
                        "snippet": "Evidence snippet",
                        "source_ids": ["telegram:1:10"],
                        "resolved_sources": [],
                    }
                ]
            }

            with patch.object(wiki_context.config, "WIKI_DIR", wiki_dir):
                formatted = wiki_context._format_wiki_prompt_context(context)

        self.assertIn("claim_guardrails:", formatted)
        self.assertIn("Use only cited evidence.", formatted)
        self.assertIn("Separate fake/deepfake evidence from support claims.", formatted)


if __name__ == "__main__":
    unittest.main()
