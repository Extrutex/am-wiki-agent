import tempfile
import unittest
from pathlib import Path

import build_pages


class Seite(unittest.TestCase):
    def test_build(self):
        with tempfile.TemporaryDirectory() as d:
            out = build_pages.build(Path(d) / "site")
            self.assertTrue((out / "index.html").is_file())
            self.assertTrue((out / ".nojekyll").is_file())
            for lang in ("de", "en"):
                seite = (out / lang / "klipper-makros-jinja2.html").read_text(encoding="utf-8")
                self.assertIn("gcode_macro", seite)
                self.assertNotIn("<script>", seite.lower())
                self.assertIn('href="../style.css"', seite)
            self.assertIn("de/klipper-makros-jinja2.html", (out / "index.html").read_text(encoding="utf-8"))

    def test_skript_im_artikel_wird_abgelehnt(self):
        with self.assertRaises(ValueError):
            build_pages.render("de", {"id": "x", "titel": "x", "status": "offen", "geprueft_am": "-", "quellen": []},
                               "<script>alert(1)</script>")


if __name__ == "__main__":
    unittest.main()
