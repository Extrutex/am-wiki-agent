"""Minimaler .env-Lader (ohne Abhaengigkeit). Bereits gesetzte Umgebungsvariablen gewinnen."""
import os
from pathlib import Path


def load_env(path):
    path = Path(path)
    if not path.is_file():
        return []
    gesetzt = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = val
            gesetzt.append(key)
    return gesetzt
