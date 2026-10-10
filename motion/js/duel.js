// Vidéo quiz « ça ou ça » (1080×1920) : ouverture plein écran, sous-titres mot à mot
// calés sur la voix off, questions à deux images + compte à rebours.
// Le contenu vient de ./duel/video.json  — ?manual : rendu image par image.
const Q = new URLSearchParams(location.search);
const BASE = './duel/';
const CFG = await (await fetch(`${BASE}${Q.get('v') || 'video'}.json`)).json();

const cv = document.getElementById('c'), g = cv.getContext('2d');
const W = 1080, H = 1920;
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const ss = (a, b, x) => { const u = clamp((x - a) / (b - a)); return u * u * (3 - 2 * u); };
const back = (u) => { u = clamp(u); const c = 1.7; return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2; };
const FONT = (w, s) => `${w} ${s}px Montserrat, "Noto Color Emoji", sans-serif`;
const RED = '#ff2a4d', GOLD = '#ffd23f';

// ---------- Chargement des images ----------
const IMG = {};
const names = new Set();
for (const s of CFG.scenes) for (const k of ['img', 'logo']) if (s[k]) names.add(s[k]);
for (const s of CFG.scenes) for (const k of ['a', 'b']) if (s[k]) { names.add(s[k].img); if (s[k].logo) names.add(s[k].logo); }
if (CFG.bg) names.add(CFG.bg);
await Promise.all([...names].map((n) => new Promise((res) => { const im = new Image(); im.onload = () => { IMG[n] = im; res(); }; im.onerror = res; im.src = `${BASE}img/${n}.jpg`; })));

// ---------- Chronologie ----------
let t = 0;
for (const s of CFG.scenes) { s.t0 = s.t ?? t; t = s.t0 + s.d; }
const DUR = t;
const EVENTS = [];
for (const s of CFG.scenes) {
  EVENTS.push({ t: s.t0, type: 'whoosh' });
  if (s.type === 'q') { EVENTS.push({ t: s.t0 + 0.1, type: 'pop' }, { t: s.t0 + 0.35, type: 'pop' }); for (let k = 0; k < 3; k++) EVENTS.push({ t: s.t0 + s.cd + k, type: 'tick' }); EVENTS.push({ t: s.t0 + s.cd + 3, type: 'ding' }); }
  if (s.type === 'say' && s.img) EVENTS.push({ t: s.t0 + 0.05, type: 'pop' });
}
Object.assign(window, { DUR, EVENTS, CFG });

// ---------- Fond : papier froissé (généré une fois) ----------
const paper = document.createElement('canvas');
paper.width = W; paper.height = H;
{
  const p = paper.getContext('2d');
  const gr = p.createLinearGradient(0, 0, W, H);
  gr.addColorStop(0, CFG.colors?.[0] || '#9b59d0'); gr.addColorStop(1, CFG.colors?.[1] || '#c86ad8');
  p.fillStyle = gr; p.fillRect(0, 0, W, H);
  let seed = 11; const r = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
  // plis : grands triangles légèrement plus clairs / plus sombres
  for (let i = 0; i < 260; i++) {
    const x = r() * W, y = r() * H, s = 120 + r() * 380, a = r() * Math.PI * 2;
    p.beginPath(); p.moveTo(x, y);
    p.lineTo(x + Math.cos(a) * s, y + Math.sin(a) * s);
    p.lineTo(x + Math.cos(a + 0.6 + r()) * s * 0.8, y + Math.sin(a + 0.6 + r()) * s * 0.8);
    p.closePath();
    p.fillStyle = r() < 0.5 ? `rgba(255,255,255,${0.02 + r() * 0.04})` : `rgba(40,0,60,${0.02 + r() * 0.04})`;
    p.fill();
  }
  for (let i = 0; i < 90; i++) { // fines lignes de pli
    p.beginPath(); let x = r() * W, y = r() * H; p.moveTo(x, y);
    for (let k = 0; k < 4; k++) { x += (r() - 0.5) * 260; y += (r() - 0.5) * 260; p.lineTo(x, y); }
    p.strokeStyle = `rgba(255,255,255,${0.04 + r() * 0.05})`; p.lineWidth = 1 + r() * 1.5; p.stroke();
  }
}

