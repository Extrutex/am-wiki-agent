// Alle Inhalte werden nur als Text eingefuegt, damit Antworten kein HTML einschleusen koennen.
const $ = (id) => document.getElementById(id);

function add(cls, text, meta, warnungen) {
  const div = document.createElement("div");
  div.className = "msg " + cls;
  div.textContent = text;
  if (meta) {
    const m = document.createElement("div");
    m.className = "meta";
    m.textContent = meta;
    div.append(m);
  }
  for (const w of warnungen || []) {
    const e = document.createElement("div");
    e.className = "meta warn";
    e.textContent = "Warnung: " + w;
    div.append(e);
  }
  $("verlauf").append(div);
}

async function ladeListe() {
  const res = await fetch("/api/wiki?sprache=" + $("lang").value);
  const liste = await res.json();
  $("artikel").replaceChildren();
  for (const a of liste) {
    const li = document.createElement("li");
    const link = document.createElement("a");
    link.textContent = a.titel;
    link.onclick = async () => {
      const r = await fetch(`/api/wiki/${$("lang").value}/${encodeURIComponent(a.id)}`);
      const d = await r.json();
      $("text").textContent = d.text;
      $("text").hidden = false;
    };
    li.append(link, ` (${a.status}, geprüft ${a.geprueft_am})`);
    $("artikel").append(li);
  }
}

$("lang").addEventListener("change", ladeListe);
$("form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const frage = $("frage").value;
  add("ich", frage);
  $("frage").value = "";
  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ frage, sprache: $("lang").value }),
    });
    const d = await res.json();
    if (!res.ok) return add("", "Fehler: " + (d.detail || res.status));
    const belege = d.zitate.map((z) => z.schluessel).join(", ");
    add("", d.antwort, `Einstufung: ${d.daten_klasse}${belege ? " | Belege: " + belege : ""}`, d.warnungen);
  } catch (err) {
    add("", "Fehler: " + err);
  }
});
ladeListe();
