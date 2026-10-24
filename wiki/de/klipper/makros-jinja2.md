---
id: klipper-makros-jinja2
sprache: de
titel: Klipper-Makros und Jinja2
firmware: klipper
status: bestaetigt
quellen: klipper-command-templates, klipper-gcode-macro-source
beispiele: klipper/anteil_melden.cfg, klipper/bett_vorheizen.cfg, klipper/duese_wischen.cfg, klipper/bett_merken.cfg
geprueft_am: 2026-10-24
---

# Klipper-Makros und Jinja2

## Kurzfassung
Ein Klipper-Makro ist ein `[gcode_macro NAME]`-Abschnitt mit einer `gcode:`-Option. Dieser G-Code wird als **Jinja2-Template** ausgewertet. Erst wird das ganze Template zu Text ausgewertet, danach führt Klipper die entstandenen Befehle aus. Fast alle Fallstricke ergeben sich aus dieser Reihenfolge.

## Aufbau und Namen
- Makronamen sind nicht von der Groß-/Kleinschreibung abhängig. Enthält ein Name Zahlen, müssen sie am Ende stehen (`TEST_MAKRO25` ja, `MAKRO25_TEST3` nein).
- Der Abschnittsname darf aus dem Typ und genau einem Namen bestehen. Leerzeichen im Namen weist Klipper ab (Fehlermeldung "contains illegal whitespace").
- `gcode:` beginnt am Zeilenanfang, alle folgenden Befehlszeilen sind eingerückt.
- `description:` ist optional (Standard: "G-Code macro") und erscheint bei `HELP` und in der Autovervollständigung.

## G-Code-Zustand sichern
Bewegungen mit `G0`/`G1` hängen vom Parser-Zustand ab (`M82`, `M83`, `G90`, `G91`, `G92`, frühere `G1`). Setze den Zustand deshalb im Makro ausdrücklich und sichere ihn mit `SAVE_GCODE_STATE` / `RESTORE_GCODE_STATE`. Gib beim ersten `G1` eine Geschwindigkeit `F` an.

## Jinja2 in Klipper
- `{ ... }` wertet einen Ausdruck aus, `{% ... %}` ist eine Anweisung (`if`, `for`, `set`).
- Klipper erzeugt die Umgebung mit `jinja2.Environment('{%', '%}', '{', '}')` und setzt **keine** Extensions. Daraus folgt (Jinja2-Verhalten, nicht im Klipper-Text ausdrücklich genannt): `{% do ... %}` steht nicht zur Verfügung.
- Kommentare im Template sind `{# ... #}` (Jinja2-Standard).

## Parameter: `params`
Aufruf-Parameter stehen in `params`, die Namen in Großbuchstaben. **Die Werte sind immer Strings.** Für Rechnungen musst du mit `|float` oder `|int` umwandeln, Vorgabewerte setzt du mit `|default(...)`.

<!-- beispiel: klipper/anteil_melden.cfg -->
```ini
[gcode_macro ANTEIL_MELDEN]
description: Zeigt einen Anteil (0.0 bis 1.0) als Prozent an
gcode:
    {% set anteil = params.ANTEIL|default(0.5)|float %}
    M117 Anteil: {(anteil * 100)|int}%
```

Aufruf: `ANTEIL_MELDEN ANTEIL=0.2` zeigt `Anteil: 20%`. Ohne Parameter gilt 0.5.

<!-- beispiel: klipper/bett_vorheizen.cfg -->
```ini
[gcode_macro BETT_VORHEIZEN]
description: Heizt das Bett auf TEMPERATUR (Standard 40) und verweigert unplausible Werte
gcode:
    {% set temp = params.TEMPERATUR|default(40)|float %}
    {% if temp < 0 or temp > 120 %}
        {action_raise_error("TEMPERATUR muss zwischen 0 und 120 liegen")}
    {% endif %}
    M140 S{temp}
```

`rawparams` enthält die komplette, nicht zerlegte Parameterzeichenfolge des Aufrufs.

