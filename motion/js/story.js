// Moteur de vidéos courtes (1080×1920) pour 3 styles, piloté par ./duel/<v>.json :
//  - count : « Count her YES » (#5 → #1, boutons YES / NO)
//  - pct   : « What men / women think » (jauge circulaire qui compte jusqu'au % réel + source)
//  - flag  : « Green flag or red flag? » (tampon GREEN / RED qui s'abat sur l'image)
// Chaque ligne = une phrase de la voix off, écrite mot à mot à son rythme.
const Q = new URLSearchParams(location.search);
const BASE = './duel/';
const CFG = await (await fetch(`${BASE}${Q.get('v')}.json`)).json();
const cv = document.getElementById('c'), g = cv.getContext('2d');
const W = 1080, H = 1920, DUR = CFG.dur, L = CFG.lines;
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const ss = (a, b, x) => { const u = clamp((x - a) / (b - a)); return u * u * (3 - 2 * u); };
const back = (u) => { u = clamp(u); const c = 1.8; return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2; };
const eout = (u) => 1 - (1 - clamp(u)) ** 3;
const FONT = (w, s) => `${w} ${s}px Montserrat, "Noto Color Emoji", sans-serif`;
const RED = '#ff2a4d', GOLD = '#ffd23f', GREEN = '#22c55e', INK = '#1b0a24';

// ---------- images ----------
const IMG = {};
const names = new Set([CFG.bg, CFG.hookImg, ...L.map((l) => l.img).filter(Boolean)]);
await Promise.all([...names].map((n) => new Promise((res) => { const im = new Image(); im.onload = () => { IMG[n] = im; res(); }; im.onerror = res; im.src = `${BASE}img/${n}.jpg`; })));

// ---------- scènes (lignes regroupées) ----------
const scenes = [];
for (const l of L) { let s = scenes[scenes.length - 1]; if (!s || s.id !== l.scene) { s = { id: l.scene, lines: [], kind: l.role }; scenes.push(s); } s.lines.push(l); }
scenes.forEach((s, i) => { s.t0 = s.lines[0].t0 - 0.12; s.t1 = i + 1 < scenes.length ? scenes[i + 1].lines[0].t0 - 0.12 : DUR; });

// ---------- sons ----------
const EVENTS = [];
for (const s of scenes) {
  const f = s.lines[0];
  if (s.kind === 'num') EVENTS.push({ t: f.t0 - 0.05, type: 'boom' });
  if (s.kind === 'ask' || s.kind === 'intro' || s.kind === 'end') EVENTS.push({ t: f.t0 - 0.12, type: 'whoosh' });
  for (const l of s.lines) {
    if (l.role === 'q') { EVENTS.push({ t: l.t0 - 0.12, type: 'whoosh' }, { t: l.yn, type: 'pop' }, { t: l.yn + 0.12, type: 'pop' }); }
    if (l.role === 'reveal') EVENTS.push({ t: l.t0, type: 'tick' }, { t: l.t0 + 0.25, type: 'tick' }, { t: l.t0 + 0.5, type: 'tick' });
    if (l.role === 'punch') EVENTS.push({ t: l.t0, type: 'boom' });
    if (l.role === 'reveal' && l.punchAtEnd) EVENTS.push({ t: l.t1 - 0.15, type: 'boom' });
    if (l.role === 'reveal' && !l.punchAtEnd) EVENTS.push({ t: l.t1 - 0.1, type: 'ding' });
    if (l.role === 'verdict') EVENTS.push({ t: l.t0 - 0.03, type: 'boom' });
  }
}
const hooks = L.filter((l) => l.role === 'hook');
if (hooks.length > 1) EVENTS.push({ t: hooks[hooks.length - 1].t0, type: 'boom' });
EVENTS.sort((a, b) => a.t - b.t);
Object.assign(window, { DUR, EVENTS, CFG });

