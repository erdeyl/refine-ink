import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import md_to_html
import pdf_to_markdown
import verify_references


class TestPr6Followups(unittest.TestCase):
    def test_next_section_regex_handles_appendix_variants(self):
        pattern = pdf_to_markdown._NEXT_SECTION_RE
        self.assertTrue(pattern.search("Appendix A"))
        self.assertTrue(pattern.search("Appendix B: Tables"))
        self.assertTrue(pattern.search("Supplementary Materials"))
        self.assertTrue(pattern.search("Acknowledgments"))
        self.assertFalse(pattern.search("Acknowledgments of funding"))

    def test_output_always_contains_suspicion_confidence(self):
        ref = {"title": "alpha beta gamma", "doi": "10.1234/abc.def"}
        match = verify_references.MatchResult(
            found=True,
            source="crossref",
            title="alpha beta delta",
            doi="10.1234/zzz",
            similarity=0.70,
            extra={},
        )
        out = verify_references._build_output(1, ref, match, "raw")
        self.assertIn("suspicion_confidence", out)
        self.assertIsNone(out["suspicion_confidence"])
        self.assertIsNone(out["verified_by"])

        suspicious_ref = {
            "title": "a plausible long title",
            "doi": "10.1234/example-doi",
        }
        missing = verify_references.MatchResult(
            found=False,
            source=None,
            title=None,
            doi=None,
            similarity=0.0,
            extra={},
        )
        suspicious_out = verify_references._build_output(2, suspicious_ref, missing, "raw")
        self.assertEqual(suspicious_out["status"], "suspicious")
        self.assertEqual(suspicious_out["confidence"], 0)
        self.assertEqual(suspicious_out["suspicion_confidence"], 40)

    def test_doi_normalization_preserves_significant_separators(self):
        normalized = verify_references.normalize_doi_value("https://doi.org/10.1234/abc.def")
        self.assertEqual(normalized, "10.1234/abc.def")
        self.assertNotEqual(
            verify_references.normalize_doi_value("10.1234/abc.def"),
            verify_references.normalize_doi_value("10.1234/abc/def"),
        )

    def test_title_sanitization_strips_markup(self):
        safe_title = md_to_html.sanitize_title("<script>alert(1)</script>Paper <b>Title</b>")
        self.assertNotIn("<", safe_title)
        self.assertNotIn(">", safe_title)
        self.assertIn("Paper", safe_title)
        self.assertIn("Title", safe_title)


if __name__ == "__main__":
    unittest.main()
