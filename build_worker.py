"""Bereitet das Wiki für den Cloudflare Worker auf (worker/src/wiki.json).

Aufruf: python build_worker.py
Schreibt außerdem worker/test/suche_referenz.json: Treffer der Python-Suche für Beispielfragen.
Der JS-Test prüft damit, dass der Worker genau dieselben Abschnitte findet wie am_agent/retrieval.py.
"""
import json
from pathlib import Path

import wiki_tools
from am_agent import retrieval

ROOT = Path(__file__).resolve().parent
WORKER = ROOT / "worker"
REFERENZ_FRAGEN = {
    "de": ["Wie greife ich in einem Makro auf Parameter zu?", "params rawparams", "Jinja2 Variablen setzen",
           "Wie speichere ich einen Wert zwischen zwei Makroaufrufen?", "Wetter morgen in Berlin"],
    "en": ["How do I read macro parameters?", "params rawparams", "jinja2 variables",
           "save a value between macro calls", "weather tomorrow"],
}


def abrufe(root, quellen):
    """Letzter Abruf je Quelle (wie Agent._abrufe)."""
    out = []
    for q in quellen:
        files = sorted((Path(root) / "knowledge-base" / "fetched" / q).glob("*.json"))
        if files:
            rec = json.loads(files[-1].read_text(encoding="utf-8"))
            out.append({"source_id": q, "abgerufen_am": rec["abgerufen_am"], "sha256": rec["sha256"]})
    return out


def index_daten(root=ROOT):
    daten = {"sprachen": {}}
    for lang in wiki_tools.SPRACHEN:
        daten["sprachen"][lang] = [
            {"artikel_id": c.artikel_id, "titel": c.titel, "abschnitt": c.abschnitt, "text": c.text,
             "status": c.status, "quellen": abrufe(root, c.quellen)}
            for c in retrieval.load_chunks(root, lang)]
    return daten


def referenz(root=ROOT):
    out = {}
    for lang, fragen in REFERENZ_FRAGEN.items():
        idx = retrieval.Index(retrieval.load_chunks(root, lang), lang)
        out[lang] = {f: [c.key for c in idx.search(f)] for f in fragen}
    return out


def build(root=ROOT, worker=WORKER):
    worker = Path(worker)
    (worker / "src").mkdir(parents=True, exist_ok=True)
    (worker / "test").mkdir(parents=True, exist_ok=True)
    ziel = worker / "src" / "wiki.json"
    ziel.write_text(json.dumps(index_daten(root), ensure_ascii=False), encoding="utf-8")
    (worker / "test" / "suche_referenz.json").write_text(
        json.dumps(referenz(root), ensure_ascii=False, indent=1), encoding="utf-8")
    return ziel


if __name__ == "__main__":
    print(build())
