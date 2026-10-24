"""Baut aus dem Wiki eine statische Seite fuer GitHub Pages (nur Lesen, kein Chat).

Aufruf: python build_pages.py [ausgabeordner]   (Standard: site/)
Der Chat-Agent braucht einen Server und laeuft nicht auf Pages.
"""
import html
import shutil
import sys
from pathlib import Path

import markdown

import wiki_tools

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "am_agent" / "static"
SEITE = """<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titel}</title>
<link rel="stylesheet" href="{pre}style.css">
</head>
<body>
<canvas id="bg" aria-hidden="true"></canvas>
<div id="glow" aria-hidden="true"></div>
<header class="bar">
  <h1><a href="{pre}index.html"><span class="logo">AM</span> Wiki</a></h1>
  <nav><a href="{pre}index.html#de">Deutsch</a> · <a href="{pre}index.html#en">English</a></nav>
</header>
<main style="display:block">
{inhalt}
<p class="meta">Der Chat-Agent läuft lokal, siehe README. Diese Seite zeigt nur das Wiki. Jede Aussage hat eine Quelle, Status und Prüfdatum stehen im Artikelkopf.</p>
</main>
<script src="{pre}fx.js"></script>
</body>
</html>
"""


def artikel(root=ROOT):
    for lang in wiki_tools.SPRACHEN:
        for p in sorted((root / "wiki" / lang).rglob("*.md")):
            meta, body = wiki_tools.parse_article(p)
            yield lang, meta, body


def render(lang, meta, body):
    teile = markdown.markdown(body, extensions=["fenced_code", "tables"])
    if "<script" in teile.lower():
        raise ValueError(f"{meta['id']}: Skript im Artikel nicht erlaubt")
    kopf = (f'<p class="meta"><span class="badge {html.escape(meta["status"])}">{html.escape(meta["status"])}</span> '
            f'geprüft am {html.escape(meta["geprueft_am"])} · Quellen: {html.escape(", ".join(meta["quellen"]))}</p>')
    return SEITE.format(lang=lang, titel=html.escape(meta["titel"]), pre="../",
                        inhalt=f'<article class="card">{kopf}{teile}</article>')


def build(out, root=ROOT):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for f in ("style.css", "fx.js"):
        shutil.copy(STATIC / f, out / f)
    karten = {lang: [] for lang in wiki_tools.SPRACHEN}
    for lang, meta, body in artikel(root):
        (out / lang).mkdir(exist_ok=True)
        (out / lang / f"{meta['id']}.html").write_text(render(lang, meta, body), encoding="utf-8")
        karten[lang].append(f'<li><a href="{lang}/{html.escape(meta["id"])}.html">{html.escape(meta["titel"])}</a> '
                            f'({html.escape(meta["status"])}, geprüft {html.escape(meta["geprueft_am"])})</li>')
    inhalt = "".join(f'<section class="card" id="{lang}"><h2>{name}</h2><ul>{"".join(karten[lang])}</ul></section>'
                     for lang, name in (("de", "Deutsch"), ("en", "English")))
    (out / "index.html").write_text(
        SEITE.format(lang="de", titel="AM-Wiki", pre="", inhalt=inhalt), encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    return out


if __name__ == "__main__":
    print(build(sys.argv[1] if len(sys.argv) > 1 else ROOT / "site"))
