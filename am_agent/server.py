"""FastAPI-Server: Chat-API und Wiki-Anzeige. Start: uvicorn am_agent.server:app"""
from pathlib import Path

import os

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import wiki_tools
from am_agent.env import load_env
from am_agent.limits import Gesperrt, Limits
from am_agent.service import Agent, ROOT

load_env(ROOT / ".env")  # Schluessel nur aus der Umgebung/.env, nie aus dem Browser

STATIC = Path(__file__).resolve().parent / "static"


class Frage(BaseModel):
    frage: str
    sprache: str = "de"


class CfgWunsch(BaseModel):
    wunsch: str
    cfg: str
    sprache: str = "de"
    pin_freigabe: bool = False
    pin_bestaetigung: str = ""


def create_app(client=None, root=ROOT, limits=None):
    app = FastAPI(title="AM-Wiki-Agent")
    limits = limits or Limits.from_env()
    holder = {"agent": None}

    def agent(eigener=None):
        if holder["agent"] is None:
            c = client
            if c is None:
                import anthropic  # Server-Schluessel nur aus Umgebung/.env
                try:
                    c = anthropic.Anthropic()
                except Exception as exc:
                    if eigener is None:
                        raise HTTPException(503, "Claude-API nicht konfiguriert: Server-Schlüssel fehlt, eigenen Schlüssel eingeben") from exc
                    c = None  # kein Server-Schluessel; die Anfrage nutzt den eigenen
            holder["agent"] = Agent(c, root)
        elif holder["agent"].client is None and eigener is None:
            raise HTTPException(503, "Claude-API nicht konfiguriert: Server-Schlüssel fehlt, eigenen Schlüssel eingeben")
        return holder["agent"]

    @app.get("/api/health")
    def health():
        return {"status": "ok", "kontingent": "frei" if limits.frei() else "leer"}

    def client_ip(request):
        # Hinter einem Proxy zählt nur dessen X-Forwarded-For, wenn AM_TRUST_PROXY=1 gesetzt ist.
        if os.environ.get("AM_TRUST_PROXY") == "1":
            fwd = request.headers.get("x-forwarded-for", "").split(",")[-1].strip()
            if fwd:
                return fwd
        return request.client.host if request.client else "unbekannt"

    def aufruf(request, x_anthropic_key, fn):
        # Eigener Schlüssel des Nutzers: gilt nur für diese Anfrage, wird weder gespeichert noch geloggt.
        eigener = None
        if not x_anthropic_key:  # Server-Schluessel: Limits gelten, Kosten tragen wir
            try:
                limits.pruefen(client_ip(request))
            except Gesperrt as g:
                kopf = {"Retry-After": str(g.warte_s)} if g.warte_s else None
                raise HTTPException(429, g.grund, headers=kopf) from None
        if x_anthropic_key:
            import anthropic
            eigener = anthropic.Anthropic(api_key=x_anthropic_key.strip(), max_retries=1)
        try:
            out = fn(agent(eigener), eigener)
            if not x_anthropic_key:
                n = out.get("nutzung") or {}
                limits.buchen(n.get("input", 0), n.get("output", 0))
            return out
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except Exception as exc:
            if eigener is None or not type(exc).__module__.startswith("anthropic"):
                raise
            status = getattr(exc, "status_code", None)
            if status in (401, 403):
                raise HTTPException(401, "Schlüssel wurde von Anthropic abgelehnt") from None
            if status == 429:
                raise HTTPException(429, "Anthropic: Limit erreicht, später erneut versuchen") from None
            raise HTTPException(502, "Anthropic-Aufruf fehlgeschlagen") from None

    @app.post("/api/ask")
    def ask(request: Request, body: Frage, x_anthropic_key: str | None = Header(default=None)):
        return aufruf(request, x_anthropic_key, lambda a, c: a.ask(body.frage, body.sprache, client=c))

    @app.post("/api/cfg")
    def cfg_bearbeiten(request: Request, body: CfgWunsch, x_anthropic_key: str | None = Header(default=None)):
        return aufruf(request, x_anthropic_key, lambda a, c: a.edit_cfg(
            body.wunsch, body.cfg, body.sprache, body.pin_freigabe, body.pin_bestaetigung, client=c))

    @app.get("/api/wiki")
    def wiki_liste(sprache: str = "de"):
        if sprache not in wiki_tools.SPRACHEN:
            raise HTTPException(422, "sprache muss 'de' oder 'en' sein")
        out = []
        for p in sorted((Path(root) / "wiki" / sprache).rglob("*.md")):
            meta, _ = wiki_tools.parse_article(p)
            out.append({k: meta[k] for k in ("id", "titel", "firmware", "status", "geprueft_am")})
        return out

    @app.get("/api/wiki/{sprache}/{artikel_id}")
    def wiki_artikel(sprache: str, artikel_id: str):
        if sprache in wiki_tools.SPRACHEN:
            for p in (Path(root) / "wiki" / sprache).rglob("*.md"):
                meta, body = wiki_tools.parse_article(p)
                if meta["id"] == artikel_id:
                    return {**meta, "text": body}
        raise HTTPException(404, "Artikel nicht gefunden")

    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
    return app


app = create_app(limits=Limits.from_env(ROOT / ".usage.json"))
