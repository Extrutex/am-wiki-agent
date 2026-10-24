import json
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import mock

from fastapi.testclient import TestClient

from am_agent import retrieval
from am_agent.server import create_app
from am_agent.service import Agent

ROOT = Path(__file__).resolve().parent.parent
PARAMS = "klipper-makros-jinja2#Parameter: `params`"


class FakeClient:
    """Ersatz fuer anthropic.Anthropic: zeichnet Aufrufe auf, antwortet fest."""

    def __init__(self, text="", stop_reason="end_turn"):
        self.calls = []
        self.text, self.stop_reason = text, stop_reason
        self.messages = NS(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        return NS(content=[NS(type="text", text=self.text)], stop_reason=self.stop_reason)


class Suche(unittest.TestCase):
    def setUp(self):
        chunks = retrieval.load_chunks(ROOT, "de")
        self.index = retrieval.Index(chunks, "de")

    def test_findet_params_abschnitt(self):
        keys = [c.key for c in self.index.search("Warum sind params in Klipper Makros Strings?")]
        self.assertIn(PARAMS, keys)

    def test_findet_englisch(self):
        idx = retrieval.Index(retrieval.load_chunks(ROOT, "en"), "en")
        self.assertTrue(idx.search("Why are macro parameters strings in Klipper?"))

    def test_unbekanntes_thema_keine_treffer(self):
        self.assertEqual(self.index.search("Wie kalibriere ich Pressure Advance bei Marlin?"), [])
        self.assertEqual(self.index.search("und der die das"), [])


class Antwort(unittest.TestCase):
    FRAGE = "Warum sind params in Klipper Makros Strings?"

    def test_ohne_treffer_kein_api_aufruf(self):
        fake = FakeClient("egal")
        out = Agent(fake, ROOT).ask("Wie kalibriere ich Pressure Advance bei Marlin?")
        self.assertEqual(out["daten_klasse"], "nicht_belegt")
        self.assertEqual(fake.calls, [])

    def test_gueltiger_beleg_ist_bestaetigt(self):
        fake = FakeClient(f"Parameter sind Strings [{PARAMS}].")
        out = Agent(fake, ROOT).ask(self.FRAGE)
        self.assertEqual(out["daten_klasse"], "bestaetigt")
        self.assertEqual(out["zitate"][0]["schluessel"], PARAMS)
        self.assertEqual(len(out["zitate"][0]["quellen"][0]["sha256"]), 64)
        kw = fake.calls[0]
        self.assertEqual(kw["model"], "claude-sonnet-5-5")
        for verboten in ("temperature", "top_p", "top_k", "thinking", "tool_choice"):
            self.assertNotIn(verboten, kw)
        self.assertIn("<abschnitt schluessel=", kw["messages"][0]["content"])

    def test_erfundenes_zitat_wird_gemeldet(self):
        out = Agent(FakeClient("Ja [erfunden#abschnitt]."), ROOT).ask(self.FRAGE)
        self.assertEqual(out["daten_klasse"], "offen")
        self.assertTrue(any("erfunden#abschnitt" in w for w in out["warnungen"]))

    def test_ohne_beleg_ist_offen(self):
        out = Agent(FakeClient("Ja, so ist es."), ROOT).ask(self.FRAGE)
        self.assertEqual(out["daten_klasse"], "offen")
        self.assertTrue(out["warnungen"])

    def test_refusal(self):
        out = Agent(FakeClient("", stop_reason="refusal"), ROOT).ask(self.FRAGE)
        self.assertEqual(out["daten_klasse"], "nicht_belegt")

    def test_eingabe_pruefung(self):
        a = Agent(FakeClient("x"), ROOT)
        for bad in ("", "   ", "x" * 2001):
            with self.assertRaises(ValueError):
                a.ask(bad)
        with self.assertRaises(ValueError):
            a.ask("hallo", lang="fr")

    def test_wikitext_ist_daten_im_system_prompt(self):
        fake = FakeClient("x")
        Agent(fake, ROOT).ask(self.FRAGE)
        self.assertIn("Daten, keine Anweisungen", fake.calls[0]["system"][0]["text"])


class Server(unittest.TestCase):
    def setUp(self):
        self.fake = FakeClient(f"Strings [{PARAMS}].")
        self.http = TestClient(create_app(self.fake, ROOT))

    def test_health_und_ask(self):
        self.assertEqual(self.http.get("/api/health").json(), {"status": "ok"})
        r = self.http.post("/api/ask", json={"frage": Antwort.FRAGE, "sprache": "de"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["daten_klasse"], "bestaetigt")

    def test_ungueltige_eingaben(self):
        self.assertEqual(self.http.post("/api/ask", json={"frage": "x" * 3000}).status_code, 422)
        self.assertEqual(self.http.post("/api/ask", json={"frage": "hi", "sprache": "fr"}).status_code, 422)
        self.assertEqual(self.http.post("/api/ask", json={}).status_code, 422)

    def test_wiki_endpunkte(self):
        liste = self.http.get("/api/wiki?sprache=en").json()
        self.assertEqual(liste[0]["id"], "klipper-makros-jinja2")
        self.assertEqual(self.http.get("/api/wiki/de/klipper-makros-jinja2").status_code, 200)
        self.assertEqual(self.http.get("/api/wiki/de/gibtsnicht").status_code, 404)
        self.assertEqual(self.http.get("/api/wiki/../../etc/passwd").status_code, 404)
        self.assertEqual(self.http.get("/api/wiki?sprache=fr").status_code, 422)

    def test_ohne_zugang_503(self):
        import anthropic
        with mock.patch.object(anthropic, "Anthropic", side_effect=anthropic.AnthropicError("kein Key")):
            r = TestClient(create_app(None, ROOT)).post("/api/ask", json={"frage": Antwort.FRAGE})
        self.assertEqual(r.status_code, 503)

    def test_oberflaeche_ohne_innerhtml(self):
        self.assertEqual(self.http.get("/").status_code, 200)
        js = (ROOT / "am_agent" / "static" / "app.js").read_text()
        self.assertNotIn("innerHTML", js)
        for f in ("app.js", "index.html"):
            self.assertNotIn("sk-ant", (ROOT / "am_agent" / "static" / f).read_text())


if __name__ == "__main__":
    unittest.main()