// ---------- Outils de dessin ----------
function rr(x, y, w, h, r) { g.beginPath(); g.roundRect(x, y, w, h, r); }
function cover(img, x, y, w, h, zoom = 1, fx = 0.5, fy = 0.5) {
  if (!img) return;
  const s = Math.max(w / img.width, h / img.height) * zoom;
  const iw = img.width * s, ih = img.height * s;
  g.drawImage(img, x + (w - iw) * fx, y + (h - ih) * fy, iw, ih);
}
// texte avec *mots en rouge*, contour sombre, retour à la ligne auto ; n = nb de mots visibles
function words(str) { let red = false; return str.split(' ').map((w) => { const s0 = w.startsWith('*'), s1 = w.endsWith('*'); if (s0) red = true; const o = { w: w.replace(/\*/g, ''), red }; if (s1) red = false; return o; }); }
function rich(str, cx, cy, size, maxW, n = 1e9, alpha = 1, popLast = 0) {
  g.font = FONT(900, size);
  const ws = words(str), sp = g.measureText(' ').width;
  const lines = [[]]; let lw = 0;
  for (const w of ws) { const ww = g.measureText(w.w).width; if (lw + ww > maxW && lines[lines.length - 1].length) { lines.push([]); lw = 0; } lines[lines.length - 1].push({ ...w, ww }); lw += ww + sp; }
  const lh = size * 1.2; let idx = 0;
  lines.forEach((ln, li) => {
    const tw = ln.reduce((a, w) => a + w.ww, 0) + sp * (ln.length - 1);
    let x = cx - tw / 2; const y = cy + (li - (lines.length - 1) / 2) * lh;
    for (const w of ln) {
      if (idx < n) {
        const last = idx === n - 1, sc = last ? 1 + 0.25 * popLast : 1;
        g.save(); g.globalAlpha = alpha; g.translate(x + w.ww / 2, y); g.scale(sc, sc);
        g.textAlign = 'center'; g.textBaseline = 'middle'; g.lineJoin = 'round';
        g.lineWidth = size * 0.2; g.strokeStyle = '#1b0a24'; g.strokeText(w.w, 0, 0);
        g.shadowColor = 'rgba(0,0,0,0.4)'; g.shadowBlur = 10; g.shadowOffsetY = 5;
        g.fillStyle = w.red ? RED : '#fffaf0'; g.fillText(w.w, 0, 0);
        g.restore();
      }
      x += w.ww + sp; idx++;
    }
  });
  return lines.length * lh;
}
function card(img, cx, cy, w, h, u, rot = 0, label, logo) {
  if (u <= 0.001) return;
  g.save(); g.translate(cx, cy); g.rotate(rot); g.scale(u, u);
  g.shadowColor = 'rgba(30,0,40,0.45)'; g.shadowBlur = 40; g.shadowOffsetY = 18;
  rr(-w / 2, -h / 2, w, h, 44); g.fillStyle = '#fff'; g.fill();
  g.shadowColor = 'transparent';
  g.save(); rr(-w / 2 + 8, -h / 2 + 8, w - 16, h - 16, 38); g.clip(); cover(img, -w / 2, -h / 2, w, h, 1.02);
  if (logo) { const lw = w * 0.5; g.globalCompositeOperation = 'screen'; g.drawImage(logo, -lw / 2, -h / 2 + 16, lw, lw * logo.height / logo.width); g.globalCompositeOperation = 'source-over'; }
  g.restore();
  if (label) {
    g.font = FONT(900, 56); const tw = g.measureText(label).width + 60;
    rr(-tw / 2, h / 2 - 44, tw, 88, 44); g.fillStyle = '#1b0a24'; g.fill();
    g.fillStyle = '#fff'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(label, 0, h / 2 + 2);
  }
  g.restore();
}
function countdown(cx, cy, local) { // local : 0 → 3 s
  const n = Math.max(0, 3 - Math.floor(clamp(local, 0, 2.999))), f = clamp(local - Math.floor(clamp(local, 0, 2.999)));
  const pul = 1 + 0.12 * Math.max(0, 1 - f * 4), r = 78;
  g.save(); g.translate(cx, cy); g.scale(pul, pul);
  g.beginPath(); g.arc(0, 0, r, 0, Math.PI * 2); g.fillStyle = '#120616'; g.fill();
  g.beginPath(); g.arc(0, 0, r - 11, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * (1 - f)); g.lineWidth = 11; g.lineCap = 'round'; g.strokeStyle = '#fff'; g.stroke();
  g.font = FONT(900, 80); g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillStyle = '#fff'; g.fillText(String(n), 0, 6);
  g.restore();
}
// sous-titres : mot à mot sur la durée de chaque phrase de la voix
function caption(T, cy, size = 82) {
  const c = (CFG.captions || []).find((x) => T >= x.t0 - 0.05 && T < x.t1 + 0.35);
  if (!c) return;
  const ws = words(c.text).length;
  const u = clamp((T - c.t0) / Math.max(0.2, c.t1 - c.t0));
  const n = Math.min(ws, 1 + Math.floor(u * ws));
  const k = (u * ws) % 1;
  rich(c.text, W / 2, cy, size, 900, n, 1, Math.max(0, 1 - k * 3) * (n < ws ? 1 : 0));
}

