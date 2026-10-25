// Volltextsuche (BM25) über Wiki-Abschnitte, gleich gerechnet wie am_agent/retrieval.py.
// Abweichungen fallen im Test gegen worker/test/suche_referenz.json auf.

const STOP = {
  de: new Set("der die das und oder ein eine einen einem einer ist sind wird werden mit von zu im in am an auf für fuer wie was wo kann man ich du es nicht auch dem den des zum zur bei aus als wenn dann dass".split(" ")),
  en: new Set("the a an and or is are was be been with of to in on at for how what where can i you it not also from as if then that this do does".split(" ")),
};
export const SPRACHEN = Object.keys(STOP);

function stem(wort) {
  for (const suf of ["en", "er", "es", "e", "n", "s"]) {
    if (wort.length > 4 && wort.endsWith(suf)) return wort.slice(0, -suf.length);
  }
  return wort;
}

export function tokenize(text, lang) {
  const woerter = text.toLowerCase().match(/[a-zäöüß0-9_]+/g) || [];
  return woerter.filter((w) => !STOP[lang].has(w) && w.length > 1).map(stem);
}

export class Index {
  constructor(chunks, lang, k1 = 1.5, b = 0.75) {
    Object.assign(this, { chunks, lang, k1, b });
    this.tokens = chunks.map((c) => tokenize(c.titel + " " + c.text, lang));
    this.avg = chunks.length ? this.tokens.reduce((s, t) => s + t.length, 0) / chunks.length : 0;
    this.df = new Map();
    for (const toks of this.tokens) {
      for (const t of new Set(toks)) this.df.set(t, (this.df.get(t) || 0) + 1);
    }
  }

  search(query, k = 4) {
    const q = [...new Set(tokenize(query, this.lang))];
    if (!q.length || !this.chunks.length) return [];
    const need = Math.min(2, q.length);
    const n = this.chunks.length;
    const hits = [];
    this.chunks.forEach((chunk, i) => {
      const toks = this.tokens[i];
      const matched = q.filter((t) => toks.includes(t));
      if (matched.length < need) return;
      let score = 0;
      for (const t of matched) {
        const tf = toks.filter((x) => x === t).length;
        const df = this.df.get(t);
        const idf = Math.log(1 + (n - df + 0.5) / (df + 0.5));
        score += idf * tf * (this.k1 + 1) / (tf + this.k1 * (1 - this.b + this.b * toks.length / (this.avg || 1)));
      }
      hits.push([score, chunk]);
    });
    hits.sort((a, b) => b[0] - a[0]);
    return hits.slice(0, k).map(([, c]) => c);
  }
}

export const schluessel = (c) => `${c.artikel_id}#${c.abschnitt}`;
