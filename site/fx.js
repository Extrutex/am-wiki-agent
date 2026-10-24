// Effekte: Hintergrundnetz, Maus-Glow, Karten-Tilt. Alles aus bei prefers-reduced-motion.
(() => {
  const ruhig = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (ruhig) return;

  const glow = document.getElementById("glow");
  addEventListener("pointermove", (e) => {
    glow.style.setProperty("--mx", e.clientX + "px");
    glow.style.setProperty("--my", e.clientY + "px");
  }, { passive: true });

  document.addEventListener("pointermove", (e) => {
    const card = e.target.closest && e.target.closest(".tilt");
    document.querySelectorAll(".tilt").forEach((c) => {
      if (c !== card) { c.style.setProperty("--rx", "0deg"); c.style.setProperty("--ry", "0deg"); }
    });
    if (!card || e.target.closest("textarea, input, pre, select")) return;
    const r = card.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
    card.style.setProperty("--ry", (x * 5).toFixed(2) + "deg");
    card.style.setProperty("--rx", (-y * 5).toFixed(2) + "deg");
  }, { passive: true });

  const cv = document.getElementById("bg");
  const ctx = cv.getContext("2d");
  let w, h, pts = [], maus = { x: -999, y: -999 };
  const N = () => Math.min(70, Math.floor((w * h) / 22000));
  function groesse() {
    w = cv.width = innerWidth; h = cv.height = innerHeight;
    pts = Array.from({ length: N() }, () => ({ x: Math.random() * w, y: Math.random() * h, vx: (Math.random() - .5) * .3, vy: (Math.random() - .5) * .3 }));
  }
  addEventListener("resize", groesse);
  addEventListener("pointermove", (e) => { maus = { x: e.clientX, y: e.clientY }; }, { passive: true });
  function frame() {
    ctx.clearRect(0, 0, w, h);
    for (const p of pts) {
      p.x += p.vx; p.y += p.vy;
      if (p.x < 0 || p.x > w) p.vx *= -1;
      if (p.y < 0 || p.y > h) p.vy *= -1;
      const dm = Math.hypot(p.x - maus.x, p.y - maus.y);
      if (dm < 140) { p.x += (p.x - maus.x) * 0.004; p.y += (p.y - maus.y) * 0.004; }
      ctx.fillStyle = "rgba(94,234,212,.7)";
      ctx.fillRect(p.x, p.y, 2, 2);
    }
    for (let i = 0; i < pts.length; i++) for (let j = i + 1; j < pts.length; j++) {
      const d = Math.hypot(pts[i].x - pts[j].x, pts[i].y - pts[j].y);
      if (d < 120) {
        ctx.strokeStyle = `rgba(129,140,248,${(1 - d / 120) * 0.35})`;
        ctx.beginPath(); ctx.moveTo(pts[i].x, pts[i].y); ctx.lineTo(pts[j].x, pts[j].y); ctx.stroke();
      }
    }
    if (!document.hidden) requestAnimationFrame(frame);
  }
  document.addEventListener("visibilitychange", () => { if (!document.hidden) requestAnimationFrame(frame); });
  groesse();
  requestAnimationFrame(frame);
})();
