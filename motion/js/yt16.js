// Vidéo YouTube format long (1920×1080), style « croquis manga sur fond noir ».
// Personnages détourés (PNG transparents) : entrées animées, caméra qui se déplace
// et zoome sur les muscles, répétitions en boucle (2 poses), muscle qui s'allume
// (fondu vers la version coloriée), étiquettes d'exercice, peu de texte (moments forts).
const Q = new URLSearchParams(location.search);
const BASE = './youtube/';
const CFG = await (await fetch(`${BASE}${Q.get('v') || 'v1/long'}.json`)).json();
const cv = document.getElementById('c'), g = cv.getContext('2d');
const W = 1920, H = 1080, DUR = CFG.dur, SC = CFG.scenes;
cv.width = W; cv.height = H;
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const ss = (a, b, x) => { const u = clamp((x - a) / (b - a)); return u * u * (3 - 2 * u); };
const eio = (u) => { u = clamp(u); return u < 0.5 ? 4 * u * u * u : 1 - (-2 * u + 2) ** 3 / 2; };
const back = (u) => { u = clamp(u); const c = 1.5; return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2; };
const lerp = (a, b, u) => a + (b - a) * u;
const FONT = (w, s, it = '') => `${it} ${w} ${s}px Montserrat, "Noto Color Emoji", sans-serif`;
const COL = { red: '#ff3b4f', green: '#36d27a', orange: '#ff9b3d', yellow: '#ffd23f', white: '#ffffff' };

const IMG = {};
const names = new Set();
for (const s of SC) {
  for (const k of ['img', 'alt', 'hl']) if (s[k]) names.add(s[k]);
  (s.seq || []).forEach((q) => { names.add(q.img); if (q.hl) names.add(q.hl); });
}
await Promise.all([...names].map((n) => new Promise((res) => { const im = new Image(); im.onload = () => { IMG[n] = im; res(); }; im.onerror = res; im.src = `${BASE}png/${n}.png`; })));

const at = (s, f) => s.t0 + f * (s.t1 - s.t0);
// ---------- gros texte derrière le personnage ----------
// say : mot par mot, calé sur la voix (les mots de « spoken » répartis sur les phrases de la scène)
// big : toute la ligne d'un coup. *mot* = mot en couleur.
function wordTimes(s) {
  const spoken = (s.spoken || s.say).replace(/\*/g, '').split(/\s+/), parts = s.parts || [[s.t0, s.t1]];
  const tot = parts.reduce((a, p) => a + p[1] - p[0], 0), chars = spoken.reduce((a, w) => a + w.length + 1, 0);
  let c = 0; const ts = spoken.map((w) => { const f = c / chars; c += w.length + 1; let x = f * tot;
    for (const p of parts) { if (x <= p[1] - p[0]) return p[0] + x; x -= p[1] - p[0]; } return parts.at(-1)[1]; });
  const n = s.say.split(/\s+/).length, a = s.sayFrom ?? ts.length - n; return ts.slice(a, a + n);
}
function layout(s, txt) { // une ligne si possible (taille réduite jusqu'à 110 px), sinon plusieurs ; mémorisé
  const key = '_lay' + txt; if (s[key]) return s[key];
  let BIG = 150; g.save(); g.font = FONT(800, BIG, 'italic');
  const full = g.measureText(txt.replace(/\*/g, '').toUpperCase()).width;
  if (full > 1760) { BIG = Math.max(110, Math.floor(BIG * 1760 / full)); g.font = FONT(800, BIG, 'italic'); }
  const sp = g.measureText(' ').width;
  const words = txt.split(/\s+/).map((w) => ({ hot: /^\*.*\*[.,!?]*$/.test(w), w: w.replace(/\*/g, '').toUpperCase() }));
  const lines = [[]]; let lw = 0;
  for (const w of words) { w.wd = g.measureText(w.w).width; if (lw && lw + sp + w.wd > 1760) { lines.push([]); lw = 0; } lines.at(-1).push(w); lw += (lw ? sp : 0) + w.wd; }
  lines.forEach((l, i) => { const tw = l.reduce((a, w) => a + w.wd, 0) + sp * (l.length - 1); let x = (s.sayX ?? 0.5) * W - tw / 2;
    for (const w of l) { w.x = x + w.wd / 2; w.line = i; x += w.wd + sp; } });
  g.restore(); return (s[key] = { words, n: lines.length, BIG });
}
function bigText(s, T) {
  const txt = s.say || s.big; if (!txt) return;
  const L = layout(s, txt), BIG = L.BIG, ts = s.say ? wordTimes(s) : null, y0 = (s.sayY ?? 0.24) * H - (L.n - 1) * BIG * 0.55;
  g.save(); g.font = FONT(800, BIG, 'italic'); g.textAlign = 'center'; g.textBaseline = 'middle';
  L.words.forEach((w, i) => {
    const t = ts ? ts[i] : at(s, s.bigAt ?? 0.15), k = (T - t) / 0.18; if (k <= 0) return;
    g.save(); g.translate(w.x, y0 + w.line * BIG * 1.1); const sc = 0.6 + 0.4 * back(k); g.scale(sc, sc); g.globalAlpha = clamp(k * 1.5);
    g.fillStyle = w.hot ? COL.yellow : '#fff'; g.fillText(w.w, 0, 0); g.restore();
  });
  g.restore();
}

