"""Baut aus dem Wiki eine statische Seite fuer GitHub Pages (nur Lesen, kein Chat).

Aufruf: python build_pages.py [ausgabeordner]   (Standard: site/)
Der Chat-Agent braucht einen Server und laeuft nicht auf Pages.
"""
import html
import os
import json
import re
import shutil
import sys
from pathlib import Path

import markdown

import wiki_tools

ROOT = Path(__file__).resolve().parent
BASE = os.environ.get("AM_SITE_URL", "https://extrutex.github.io/am-wiki-agent/").rstrip("/") + "/"
STATIC = ROOT / "am_agent" / "static"
SEITE = """<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titel}</title>
{meta}
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


def beschreibung(body, limit=160):
    """Erster Absatz nach 'Kurzfassung'/'Summary' (sonst erster Absatz), ohne Markdown, auf limit gekuerzt."""
    m = re.search(r"^##\s+(?:Kurzfassung|Summary)\s*\n+(.+?)(?:\n\n|\Z)", body, re.M | re.S)
    text = m.group(1) if m else next((b for b in body.split("\n\n") if b.strip() and not b.startswith("#")), "")
    text = re.sub(r"[`*#>\[\]]|\(https?://[^)]*\)", "", " ".join(text.split()))
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def meta_tags(lang, titel, desc, pfad, alternativen=None, json_ld=None, typ="article"):
    url = BASE + pfad
    zeilen = [
        f'<meta name="description" content="{html.escape(desc, quote=True)}">',
        f'<link rel="canonical" href="{url}">',
        '<meta name="robots" content="index,follow">',
        f'<meta property="og:type" content="{typ}">',
        f'<meta property="og:title" content="{html.escape(titel, quote=True)}">',
        f'<meta property="og:description" content="{html.escape(desc, quote=True)}">',
        f'<meta property="og:url" content="{url}">',
        f'<meta property="og:locale" content="{"de_DE" if lang == "de" else "en_US"}">',
        '<meta name="twitter:card" content="summary">',
    ]
    for alt_lang, alt_pfad in (alternativen or {}).items():
        zeilen.append(f'<link rel="alternate" hreflang="{alt_lang}" href="{BASE}{alt_pfad}">')
    if alternativen:
        zeilen.append(f'<link rel="alternate" hreflang="x-default" href="{BASE}{alternativen.get("de", pfad)}">')
    if json_ld:
        daten = json.dumps(json_ld, ensure_ascii=False).replace("</", "<\\/")
        zeilen.append(f'<script type="application/ld+json">{daten}</script>')
    return "\n".join(zeilen)


def render(lang, meta, body, alternativen=None):
    teile = markdown.markdown(body, extensions=["fenced_code", "tables"])
    if "<script" in teile.lower():
        raise ValueError(f"{meta['id']}: Skript im Artikel nicht erlaubt")
    kopf = (f'<p class="meta"><span class="badge {html.escape(meta["status"])}">{html.escape(meta["status"])}</span> '
            f'geprüft am {html.escape(meta["geprueft_am"])} · Quellen: {html.escape(", ".join(meta["quellen"]))}</p>')
    pfad = f"{lang}/{meta['id']}.html"
    ld = {"@context": "https://schema.org", "@type": "TechArticle", "headline": meta["titel"],
          "inLanguage": lang, "dateModified": meta["geprueft_am"], "url": BASE + pfad,
          "isBasedOn": meta["quellen"]}
    tags = meta_tags(lang, meta["titel"], beschreibung(body), pfad, alternativen, ld)
    return SEITE.format(lang=lang, titel=html.escape(meta["titel"]) + " – AM-Wiki", pre="../", meta=tags,
                        inhalt=f'<article class="card">{kopf}{teile}</article>')


def build(out, root=ROOT):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for f in ("style.css", "fx.js"):
        shutil.copy(STATIC / f, out / f)
    karten = {lang: [] for lang in wiki_tools.SPRACHEN}
    alle = list(artikel(root))
    seiten = []
    for lang, meta, body in alle:
        alt = {l: f"{l}/{m['id']}.html" for l, m, _ in alle if m["id"] == meta["id"]}
        (out / lang).mkdir(exist_ok=True)
        (out / lang / f"{meta['id']}.html").write_text(render(lang, meta, body, alt if len(alt) > 1 else None), encoding="utf-8")
        seiten.append((f"{lang}/{meta['id']}.html", meta["geprueft_am"]))
        karten[lang].append(f'<li><a href="{lang}/{html.escape(meta["id"])}.html">{html.escape(meta["titel"])}</a> '
                            f'({html.escape(meta["status"])}, geprüft {html.escape(meta["geprueft_am"])})</li>')
    inhalt = "".join(f'<section class="card" id="{lang}"><h2>{name}</h2><ul>{"".join(karten[lang])}</ul></section>'
                     for lang, name in (("de", "Deutsch"), ("en", "English")))
    desc = "Wiki für 3D-Druck-Firmware (Klipper, Marlin, RepRap): jede Aussage mit Quelle, Beispiele getestet."
    ld = {"@context": "https://schema.org", "@type": "WebSite", "name": "AM-Wiki", "url": BASE,
          "inLanguage": ["de", "en"], "description": desc}
    (out / "index.html").write_text(
        SEITE.format(lang="de", titel="AM-Wiki – 3D-Druck-Firmware mit Quellen", pre="",
                     meta=meta_tags("de", "AM-Wiki – 3D-Druck-Firmware mit Quellen", desc, "", None, ld, "website"),
                     inhalt=inhalt), encoding="utf-8")
    urls = [("", max((d for _, d in seiten), default=None))] + seiten
    eintraege = "".join(f"<url><loc>{BASE}{p}</loc>" + (f"<lastmod>{d}</lastmod>" if d else "") + "</url>" for p, d in urls)
    (out / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{eintraege}</urlset>\n',
        encoding="utf-8")
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {BASE}sitemap.xml\n", encoding="utf-8")
    (out / "404.html").write_text(SEITE.format(
        lang="de", titel="Nicht gefunden – AM-Wiki", pre=BASE,
        meta='<meta name="robots" content="noindex">',
        inhalt='<section class="card"><h2>Seite nicht gefunden</h2><p><a href="' + BASE + '">Zur Startseite</a></p></section>'),
        encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    return out


if __name__ == "__main__":
    print(build(sys.argv[1] if len(sys.argv) > 1 else ROOT / "site"))
