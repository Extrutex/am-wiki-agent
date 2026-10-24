# AM-Plattform-Workspace

Recherche-Gerüst, Spezialisten-Spezifikation und Demo-Shop für Additive Fertigung (Firmware, Toolchanger, B2B).

## Inhalt
| Pfad | Zweck |
|---|---|
| `am_research_builder.py` | Ruft Websites und GitHub-Releases aus dem Register ab (nur HTTPS-GET). Speichert Abrufzeit, Quell-URL, SHA-256, Status. Fehler in `errors.jsonl`. |
| `am_specialist_spec.json` | Versionierte Spezifikation: Zuständigkeiten, Quellenverweise, Trennung `bestaetigt` / `beispiel`. |
| `am_validate.py` | Offline-Prüfung von Spezifikation und Register. |
| `agents/` | Koordinator, Firmware, Hardware/Toolchanger, Quellenprüfung, B2B. |
| `knowledge-base/sources.json` | Quellenregister (Klipper, RepRapFirmware, Marlin, Bambu, Toolchanger). |
| `knowledge-base/fetched/` | Echte Abrufe, getrennt vom Register. |
| `web-shop/` | Statische Demo-Oberfläche (GitHub-Pages-fähig, ohne Build). `API.md` beschreibt die spätere Schnittstelle. |
| `tests/`, `.github/workflows/` | Offline-Tests und Actions. |

## Benutzung
Nur Python 3 (Standardbibliothek), keine Installation nötig.
```
python3 am_validate.py                     # Register + Spezifikation prüfen
python3 -m unittest discover -s tests -t . # Offline-Tests
python3 am_research_builder.py --list      # Quellen anzeigen
python3 am_research_builder.py --only klipper-releases   # echter Abruf
```
Der Workflow `Recherche` läuft manuell oder montags 05:00 UTC und legt das Ergebnis nur als Artefakt ab.

## Erweitern
Neue Quelle: Eintrag in `knowledge-base/sources.json` (Host in `allowed_hosts` ergänzen), Quelle dem Agenten in `am_specialist_spec.json` zuordnen, `am_validate.py` ausführen.

## Datenklassen
- `bestaetigt`: nur mit Quelle und Abruf.
- `beispiel`: Demodaten, nie als Fakt verwenden. Alle Shop-Inhalte sind Beispiele.

## Sicherheit
Keine automatischen Firmware-Updates, Druckerbefehle, Zahlungen oder Veröffentlichungen. Das Skript liest nur, Workflows haben nur `contents: read`, die Shop-Seite sendet nichts.
