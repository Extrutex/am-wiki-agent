// Gratisfragen pro Besucher und Tagesbudget an Tokens, gespeichert in Workers KV.
//
// Gespeichert werden nur Zähler. Statt der IP steht dort ein SHA-256 aus IP, Tag und geheimem Salz,
// der sich jeden Tag ändert. Fragen und Schlüssel werden nie gespeichert.
// KV ist nicht streng konsistent: Gleichzeitige Anfragen können ein Limit knapp überschreiten.
// Die harte Grenze ist das Spend-Limit in der Anthropic-Console.

const TAG_S = 86400;

export const heute = (jetzt = Date.now()) => new Date(jetzt).toISOString().slice(0, 10);

async function sha256(text) {
  const bytes = new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text)));
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function zahl(wert, std) {
  const n = Number.parseInt(wert, 10);
  return Number.isFinite(n) && n >= 0 ? n : std;
}

export class Limits {
  constructor(kv, env = {}, uhr = Date.now) {
    this.kv = kv;
    this.uhr = uhr;
    this.gratis = zahl(env.AM_GRATIS_PRO_TAG, 5);
    this.budget = zahl(env.AM_TAGESBUDGET_TOKENS, 300000);
    this.salz = env.AM_SALZ || "";
  }

  async besucher(ip) {
    return "b:" + heute(this.uhr()) + ":" + (await sha256(`${this.salz}|${heute(this.uhr())}|${ip}`));
  }

  async tokensHeute() {
    const d = await this.kv.get("t:" + heute(this.uhr()), "json");
    return d ? d.input + d.output : 0;
  }

  async frei() {
    return (await this.tokensHeute()) < this.budget;
  }

  // Vor dem Claude-Aufruf: {ok, grund, rest}
  async pruefen(ip) {
    if (!(await this.frei())) return { ok: false, grund: "budget", rest: 0 };
    const genutzt = zahl(await this.kv.get(await this.besucher(ip)), 0);
    if (genutzt >= this.gratis) return { ok: false, grund: "gratis", rest: 0 };
    return { ok: true, rest: this.gratis - genutzt };
  }

  // Nach einer Antwort von Claude: eine Gratisfrage verbraucht, Tokens gebucht. Gibt den Rest zurück.
  async buchen(ip, input, output) {
    const kb = await this.besucher(ip);
    const genutzt = zahl(await this.kv.get(kb), 0) + 1;
    const kt = "t:" + heute(this.uhr());
    const t = (await this.kv.get(kt, "json")) || { anfragen: 0, input: 0, output: 0 };
    t.anfragen += 1;
    t.input += Math.max(0, input | 0);
    t.output += Math.max(0, output | 0);
    await Promise.all([
      this.kv.put(kb, String(genutzt), { expirationTtl: 2 * TAG_S }),
      this.kv.put(kt, JSON.stringify(t), { expirationTtl: 8 * TAG_S }),
    ]);
    return Math.max(0, this.gratis - genutzt);
  }
}
