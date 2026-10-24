# AM-Plattform-Workspace

Next-Gen-Wiki mit Chat-Agent für 3D-Druck (Klipper, Marlin, Bambu Lab, Prusa, Tuning, später alle Verfahren). Jede Aussage hat eine Quelle, Beispiele sind getestet. Der Chat-Agent (FastAPI + Claude API) beantwortet Fragen nur mit Zitaten aus dem Wiki.

## Inhalt
| Pfad | Zweck |
|---|---|
| `am_research_builder.py` | Ruft Websites und GitHub-Releases aus dem Register ab (nur HTTPS-GET). Speichert Abrufzeit, Quell-URL, SHA-256, Status. Fehler in `errors.jsonl`. |
| `am_specialist_spec.json` | Versionierte Spezifikation: Zuständigkeiten, Quellenverweise, Trennung `bestaetigt` / `beispiel`. |
| `am_validate.py` | Offline-Prüfung von Spezifikation und Register. |
| `agents/` | Koordinator, Firmware, Hardware/Toolchanger, Quellenprüfung, B2B. |
| `knowledge-base/sources.json` | Quellenregister (Klipper, RepRapFirmware, Marlin, Bambu, Toolchanger). |
| `knowledge-base/fetched/` | Echte Abrufe, getrennt vom Register. |
| `wiki/de`, `wiki/en` | Zweisprachige Artikel mit Kopfdaten (Quellen, Status, Prüfdatum). Erstes Kapitel: `klipper/makros-jinja2`. |
| `wiki/beispiele/` | Getestete Beispieldateien, die in den Artikeln eingebettet sind. |
| `klipper_macro_check.py` | Lint und Test-Rendering von Klipper-Makros mit Klippers Jinja2-Einstellungen (nur Rendern). |
| `wiki_tools.py` | Prüft Artikel: Quellen, Abrufe, Beispiele, de/en-Paare. |
| `am_agent/` | Chat-Agent: Suche (BM25) über Wiki-Abschnitte, Claude-Aufruf mit Zitatprüfung, FastAPI-Server, Oberfläche (`static/`). Ohne passenden Abschnitt wird Claude nicht gefragt. |
| `tests/`, `.github/workflows/` | Offline-Tests und Actions. |

## Benutzung
Python 3; für Makro-Tests wird Jinja2 gebraucht.
```
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python am_validate.py                       # Register, Spezifikation, Wiki prüfen
.venv/bin/python -m unittest discover -s tests -t .   # Offline-Tests
python3 am_research_builder.py --list      # Quellen anzeigen
python3 am_research_builder.py --only klipper-releases   # echter Abruf
```
## Chat-Agent starten
```
cp .env.example .env      # ANTHROPIC_API_KEY dort eintragen (.env ist nicht in Git); oder: ant auth login
.venv/bin/uvicorn am_agent.server:app --port 8791
```
Modell über `AM_MODEL` (Standard `claude-sonnet-5-5`). **Jede Frage kostet Geld auf deinem API-Konto.** Der Server hat noch kein Nutzungslimit: nicht öffentlich betreiben, bevor Kontingent und Kostendeckel (Spend-Limit in der Console) eingerichtet sind.

Der Workflow `Recherche` läuft manuell oder montags 05:00 UTC und legt das Ergebnis nur als Artefakt ab.

## Erweitern
Neue Quelle: Eintrag in `knowledge-base/sources.json` (Host in `allowed_hosts` ergänzen), Quelle dem Agenten in `am_specialist_spec.json` zuordnen, `am_validate.py` ausführen.

## Datenklassen
- `bestaetigt`: nur mit Quelle und Abruf.
- `beispiel`: Demodaten, nie als Fakt verwenden.

## Wiki-Regeln
- Artikel werden neu aus Primärquellen geschrieben. Fremde Guides werden nicht kopiert.
- Status `bestaetigt` nur mit Quelle und Abruf unter `knowledge-base/fetched/`.
- Jeder Artikel existiert in `de` und `en` mit gleichen Quellen und Beispielen.
- Codeblöcke mit `<!-- beispiel: datei -->` müssen mit der Datei in `wiki/beispiele/` übereinstimmen.

## Sicherheit
Keine automatischen Firmware-Updates, Druckerbefehle, Zahlungen oder Veröffentlichungen. Das Skript liest nur, Makros werden nur gerendert, Workflows haben nur `contents: read`.
