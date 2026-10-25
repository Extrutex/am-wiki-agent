// Chat-Fenster unten rechts auf der Wiki-Seite. Spricht mit dem Cloudflare Worker (data-api).
// Alle Inhalte werden nur als Text eingefügt, damit Antworten kein HTML einschleusen können.
(() => {
  const skript = document.currentScript;
  const API = (skript.dataset.api || "").replace(/\/$/, "");
  const PRE = skript.dataset.pre || "";
  if (!API) return;
  const LANG = document.documentElement.lang === "en" ? "en" : "de";
  const T = {
    de: {
      knopf: "Frage an den Wiki-Agenten", titel: "AM-Wiki-Agent", schliessen: "Schließen",
      hinweis: "Dieser Assistent ist eine KI (Claude von Anthropic). Er antwortet nur aus den Wiki-Artikeln und nennt die Belege. Deine Fragen werden zur Beantwortung an Anthropic (USA) übermittelt und hier nicht gespeichert. Bitte keine persönlichen Daten eingeben.",
      start: "Verstanden, Chat starten", platzhalter: "Deine Frage zu Klipper-Makros …", senden: "Senden",
      denkt: "Der Agent sucht im Wiki und schreibt …", belege: "Belege", rest: (n) => `Noch ${n} Gratisfrage${n === 1 ? "" : "n"} heute`,
      spenden: "Spenden", spendenBald: "Der Spendenlink folgt bald.", eigener: "Eigener Anthropic-Schlüssel (optional)",
      eigenerInfo: "Gilt nur in diesem Tab, wird nicht gespeichert. Dann zählen keine Gratisfragen.",
      fehler: "Der Agent antwortet gerade nicht. Bitte später noch einmal versuchen.",
      klasse: { bestaetigt: "bestätigt", offen: "offen", nicht_belegt: "nicht belegt" }, warnung: "Hinweis",
      neu: "Neues Gespräch", begruessung: "Hallo! Frag mich etwas zu Klipper-Makros und Jinja2. Ich antworte nur mit Belegen aus dem Wiki.",
    },
    en: {
      knopf: "Ask the wiki agent", titel: "AM wiki agent", schliessen: "Close",
      hinweis: "This assistant is an AI (Claude by Anthropic). It answers only from the wiki articles and cites them. Your questions are sent to Anthropic (USA) to be answered and are not stored here. Please do not enter personal data.",
      start: "Got it, start chat", platzhalter: "Your question about Klipper macros …", senden: "Send",
      denkt: "The agent is searching the wiki and writing …", belege: "Sources", rest: (n) => `${n} free question${n === 1 ? "" : "s"} left today`,
      spenden: "Donate", spendenBald: "Donation link coming soon.", eigener: "Own Anthropic key (optional)",
      eigenerInfo: "Only used in this tab, never stored. Free questions are not counted then.",
      fehler: "The agent is not responding right now. Please try again later.",
      klasse: { bestaetigt: "confirmed", offen: "open", nicht_belegt: "not sourced" }, warnung: "Note",
      neu: "New conversation", begruessung: "Hi! Ask me about Klipper macros and Jinja2. I only answer with sources from the wiki.",
    },
  }[LANG];

  const speicher = {
    get(k) { try { return JSON.parse(sessionStorage.getItem(k)); } catch { return null; } },
    set(k, v) { try { sessionStorage.setItem(k, JSON.stringify(v)); } catch { /* ohne Speicher weiter */ } },
  };
  let verlauf = speicher.get("am-chat-verlauf") || [];
  let zustimmung = false;
  try { zustimmung = localStorage.getItem("am-chat-ok") === "1"; } catch { /* ohne Speicher weiter */ }

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  // Text mit ```Codeblöcken``` und [beleg]-Markern; Marker werden zu Nummern.
  function textMitBelegen(text, nummern) {
    const box = el("div", "chat-text");
    text.split(/```[a-z0-9]*\n?/i).forEach((teil, i) => {
      if (i % 2) { box.append(el("pre", "chat-code", teil.replace(/\n$/, ""))); return; }
      const absatz = el("div");
      let rest = teil;
      for (const [k, n] of nummern) rest = rest.split(`[${k}]`).join(`\u0000${n}\u0000`);
      rest.split("\u0000").forEach((s, j) => {
        if (j % 2) { absatz.append(el("sup", "chat-ref", `[${s}]`)); return; }
        s.split(/`([^`\n]+)`/).forEach((t, m) => absatz.append(m % 2 ? el("code", "", t) : t));
      });
      box.append(absatz);
    });
    return box;
  }

  const knopf = el("button", "chat-knopf", T.knopf);
  knopf.type = "button";
  knopf.setAttribute("aria-expanded", "false");
  const fenster = el("section", "chat-fenster");
  fenster.setAttribute("aria-label", T.titel);
  fenster.hidden = true;
  const kopf = el("header", "chat-kopf");
  const neu = el("button", "chat-mini", T.neu);
  const zu = el("button", "chat-mini", "×");
  neu.type = zu.type = "button";
  zu.setAttribute("aria-label", T.schliessen);
  kopf.append(el("b", "", T.titel), el("span", "chat-luecke"), neu, zu);
  const liste = el("div", "chat-liste");
  liste.setAttribute("aria-live", "polite");
  const status = el("div", "chat-status");
  const form = el("form", "chat-form");
  const eingabe = el("textarea");
  eingabe.rows = 2;
  eingabe.maxLength = 2000;
  eingabe.placeholder = T.platzhalter;
  const senden = el("button", "btn", T.senden);
  senden.type = "submit";
  form.append(eingabe, senden);
  const details = el("details", "chat-key");
  const key = el("input");
  key.type = "password";
  key.autocomplete = "off";
  key.placeholder = "sk-ant-…";
  details.append(el("summary", "", T.eigener), key, el("div", "meta", T.eigenerInfo));
  const zustimmungBox = el("div", "chat-hinweis");
  const startKnopf = el("button", "btn", T.start);
  startKnopf.type = "button";
  zustimmungBox.append(el("p", "", T.hinweis), startKnopf);
  fenster.append(kopf, liste, zustimmungBox, status, form, details);
  document.body.append(knopf, fenster);

  function zeigeZustimmung() {
    zustimmungBox.hidden = zustimmung;
    form.hidden = details.hidden = !zustimmung;
  }

  function nachricht(rolle, d) {
    const div = el("div", "msg chat-msg" + (rolle === "ich" ? " ich" : ""));
    if (rolle === "ich") { div.textContent = d.text; liste.append(div); return div; }
    const nummern = new Map((d.zitate || []).map((z, i) => [z.schluessel, i + 1]));
    div.append(textMitBelegen(d.text, nummern));
    if (d.daten_klasse) {
      const m = el("div", "meta");
      m.append(el("span", "badge " + d.daten_klasse, T.klasse[d.daten_klasse] || d.daten_klasse));
      div.append(m);
    }
    if (d.zitate && d.zitate.length) {
      const ol = el("ol", "chat-belege");
      for (const z of d.zitate) {
        const li = el("li");
        const a = el("a", "", `${z.titel} – ${z.schluessel.split("#").slice(1).join("#")}`);
        a.href = `${PRE}${LANG}/${encodeURIComponent(z.artikel_id)}.html`;
        li.append(a);
        ol.append(li);
      }
      div.append(el("div", "meta", T.belege + ":"), ol);
    }
    for (const w of d.warnungen || []) div.append(el("div", "meta warn", `${T.warnung}: ${w}`));
    if (d.spenden !== undefined) {
      const zeile = el("div", "row");
      if (d.spenden) {
        const a = el("a", "btn", T.spenden);
        a.href = d.spenden;
        a.target = "_blank";
        a.rel = "noopener";
        zeile.append(a);
      } else {
        zeile.append(el("div", "meta", T.spendenBald));
      }
      div.append(zeile);
    }
    liste.append(div);
    return div;
  }

  function alleZeigen() {
    liste.replaceChildren();
    nachricht("agent", { text: T.begruessung });
    for (const v of verlauf) nachricht(v.rolle, v);
    liste.scrollTop = liste.scrollHeight;
  }

  function oeffnen(an) {
    fenster.hidden = !an;
    knopf.setAttribute("aria-expanded", String(an));
    knopf.hidden = an;
    if (an) { zeigeZustimmung(); alleZeigen(); (zustimmung ? eingabe : startKnopf).focus(); }
  }

  knopf.addEventListener("click", () => oeffnen(true));
  zu.addEventListener("click", () => { oeffnen(false); knopf.focus(); });
  neu.addEventListener("click", () => { verlauf = []; speicher.set("am-chat-verlauf", verlauf); status.textContent = ""; alleZeigen(); });
  startKnopf.addEventListener("click", () => {
    zustimmung = true;
    try { localStorage.setItem("am-chat-ok", "1"); } catch { /* ohne Speicher weiter */ }
    zeigeZustimmung();
    eingabe.focus();
  });
  eingabe.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !fenster.hidden) oeffnen(false); });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const frage = eingabe.value.trim();
    if (!frage || senden.disabled) return;
    const bisher = verlauf.map((v) => ({ rolle: v.rolle, text: v.text }));
    verlauf.push({ rolle: "ich", text: frage });
    nachricht("ich", { text: frage });
    eingabe.value = "";
    senden.disabled = true;
    status.textContent = T.denkt;
    status.classList.add("laeuft");
    liste.scrollTop = liste.scrollHeight;
    const kopfzeilen = { "Content-Type": "application/json" };
    if (key.value.trim()) kopfzeilen["X-Anthropic-Key"] = key.value.trim();
    let eintrag;
    try {
      const res = await fetch(API + "/api/ask", {
        method: "POST", headers: kopfzeilen, body: JSON.stringify({ frage, sprache: LANG, verlauf: bisher }),
      });
      let d = {};
      try { d = await res.json(); } catch { /* kein JSON */ }
      if (res.ok) {
        eintrag = { rolle: "agent", text: d.antwort, daten_klasse: d.daten_klasse, zitate: d.zitate, warnungen: d.warnungen };
        status.textContent = typeof d.gratis_rest === "number" ? T.rest(d.gratis_rest) : "";
      } else if (res.status === 429 && (d.fehler === "gratis" || d.fehler === "budget")) {
        eintrag = { rolle: "agent", text: d.detail, spenden: d.spenden_url || "" };
        details.open = true;
        status.textContent = "";
      } else {
        eintrag = { rolle: "agent", text: d.detail || T.fehler };
        status.textContent = "";
      }
    } catch {
      eintrag = { rolle: "agent", text: T.fehler };
      status.textContent = "";
    }
    status.classList.remove("laeuft");
    senden.disabled = false;
    nachricht("agent", eintrag);
    // Nur echte Antworten gehen in den Verlauf, den der Agent bei Rückfragen sieht
    if (eintrag.daten_klasse) verlauf.push(eintrag);
    else verlauf.pop();
    verlauf = verlauf.slice(-20);
    speicher.set("am-chat-verlauf", verlauf);
    liste.scrollTop = liste.scrollHeight;
    eingabe.focus();
  });
})();
