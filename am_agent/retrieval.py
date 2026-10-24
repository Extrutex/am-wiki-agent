"""Einfache Volltextsuche (BM25) über Wiki-Abschnitte. Keine Vektor-DB."""
import math
import re
from dataclasses import dataclass
from pathlib import Path

import wiki_tools

STOP = {
    "de": set("der die das und oder ein eine einen einem einer ist sind wird werden mit von zu im in am an auf für fuer wie was wo kann man ich du es nicht auch dem den des zum zur bei aus als wenn dann dass".split()),
    "en": set("the a an and or is are was be been with of to in on at for how what where can i you it not also from as if then that this do does".split()),
}


def stem(word):
    for suf in ("en", "er", "es", "e", "n", "s"):
        if len(word) > 4 and word.endswith(suf):
            return word[: -len(suf)]
    return word


def tokenize(text, lang):
    words = re.findall(r"[a-zäöüß0-9_]+", text.lower())
    return [stem(w) for w in words if w not in STOP.get(lang, ()) and len(w) > 1]


@dataclass
class Chunk:
    artikel_id: str
    lang: str
    titel: str
    abschnitt: str
    text: str
    status: str
    quellen: list

    @property
    def key(self):
        return f"{self.artikel_id}#{self.abschnitt}"


def load_chunks(root, lang):
    chunks = []
    for path in sorted((Path(root) / "wiki" / lang).rglob("*.md")):
        meta, body = wiki_tools.parse_article(path)
        parts = re.split(r"^## ", body, flags=re.M)
        for part in parts[1:]:
            head, _, rest = part.partition("\n")
            chunks.append(Chunk(meta["id"], lang, meta["titel"], head.strip(),
                                f"{head.strip()}\n{rest.strip()}", meta["status"], meta["quellen"]))
    return chunks


class Index:
    def __init__(self, chunks, lang, k1=1.5, b=0.75):
        self.chunks, self.lang, self.k1, self.b = chunks, lang, k1, b
        self.tokens = [tokenize(c.titel + " " + c.text, lang) for c in chunks]
        self.avg = (sum(map(len, self.tokens)) / len(chunks)) if chunks else 0
        self.df = {}
        for toks in self.tokens:
            for t in set(toks):
                self.df[t] = self.df.get(t, 0) + 1

    def search(self, query, k=4):
        q = list(dict.fromkeys(tokenize(query, self.lang)))
        if not q or not self.chunks:
            return []
        need = min(2, len(q))
        n, hits = len(self.chunks), []
        for chunk, toks in zip(self.chunks, self.tokens):
            matched = [t for t in q if t in toks]
            if len(matched) < need:
                continue
            score = 0.0
            for t in matched:
                tf = toks.count(t)
                idf = math.log(1 + (n - self.df[t] + 0.5) / (self.df[t] + 0.5))
                score += idf * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * len(toks) / (self.avg or 1)))
            hits.append((score, chunk))
        hits.sort(key=lambda h: -h[0])
        return [c for _, c in hits[:k]]