// ---------- Scènes ----------
function sceneOpen(s, L) {
  // image plein écran qui se rapproche lentement (gros plan)
  const z = 1.05 + 0.45 * ss(0, s.d, L), up = back(L / 0.5), cw = 820, ch = 900, cy = 1150;
  g.save(); g.translate(W / 2, cy); g.rotate(Math.sin(L * 1.3) * 0.015); g.scale(up, up);
  g.shadowColor = 'rgba(30,0,40,0.45)'; g.shadowBlur = 40; g.shadowOffsetY = 18;
  rr(-cw / 2, -ch / 2, cw, ch, 48); g.fillStyle = '#fff'; g.fill(); g.shadowColor = 'transparent';
  rr(-cw / 2 + 9, -ch / 2 + 9, cw - 18, ch - 18, 42); g.clip();
  cover(IMG[s.img], -cw / 2, -ch / 2, cw, ch, z, s.fx ?? 0.5, s.fy ?? 0.5);
  const gr = g.createLinearGradient(0, 0, 0, ch / 2); gr.addColorStop(0, 'rgba(10,0,20,0)'); gr.addColorStop(1, 'rgba(10,0,20,0.75)');
  g.fillStyle = gr; g.fillRect(-cw / 2, 0, cw, ch / 2);
  g.restore();
  const c = CFG.captions[0], nw = words(s.title).length;
  const u = clamp((L + s.t0 - c.t0) / (c.t1 - c.t0)), n = Math.min(nw, Math.floor(u * nw) + (u > 0 ? 1 : 0));
  const b = back((L - (c.t1 - s.t0) + 0.1) / 0.5);
  rich(s.title, W / 2, 1420, 84, 760, n, 1, n < nw ? Math.max(0, 1 - ((u * nw) % 1) * 3) : 0);
  g.save(); g.translate(W / 2, 1655); g.rotate(-0.03); g.scale(b, b);
  g.font = FONT(900, 60); const tw = g.measureText(s.tag).width + 70;
  rr(-tw / 2, -52, tw, 104, 52); g.fillStyle = RED; g.fill();
  g.fillStyle = '#fff'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(s.tag, 0, 4); g.restore();
}
function sceneSay(s, L, T) {
  if (s.img) {
    const u = back(L / 0.45), bob = Math.sin(L * 2.4) * 10;
    card(IMG[s.img], W / 2, 620 + bob, s.w || 560, s.h || 700, u, Math.sin(L * 1.3) * 0.03);
  }
  caption(T, s.img ? 1180 : 900);
  if (s.emoji) { const u = back((L - 0.3) / 0.5); g.save(); g.translate(W / 2, 1420); g.scale(u, u); g.font = FONT(400, 170); g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(s.emoji, 0, 0); g.restore(); }
}
function sceneQ(s, L) {
  const ua = back((L - 0.05) / 0.5), ub = back((L - 0.3) / 0.5);
  const cw = 760, ch = 620;
  // la question s'écrit mot à mot pendant que la voix la dit
  const nw = words(s.q).length, uq = clamp((L - s.qv[0]) / (s.qv[1] - s.qv[0]));
  const nq = L < s.qv[0] ? 0 : Math.min(nw, Math.floor(uq * nw) + 1), pq = nq < nw ? Math.max(0, 1 - ((uq * nw) % 1) * 3) : 0;
  const cd = L - s.cd;
  if (!s.b) { // une seule image (ex. « Who is his future wife? »)
    card(IMG[s.a.img], W / 2, 700 + Math.sin(L * 2) * 8, 820, 1000, ua, Math.sin(L * 1.2) * 0.02);
    rich(s.q, W / 2, 1360, 80, 980, nq, 1, pq);
    if (cd > -0.1 && cd < 3.3) { g.save(); g.globalAlpha = ss(-0.1, 0.1, cd) * (1 - ss(3.0, 3.3, cd)); countdown(W / 2, 1580, clamp(cd, 0, 3)); g.restore(); }
    return;
  }
  card(IMG[s.a.img], W / 2 - (1 - ss(0, 0.5, L)) * 500, 450, cw, ch, ua, -0.015, s.a.label, IMG[s.a.logo]);
  card(IMG[s.b.img], W / 2 + (1 - ss(0.25, 0.75, L)) * 500, 1400, cw, ch, ub, 0.015, s.b.label, IMG[s.b.logo]);
  const qa = 1 - ss(-0.15, 0.1, cd);
  if (qa > 0 && nq > 0) rich(s.q, W / 2, 925, 72, 980, nq, qa, pq);
  if (cd > -0.1 && cd < 3.3) { g.save(); g.globalAlpha = ss(-0.1, 0.1, cd) * (1 - ss(3.0, 3.3, cd)); countdown(W / 2, 925, clamp(cd, 0, 3)); g.restore(); }
}

