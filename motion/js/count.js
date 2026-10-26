// « Count her YES » : quiz couple ultra-rapide (≤ 30 s) en 1080×1920.
// Accroche-défi, numéros #5 → #1 qui claquent, image + question mot à mot,
// boutons YES / NO après chaque question, fin qui renvoie au début (boucle).
const Q = new URLSearchParams(location.search);
const BASE = './duel/';
const CFG = await (await fetch(`${BASE}${Q.get('v') || 'count1'}.json`)).json();
const cv = document.getElementById('c'), g = cv.getContext('2d');
const W = 1080, H = 1920, DUR = CFG.dur;
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const ss = (a, b, x) => { const u = clamp((x - a) / (b - a)); return u * u * (3 - 2 * u); };
const back = (u) => { u = clamp(u); const c = 1.8; return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2; };
const FONT = (w, s) => `${w} ${s}px Montserrat, "Noto Color Emoji", sans-serif`;
const RED = '#ff2a4d', GOLD = '#ffd23f', GREEN = '#22c55e', INK = '#1b0a24';

const IMG = {};
const names = [CFG.bg, CFG.hookImg, ...Object.values(CFG.img)];
await Promise.all(names.map((n) => new Promise((res) => { const im = new Image(); im.onload = () => { IMG[n] = im; res(); }; im.onerror = res; im.src = `${BASE}img/${n}.jpg`; })));

// sons
const EVENTS = [];
CFG.lines.forEach((l, i) => {
  if (l.role === 'num') EVENTS.push({ t: l.t0 - 0.05, type: 'boom' });
  if (l.role === 'q') EVENTS.push({ t: l.t0 - 0.12, type: 'whoosh' }, { t: l.yn, type: 'pop' }, { t: l.yn + 0.12, type: 'pop' });
  if (i === 1) EVENTS.push({ t: l.t0, type: 'boom' });
  if (i === 2) EVENTS.push({ t: l.t0, type: 'whoosh' });
  if (i === 3) EVENTS.push({ t: l.t0 + 0.3, type: 'ding' });
  if (i === 14) EVENTS.push({ t: l.t0, type: 'whoosh' });
});
Object.assign(window, { DUR, EVENTS, CFG });

