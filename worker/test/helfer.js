// Ersatz für Workers KV und den Anthropic-Client, damit die Tests ohne Netz und ohne Kosten laufen.
export class FakeKV {
  constructor() {
    this.daten = new Map();
    this.ttl = new Map();
  }
  async get(key, typ) {
    const v = this.daten.get(key);
    if (v === undefined) return null;
    return typ === "json" ? JSON.parse(v) : v;
  }
  async put(key, wert, opts = {}) {
    this.daten.set(key, wert);
    this.ttl.set(key, opts.expirationTtl);
  }
}

export class FakeClient {
  constructor(antworten = []) {
    this.antworten = antworten;
    this.aufrufe = [];
    this.beta = { messages: { create: async (params) => this.create(params) } };
  }
  async create(params) {
    this.aufrufe.push(params);
    const a = this.antworten.shift();
    if (a instanceof Error) throw a;
    return a;
  }
}

export const antwort = (text, extra = {}) => ({
  content: [{ type: "text", text }],
  stop_reason: "end_turn",
  usage: { input_tokens: 1000, output_tokens: 200, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 },
  ...extra,
});

export const PARAMS_DE = "klipper-makros-jinja2#Parameter: `params`";
