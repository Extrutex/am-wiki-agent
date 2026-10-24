"""FastAPI-Server: Chat-API und Wiki-Anzeige. Start: uvicorn am_agent.server:app"""
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import wiki_tools
from am_agent.env import load_env
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


def create_app(client=None, root=ROOT):
    app = FastAPI(title="AM-Wiki-Agent")
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
        return {"status": "ok"}

    def aufruf(x_anthropic_key, fn):
        # Eigener Schluessel des Nutzers: gilt nur fuer diese Anfrage, wird weder gespeichert noch geloggt.
        eigener = None
        if x_anthropic_key:
            import anthropic
            eigener = anthropic.Anthropic(api_key=x_anthropic_key.strip(), max_retries=1)
        try:
            return fn(agent(eigener), eigener)
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
    def ask(body: Frage, x_anthropic_key: str | None = Header(default=None)):
        return aufruf(x_anthropic_key, lambda a, c: a.ask(body.frage, body.sprache, client=c))

    @app.post("/api/cfg")
    def cfg_bearbeiten(body: CfgWunsch, x_anthropic_key: str | None = Header(default=None)):
        return aufruf(x_anthropic_key, lambda a, c: a.edit_cfg(
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


app = create_app()
