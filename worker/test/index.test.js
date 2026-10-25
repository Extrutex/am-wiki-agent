import assert from "node:assert/strict";
import test from "node:test";

import Anthropic from "@anthropic-ai/sdk";

import { handle } from "../src/index.js";
import { Limits } from "../src/limits.js";
import { FakeClient, FakeKV, PARAMS_DE, antwort } from "./helfer.js";

const ORIGIN = "https://extrutex.github.io";
const FRAGE = "Wie greife ich in einem Makro auf Parameter zu?";

function umgebung(extra = {}) {
  return { NUTZUNG: new FakeKV(), ANTHROPIC_API_KEY: "sk-test", AM_SALZ: "salz", AM_GRATIS_PRO_TAG: "2",
    ERLAUBTE_ORIGINS: ORIGIN, SPENDEN_URL: "https://example.org/spenden", ...extra };
}

function frage(body, kopf = {}) {
  return new Request("https://worker.example/api/ask", {
    method: "POST", body: JSON.stringify(body),
    headers: { "Content-Type": "application/json", Origin: ORIGIN, "CF-Connecting-IP": "203.0.113.7", ...kopf },
  });
}

test("Antwort mit Belegen, Gratisfrage wird gezählt, CORS stimmt", async () => {
  const env = umgebung();
  const client = new FakeClient([antwort(`Über params [${PARAMS_DE}].`)]);
  const res = await handle(frage({ frage: FRAGE }), env, {}, { client });
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("Access-Control-Allow-Origin"), ORIGIN);
  const d = await res.json();
  assert.equal(d.zitate[0].schluessel, PARAMS_DE);
  assert.equal(d.gratis_rest, 1);
  assert.equal(d.nutzung, undefined);
});

test("nach den Gratisfragen kommt der Spendenhinweis, Claude wird nicht mehr gefragt", async () => {
  const env = umgebung();
  const client = new FakeClient([antwort(`a [${PARAMS_DE}]`), antwort(`b [${PARAMS_DE}]`)]);
  for (let i = 0; i < 2; i++) assert.equal((await handle(frage({ frage: FRAGE }), env, {}, { client })).status, 200);
  const res = await handle(frage({ frage: FRAGE }), env, {}, { client });
  assert.equal(res.status, 429);
  const d = await res.json();
  assert.equal(d.fehler, "gratis");
  assert.equal(d.spenden_url, "https://example.org/spenden");
  assert.match(d.detail, /Spenden/);
  assert.equal(client.aufrufe.length, 2);
});

test("unbelegte Fragen kosten keine Gratisfrage", async () => {
  const env = umgebung();
  const client = new FakeClient();
  for (let i = 0; i < 3; i++) {
    const d = await (await handle(frage({ frage: "Wetter morgen in Berlin" }), env, {}, { client })).json();
    assert.equal(d.daten_klasse, "nicht_belegt");
    assert.equal(d.gratis_rest, 2);
  }
});

test("eigener Schlüssel: keine Limits, keine Zählung", async () => {
  const env = umgebung({ AM_GRATIS_PRO_TAG: "0" });
  const client = new FakeClient([antwort(`x [${PARAMS_DE}]`)]);
  const res = await handle(frage({ frage: FRAGE }, { "X-Anthropic-Key": "sk-eigen" }), env, {}, { client });
  assert.equal(res.status, 200);
  assert.equal((await res.json()).gratis_rest, null);
  assert.equal(env.NUTZUNG.daten.size, 0);
});

test("Tagesbudget leer: Hinweis statt Aufruf", async () => {
  const env = umgebung({ AM_TAGESBUDGET_TOKENS: "100" });
  await new Limits(env.NUTZUNG, env).buchen("198.51.100.1", 90, 20);
  const client = new FakeClient();
  const res = await handle(frage({ frage: FRAGE }), env, {}, { client });
  assert.equal(res.status, 429);
  assert.equal((await res.json()).fehler, "budget");
  const h = await handle(new Request("https://worker.example/api/health", { headers: { Origin: ORIGIN } }), env, {});
  assert.equal((await h.json()).kontingent, "leer");
});

test("fremde Origin wird abgewiesen, Preflight erlaubt", async () => {
  const env = umgebung();
  const fremd = await handle(frage({ frage: FRAGE }, { Origin: "https://boese.example" }), env, {}, { client: new FakeClient() });
  assert.equal(fremd.status, 403);
  const pre = await handle(new Request("https://worker.example/api/ask", { method: "OPTIONS", headers: { Origin: ORIGIN } }), env, {});
  assert.equal(pre.status, 204);
  assert.match(pre.headers.get("Access-Control-Allow-Headers"), /X-Anthropic-Key/);
});

test("Fehler von Anthropic werden freundlich gemeldet", async () => {
  const env = umgebung();
  const kaputt = new Anthropic.APIError(500, { type: "error" }, "Serverfehler", new Headers());
  const res = await handle(frage({ frage: FRAGE }), env, {}, { client: new FakeClient([kaputt]) });
  assert.equal(res.status, 502);
  assert.match((await res.json()).detail, /antwortet gerade nicht/);
  assert.equal(env.NUTZUNG.daten.size, 0);
});

test("ohne Server-Schlüssel: 503, ungültige Eingabe: 422, falscher Pfad: 404", async () => {
  assert.equal((await handle(frage({ frage: FRAGE }), umgebung({ ANTHROPIC_API_KEY: "" }), {})).status, 503);
  assert.equal((await handle(frage({ frage: "" }), umgebung(), {}, { client: new FakeClient() })).status, 422);
  const r = await handle(new Request("https://worker.example/x"), umgebung(), {});
  assert.equal(r.status, 404);
});

test("Zähler speichern keine IP im Klartext", async () => {
  const env = umgebung();
  await handle(frage({ frage: FRAGE }), env, {}, { client: new FakeClient([antwort(`x [${PARAMS_DE}]`)]) });
  const schluessel = [...env.NUTZUNG.daten.keys()].join(" ");
  assert.ok(!schluessel.includes("203.0.113.7"));
  assert.match(schluessel, /^b:\d{4}-\d{2}-\d{2}:[0-9a-f]{64} t:\d{4}-\d{2}-\d{2}$/);
});