// ---------- dessin ----------
function rr(x, y, w, h, r) { g.beginPath(); g.roundRect(x, y, w, h, r); }
function cover(img, x, y, w, h, z = 1) {
  if (!img) return; const s = Math.max(w / img.width, h / img.height) * z, iw = img.width * s, ih = img.height * s;
  g.drawImage(img, x + (w - iw) / 2, y + (h - ih) / 2, iw, ih);
}
function words(str) { let red = false; return str.split(' ').map((w) => { const s0 = w.startsWith('*'), s1 = w.endsWith('*'); if (s0) red = true; const o = { w: w.replace(/\*/g, ''), red }; if (s1) red = false; return o; }); }
function rich(str, cx, cy, size, maxW, n = 1e9, pop = 0) {
  g.font = FONT(900, size);
  const ws = words(str), sp = g.measureText(' ').width, lines = [[]]; let lw = 0;
  for (const w of ws) { const ww = g.measureText(w.w).width; if (lw + ww > maxW && lines[lines.length - 1].length) { lines.push([]); lw = 0; } lines[lines.length - 1].push({ ...w, ww }); lw += ww + sp; }
  const lh = size * 1.18; let idx = 0;
  lines.forEach((ln, li) => {
    const tw = ln.reduce((a, w) => a + w.ww, 0) + sp * (ln.length - 1);
    let x = cx - tw / 2; const y = cy + (li - (lines.length - 1) / 2) * lh;
    for (const w of ln) {
      if (idx < n) {
        const sc = idx === n - 1 ? 1 + 0.3 * pop : 1;
        g.save(); g.translate(x + w.ww / 2, y); g.scale(sc, sc); g.textAlign = 'center'; g.textBaseline = 'middle'; g.lineJoin = 'round';
        g.lineWidth = size * 0.22; g.strokeStyle = INK; g.strokeText(w.w, 0, 0);
        g.shadowColor = 'rgba(0,0,0,0.45)'; g.shadowBlur = 12; g.shadowOffsetY = 6; g.fillStyle = w.red ? RED : '#fffaf0'; g.fillText(w.w, 0, 0); g.restore();
      }
      x += w.ww + sp; idx++;
    }
  });
}
function say(l, T, cy, size = 82) { // mot à mot au rythme de la voix
  const nw = words(l.text).length, u = clamp((T - l.t0) / Math.max(0.2, l.t1 - l.t0));
  const n = T < l.t0 - 0.05 ? 0 : Math.min(nw, Math.floor(u * nw) + 1), pop = n < nw ? Math.max(0, 1 - ((u * nw) % 1) * 3) : 0;
  rich(l.text, W / 2, cy, size, 940, n, pop);
}
function card(img, cx, cy, w, h, u, rot, z = 1) {
  if (u <= 0.001) return;
  g.save(); g.translate(cx, cy); g.rotate(rot); g.scale(u, u);
  g.shadowColor = 'rgba(30,0,40,0.5)'; g.shadowBlur = 50; g.shadowOffsetY = 22;
  rr(-w / 2, -h / 2, w, h, 52); g.fillStyle = '#fff'; g.fill(); g.shadowColor = 'transparent';
  rr(-w / 2 + 10, -h / 2 + 10, w - 20, h - 20, 44); g.clip(); cover(img, -w / 2, -h / 2, w, h, z); g.restore();
}
function pill(txt, cx, cy, size, bg, fg, u = 1, rot = 0, border = '#fff') {
  if (u <= 0.001) return;
  g.save(); g.translate(cx, cy); g.rotate(rot); g.scale(u, u); g.font = FONT(900, size);
  const tw = g.measureText(txt).width + size * 1.1, h = size * 1.75;
  g.shadowColor = 'rgba(0,0,0,0.35)'; g.shadowBlur = 20; g.shadowOffsetY = 10;
  rr(-tw / 2, -h / 2, tw, h, h / 2); g.fillStyle = bg; g.fill(); g.shadowColor = 'transparent';
  g.lineWidth = 6; g.strokeStyle = border; g.stroke();
  g.fillStyle = fg; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(txt, 0, size * 0.06); g.restore();
}
function bigText(txt, cx, cy, size, color, sc = 1) {
  g.save(); g.translate(cx, cy); g.scale(sc, sc); g.font = FONT(900, size); g.textAlign = 'center'; g.textBaseline = 'middle'; g.lineJoin = 'round';
  g.lineWidth = size * 0.1; g.strokeStyle = INK; g.strokeText(txt, 0, 0); g.shadowColor = 'rgba(255,210,63,0.55)'; g.shadowBlur = 40; g.fillStyle = color; g.fillText(txt, 0, 0); g.restore();
}
// jauge circulaire : se remplit pendant que le nombre compte jusqu'au % réel
function gauge(cx, cy, r, value, u, label, punch) {
  const v = Math.round(value * eout(u));
  g.save(); g.translate(cx, cy); const s = (1 + 0.12 * punch) * back(Math.min(1, u * 3)); g.scale(s, s);
  g.beginPath(); g.arc(0, 0, r + 14, 0, Math.PI * 2); g.fillStyle = INK; g.fill();
  g.beginPath(); g.arc(0, 0, r - 8, 0, Math.PI * 2); g.lineWidth = 30; g.strokeStyle = 'rgba(255,255,255,0.15)'; g.stroke();
  const grd = g.createLinearGradient(-r, -r, r, r); grd.addColorStop(0, GOLD); grd.addColorStop(1, '#ff7a3d');
  g.beginPath(); g.arc(0, 0, r - 8, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * (v / 100)); g.lineWidth = 30; g.lineCap = 'round'; g.strokeStyle = grd;
  g.shadowColor = 'rgba(255,190,60,0.8)'; g.shadowBlur = 30; g.stroke(); g.shadowColor = 'transparent';
  g.font = FONT(900, r * 0.62); g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillStyle = '#fff'; g.fillText(v + '%', 0, 8);
  g.restore();
  if (label) pill(label, cx, cy + r + 70, Math.min(46, 900 / label.length), '#fff', INK, back(Math.min(1, u * 2.5 - 0.6)), 0, INK);
}
function confetti(cx, cy, t0, T) {
  const k = T - t0; if (k < 0 || k > 1.2) return;
  const cols = [GOLD, RED, GREEN, '#3fa7ff', '#fff'];
  for (let i = 0; i < 46; i++) {
    const a = (i / 46) * Math.PI * 2 + i, sp = 500 + (i * 137) % 600, x = cx + Math.cos(a) * sp * k, y = cy + Math.sin(a) * sp * k + 900 * k * k;
    g.save(); g.globalAlpha = 1 - k / 1.2; g.translate(x, y); g.rotate(k * 8 + i); g.fillStyle = cols[i % 5]; g.fillRect(-9, -5, 18, 10); g.restore();
  }
}

