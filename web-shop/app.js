// Demo-Oberfläche. Alle Daten unten sind Beispieldaten (daten_klasse "beispiel").
// Es werden keine Anfragen gesendet; siehe API.md für die spätere Schnittstelle.
const PRODUCTS = [
  { name: "Beispiel-Düse 0,4 mm", preis: "12,00 €" },
  { name: "Beispiel-Toolchanger-Halter", preis: "89,00 €" },
  { name: "Beispiel-Filament PETG 1 kg", preis: "24,00 €" },
];

const ANSWERS = [
  { key: "klipper", text: "Beispielantwort zu Klipper. Echte Antworten brauchen einen bestätigten Abruf mit Quelle." },
  { key: "toolchanger", text: "Beispielantwort zu Toolchangern. Nicht als Fakt verwenden." },
  { key: "marlin", text: "Beispielantwort zu Marlin. Nicht als Fakt verwenden." },
];

const list = document.getElementById("products");
for (const p of PRODUCTS) {
  const li = document.createElement("li");
  li.textContent = `${p.name} – ${p.preis} `;
  const tag = document.createElement("span");
  tag.className = "tag";
  tag.textContent = "(Beispiel)";
  li.append(tag);
  list.append(li);
}

document.getElementById("b2b").addEventListener("submit", (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  const out = document.getElementById("draft");
  out.textContent = `ENTWURF (nicht gesendet)\nFirma: ${f.get("firma")}\nAnliegen: ${f.get("anliegen")}`;
  out.hidden = false;
});

document.getElementById("ask").addEventListener("submit", (e) => {
  e.preventDefault();
  const q = document.getElementById("q");
  const hit = ANSWERS.find((a) => q.value.toLowerCase().includes(a.key));
  const chat = document.getElementById("chat");
  for (const [who, text] of [["Du", q.value], ["Demo-Assistent", hit ? hit.text : "Dazu habe ich nur Beispieldaten und keine bestätigte Quelle."]]) {
    const div = document.createElement("div");
    div.className = "msg";
    div.textContent = `${who}: ${text}`;
    chat.append(div);
  }
  q.value = "";
});
