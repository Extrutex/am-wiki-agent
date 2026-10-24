#!/usr/bin/env python3
"""Offline-Prüfung und Test-Rendering von Klipper-Makros (gcode_macro).

Bildet Klippers Jinja2-Umgebung nach (klippy/extras/gcode_macro.py):
jinja2.Environment('{%', '%}', '{', '}') ohne Extensions. Nur Rendern, nichts
wird an einen Drucker gesendet.
"""
import ast
import configparser
import re
import sys

import jinja2


class MacroError(Exception):
    """action_raise_error oder Rendering-Fehler im Makro."""


def make_env():
    return jinja2.Environment('{%', '%}', '{', '}')


def parse_cfg(text):
    cp = configparser.ConfigParser(interpolation=None, strict=True)
    cp.read_string(text)
    return cp


def macro_sections(cp):
    return [s for s in cp.sections() if s.split(None, 1)[0] == "gcode_macro"]


def lint(text):
    """Gibt eine Liste von Befunden (Strings) zurück."""
    problems = []
    cp = parse_cfg(text)
    for sec in macro_sections(cp):
        parts = sec.split()
        if len(parts) != 2:
            problems.append(f"[{sec}]: Name darf keine Leerzeichen enthalten")
            continue
        name = parts[1]
        if not re.fullmatch(r"\D*\d*", name):
            problems.append(f"[{sec}]: Zahlen im Namen nur am Ende")
        if "gcode" not in cp[sec]:
            problems.append(f"[{sec}]: Option 'gcode' fehlt")
        else:
            try:
                make_env().from_string(cp[sec]["gcode"])
            except jinja2.TemplateSyntaxError as exc:
                problems.append(f"[{sec}]: Jinja2-Syntaxfehler: {exc}")
        for opt, val in cp[sec].items():
            if opt.startswith("variable_"):
                try:
                    ast.literal_eval(val)
                except (ValueError, SyntaxError) as exc:
                    problems.append(f"[{sec}]: {opt} ist kein gueltiges Literal: {exc}")
    # Klipper verlangt Kleinbuchstaben in Variablennamen; configparser würde sie still klein machen.
    for m in re.finditer(r"^(variable_\w*[A-Z]\w*)\s*[:=]", text, re.M):
        problems.append(f"{m.group(1)}: Variablennamen nur in Kleinbuchstaben")
    return problems


def render(text, name, params=None, printer=None):
    """Rendert Makro `name`. Gibt (G-Code-Zeilen, Meldungen) zurück."""
    cp = parse_cfg(text)
    sec = next((s for s in macro_sections(cp)
                if len(s.split()) == 2 and s.split()[1].upper() == name.upper()), None)
    if sec is None:
        raise MacroError(f"Makro {name} nicht gefunden")
    messages = []

    def respond_info(msg):
        messages.append(("info", msg))

    def raise_error(msg):
        raise MacroError(msg)

    def emergency_stop(msg="action_emergency_stop"):
        raise MacroError(f"NOTAUS: {msg}")

    def call_remote_method(method, **kwargs):
        messages.append(("remote", method, kwargs))

    ctx = {}
    for opt, val in cp[sec].items():
        if opt.startswith("variable_"):
            ctx[opt[len("variable_"):]] = ast.literal_eval(val)
    # Parameterwerte sind in Klipper immer Strings.
    params = {k.upper(): str(v) for k, v in (params or {}).items()}
    ctx.update(printer=printer or {}, params=params,
               rawparams=" ".join(f"{k}={v}" for k, v in params.items()),
               action_respond_info=respond_info, action_raise_error=raise_error,
               action_emergency_stop=emergency_stop,
               action_call_remote_method=call_remote_method)
    try:
        out = make_env().from_string(cp[sec]["gcode"]).render(**ctx)
    except jinja2.TemplateError as exc:
        raise MacroError(f"Jinja2-Fehler: {exc}") from exc
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    return lines, messages


if __name__ == "__main__":
    status = 0
    for path in sys.argv[1:]:
        for p in lint(open(path, encoding="utf-8").read()):
            print(f"{path}: {p}")
            status = 1
    print("Macro-Check:", "Befunde" if status else "ok")
    sys.exit(status)