const EVENTS = [];
const ev = (t, type) => EVENTS.push({ t, type });
SC.forEach((s, i) => {
  if (s.card || (SC[i - 1] && SC[i - 1].card)) ev(s.t0 - 0.15, 'whoosh'); // passage vers/depuis un écran noir
  if (s.enter && s.enter !== 'fade') ev(s.t0 - 0.05, 'swish');           // le personnage entre
  if (s.label) ev(s.t0 + 0.05, 'pop');
  (s.icons || []).forEach((ic) => ev(at(s, ic.at), ic.kind === 'x' ? 'tick' : 'ding'));
  if (s.hl) ev(at(s, s.hlAt ?? 0.15), 'shine');
  (s.seq || []).forEach((q) => { ev(at(s, q.at), 'swish'); if (q.hl) ev(at(s, q.at) + 0.1, 'shine'); });
  if (s.alt) { // répétitions : souffle à chaque mouvement, haltère qui « claque » en bas
    const per = s.period || 0.8;
    for (let t = s.t0; t < s.t1 - 0.2; t += 2 * per) {
      if (t + per * 0.65 < s.t1) ev(t + per * 0.65, 'swish');
      if (t + per * 1.65 < s.t1) ev(t + per * 1.65, 'swish');
      if (t + per * 2 < s.t1 + 0.1) ev(t + per * 2, 'clank');
    }
  }
  if (s.say) wordTimes(s).forEach((t) => ev(t, 'tap'));
  if (s.big) ev(at(s, s.bigAt ?? 0.15), 'pop');
  (s.sfx || []).forEach((x) => ev(at(s, x.at), x.type));
});
Object.assign(window, { DUR, EVENTS, CFG });

// ---------- dessin du personnage avec caméra ----------
// L'image (carrée, personnage centré) est placée à la position écran px,py (centre), taille size.
function charRect(s, T, im) {
  const u = eio((T - s.t0 + 0.15) / Math.max(0.4, s.t1 - s.t0 + 0.6));
  const cam = s.cam || [1, 0.5, 0.5, 1.08, 0.5, 0.45];
  const z = lerp(cam[0], cam[3], u), fx = lerp(cam[1], cam[4], u), fy = lerp(cam[2], cam[5], u);
  const size = 1000 * z * (s.scale || 1);
  const px = (s.x ?? 0.5) * W, py = 540;
  // le point (fx,fy) de l'image va vers le centre de l'emplacement du personnage
  let x = px - fx * size, y = py - fy * size + (0.5 - 0.5) * size;
  // entrée animée
  const e = clamp((T - s.t0 + 0.15) / 0.7), k = 1 - eio(e);
  if (s.enter === 'up') y += k * 700;
  if (s.enter === 'left') x -= k * 1200;
  if (s.enter === 'right') x += k * 1200;
  const a = s.enter === 'fade' || !s.enter ? clamp((T - s.t0 + 0.15) / 0.35) : 1;
  // respiration
  const br = 1 + 0.004 * Math.sin(T * 2.2);
  return { x: x + size * (1 - br) / 2, y: y + size * (1 - br), w: size * br, h: size * br, a };
}
function drawChar(im, r, a = 1) { if (!im) return; g.save(); g.globalAlpha = a * r.a; g.drawImage(im, r.x, r.y, r.w, r.h); g.restore(); }

