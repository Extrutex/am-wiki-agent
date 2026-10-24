// Alle Inhalte werden nur als Text eingefügt, damit Antworten kein HTML einschleusen können.
const $ = (id) => document.getElementById(id);
const KEY = "am-anthropic-key";
let letzteCfg = null;

// Anzeigenamen: die API-Werte bleiben technisch (ASCII), sichtbar sind echte Umlaute
const LABEL = { bestaetigt: "bestätigt", nicht_belegt: "nicht belegt", offen: "offen",
  geaendert: "geändert", hinzugefuegt: "hinzugefügt", entfernt: "entfernt" };
const label = (w) => LABEL[w] || w;

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function add(cls, text, meta, warnungen, klasse) {
  const div = el("div", "msg " + cls, text);
  if (meta || klasse) {
    const m = el("div", "meta");
    if (klasse) m.append(el("span", "badge " + klasse, label(klasse)), " ");
    m.append(meta || "");
    div.append(m);
  }
  for (const w of warnungen || []) div.append(el("div", "meta warn", "Warnung: " + w));
  $("verlauf").append(div);
}

function headers() {
  const h = { "Content-Type": "application/json" };
  const k = $("key").value.trim();
  if (k) h["X-Anthropic-Key"] = k;
  return h;
}

// Ablauf-Visualisierung: Knoten leuchten nacheinander, solange die Anfrage läuft
let flowTimer = null;
function flow(an) {
  clearInterval(flowTimer);
  const li = [...document.querySelectorAll("#flow li")];
  li.forEach((n) => n.classList.remove("an"));
  if (!an) return;
  let i = 0;
  li[0].classList.add("an");
  flowTimer = setInterval(() => { if (i < li.length - 2) li[++i].classList.add("an"); }, 700);
}
function flowFertig() {
  clearInterval(flowTimer);
  document.querySelectorAll("#flow li").forEach((n) => n.classList.add("an"));
}

async function post(pfad, body) {
  const res = await fetch(pfad, { method: "POST", headers: headers(), body: JSON.stringify(body) });
  let d = {};
  try { d = await res.json(); } catch (e) { /* kein JSON */ }
  return { ok: res.ok, status: res.status, d };
}

// Tabs
function zeigeTab(name) {
  for (const b of document.querySelectorAll("#tabs button")) b.setAttribute("aria-selected", String(b.dataset.tab === name));
  for (const s of document.querySelectorAll(".tab")) s.hidden = s.id !== "tab-" + name;
}
$("tabs").addEventListener("click", (e) => { if (e.target.dataset.tab) zeigeTab(e.target.dataset.tab); });

// Schlüssel nur im Tab
try { $("key").value = sessionStorage.getItem(KEY) || ""; } catch (e) { /* ohne Speicher weiter */ }
$("key").addEventListener("change", () => {
  try { sessionStorage.setItem(KEY, $("key").value.trim()); } catch (e) { /* ignorieren */ }
});

// Wiki
async function ladeListe() {
  const res = await fetch("/api/wiki?sprache=" + $("lang").value);
  const liste = await res.json();
  $("artikel").replaceChildren();
  for (const a of liste) {
    const li = el("li");
    const link = el("a", "", a.titel);
    link.tabIndex = 0;
    const oeffnen = async () => {
      const r = await fetch(`/api/wiki/${$("lang").value}/${encodeURIComponent(a.id)}`);
      const d = await r.json();
      $("text").textContent = d.text;
      $("text").hidden = false;
    };
    link.onclick = oeffnen;
    link.onkeydown = (e) => { if (e.key === "Enter") oeffnen(); };
    li.append(link, ` (${label(a.status)}, geprüft ${a.geprueft_am})`);
    $("artikel").append(li);
  }
}
$("lang").addEventListener("change", ladeListe);