function draw(T) {
  T = clamp(T, 0, DUR - 1e-4);
  if (IMG[CFG.bg]) g.drawImage(IMG[CFG.bg], 0, 0, W, H); else g.drawImage(paper, 0, 0);
  const s = CFG.scenes.find((x) => T >= x.t0 && T < x.t0 + x.d) || CFG.scenes[CFG.scenes.length - 1];
  const L = T - s.t0;
  const tin = ss(0, 0.2, L), tout = ss(s.d - 0.18, s.d, L);
  g.save(); g.globalAlpha = Math.min(tin, 1 - tout);
  if (s.type === 'open') sceneOpen(s, L);
  else if (s.type === 'say') sceneSay(s, L, T);
  else if (s.type === 'q') sceneQ(s, L);
  g.restore();
  // signature du compte
  g.save(); g.font = FONT(800, 38); g.textAlign = 'right'; g.globalAlpha = 0.9; g.fillStyle = '#fff';
  g.shadowColor = 'rgba(0,0,0,0.5)'; g.shadowBlur = 8; g.fillText(CFG.pseudo || '', W - 40, H - 60); g.restore();
}

await document.fonts.load('900 80px Montserrat');
await document.fonts.load('400 80px "Noto Color Emoji"').catch(() => {});
window.renderAt = (T) => draw(T);
document.body.classList.add('ready');
if (!Q.has('manual')) {
  const au = new Audio(BASE + CFG.voice);
  const t0 = performance.now();
  document.addEventListener('click', () => { au.currentTime = 0; au.play(); });
  const loop = () => { draw(((performance.now() - t0) / 1000) % DUR); requestAnimationFrame(loop); };
  loop();
}
