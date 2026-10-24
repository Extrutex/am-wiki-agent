"""FastAPI-Server: Chat-API und Wiki-Anzeige. Start: uvicorn am_agent.server:app"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import wiki_tools
from am_agent.service import Agent, ROOT

STATIC = Path(__file__).resolve().parent / "static"


class Frage(BaseModel):
    frage: str
    sprache: str = "de"


def create_app(client=None, root=ROOT):
    app = FastAPI(title="AM-Wiki-Agent")
    holder = {"agent": None}

    def agent():
        if holder["agent"] is None:
            c = client
            if c is None:
                import anthropic  # Zugangsdaten kommen aus der Umgebung, nie aus dem Browser
                try:
                    c = anthropic.Anthropic()
                except Exception as exc:
                    raise HTTPException(503, "Claude-API nicht konfiguriert") from exc
            holder["agent"] = Agent(c, root)
        return holder["agent"]

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/ask")
    def ask(body: Frage):
        try:
            return agent().ask(body.frage, body.sprache)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

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