function tag(r, t, T, t0) { // étiquette muscle : point coloré + trait + nom (comme la référence)
  const k = T - t0; if (k < 0) return;
  const a = clamp(k / 0.3), cx = r.x + t.x * r.w, cy = r.y + t.y * r.h, dir = t.side === 'left' ? -1 : 1;
  const lx = cx + dir * 170, ly = cy - 70;
  g.save(); g.globalAlpha = a; g.strokeStyle = 'rgba(255,255,255,0.9)'; g.lineWidth = 2;
  g.beginPath(); g.moveTo(cx, cy); g.lineTo(lx, ly); g.lineTo(lx + dir * 40, ly); g.stroke();
  g.beginPath(); g.arc(lx + dir * 62, ly, 16, 0, Math.PI * 2); g.fillStyle = COL[t.color]; g.fill();
  g.font = FONT(600, 34, 'italic'); g.textAlign = dir > 0 ? 'left' : 'right'; g.textBaseline = 'middle'; g.fillStyle = '#fff';
  g.fillText(t.name, lx + dir * 90, ly + 2); g.restore();
}
function label(txt, u) { // « #1. Lateral Raise » : petit cadre blanc, texte noir
  if (u <= 0) return;
  g.save(); g.globalAlpha = clamp(u * 2); g.translate(W / 2, 90); const s = 0.9 + 0.1 * back(u); g.scale(s, s);
  g.font = FONT(700, 40); const tw = g.measureText(txt).width + 50;
  g.fillStyle = '#fff'; g.fillRect(-tw / 2, -34, tw, 68); g.strokeStyle = '#000'; g.lineWidth = 3; g.strokeRect(-tw / 2 + 6, -28, tw - 12, 56);
  g.fillStyle = '#000'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(txt, 0, 2); g.restore();
}
function italic(txt, x, y, size, a) { // texte des moments forts : petit, italique, blanc
  if (a <= 0) return;
  g.save(); g.globalAlpha = a; g.font = FONT(500, size, 'italic'); g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillStyle = '#fff';
  const hw = g.measureText(txt).width / 2 + 60; // reste dans l'écran
  g.lineWidth = 10; g.lineJoin = 'round'; g.strokeStyle = '#000'; g.strokeText(txt, clamp(x, hw, W - hw), y);
  g.fillText(txt, clamp(x, hw, W - hw), y); g.restore();
}
function icon(kind, x, y, u) { // rond rouge barré / rond vert validé
  if (u <= 0) return;
  g.save(); g.translate(x, y); const s = back(u); g.scale(s, s);
  g.beginPath(); g.arc(0, 0, 58, 0, Math.PI * 2); g.fillStyle = kind === 'x' ? '#d92b3a' : '#2fbf6b'; g.fill();
  g.lineWidth = 5; g.strokeStyle = '#fff'; g.stroke(); g.lineWidth = 11; g.lineCap = 'round'; g.beginPath();
  if (kind === 'x') { g.moveTo(-22, -22); g.lineTo(22, 22); g.moveTo(22, -22); g.lineTo(-22, 22); } else { g.moveTo(-24, 2); g.lineTo(-6, 20); g.lineTo(26, -18); }
  g.stroke(); g.restore();
}

function draw(T) {
  T = clamp(T, 0, DUR - 1e-4);
  g.fillStyle = '#000'; g.fillRect(0, 0, W, H);
  let i = SC.length - 1; for (let k = 0; k < SC.length; k++) if (T < (SC[k + 1] ? SC[k + 1].t0 - 0.15 : 1e9)) { i = k; break; }
  const s = SC[i];
  const out = SC[i + 1] ? ss(SC[i + 1].t0 - 0.35, SC[i + 1].t0 - 0.15, T) : ss(DUR - 0.8, DUR, T);
  g.save(); g.globalAlpha = 1 - out;
  if (s.card) { // écran noir avec juste une phrase en italique
    italic(s.card, W / 2, H / 2, 54, clamp((T - s.t0 + 0.1) / 0.4));
  } else {
    // image courante (séquence éventuelle), répétitions en boucle, version coloriée
    let cur = { img: s.img, hl: s.hl, hlAt: s.hlAt ?? 0.15 };
    for (const q of s.seq || []) if (T >= at(s, q.at)) cur = { ...q, hlAt: q.at };
    bigText(s, T); // derrière le personnage
    const im = IMG[cur.img];
    const r = charRect(s, T, im);
    if (s.alt) {
      const per = s.period || 0.8, ph = ((T - s.t0) / per) % 2, mix = ph < 1 ? ss(0.65, 1, ph) : 1 - ss(1.65, 2, ph);
      drawChar(im, r, 1 - mix); drawChar(IMG[s.alt], r, mix);
    } else drawChar(im, r);
    if (cur.hl) { // le muscle s'allume puis pulse doucement
      const k = T - at(s, cur.hlAt); const a = clamp(k / 0.5) * (0.82 + 0.18 * Math.sin(T * 4));
      if (k > 0) drawChar(IMG[cur.hl], r, a);
    }
    for (const t of s.tags || []) if (t.until === undefined || T < at(s, t.until)) tag(r, t, T, at(s, t.at ?? 0.2));
    if (s.guide !== undefined && T > at(s, 0.15)) { // ligne pointillée « hauteur des épaules »
      g.save(); g.globalAlpha = clamp((T - at(s, 0.15)) / 0.4) * 0.9; g.setLineDash([18, 14]); g.strokeStyle = '#36d27a'; g.lineWidth = 4;
      const y = r.y + s.guide * r.h; g.beginPath(); g.moveTo(r.x + r.w * 0.05, y); g.lineTo(r.x + r.w * 0.95, y); g.stroke(); g.restore();
    }
    if (s.text) italic(s.text, (s.textX ?? 0.79) * W, (s.textY ?? 0.5) * H, 46, clamp((T - at(s, s.textAt ?? 0.2)) / 0.4));
  }
  for (const ic of s.icons || []) icon(ic.kind, (ic.x ?? 0.21) * W, (ic.y ?? 0.5) * H, (T - at(s, ic.at)) / 0.3);
  if (s.label) label(s.label, (T - s.t0 + 0.1) / 0.35);
  g.restore();
}

await document.fonts.load('italic 500 40px Montserrat');
await document.fonts.load('700 40px Montserrat');
window.renderAt = (T) => draw(T);
document.body.classList.add('ready');
if (!Q.has('manual')) { const t0 = performance.now(); const loop = () => { draw(((performance.now() - t0) / 1000) % DUR); requestAnimationFrame(loop); }; loop(); }
