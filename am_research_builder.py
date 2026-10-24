#!/usr/bin/env python3
"""Konfigurierbare Recherche offizieller Websites und GitHub-Releases.

Nur lesende HTTPS-GET-Abrufe. Pro Abruf werden Abrufzeit, Quell-URL, SHA-256
und Status gespeichert; Fehler landen im Fehlerprotokoll.
"""
import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
SOURCES = ROOT / "knowledge-base" / "sources.json"
OUT_DIR = ROOT / "knowledge-base" / "fetched"
USER_AGENT = "am-research-builder/0.1 (nur lesend)"


def load_sources(path=SOURCES):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def request_url(source):
    if source["type"] == "github_releases":
        return f"https://api.github.com/repos/{source['repo']}/releases?per_page=5"
    return source["url"]


def check_host(url, allowed_hosts):
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"nur https erlaubt: {url}")
    if parsed.hostname not in allowed_hosts:
        raise ValueError(f"Host nicht in allowed_hosts: {parsed.hostname}")


def http_get(url, timeout=20):
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def summarize(source, body):
    if source["type"] != "github_releases":
        return {}
    releases = json.loads(body.decode("utf-8"))
    return {"releases": [
        {"tag": r.get("tag_name"), "published_at": r.get("published_at"),
         "url": r.get("html_url"), "prerelease": r.get("prerelease")}
        for r in releases]}


def now_utc():
    return datetime.now(timezone.utc)


def fetch_source(source, allowed_hosts, getter=http_get, clock=now_utc):
    """Gibt einen Datensatz zurueck; wirft bei Fehlern."""
    url = request_url(source)
    check_host(url, allowed_hosts)
    status, body = getter(url)
    return {
        "source_id": source["id"],
        "quell_url": url,
        "abgerufen_am": clock().isoformat(timespec="seconds"),
        "http_status": status,
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "daten_klasse": "bestaetigt",
        **summarize(source, body),
    }


def log_error(out_dir, source, exc, clock=now_utc):
    out_dir.mkdir(parents=True, exist_ok=True)
    entry = {"source_id": source["id"], "zeit": clock().isoformat(timespec="seconds"),
             "fehler": f"{type(exc).__name__}: {exc}"}
    with open(out_dir / "errors.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def run(config, only=None, out_dir=OUT_DIR, getter=http_get, clock=now_utc):
    ok, failed = [], []
    for source in config["sources"]:
        if only and source["id"] not in only:
            continue
        try:
            record = fetch_source(source, config["allowed_hosts"], getter, clock)
        except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
            log_error(out_dir, source, exc, clock)
            failed.append(source["id"])
            continue
        target = out_dir / source["id"]
        target.mkdir(parents=True, exist_ok=True)
        stamp = record["abgerufen_am"].replace(":", "").replace("-", "")
        (target / f"{stamp}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        ok.append(source["id"])
    return ok, failed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sources", default=str(SOURCES), help="Pfad zum Quellenregister")
    ap.add_argument("--only", nargs="*", help="nur diese source_ids abrufen")
    ap.add_argument("--list", action="store_true", help="Quellen anzeigen, nichts abrufen")
    args = ap.parse_args(argv)
    config = load_sources(args.sources)
    if args.list:
        for s in config["sources"]:
            print(f"{s['id']:32} {s['type']:16} {request_url(s)}")
        return 0
    ok, failed = run(config, args.only)
    print(f"abgerufen: {len(ok)}  Fehler: {len(failed)}")
    for sid in failed:
        print(f"  Fehler: {sid} (siehe knowledge-base/fetched/errors.jsonl)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