// Chat
$("form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const frage = $("frage").value;
  add("ich", frage);
  $("frage").value = "";
  flow(true);
  try {
    const { ok, status, d } = await post("/api/ask", { frage, sprache: $("lang").value });
    flowFertig();
    if (!ok) return add("", "Fehler: " + (d.detail || status));
    const belege = d.zitate.map((z) => z.schluessel).join(", ");
    add("", d.antwort, belege ? "Belege: " + belege : "", d.warnungen, d.daten_klasse);
  } catch (err) {
    flow(false);
    add("", "Fehler: " + err);
  }
});

// Config-Editor
$("pinfrei").addEventListener("change", () => { $("pinwarn").hidden = !$("pinfrei").checked; });
$("cfgdatei").addEventListener("change", async () => {
  const f = $("cfgdatei").files[0];
  if (f) $("cfg").value = await f.text();
});

function zeigeDiff(text) {
  $("diff").replaceChildren();
  for (const z of text.split("\n")) {
    const cls = z.startsWith("+++") || z.startsWith("---") || z.startsWith("@@") ? "hdr" : z.startsWith("+") ? "add" : z.startsWith("-") ? "del" : "";
    $("diff").append(el("div", cls, z || " "));
  }
}

$("cfgsenden").addEventListener("click", async () => {
  const btn = $("cfgsenden");
  const pin = $("pinfrei").checked;
  if (!$("cfg").value.trim() || !$("wunsch").value.trim()) return;
  btn.disabled = true;
  btn.textContent = "Agent arbeitet …";
  try {
    const { ok, status, d } = await post("/api/cfg", {
      wunsch: $("wunsch").value, cfg: $("cfg").value, sprache: $("lang").value,
      pin_freigabe: pin, pin_bestaetigung: pin ? $("pinsatz").value : "",
    });
    $("cfgergebnis").hidden = false;
    $("cfgtext").replaceChildren();
    $("pinliste").replaceChildren();
    $("diff").replaceChildren();
    letzteCfg = null;
    $("kopieren").disabled = $("laden").disabled = true;
    if (!ok) { $("cfgtext").append(el("div", "msg", "Fehler: " + (d.detail || status))); return; }
    const kopf = el("div", "msg", d.antwort || "");
    kopf.append(el("div", "meta", ""));
    kopf.lastChild.append(el("span", "badge " + d.daten_klasse, label(d.daten_klasse)));
    for (const w of d.warnungen || []) kopf.append(el("div", "meta warn", "Warnung: " + w));
    $("cfgtext").append(kopf);
    for (const p of d.pin_aenderungen || []) {
      $("pinliste").append(el("div", "pin", `${d.blockiert ? "Gesperrt" : "Pin-Änderung"}: [${p.sektion}] ${p.schluessel} ${label(p.art)}: "${p.alt}" → "${p.neu}"`));
    }
    if (d.cfg_neu) {
      letzteCfg = d.cfg_neu;
      zeigeDiff(d.diff || "(keine Änderung)");
      $("kopieren").disabled = $("laden").disabled = false;
    }
  } catch (err) {
    $("cfgergebnis").hidden = false;
    $("cfgtext").replaceChildren(el("div", "msg", "Fehler: " + err));
  } finally {
    btn.disabled = false;
    btn.textContent = "Änderung vorschlagen";
  }
});

$("kopieren").addEventListener("click", async () => {
  if (!letzteCfg) return;
  try { await navigator.clipboard.writeText(letzteCfg); $("kopieren").textContent = "Kopiert"; }
  catch (e) { $("kopieren").textContent = "Kopieren nicht möglich"; }
  setTimeout(() => { $("kopieren").textContent = "Neue cfg kopieren"; }, 1800);
});
$("laden").addEventListener("click", () => {
  if (!letzteCfg) return;
  const a = el("a");
  a.href = URL.createObjectURL(new Blob([letzteCfg], { type: "text/plain" }));
  a.download = "printer.neu.cfg";
  a.click();
  URL.revokeObjectURL(a.href);
});

ladeListe();
