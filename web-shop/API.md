# Schnittstelle für einen späteren Agentenserver (Entwurf)

Aktuell gibt es **keinen** Server. Der Demo-Assistent in `app.js` antwortet lokal mit Beispieldaten.

## Geplant: `POST /api/ask`
Anfrage: `{ "frage": "string" }`

Antwort:
```json
{
  "antwort": "string",
  "daten_klasse": "bestaetigt | offen | beispiel",
  "quellen": [{ "source_id": "klipper-docs", "abgerufen_am": "ISO-8601", "sha256": "hex" }]
}
```

## Regeln
- `bestaetigt` nur mit mindestens einer Quelle aus `knowledge-base/fetched/`.
- Der Server löst keine Firmware-Updates, Druckerbefehle, Zahlungen oder Veröffentlichungen aus.
- Authentifizierung, Rate-Limit und CORS-Whitelist sind vor dem Betrieb festzulegen.
