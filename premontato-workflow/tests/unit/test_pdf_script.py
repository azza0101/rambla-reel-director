import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[2] / "worker"))
from pdf_script import extract_pdf_text


class PdfScriptTests(unittest.TestCase):
    def test_extracts_each_page_in_layout_mode_and_joins_pages(self):
        pages = [unittest.mock.Mock(), unittest.mock.Mock()]
        pages[0].extract_text.return_value = "SCENA 01 INT. SALOTTO - SERA"
        pages[1].extract_text.return_value = "CLAUDIO\n  Zenzero e limone?"
        reader = unittest.mock.Mock(pages=pages, is_encrypted=False)
        with patch("pypdf.PdfReader", return_value=reader):
            text = extract_pdf_text("script.pdf")
        self.assertEqual(text, "SCENA 01 INT. SALOTTO - SERA\n\nCLAUDIO\n  Zenzero e limone?")
        self.assertTrue(all(page.extract_text.call_args.kwargs["extraction_mode"] == "layout" for page in pages))


if __name__ == "__main__":
    unittest.main()