// ---------- scènes ----------
function sceneHook(s, T) {
  const ls = s.lines, z = 1.05 + 0.25 * ss(s.t0, s.t1, T), u = back((T - s.t0) / 0.4);
  card(IMG[CFG.hookImg], W / 2, 740, 840, 1000, u, Math.sin(T * 1.5) * 0.02, z);
  if (ls.length === 1) say(ls[0], T, 1440, 84);
  else { say(ls[0], T, 1390, 80); if (T >= ls[1].t0 - 0.05) say(ls[1], T, 1620, 104); }
}
function sceneIntro(s, T) {
  const a = T - s.t0, u = back(a / 0.35);
  bigText('5', W / 2, 760, 420, GOLD, (1 + 2.2 * Math.exp(-a * 7)) * u);
  say(s.lines[0], T, 1130, 90);
  if (s.lines[1] && T >= s.lines[1].t0 - 0.05) { say(s.lines[1], T, 1300, 96); pill('YES ✅ = 1 point', W / 2, 1520, 62, GREEN, '#fff', back((T - s.lines[1].t0 - 0.3) / 0.4), -0.04); }
}
function sceneNum(s, T) {
  const num = s.lines[0], q = s.lines[1], n = num.n, a = T - s.t0;
  const toBadge = ss(q.t0 - 0.15, q.t0 + 0.25, T);
  const big = (1 + 2.5 * Math.exp(-a * 8)) * back(a / 0.3);
  const sc = big * (1 - toBadge) + 0.32 * toBadge, cx = W / 2 * (1 - toBadge) + 170 * toBadge, cy = 900 * (1 - toBadge) + 330 * toBadge;
  if (toBadge < 1) { g.save(); g.globalAlpha = 0.3 * (1 - toBadge); g.fillStyle = '#12051c'; g.fillRect(-50, -50, W + 100, H + 100); g.restore(); }
  const qa = T - q.t0;
  if (T >= q.t0 - 0.05) { card(IMG[q.img], W / 2, 760, 780, 900, back(qa / 0.4), Math.sin(T * 1.6) * 0.02, 1.03 + 0.06 * clamp(qa / 3)); say(q, T, 1340, 80); }
  bigText('#' + n, cx, cy, 340, GOLD, sc);
  if (T >= q.yn) {
    const p = 1 + 0.06 * Math.sin(T * 12);
    pill('YES ✅', W / 2 - 230, 1600, 70, GREEN, '#fff', back((T - q.yn) / 0.35) * p, -0.05);
    pill('NO ❌', W / 2 + 230, 1600, 70, RED, '#fff', back((T - q.yn - 0.12) / 0.35) * p, 0.05);
  }
}
function scenePct(s, T) {
  const ask = s.lines[0], rv = s.lines.filter((l) => l.role === 'reveal'), punch = s.lines.find((l) => l.role === 'punch');
  const a = T - s.t0, revealing = T >= rv[0].t0 - 0.1;
  const shrink = ss(rv[0].t0 - 0.2, rv[0].t0 + 0.3, T);
  card(IMG[ask.img], W / 2, 700 - 120 * shrink, 800 - 140 * shrink, 900 - 230 * shrink, back(a / 0.4), Math.sin(T * 1.5) * 0.02, 1.03 + 0.05 * clamp(a / 4));
  // la question reste en haut, la phrase de la voix en cours s'écrit dessous
  if (!revealing) say(ask, T, 1340, 80);
  if (!revealing && T > ask.t1) { // petite attente : « devine… »
    const k = T - ask.t1; pill('Guess… 🤔', W / 2, 1600, 60, INK, GOLD, back(k / 0.3) * (1 + 0.05 * Math.sin(T * 10)));
  }
  if (revealing) {
    const cur = [...s.lines].reverse().find((l) => T >= l.t0 - 0.05 && l.role !== 'ask') || rv[0];
    rv.forEach((r, i) => {
      const u = clamp((T - r.t0) / Math.max(0.6, (r.t1 - r.t0) * 0.75));
      if (T < r.t0 - 0.05) return;
      const pt = r.punchAtEnd ? r.t1 - 0.15 : punch ? punch.t0 : r.t1;
      const pk = T > pt ? Math.exp(-(T - pt) * 6) : 0;
      const cx = rv.length > 1 ? (i ? 790 : 290) : W / 2, rad = rv.length > 1 ? 165 : 210;
      gauge(cx, 1410, rad, r.value, u, r.label, pk);
      if (T > pt) confetti(cx, 1410, pt, T);
    });
    if (punch && T >= punch.t0 - 0.05) pill('YES!', W / 2 + 250, 1250, 74, GREEN, '#fff', back((T - punch.t0) / 0.3), -0.12);
    say(cur, T, 1060, 72);
  }
  if (ask.src) { g.save(); g.font = FONT(600, 26); g.fillStyle = 'rgba(255,255,255,0.85)'; g.textAlign = 'left'; g.fillText(ask.src, 40, H - 52); g.restore(); }
}
function sceneFlag(s, T) {
  const ask = s.lines[0], v = s.lines.find((l) => l.role === 'verdict'), a = T - s.t0;
  card(IMG[ask.img], W / 2, 760, 820, 960, back(a / 0.4), Math.sin(T * 1.5) * 0.02, 1.03 + 0.05 * clamp(a / 4));
  say(ask, T, 1390, 78);
  if (v && T < v.t0 - 0.05 && T > ask.t1) {
    const p = 1 + 0.05 * Math.sin(T * 10);
    pill('🟢', W / 2 - 150, 1620, 70, GREEN, '#fff', back((T - ask.t1) / 0.3) * p);
    pill('🔴', W / 2 + 150, 1620, 70, RED, '#fff', back((T - ask.t1 - 0.1) / 0.3) * p);
  }
  if (v && T >= v.t0 - 0.05) {
    const k = T - v.t0, col = v.verdict === 'green' ? GREEN : v.verdict === 'red' ? RED : GOLD;
    g.save(); g.globalAlpha = 0.28 * Math.exp(-k * 2.5); g.fillStyle = col; g.fillRect(0, 0, W, H); g.restore();
    if (v.verdict === '?') {
      pill('GREEN 🟢', W / 2 - 200, 760, 66, GREEN, '#fff', back(k / 0.3), -0.12);
      pill('RED 🔴', W / 2 + 210, 900, 66, RED, '#fff', back((k - 0.15) / 0.3), 0.1);
      say(v, T, 1620, 96);
    } else {
      const sc = (1 + 1.8 * Math.exp(-k * 10)) * back(k / 0.25);
      g.save(); g.translate(W / 2, 760); g.rotate(-0.16); g.scale(sc, sc);
      g.font = FONT(900, 120); const txt = v.verdict === 'green' ? 'GREEN FLAG' : 'RED FLAG', tw = g.measureText(txt).width + 90;
      rr(-tw / 2, -100, tw, 200, 30); g.fillStyle = col; g.shadowColor = 'rgba(0,0,0,0.5)'; g.shadowBlur = 30; g.fill(); g.shadowColor = 'transparent';
      g.lineWidth = 14; g.strokeStyle = '#fff'; g.stroke();
      g.fillStyle = '#fff'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(txt, 0, 8); g.restore();
      bigText(v.verdict === 'green' ? '🟢' : '🚩', W / 2, 1620, 150, '#fff', back((k - 0.1) / 0.3));
    }
  }
}
function sceneEnd(s, T) {
  const ls = s.lines, a = T - s.t0, last = ls[ls.length - 1];
  const em = CFG.style === 'count' && T > last.t0 ? '🔁' : '💬';
  g.save(); g.translate(W / 2, 660); const u = back(a / 0.4) * (1 + 0.05 * Math.sin(T * 7)); g.scale(u, u);
  g.font = FONT(400, 300); g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(em, 0, 0); g.restore();
  const ys = [980, 1180, 1400], sz = [100, 80, 74];
  ls.forEach((l, i) => { if (T >= l.t0 - 0.05) say(l, T, ys[i], sz[i]); });
}

