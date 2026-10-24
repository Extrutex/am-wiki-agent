#!/usr/bin/env python3
"""Offline-Validierung von Spezifikation und Quellenregister."""
import json
import sys

import wiki_tools
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
SOURCE_TYPES = {"website", "github_releases"}


def validate(root=ROOT):
    errors = []
    spec = json.loads((root / "am_specialist_spec.json").read_text(encoding="utf-8"))
    reg = json.loads((root / "knowledge-base" / "sources.json").read_text(encoding="utf-8"))
    hosts = set(reg.get("allowed_hosts", []))
    ids = [s.get("id") for s in reg.get("sources", [])]
    if len(ids) != len(set(ids)):
        errors.append("doppelte source_id im Register")
    for s in reg["sources"]:
        sid = s.get("id", "?")
        for key in ("id", "topic", "type", "url", "owner", "agent"):
            if not s.get(key):
                errors.append(f"{sid}: Feld '{key}' fehlt")
        if s.get("type") not in SOURCE_TYPES:
            errors.append(f"{sid}: unbekannter Typ {s.get('type')}")
        if s.get("type") == "github_releases" and not s.get("repo"):
            errors.append(f"{sid}: 'repo' fehlt")
        parsed = urlparse(s.get("url", ""))
        if parsed.scheme != "https":
            errors.append(f"{sid}: URL nicht https")
        if parsed.hostname not in hosts:
            errors.append(f"{sid}: Host {parsed.hostname} nicht in allowed_hosts")
    agent_ids = {a["id"] for a in spec["agents"]}
    for a in spec["agents"]:
        if not (root / a["datei"]).is_file():
            errors.append(f"Agent {a['id']}: Datei {a['datei']} fehlt")
        for q in a["quellen"]:
            if q not in ids:
                errors.append(f"Agent {a['id']}: unbekannte Quelle {q}")
        for u in a["uebergabe_an"]:
            if u not in agent_ids:
                errors.append(f"Agent {a['id']}: unbekannte Uebergabe {u}")
    for s in reg["sources"]:
        if s.get("agent") not in agent_ids:
            errors.append(f"{s['id']}: unbekannter Agent {s.get('agent')}")
    if set(spec.get("datenklassen", {})) != {"bestaetigt", "beispiel"}:
        errors.append("datenklassen muss genau 'bestaetigt' und 'beispiel' enthalten")
    errors += wiki_tools.validate(root)
    return errors


if __name__ == "__main__":
    problems = validate()
    for p in problems:
        print("FEHLER:", p)
    print("Validierung:", "fehlgeschlagen" if problems else "ok")
    sys.exit(1 if problems else 0)
