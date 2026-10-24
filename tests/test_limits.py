import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import mock

from fastapi.testclient import TestClient

from am_agent.limits import Gesperrt, Limits
from am_agent.server import create_app
from tests.test_agent import Antwort, FakeClient, PARAMS, ROOT


class Uhr:
    def __init__(self, t=1_800_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


class Grenzen(unittest.TestCase):
    def test_rate_pro_minute(self):
        u = Uhr()
        lim = Limits(pro_minute=2, pro_tag=100, uhr=u)
        lim.pruefen("a"); lim.pruefen("a")
        with self.assertRaises(Gesperrt) as g:
            lim.pruefen("a")
        self.assertTrue(0 < g.exception.warte_s <= 60)
        lim.pruefen("b")  # andere IP unabhaengig
        u.t += 61
        lim.pruefen("a")

    def test_rate_pro_tag(self):
        u = Uhr()
        lim = Limits(pro_minute=100, pro_tag=3, uhr=u)
        for _ in range(3):
            lim.pruefen("a")
        with self.assertRaises(Gesperrt):
            lim.pruefen("a")
        u.t += 86401
        lim.pruefen("a")

    def test_tagesbudget_und_tageswechsel(self):
        u = Uhr()
        lim = Limits(tagesbudget=1000, uhr=u)
        lim.pruefen("a")
        lim.buchen(600, 500)
        self.assertFalse(lim.frei())
        with self.assertRaises(Gesperrt):
            lim.pruefen("b")
        u.t += 86400
        self.assertTrue(lim.frei())
        lim.pruefen("b")

    def test_speichern_nur_zaehler(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "u.json"
            u = Uhr()
            a = Limits(datei=f, uhr=u)
            a.pruefen("1.2.3.4")
            a.buchen(10, 20)
            text = f.read_text()
            self.assertNotIn("1.2.3.4", text)
            self.assertEqual(Limits(datei=f, uhr=u).tokens_heute(), 30)
            u.t += 86400
            self.assertEqual(Limits(datei=f, uhr=u).tokens_heute(), 0)

    def test_kaputte_datei_wird_ignoriert(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "u.json"
            f.write_text("{kaputt")
            self.assertEqual(Limits(datei=f).tokens_heute(), 0)

    def test_env(self):
        with mock.patch.dict(os.environ, {"AM_TAGESBUDGET_TOKENS": "5", "AM_RATE_PRO_MIN": "x"}):
            lim = Limits.from_env()
        self.assertEqual((lim.tagesbudget, lim.pro_minute), (5, 5))


def fake_mit_usage(text):
    fake = FakeClient(text)
    orig = fake._create

    def create(**kw):
        r = orig(**kw)
        r.usage = NS(input_tokens=100, cache_creation_input_tokens=50, cache_read_input_tokens=0, output_tokens=40)
        return r
    fake.messages = NS(create=create)
    return fake


class ServerLimits(unittest.TestCase):
    def app(self, **kw):
        fake = fake_mit_usage(f"Strings [{PARAMS}].")
        lim = Limits(**kw)
        return TestClient(create_app(fake, ROOT, limits=lim)), fake, lim

    def test_tokens_werden_gebucht(self):
        http, _, lim = self.app()
        r = http.post("/api/ask", json={"frage": Antwort.FRAGE})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["nutzung"], {"input": 150, "output": 40})
        self.assertEqual(lim.tokens_heute(), 190)

    def test_rate_limit_429_mit_retry_after(self):
        http, fake, _ = self.app(pro_minute=1)
        self.assertEqual(http.post("/api/ask", json={"frage": Antwort.FRAGE}).status_code, 200)
        r = http.post("/api/ask", json={"frage": Antwort.FRAGE})
        self.assertEqual(r.status_code, 429)
        self.assertIn("Retry-After", r.headers)
        self.assertEqual(len(fake.calls), 1)  # kein zweiter Claude-Aufruf

    def test_budget_leer_kein_aufruf_auch_fuer_cfg(self):
        http, fake, lim = self.app(tagesbudget=100)
        http.post("/api/ask", json={"frage": Antwort.FRAGE})
        self.assertEqual(http.get("/api/health").json()["kontingent"], "leer")
        for pfad, body in (("/api/ask", {"frage": Antwort.FRAGE}), ("/api/cfg", {"wunsch": "x", "cfg": "[a]\nb: 1"})):
            r = http.post(pfad, json=body)
            self.assertEqual(r.status_code, 429, pfad)
        self.assertEqual(len(fake.calls), 1)

    def test_eigener_schluessel_umgeht_limits_und_zaehlt_nicht(self):
        import anthropic
        fake = fake_mit_usage(f"Strings [{PARAMS}].")
        lim = Limits(tagesbudget=1, pro_minute=1, pro_tag=1)
        lim.buchen(5, 5)  # Budget schon leer
        with mock.patch.object(anthropic, "Anthropic", return_value=fake):
            http = TestClient(create_app(None, ROOT, limits=lim))
            for _ in range(3):
                r = http.post("/api/ask", json={"frage": Antwort.FRAGE}, headers={"X-Anthropic-Key": "k"})
                self.assertEqual(r.status_code, 200)
        self.assertEqual(lim.tokens_heute(), 10)

    def test_proxy_header_nur_wenn_vertraut(self):
        http, _, _ = self.app(pro_minute=1)
        h = lambda ip: {"X-Forwarded-For": ip}
        self.assertEqual(http.post("/api/ask", json={"frage": Antwort.FRAGE}, headers=h("1.1.1.1")).status_code, 200)
        # ohne AM_TRUST_PROXY wird der Header ignoriert: gleiche IP, also gesperrt
        self.assertEqual(http.post("/api/ask", json={"frage": Antwort.FRAGE}, headers=h("2.2.2.2")).status_code, 429)
        with mock.patch.dict(os.environ, {"AM_TRUST_PROXY": "1"}):
            http, _, _ = self.app(pro_minute=1)
            self.assertEqual(http.post("/api/ask", json={"frage": Antwort.FRAGE}, headers=h("1.1.1.1")).status_code, 200)
            self.assertEqual(http.post("/api/ask", json={"frage": Antwort.FRAGE}, headers=h("2.2.2.2")).status_code, 200)
            self.assertEqual(http.post("/api/ask", json={"frage": Antwort.FRAGE}, headers=h("1.1.1.1")).status_code, 429)


if __name__ == "__main__":
    unittest.main()
