import json
import tempfile
import unittest
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

import am_research_builder as rb
import am_validate

ROOT = Path(__file__).resolve().parent.parent
FIXED = lambda: datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


class Validierung(unittest.TestCase):
    def test_repo_ist_konsistent(self):
        self.assertEqual(am_validate.validate(ROOT), [])


class Builder(unittest.TestCase):
    def config(self):
        return rb.load_sources()

    def test_erfolg_speichert_datensatz(self):
        body = json.dumps([{"tag_name": "v1", "published_at": "x", "html_url": "u", "prerelease": False}]).encode()
        with tempfile.TemporaryDirectory() as d:
            ok, failed = rb.run(self.config(), ["klipper-releases"], Path(d), lambda url: (200, body), FIXED)
            self.assertEqual((ok, failed), (["klipper-releases"], []))
            rec = json.loads(next((Path(d) / "klipper-releases").glob("*.json")).read_text())
            self.assertEqual(rec["abgerufen_am"], "2026-01-02T03:04:05+00:00")
            self.assertEqual(len(rec["sha256"]), 64)
            self.assertEqual(rec["releases"][0]["tag"], "v1")
            self.assertIn("api.github.com", rec["quell_url"])

    def test_fehler_wird_protokolliert(self):
        def boom(url):
            raise urllib.error.URLError("offline")
        with tempfile.TemporaryDirectory() as d:
            ok, failed = rb.run(self.config(), ["klipper-docs"], Path(d), boom, FIXED)
            self.assertEqual((ok, failed), ([], ["klipper-docs"]))
            line = json.loads((Path(d) / "errors.jsonl").read_text().splitlines()[0])
            self.assertEqual(line["source_id"], "klipper-docs")

    def test_fremder_host_wird_abgelehnt(self):
        with self.assertRaises(ValueError):
            rb.check_host("https://evil.example/", ["marlinfw.org"])
        with self.assertRaises(ValueError):
            rb.check_host("http://marlinfw.org/", ["marlinfw.org"])

    def test_nur_get(self):
        src = (ROOT / "am_research_builder.py").read_text()
        self.assertIn('method="GET"', src)
        for verboten in ("method=\"POST\"", "method=\"PUT\"", "method=\"DELETE\"", "subprocess"):
            self.assertNotIn(verboten, src)


class Shop(unittest.TestCase):
    def test_demo_gekennzeichnet(self):
        html = (ROOT / "web-shop" / "index.html").read_text()
        self.assertIn("DEMO", html)
        js = (ROOT / "web-shop" / "app.js").read_text()
        self.assertNotIn("fetch(", js)
        self.assertNotIn("XMLHttpRequest", js)


if __name__ == "__main__":
    unittest.main()
