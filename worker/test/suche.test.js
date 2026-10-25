import assert from "node:assert/strict";
import test from "node:test";

import { Index, schluessel, tokenize } from "../src/suche.js";
import referenz from "./suche_referenz.json" with { type: "json" };
import wiki from "../src/wiki.json" with { type: "json" };

test("findet dieselben Abschnitte wie die Python-Suche", () => {
  for (const [lang, fragen] of Object.entries(referenz)) {
    const idx = new Index(wiki.sprachen[lang], lang);
    for (const [frage, erwartet] of Object.entries(fragen)) {
      assert.deepEqual(idx.search(frage).map(schluessel), erwartet, `${lang}: ${frage}`);
    }
  }
});

test("Tokenisierung: Umlaute, Stoppwörter, Stamm", () => {
  assert.deepEqual(tokenize("Wie ändere ich die Größe der Düse?", "de"), ["änder", "größ", "düse"]);
  assert.deepEqual(tokenize("How do the macros work", "en"), ["macro", "work"]);
});

test("leere Suche und leerer Index", () => {
  assert.deepEqual(new Index(wiki.sprachen.de, "de").search("der die das"), []);
  assert.deepEqual(new Index([], "de").search("makro parameter"), []);
});