## Zustand lesen: `printer`
`printer` gibt Zugriff auf den aktuellen Druckerzustand (Felder: Status-Referenz der Klipper-Doku). Nach `printer` folgt der Name des Konfigurationsabschnitts, etwa `printer.fan`; Ausnahmen sind unter anderem `gcode_move` und `toolhead`. Abschnitte mit Leerzeichen im Namen schreibst du mit eckigen Klammern: `printer["gcode_macro NAME"]`.

## Auswertung kommt vor Ausführung
- Das Makro wird **vollständig ausgewertet, bevor** der erste erzeugte Befehl läuft. Zustandsänderungen durch diese Befehle sind während der Auswertung nicht sichtbar.
- Ein verschachteltes Makro wird erst ausgewertet, wenn es aufgerufen wird, also nach der vollständigen Auswertung des aufrufenden Makros.

## Variablen zwischen Aufrufen
Mit `variable_<name>` legst du einen Startwert fest, `SET_GCODE_VARIABLE` ändert ihn. Variablennamen enthalten keine Großbuchstaben. Der Wert muss ein gültiges Python-Literal sein. Wegen der Reihenfolge oben gilt die Änderung erst nach der Ausführung, nicht innerhalb derselben Auswertung.

<!-- beispiel: klipper/bett_merken.cfg -->
```ini
[gcode_macro BETT_MERKEN]
variable_gemerkt: 0
gcode:
    SET_GCODE_VARIABLE MACRO=BETT_MERKEN VARIABLE=gemerkt VALUE={printer.heater_bed.target}
    M140 S0

[gcode_macro BETT_ZURUECK]
gcode:
    M140 S{printer["gcode_macro BETT_MERKEN"].gemerkt}
```

<!-- beispiel: klipper/duese_wischen.cfg -->
```ini
[gcode_macro DUESE_WISCHEN]
description: Wischt die Duese in mehreren Durchgaengen
variable_durchgaenge: 3
gcode:
    SAVE_GCODE_STATE NAME=wischen
    G90
    {% for i in range(durchgaenge) %}
        G1 X{20 + i * 5} F6000
        G1 X{60 + i * 5} F6000
    {% endfor %}
    RESTORE_GCODE_STATE NAME=wischen
```

## Aktionen
Aktionen wirken bereits bei der **Auswertung**, also unter Umständen deutlich vor den erzeugten Befehlen:
- `action_respond_info(msg)`: Meldung an die Konsole.
- `action_raise_error(msg)`: bricht dieses und alle aufrufenden Makros ab.
- `action_emergency_stop(msg)`: versetzt den Drucker in den Shutdown (`msg` optional).
- `action_call_remote_method(name, ...)`: ruft eine von einem Client registrierte Methode auf.

## Verzögerter G-Code und gespeicherte Variablen
- `[delayed_gcode]` führt G-Code nach einer Wartezeit aus, gestartet mit `UPDATE_DELAYED_GCODE ID=... DURATION=...`. `DURATION=0` bricht ab. `initial_duration` startet nach dem Zustand "ready".
- Mit `[save_variables]` speichert `SAVE_VARIABLE VARIABLE=<name> VALUE=<wert>` Werte über Neustarts hinweg. Sie stehen danach in `printer.save_variables.variables`.

## Fallstricke
1. Parameter sind Strings, rechne nie ohne `|float`/`|int`.
2. Kein Zustandswechsel innerhalb einer Auswertung sichtbar.
3. `SET_GCODE_VARIABLE` wirkt erst nach der Ausführung.
4. Aktionen laufen früher als der erzeugte G-Code.
5. Einrückung und Kleinbuchstaben in Variablennamen beachten.

## Geprüft
Die Beispiele oben liegen als Dateien in `wiki/beispiele/klipper/` und werden bei jedem Testlauf mit Jinja2 3.1.6 und Klippers Umgebungseinstellungen gerendert (siehe `tests/`). Das ersetzt keinen Lauf auf einem echten Klipper.

## Quellen
- `klipper-command-templates`: Klipper-Doku "Command Templates" (Abruf siehe `knowledge-base/fetched/`).
- `klipper-gcode-macro-source`: `klippy/extras/gcode_macro.py` (Environment, Kontext, Namensprüfung).
