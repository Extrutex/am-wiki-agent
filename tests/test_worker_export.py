import json
import tempfile
import unittest
from pathlib import Path

import build_worker
from am_agent import retrieval


class WorkerExport(unittest.TestCase):
    def test_export_enthaelt_alle_abschnitte_mit_quellen(self):
        with tempfile.TemporaryDirectory() as d:
            ziel = build_worker.build(worker=Path(d))
            daten = json.loads(ziel.read_text(encoding="utf-8"))
            for lang in ("de", "en"):
                chunks = retrieval.load_chunks(build_worker.ROOT, lang)
                export = daten["sprachen"][lang]
                self.assertEqual([f'{c["artikel_id"]}#{c["abschnitt"]}' for c in export], [c.key for c in chunks])
                self.assertTrue(all(c["quellen"] and c["quellen"][0]["sha256"] for c in export))
            ref = json.loads((Path(d) / "test" / "suche_referenz.json").read_text(encoding="utf-8"))
            self.assertEqual(ref["de"]["Wetter morgen in Berlin"], [])
            self.assertTrue(ref["de"]["params rawparams"])


if __name__ == "__main__":
    unittest.main()
