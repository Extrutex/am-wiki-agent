---
id: klipper-makros-jinja2
sprache: en
titel: Klipper macros and Jinja2
firmware: klipper
status: bestaetigt
quellen: klipper-command-templates, klipper-gcode-macro-source
beispiele: klipper/anteil_melden.cfg, klipper/bett_vorheizen.cfg, klipper/duese_wischen.cfg, klipper/bett_merken.cfg
geprueft_am: 2026-10-24
---

# Klipper macros and Jinja2

## Summary
A Klipper macro is a `[gcode_macro NAME]` section with a `gcode:` option. That G-code is evaluated as a **Jinja2 template**. The whole template is first evaluated to text, and only then does Klipper run the resulting commands. Most pitfalls follow from this order.

## Structure and names
- Macro names are case-insensitive. If a name contains digits, they must come at the end (`TEST_MACRO25` is valid, `MACRO25_TEST3` is not).
- A section name consists of the type and exactly one name. Klipper rejects whitespace in the name (error "contains illegal whitespace").
- `gcode:` starts at the beginning of the line, all following command lines are indented.
- `description:` is optional (default: "G-Code macro") and shows up in `HELP` and autocomplete.

## Saving G-code state
`G0`/`G1` moves depend on the parser state (`M82`, `M83`, `G90`, `G91`, `G92`, earlier `G1`). Set the state explicitly in the macro and wrap it in `SAVE_GCODE_STATE` / `RESTORE_GCODE_STATE`. Give the first `G1` an explicit feed rate `F`.

## Jinja2 in Klipper
- `{ ... }` evaluates an expression, `{% ... %}` is a statement (`if`, `for`, `set`).
- Klipper creates the environment with `jinja2.Environment('{%', '%}', '{', '}')` and sets **no** extensions. It follows (Jinja2 behaviour, not stated explicitly in the Klipper text) that `{% do ... %}` is not available.
- Template comments are `{# ... #}` (Jinja2 default).

## Parameters: `params`
Call parameters are in `params`, names in upper case. **Values are always strings.** Convert with `|float` or `|int` before doing math, and set defaults with `|default(...)`.

<!-- beispiel: klipper/anteil_melden.cfg -->
```ini
[gcode_macro ANTEIL_MELDEN]
description: Zeigt einen Anteil (0.0 bis 1.0) als Prozent an
gcode:
    {% set anteil = params.ANTEIL|default(0.5)|float %}
    M117 Anteil: {(anteil * 100)|int}%
```

Calling `ANTEIL_MELDEN ANTEIL=0.2` shows `Anteil: 20%`. Without a parameter the value is 0.5.

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

`rawparams` holds the complete, unparsed parameter string of the call.

## Reading state: `printer`
`printer` exposes the current printer state (fields: see the Status Reference in the Klipper docs). The name after `printer` is the config section name, e.g. `printer.fan`; exceptions include `gcode_move` and `toolhead`. Sections with spaces in the name use brackets: `printer["gcode_macro NAME"]`.

## Evaluation comes before execution
- The macro is **fully evaluated before** the first generated command runs. State changes caused by those commands are not visible during evaluation.
- A nested macro is evaluated only when it is invoked, i.e. after the calling macro was fully evaluated.

## Variables between calls
Use `variable_<name>` for an initial value and `SET_GCODE_VARIABLE` to change it. Variable names contain no upper-case characters. The value must be a valid Python literal. Because of the order above, the change applies after execution, not within the same evaluation.

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

## Actions
Actions take effect at **evaluation** time, possibly well before the generated commands run:
- `action_respond_info(msg)`: message to the console.
- `action_raise_error(msg)`: aborts this macro and all callers.
- `action_emergency_stop(msg)`: puts the printer into shutdown (`msg` optional).
- `action_call_remote_method(name, ...)`: calls a method registered by a client.

## Delayed G-code and saved variables
- `[delayed_gcode]` runs G-code after a countdown, started with `UPDATE_DELAYED_GCODE ID=... DURATION=...`. `DURATION=0` cancels it. `initial_duration` starts counting from the "ready" state.
- With `[save_variables]`, `SAVE_VARIABLE VARIABLE=<name> VALUE=<value>` persists values across restarts. They are then available in `printer.save_variables.variables`.

## Pitfalls
1. Parameters are strings, never calculate without `|float`/`|int`.
2. State changes are not visible within one evaluation.
3. `SET_GCODE_VARIABLE` takes effect after execution.
4. Actions run earlier than the generated G-code.
5. Mind indentation and lower-case variable names.

## Verified
The examples above live as files in `wiki/beispiele/klipper/` and are rendered on every test run with Jinja2 3.1.6 and Klipper's environment settings (see `tests/`). This does not replace a run on a real Klipper.

## Sources
- `klipper-command-templates`: Klipper docs "Command Templates" (retrieval: see `knowledge-base/fetched/`).
- `klipper-gcode-macro-source`: `klippy/extras/gcode_macro.py` (environment, context, name check).
