# Quellenprüfung

**Aufgabe:** Jede Aussage einstufen:
- **bestätigt:** `source_id` im Register und Abruf mit Zeit, URL und SHA-256 vorhanden.
- **offen:** plausibel, aber ohne Abruf.
- **Beispiel:** Demodaten.

## Prüfschritte
1. `source_id` in `knowledge-base/sources.json` vorhanden?
2. Abruf in `knowledge-base/fetched/<id>/` vorhanden, ohne Fehlerprotokoll-Eintrag?
3. Aussage deckt sich mit dem abgerufenen Inhalt?

## Übergabe
Ergebnis an `koordinator` (oder `b2b`).
