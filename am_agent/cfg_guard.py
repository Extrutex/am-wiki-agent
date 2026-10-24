"""Schutz der Hardware-Zuordnung in einer printer.cfg.

Vergleicht Original und Vorschlag und meldet jede Änderung an Pins und
Gerätekennungen. Der Server prüft damit jeden Vorschlag des Agenten; die
Regel steht hier im Code und nicht nur im Prompt.
"""
import difflib
import re
from dataclasses import dataclass

BESTAETIGUNG = "ich weiss was ich tue"
MAX_CFG = 200_000

SEKTION = re.compile(r"^\[([^\]]*)\]")
SCHLUESSEL = re.compile(r"^([^\s:=#;][^:=]*?)\s*[:=]\s*(.*)$")
INLINE_KOMMENTAR = re.compile(r"\s+[#;].*$")
# Schlüssel ohne _pin-Endung, die trotzdem Hardware festlegen
FESTE_SCHLUESSEL = {"pin", "pins", "adc1", "adc2", "serial", "canbus_uuid", "canbus_interface"}
INCLUDE = "[include]"


@dataclass(frozen=True)
class Aenderung:
    art: str  # hinzugefuegt | entfernt | geaendert
    sektion: str
    schluessel: str
    alt: str
    neu: str

    def als_dict(self):
        return {"art": self.art, "sektion": self.sektion, "schluessel": self.schluessel,
                "alt": self.alt, "neu": self.neu}


def bestaetigt(satz):
    """Der Extra-Bestätigungssatz, tolerant gegen Gross-/Kleinschreibung, Leerraum und Punkt."""
    norm = re.sub(r"[\s.!]+", " ", (satz or "").lower()).strip()
    norm = norm.replace("ß", "ss").replace("weiß", "weiss")
    return norm == BESTAETIGUNG


def ist_geschuetzt(sektion, schluessel):
    s, k = sektion.strip().lower(), schluessel.strip().lower()
    if s == "board_pins":
        return True
    return k in FESTE_SCHLUESSEL or k.endswith("_pin") or k.endswith("_pins")


def geschuetzte_werte(text):
    """Alle geschützten Einträge als {(sektion, schlüssel): [werte]}. Auch der SAVE_CONFIG-Block (#*#)."""
    out, sektion, schluessel = {}, None, None
    for roh in (text or "").splitlines():
        zeile = roh
        if zeile.startswith("#*#"):
            zeile = zeile[3:]
            zeile = zeile[1:] if zeile.startswith(" ") else zeile
        if not zeile.strip() or zeile.lstrip().startswith(("#", ";")):
            continue
        if zeile[0] in " \t":  # Fortsetzungszeile gehoert zum letzten Schluessel
            if sektion is not None and schluessel is not None and ist_geschuetzt(sektion, schluessel):
                out[(sektion, schluessel)][-1] += " " + INLINE_KOMMENTAR.sub("", zeile).strip()
            continue
        m = SEKTION.match(zeile)
        if m:
            sektion, schluessel = m.group(1).strip(), None
            if sektion.lower().startswith("include"):
                out.setdefault((sektion, INCLUDE), []).append("")
            continue
        m = SCHLUESSEL.match(zeile)
        if m and sektion is not None:
            schluessel = m.group(1).strip().lower()
            if ist_geschuetzt(sektion, schluessel):
                wert = INLINE_KOMMENTAR.sub("", m.group(2)).strip()
                out.setdefault((sektion, schluessel), []).append(wert)
        else:
            schluessel = None
    return out


def pin_aenderungen(original, neu):
    a, b = geschuetzte_werte(original), geschuetzte_werte(neu)
    aend = []
    for key in sorted(set(a) | set(b)):
        alt, nw = a.get(key, []), b.get(key, [])
        if alt == nw:
            continue
        sek, schl = key
        if not alt:
            art = "hinzugefuegt"
        elif not nw:
            art = "entfernt"
        else:
            art = "geaendert"
        aend.append(Aenderung(art, sek, schl, " | ".join(alt), " | ".join(nw)))
    return aend


def diff(original, neu):
    return "".join(difflib.unified_diff(
        (original or "").splitlines(keepends=True), (neu or "").splitlines(keepends=True),
        "printer.cfg (alt)", "printer.cfg (neu)"))