function rr(x, y, w, h, r) { g.beginPath(); g.roundRect(x, y, w, h, r); }
function cover(img, x, y, w, h, z = 1, fx = 0.5, fy = 0.5) {
  if (!img) return; const s = Math.max(w / img.width, h / img.height) * z, iw = img.width * s, ih = img.height * s;
  g.drawImage(img, x + (w - iw) * fx, y + (h - ih) * fy, iw, ih);
}
function words(str) { let red = false; return str.split(' ').map((w) => { const s0 = w.startsWith('*'), s1 = w.endsWith('*'); if (s0) red = true; const o = { w: w.replace(/\*/g, ''), red }; if (s1) red = false; return o; }); }
function rich(str, cx, cy, size, maxW, n = 1e9, pop = 0) {
  g.font = FONT(900, size);
  if (g.measureText(str.replace(/\*/g, '')).width > maxW && size > 60 && str.length < 26) return rich(str, cx, cy, size * 0.9, maxW, n, pop);
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
// texte qui s'écrit mot à mot au rythme de la voix
function say(l, T, cy, size = 84) {
  const nw = words(l.text).length, u = clamp((T - l.t0) / Math.max(0.2, l.t1 - l.t0));
  const n = T < l.t0 ? 0 : Math.min(nw, Math.floor(u * nw) + 1), pop = n < nw ? Math.max(0, 1 - ((u * nw) % 1) * 3) : 0;
  rich(l.text, W / 2, cy, size, 940, n, pop);
}
function card(img, cx, cy, w, h, u, rot, z = 1) {
  if (u <= 0.001) return;
  g.save(); g.translate(cx, cy); g.rotate(rot); g.scale(u, u);
  g.shadowColor = 'rgba(30,0,40,0.5)'; g.shadowBlur = 50; g.shadowOffsetY = 22;
  rr(-w / 2, -h / 2, w, h, 52); g.fillStyle = '#fff'; g.fill(); g.shadowColor = 'transparent';
  rr(-w / 2 + 10, -h / 2 + 10, w - 20, h - 20, 44); g.clip(); cover(img, -w / 2, -h / 2, w, h, z); g.restore();
}
function pill(txt, cx, cy, size, bg, fg, u = 1, rot = 0) {
  if (u <= 0.001) return;
  g.save(); g.translate(cx, cy); g.rotate(rot); g.scale(u, u); g.font = FONT(900, size);
  const tw = g.measureText(txt).width + size * 1.1, h = size * 1.75;
  g.shadowColor = 'rgba(0,0,0,0.35)'; g.shadowBlur = 20; g.shadowOffsetY = 10;
  rr(-tw / 2, -h / 2, tw, h, h / 2); g.fillStyle = bg; g.fill(); g.shadowColor = 'transparent';
  g.lineWidth = 6; g.strokeStyle = '#fff'; g.stroke();
  g.fillStyle = fg; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(txt, 0, size * 0.06); g.restore();
}

function draw(T) {
  T = clamp(T, 0, DUR - 1e-4);
  const L = CFG.lines;
  let k = 0; for (let i = 0; i < L.length; i++) if (T >= L[i].t0 - 0.12) k = i;
  const l = L[k];
  // secousse sur les « boom »
  let shake = 0;
  for (const e of EVENTS) if (e.type === 'boom' && T >= e.t && T < e.t + 0.5) shake = Math.max(shake, Math.exp(-(T - e.t) * 9) * 28);
  g.save(); g.translate(Math.sin(T * 93) * shake, Math.cos(T * 71) * shake);
  g.drawImage(IMG[CFG.bg], -40, -40, W + 80, H + 80);

  if (l.role === 'hook') {
    const z = 1.05 + 0.25 * ss(0, L[2].t0, T), u = back(T / 0.4);
    card(IMG[CFG.hookImg], W / 2, 740, 840, 1000, u, Math.sin(T * 1.5) * 0.02, z);
    say(L[0], T, 1390, 80);
    if (T >= L[1].t0 - 0.05) say(L[1], T, 1620, 110);
  } else if (l.role === 'intro') {
    const a = T - L[2].t0, u = back(a / 0.35);
    g.save(); g.translate(W / 2, 760); const s = (1 + 2.2 * Math.exp(-a * 7)) * u; g.scale(s, s);
    g.font = FONT(900, 420); g.textAlign = 'center'; g.textBaseline = 'middle'; g.lineJoin = 'round';
    g.lineWidth = 40; g.strokeStyle = INK; g.strokeText('5', 0, 0); g.fillStyle = GOLD; g.shadowColor = 'rgba(255,210,63,0.6)'; g.shadowBlur = 50; g.fillText('5', 0, 0); g.restore();
    say(L[2], T, 1130, 90);
    if (T >= L[3].t0 - 0.05) { say(L[3], T, 1300, 96); pill('YES ✅ = 1 point', W / 2, 1520, 62, GREEN, '#fff', back((T - L[3].t0 - 0.3) / 0.4), -0.04); }
  } else if (l.role === 'num' || l.role === 'q') {
    const n = l.n, num = L.find((x) => x.role === 'num' && x.n === n), q = L.find((x) => x.role === 'q' && x.n === n);
    const a = T - (num.t0 - 0.12);
    // grand numéro qui claque, puis rétrécit en badge
    const toBadge = ss(q.t0 - 0.15, q.t0 + 0.25, T);
    const big = (1 + 2.5 * Math.exp(-a * 8)) * back(a / 0.3);
    const sc = big * (1 - toBadge) + 0.32 * toBadge, cx = W / 2 * (1 - toBadge) + 170 * toBadge, cy = 900 * (1 - toBadge) + 310 * toBadge;
    if (toBadge < 1) { g.save(); g.globalAlpha = 0.3 * (1 - toBadge); g.fillStyle = '#12051c'; g.fillRect(-50, -50, W + 100, H + 100); g.restore(); }
    const qa = T - q.t0, cu = back(qa / 0.4);
    if (T >= q.t0 - 0.05) {
      card(IMG[CFG.img[n]], W / 2, 760, 780, 900, cu, Math.sin(T * 1.6) * 0.02, 1.03 + 0.06 * clamp(qa / 3));
      say(q, T, 1340, 80);
    }
    g.save(); g.translate(cx, cy); g.scale(sc, sc); g.font = FONT(900, 340); g.textAlign = 'center'; g.textBaseline = 'middle'; g.lineJoin = 'round';
    g.lineWidth = 34; g.strokeStyle = INK; g.strokeText('#' + n, 0, 0); g.shadowColor = 'rgba(255,210,63,0.6)'; g.shadowBlur = 40; g.fillStyle = GOLD; g.fillText('#' + n, 0, 0); g.restore();
    if (T >= q.yn) {
      const y1 = back((T - q.yn) / 0.35), y2 = back((T - q.yn - 0.12) / 0.35), p = 1 + 0.06 * Math.sin(T * 12);
      pill('YES ✅', W / 2 - 230, 1600, 70, GREEN, '#fff', y1 * p, -0.05);
      pill('NO ❌', W / 2 + 230, 1600, 70, RED, '#fff', y2 * p, 0.05);
    }
  } else { // fin : score + boucle
    const a = T - L[14].t0;
    g.save(); g.translate(W / 2, 640); const u = back(a / 0.4) * (1 + 0.05 * Math.sin(T * 7)); g.scale(u, u);
    g.font = FONT(400, 300); g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(T > L[16].t0 ? '🔁' : '💬', 0, 0); g.restore();
    say(L[14], T, 960, 100);
    if (T >= L[15].t0 - 0.05) say(L[15], T, 1170, 80);
    if (T >= L[16].t0 - 0.05) say(L[16], T, 1400, 74);
  }
  g.restore();
  // bandeau permanent + progression #5 → #1
  if (T > L[2].t0) {
    const u = back((T - L[2].t0) / 0.4);
    pill('COUNT HER YES 👀', W / 2, 130, 50, INK, GOLD, u);
    const cur = l.n || (l.role === 'end' ? 0 : 6);
    for (let i = 0; i < 5; i++) {
      const n = 5 - i, done = cur <= n && cur !== 6, x = W / 2 + (i - 2) * 90;
      g.save(); g.globalAlpha = u; g.beginPath(); g.arc(x, 230, 30, 0, Math.PI * 2); g.fillStyle = n === cur ? GOLD : done ? '#fff' : 'rgba(255,255,255,0.35)'; g.fill();
      g.font = FONT(900, 32); g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillStyle = INK; g.fillText(String(n), x, 232); g.restore();
    }
  }
  g.save(); g.font = FONT(800, 38); g.textAlign = 'right'; g.fillStyle = '#fff'; g.shadowColor = 'rgba(0,0,0,0.5)'; g.shadowBlur = 8; g.fillText(CFG.pseudo, W - 40, H - 60); g.restore();
  // flash blanc sur les « boom »
  for (const e of EVENTS) if (e.type === 'boom' && T >= e.t && T < e.t + 0.18) { g.save(); g.globalAlpha = (1 - (T - e.t) / 0.18) * 0.45; g.fillStyle = '#fff'; g.fillRect(0, 0, W, H); g.restore(); }
}

await document.fonts.load('900 80px Montserrat');
await document.fonts.load('400 80px "Noto Color Emoji"').catch(() => {});
window.renderAt = (T) => draw(T);
document.body.classList.add('ready');
if (!Q.has('manual')) { const t0 = performance.now(); const loop = () => { draw(((performance.now() - t0) / 1000) % DUR); requestAnimationFrame(loop); }; loop(); }
