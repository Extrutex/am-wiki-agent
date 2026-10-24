"""Nutzungsgrenzen fuer den Server-Schluessel: Rate-Limit pro IP und Tagesbudget an Tokens.

Gespeichert werden nur Zaehler (Tag, Anfragen, Tokens), nie Fragen, Schluessel oder IPs.
Anfragen mit eigenem Nutzer-Schluessel zaehlen nicht, die bezahlt der Nutzer.
Ein einzelner Aufruf kann das Budget um seine eigene Groesse ueberschreiten (Pruefung vorher, Buchung nachher).
"""
import json
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path


class Gesperrt(Exception):
    def __init__(self, grund, warte_s=None):
        super().__init__(grund)
        self.grund, self.warte_s = grund, warte_s


def _tag(jetzt):
    return datetime.fromtimestamp(jetzt, timezone.utc).strftime("%Y-%m-%d")


class Limits:
    MAX_IPS = 10_000

    def __init__(self, tagesbudget=300_000, pro_minute=5, pro_tag=40, datei=None, uhr=time.time):
        self.tagesbudget, self.pro_minute, self.pro_tag = tagesbudget, pro_minute, pro_tag
        self.datei = Path(datei) if datei else None
        self.uhr, self.lock = uhr, threading.Lock()
        self.treffer = {}  # ip -> deque von Zeitstempeln (letzte 24 h)
        self.zaehler = {"tag": _tag(uhr()), "anfragen": 0, "input_tokens": 0, "output_tokens": 0}
        self._laden()

    @classmethod
    def from_env(cls, standard_datei=None):
        def zahl(name, std):
            try:
                return int(os.environ.get(name, std))
            except ValueError:
                return std
        return cls(tagesbudget=zahl("AM_TAGESBUDGET_TOKENS", 300_000), pro_minute=zahl("AM_RATE_PRO_MIN", 5),
                   pro_tag=zahl("AM_RATE_PRO_TAG", 40), datei=os.environ.get("AM_USAGE_DATEI") or standard_datei)

    def _laden(self):
        try:
            d = json.loads(self.datei.read_text(encoding="utf-8")) if self.datei else None
        except (OSError, ValueError):
            return
        if isinstance(d, dict) and d.get("tag") == self.zaehler["tag"]:
            for k in ("anfragen", "input_tokens", "output_tokens"):
                if isinstance(d.get(k), int):
                    self.zaehler[k] = d[k]

    def _speichern(self):
        if not self.datei:
            return
        try:
            tmp = self.datei.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.zaehler), encoding="utf-8")
            tmp.replace(self.datei)
        except OSError:
            pass  # Zaehlen geht im Speicher weiter

    def _tageswechsel(self, jetzt):
        if _tag(jetzt) != self.zaehler["tag"]:
            self.zaehler = {"tag": _tag(jetzt), "anfragen": 0, "input_tokens": 0, "output_tokens": 0}

    def tokens_heute(self):
        with self.lock:
            self._tageswechsel(self.uhr())
            return self.zaehler["input_tokens"] + self.zaehler["output_tokens"]

    def frei(self):
        return self.tokens_heute() < self.tagesbudget

    def pruefen(self, ip):
        """Wirft Gesperrt, sonst zaehlt die Anfrage fuer diese IP."""
        jetzt = self.uhr()
        with self.lock:
            self._tageswechsel(jetzt)
            if self.zaehler["input_tokens"] + self.zaehler["output_tokens"] >= self.tagesbudget:
                raise Gesperrt("Das Tageskontingent ist aufgebraucht. Morgen wieder, oder eigenen API-Schlüssel eingeben.")
            if len(self.treffer) > self.MAX_IPS:
                self.treffer = {k: v for k, v in self.treffer.items() if v and v[-1] > jetzt - 86400}
            q = self.treffer.setdefault(ip, deque())
            while q and q[0] <= jetzt - 86400:
                q.popleft()
            if len(q) >= self.pro_tag:
                raise Gesperrt("Tageslimit für Anfragen erreicht. Morgen wieder, oder eigenen API-Schlüssel eingeben.",
                               int(q[0] + 86400 - jetzt) + 1)
            letzte = [t for t in q if t > jetzt - 60]
            if len(letzte) >= self.pro_minute:
                raise Gesperrt("Zu viele Anfragen. Bitte eine Minute warten.", min(60, int(letzte[0] + 60 - jetzt) + 1))
            q.append(jetzt)

    def buchen(self, input_tokens, output_tokens):
        with self.lock:
            self._tageswechsel(self.uhr())
            self.zaehler["anfragen"] += 1
            self.zaehler["input_tokens"] += max(0, int(input_tokens or 0))
            self.zaehler["output_tokens"] += max(0, int(output_tokens or 0))
            self._speichern()
