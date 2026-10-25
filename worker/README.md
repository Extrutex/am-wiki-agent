# Wiki-Chat als Cloudflare Worker

Der Worker beantwortet die Fragen aus dem Chat-Fenster der Wiki-Seite. Er sucht im Wiki (BM25, gleich wie
`am_agent/retrieval.py`), fragt Claude nur mit passenden Abschnitten und prüft die Zitate.
Dein Anthropic-Schlüssel liegt als Secret bei Cloudflare, nie im Browser.

- **Gratisfragen:** 5 pro Besucher und Tag (`AM_GRATIS_PRO_TAG`). Gezählt werden nur Fragen, für die Claude
  wirklich gefragt wurde. Danach erscheint der Spendenhinweis (`SPENDEN_URL`).
- **Tagesbudget:** 300 000 Tokens für alle zusammen (`AM_TAGESBUDGET_TOKENS`).
- **Eigener Schlüssel:** Besucher können einen eigenen Anthropic-Schlüssel eintragen. Dann zählt nichts.
- **Gespeichert** werden nur Zähler in Workers KV. Statt der IP steht dort ein täglich wechselnder Hash.
- **Harte Grenze** ist nur das Spend-Limit in der Anthropic-Console. KV zählt nicht streng gleichzeitig.

## Einmalige Einrichtung (du, mit deinem Cloudflare-Konto)

```bash
cd worker
npm ci
npx wrangler login                                # Browser-Login bei Cloudflare
npx wrangler kv namespace create NUTZUNG          # ausgegebene id in wrangler.toml eintragen
npx wrangler secret put ANTHROPIC_API_KEY         # Schlüssel aus der Anthropic-Console
npx wrangler secret put AM_SALZ                   # beliebige lange Zufallszeichenkette
npm run deploy                                    # Tests, dann Veröffentlichung
```

`npm run deploy` gibt die Adresse aus, z. B. `https://am-wiki-agent.<konto>.workers.dev`.
Diese Adresse in GitHub unter *Settings → Secrets and variables → Actions → Variables* als `AM_CHAT_API`
eintragen. Beim nächsten Pages-Lauf bekommt jede Wiki-Seite das Chat-Fenster.

In der Anthropic-Console unter *Limits* ein monatliches Spend-Limit setzen.

## Einstellungen ändern

In `wrangler.toml` unter `[vars]`, danach `npm run deploy`:

| Variable | Bedeutung |
|---|---|
| `AM_MODEL` | Modell, Standard `claude-sonnet-5-5` |
| `AM_GRATIS_PRO_TAG` | Gratisfragen pro Besucher und Tag |
| `AM_TAGESBUDGET_TOKENS` | Tokens pro UTC-Tag für alle zusammen |
| `ERLAUBTE_ORIGINS` | Seiten, die den Worker aufrufen dürfen (kommagetrennt) |
| `SPENDEN_URL` | Spendenlink im Hinweis; leer = „Spendenlink folgt bald“ |

## Lokal testen

```bash
npm test                     # baut wiki.json aus dem Wiki und führt die Tests aus (ohne Netz, ohne Kosten)
npm run dev                  # Worker auf http://localhost:8787, Secrets dafür in worker/.dev.vars
AM_CHAT_API=http://localhost:8787 python ../build_pages.py site && python -m http.server -d site 8000
```

Nach Wiki-Änderungen den Worker neu veröffentlichen (`npm run deploy`), sonst kennt er die neuen Abschnitte nicht.
