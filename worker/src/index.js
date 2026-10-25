// Cloudflare Worker: Chat-API für das AM-Wiki.
//   POST /api/ask     {frage, sprache, verlauf}  -> Antwort mit Belegen
//   GET  /api/health                             -> Status und Kontingent
// Der Server-Schlüssel liegt als Secret ANTHROPIC_API_KEY bei Cloudflare, nie im Browser.
// Ein eigener Schlüssel (Header X-Anthropic-Key) gilt nur für die Anfrage und wird nicht gespeichert.
import Anthropic from "@anthropic-ai/sdk";

import { Agent, Eingabefehler } from "./agent.js";
import { Limits } from "./limits.js";
import wiki from "./wiki.json" with { type: "json" };

const TEXTE = {
  gratis: {
    de: "Deine Gratisfragen für heute sind aufgebraucht. Das Wiki lebt von Spenden: Damit bezahle ich die KI-Kosten und halte die Artikel aktuell. Morgen gibt es neue Gratisfragen, oder du trägst einen eigenen Anthropic-Schlüssel ein.",
    en: "Your free questions for today are used up. The wiki runs on donations, which pay for the AI costs and keep the articles up to date. New free questions tomorrow, or enter your own Anthropic key.",
  },
  budget: {
    de: "Das gemeinsame Tageskontingent ist aufgebraucht. Morgen geht es weiter, oder du trägst einen eigenen Anthropic-Schlüssel ein. Mit einer Spende hilfst du, das Kontingent zu erhöhen.",
    en: "The shared daily quota is used up. It resets tomorrow, or enter your own Anthropic key. A donation helps raise the quota.",
  },
  stoerung: {
    de: "Der Agent antwortet gerade nicht. Bitte später noch einmal versuchen.",
    en: "The agent is not responding right now. Please try again later.",
  },
};

let agentCache = null;
const agent = (env) => (agentCache ??= new Agent(wiki, env.AM_MODEL || "claude-sonnet-5-5"));

function erlaubteOrigins(env) {
  return (env.ERLAUBTE_ORIGINS || "").split(",").map((s) => s.trim()).filter(Boolean);
}

function corsKopf(request, env) {
  const origin = request.headers.get("Origin");
  if (!origin || !erlaubteOrigins(env).includes(origin)) return {};
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-Anthropic-Key",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  };
}

function json(daten, status, request, env) {
  return new Response(JSON.stringify(daten), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...corsKopf(request, env) },
  });
}

async function ask(request, env, ctx, deps) {
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ detail: "Ungültiges JSON" }, 400, request, env);
  }
  const lang = body && body.sprache === "en" ? "en" : "de";
  const eigenerKey = (request.headers.get("X-Anthropic-Key") || "").trim();
  const ip = request.headers.get("CF-Connecting-IP") || "unbekannt";
  const limits = deps.limits(env);

  let rest = null;
  if (!eigenerKey) {
    if (!env.ANTHROPIC_API_KEY && !deps.client) {
      return json({ detail: TEXTE.stoerung[lang] }, 503, request, env);
    }
    const p = await limits.pruefen(ip);
    if (!p.ok) {
      return json({ fehler: p.grund, detail: TEXTE[p.grund][lang], spenden_url: env.SPENDEN_URL || "" }, 429, request, env);
    }
    rest = p.rest;
  }

  const client = deps.client || new Anthropic({ apiKey: eigenerKey || env.ANTHROPIC_API_KEY, maxRetries: 1 });
  let out;
  try {
    out = await agent(env).ask(client, body.frage, lang, body.verlauf);
  } catch (err) {
    if (err instanceof Eingabefehler) return json({ detail: err.message }, 422, request, env);
    if (eigenerKey && (err instanceof Anthropic.AuthenticationError || err instanceof Anthropic.PermissionDeniedError)) {
      return json({ detail: lang === "de" ? "Dein Schlüssel wurde von Anthropic abgelehnt." : "Anthropic rejected your key." }, 401, request, env);
    }
    if (err instanceof Anthropic.RateLimitError) {
      return json({ detail: TEXTE.stoerung[lang] }, 429, request, env);
    }
    console.error("Claude-Aufruf fehlgeschlagen", err instanceof Anthropic.APIError ? err.status : err?.name);
    return json({ detail: TEXTE.stoerung[lang] }, 502, request, env);
  }

  // Nur Antworten, für die Claude gefragt wurde, kosten eine Gratisfrage
  if (!eigenerKey && out.nutzung.input + out.nutzung.output > 0) {
    rest = await limits.buchen(ip, out.nutzung.input, out.nutzung.output);
  }
  const { nutzung, ...antwort } = out;
  return json({ ...antwort, gratis_rest: rest }, 200, request, env);
}

export async function handle(request, env, ctx, deps = {}) {
  deps = { limits: (e) => new Limits(e.NUTZUNG, e), ...deps };
  const url = new URL(request.url);
  const origin = request.headers.get("Origin");
  if (origin && !erlaubteOrigins(env).includes(origin)) {
    return new Response("Origin nicht erlaubt", { status: 403 });
  }
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: corsKopf(request, env) });
  if (url.pathname === "/api/health" && request.method === "GET") {
    const frei = await deps.limits(env).frei();
    return json({ status: "ok", kontingent: frei ? "frei" : "leer" }, 200, request, env);
  }
  if (url.pathname === "/api/ask" && request.method === "POST") return ask(request, env, ctx, deps);
  return json({ detail: "Nicht gefunden" }, 404, request, env);
}

export default { fetch: (request, env, ctx) => handle(request, env, ctx) };