function draw(T) {
  T = clamp(T, 0, DUR - 1e-4);
  const s = scenes.find((x) => T >= x.t0 && T < x.t1) || scenes[0];
  let shake = 0;
  for (const e of EVENTS) if (e.type === 'boom' && T >= e.t && T < e.t + 0.5) shake = Math.max(shake, Math.exp(-(T - e.t) * 9) * 26);
  g.save(); g.translate(Math.sin(T * 93) * shake, Math.cos(T * 71) * shake);
  g.drawImage(IMG[CFG.bg], -40, -40, W + 80, H + 80);
  const k = s.kind;
  if (k === 'hook') sceneHook(s, T);
  else if (k === 'intro') sceneIntro(s, T);
  else if (k === 'num') sceneNum(s, T);
  else if (k === 'ask') (CFG.style === 'flag' ? sceneFlag : scenePct)(s, T);
  else sceneEnd(s, T);
  g.restore();
  // bandeau permanent
  const first = scenes[1] ? scenes[1].t0 : 2;
  if (CFG.banner && T > first) {
    const u = back((T - first) / 0.4);
    pill(CFG.banner, W / 2, 130, 48, INK, GOLD, u);
    if (CFG.style === 'count') {
      const cur = s.kind === 'num' ? s.lines[0].n : s.kind === 'end' ? 0 : 6;
      for (let i = 0; i < 5; i++) {
        const n = 5 - i, x = W / 2 + (i - 2) * 90;
        g.save(); g.globalAlpha = u; g.beginPath(); g.arc(x, 230, 30, 0, Math.PI * 2); g.fillStyle = n === cur ? GOLD : cur <= n && cur !== 6 ? '#fff' : 'rgba(255,255,255,0.35)'; g.fill();
        g.font = FONT(900, 32); g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillStyle = INK; g.fillText(String(n), x, 232); g.restore();
      }
    } else {
      const asks = scenes.filter((x) => x.kind === 'ask'), idx = asks.indexOf(s);
      asks.forEach((x, i) => { g.save(); g.globalAlpha = u; rr(W / 2 - asks.length * 45 + i * 90 + 8, 214, 74, 14, 7); g.fillStyle = i < idx || (s.kind === 'end') ? '#fff' : i === idx ? GOLD : 'rgba(255,255,255,0.35)'; g.fill(); g.restore(); });
    }
  }
  g.save(); g.font = FONT(800, 38); g.textAlign = 'right'; g.fillStyle = '#fff'; g.shadowColor = 'rgba(0,0,0,0.5)'; g.shadowBlur = 8; g.fillText(CFG.pseudo, W - 40, H - 52); g.restore();
  for (const e of EVENTS) if (e.type === 'boom' && T >= e.t && T < e.t + 0.18) { g.save(); g.globalAlpha = (1 - (T - e.t) / 0.18) * 0.4; g.fillStyle = '#fff'; g.fillRect(0, 0, W, H); g.restore(); }
}

await document.fonts.load('900 80px Montserrat');
await document.fonts.load('400 80px "Noto Color Emoji"').catch(() => {});
window.renderAt = (T) => draw(T);
document.body.classList.add('ready');
if (!Q.has('manual')) { const t0 = performance.now(); const loop = () => { draw(((performance.now() - t0) / 1000) % DUR); requestAnimationFrame(loop); }; loop(); }
