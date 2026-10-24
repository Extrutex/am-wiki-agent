#!/usr/bin/env python3
"""Pruefung der Wiki-Artikel (wiki/<sprache>/...): Kopfdaten, Quellen, Beispiele, Zweisprachigkeit."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPRACHEN = ("de", "en")
PFLICHT = ("id", "sprache", "titel", "firmware", "status", "quellen", "geprueft_am")
STATUS = {"bestaetigt", "offen", "erfahrungswert"}
BEISPIEL = re.compile(r"<!-- beispiel: (\S+) -->\n```\w*\n(.*?)\n```", re.S)


def parse_article(path):
    text = Path(path).read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
    if not m:
        raise ValueError(f"{path}: Kopfdaten fehlen")
    meta = {}
    for line in m.group(1).splitlines():
        key, _, val = line.partition(":")
        meta[key.strip()] = val.strip()
    for key in ("quellen", "beispiele"):
        meta[key] = [v.strip() for v in meta.get(key, "").split(",") if v.strip()]
    return meta, m.group(2)


def validate(root=ROOT, source_ids=None, fetched=None):
    import json
    fetched = fetched if fetched is not None else root / "knowledge-base" / "fetched"
    if source_ids is None:
        reg = json.loads((root / "knowledge-base" / "sources.json").read_text(encoding="utf-8"))
        source_ids = {s["id"] for s in reg["sources"]}
    errors, by_id = [], {}
    for lang in SPRACHEN:
        for path in sorted((root / "wiki" / lang).rglob("*.md")):
            rel = path.relative_to(root)
            try:
                meta, body = parse_article(path)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            for key in PFLICHT:
                if not meta.get(key):
                    errors.append(f"{rel}: Kopfdatum '{key}' fehlt")
            if meta.get("sprache") != lang:
                errors.append(f"{rel}: sprache passt nicht zum Ordner")
            if meta.get("status") not in STATUS:
                errors.append(f"{rel}: unbekannter status {meta.get('status')}")
            by_id.setdefault(meta.get("id"), {})[lang] = (path, meta)
            for q in meta["quellen"]:
                if q not in source_ids:
                    errors.append(f"{rel}: unbekannte Quelle {q}")
                elif meta.get("status") == "bestaetigt" and not list((fetched / q).glob("*.json")):
                    errors.append(f"{rel}: bestaetigt, aber kein Abruf fuer {q}")
            if meta.get("status") == "bestaetigt" and not meta["quellen"]:
                errors.append(f"{rel}: bestaetigt braucht Quellen")
            for bsp in meta["beispiele"]:
                if not (root / "wiki" / "beispiele" / bsp).is_file():
                    errors.append(f"{rel}: Beispiel {bsp} fehlt")
            for name, code in BEISPIEL.findall(body):
                f = root / "wiki" / "beispiele" / name
                if not f.is_file() or f.read_text(encoding="utf-8").rstrip("\n") != code:
                    errors.append(f"{rel}: Codeblock weicht von Beispieldatei {name} ab")
    for aid, langs in by_id.items():
        for lang in SPRACHEN:
            if lang not in langs:
                errors.append(f"Artikel {aid}: Sprache {lang} fehlt")
        if len(langs) == 2:
            (_, a), (_, b) = langs["de"], langs["en"]
            if a["quellen"] != b["quellen"] or a["beispiele"] != b["beispiele"]:
                errors.append(f"Artikel {aid}: Quellen/Beispiele in de und en unterschiedlich")
    return errors
