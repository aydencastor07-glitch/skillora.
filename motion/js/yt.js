// Short fitness faceless (1080×1920), style « croquis manga sur fond noir ».
// Chaque scène : image (ou boucle de 2 poses = mouvement), muscle qui s'allume,
// étiquette d'exercice, mot clé en italique, icônes ✗ / ✓, sous-titres mot à mot.
const Q = new URLSearchParams(location.search);
const BASE = './youtube/';
const CFG = await (await fetch(`${BASE}${Q.get('v') || 'v1/video'}.json`)).json();
const cv = document.getElementById('c'), g = cv.getContext('2d');
const W = 1080, H = 1920, DUR = CFG.dur, SC = CFG.scenes;
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const ss = (a, b, x) => { const u = clamp((x - a) / (b - a)); return u * u * (3 - 2 * u); };
const back = (u) => { u = clamp(u); const c = 1.7; return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2; };
const FONT = (w, s) => `${w} ${s}px Montserrat, "Noto Color Emoji", sans-serif`;
const RED = '#ff3b4f', GREEN = '#36d27a', GOLD = '#ffd23f', ORANGE = '#ff9b3d';
const COL = { red: RED, green: GREEN, orange: ORANGE, gold: GOLD };

const IMG = {};
const names = new Set();
for (const s of SC) { if (s.img) names.add(s.img); (s.loop || []).forEach((n) => names.add(n)); }
await Promise.all([...names].map((n) => new Promise((res) => { const im = new Image(); im.onload = () => { IMG[n] = im; res(); }; im.onerror = res; im.src = `${BASE}img/${n}.jpg`; })));

// sons
const EVENTS = [];
SC.forEach((s, i) => {
  if (i) EVENTS.push({ t: s.t0 - 0.12, type: 'whoosh' });
  if (s.label) EVENTS.push({ t: s.t0, type: 'boom' });
  if (s.icon) EVENTS.push({ t: s.t0 + (s.iconAt ?? 0.5) * (s.t1 - s.t0), type: s.icon === 'x' ? 'boom' : 'ding' });
  if (s.key) EVENTS.push({ t: s.t0 + (s.keyAt ?? 0.3) * (s.t1 - s.t0), type: 'pop' });
});
Object.assign(window, { DUR, EVENTS, CFG });

const at = (s, f) => s.t0 + f * (s.t1 - s.t0);
function words(str) { let red = false; return str.split(' ').map((w) => { const s0 = w.startsWith('*'), s1 = w.endsWith('*'); if (s0) red = true; const o = { w: w.replace(/\*/g, ''), red }; if (s1) red = false; return o; }); }
// sous-titres : mot à mot, italique, en bas
function caption(s, T) {
  const ws = words(s.text), nw = ws.length;
  // répartit les mots sur les morceaux de voix au prorata de leur durée
  const total = s.parts.reduce((a, p) => a + p[1] - p[0], 0); let acc = 0, spoken = 0;
  for (const p of s.parts) { if (T >= p[1]) acc += p[1] - p[0]; else if (T > p[0]) acc += T - p[0]; }
  spoken = acc / total;
  const n = T < s.t0 - 0.05 ? 0 : Math.min(nw, Math.floor(spoken * nw) + 1);
  g.font = FONT(800, 66);
  const sp = g.measureText(' ').width, lines = [[]]; let lw = 0;
  for (const w of ws) { const ww = g.measureText(w.w).width; if (lw + ww > 900 && lines[lines.length - 1].length) { lines.push([]); lw = 0; } lines[lines.length - 1].push({ ...w, ww }); lw += ww + sp; }
  let idx = 0;
  lines.forEach((ln, li) => {
    const tw = ln.reduce((a, w) => a + w.ww, 0) + sp * (ln.length - 1); let x = W / 2 - tw / 2;
    const y = 1640 + (li - (lines.length - 1) / 2) * 80;
    for (const w of ln) {
      if (idx < n) {
        g.save(); g.translate(x, y); g.transform(1, 0, -0.18, 1, 0, 0); g.textBaseline = 'middle'; g.lineJoin = 'round';
        g.lineWidth = 12; g.strokeStyle = '#000'; g.strokeText(w.w, 0, 0); g.fillStyle = w.red ? RED : '#fff'; g.fillText(w.w, 0, 0); g.restore();
      }
      x += w.ww + sp; idx++;
    }
  });
}
// image affichée dans une boîte, avec léger zoom ; renvoie la transformation pour placer les effets
function place(img, T, s) {
  const bw = 1040, bh = 1180, cx = W / 2, cy = 920;
  const sc0 = Math.min(bw / img.width, bh / img.height) * (s.zoom || 1);
  const z = sc0 * (1 + 0.06 * ss(s.t0 - 0.2, s.t1 + 0.6, T));
  const w = img.width * z, h = img.height * z, x = cx - w / 2 + (s.dx || 0), y = cy - h / 2 + (s.dy || 0);
  return { x, y, w, h };
}
function drawImg(img, r, a = 1) {
  g.save(); g.globalAlpha = a; g.drawImage(img, r.x, r.y, r.w, r.h);
  // bords fondus vers le noir
  const fade = (x0, y0, x1, y1) => { const gr = g.createLinearGradient(x0, y0, x1, y1); gr.addColorStop(0, 'rgba(0,0,0,1)'); gr.addColorStop(1, 'rgba(0,0,0,0)'); return gr; };
  g.globalAlpha = 1;
  g.fillStyle = fade(r.x, 0, r.x + 60, 0); g.fillRect(r.x, r.y, 60, r.h);
  g.fillStyle = fade(r.x + r.w, 0, r.x + r.w - 60, 0); g.fillRect(r.x + r.w - 60, r.y, 60, r.h);
  g.fillStyle = fade(0, r.y + r.h, 0, r.y + r.h - 90); g.fillRect(r.x, r.y + r.h - 90, r.w, 90);
  g.restore();
}
// muscle qui s'allume (lueur colorée qui pulse, en mode « écran » pour garder les traits)
function glow(r, gl, T, s) {
  const t0 = at(s, gl.at ?? 0), k = T - t0; if (k < 0) return;
  const a = clamp(k / 0.35) * (0.75 + 0.25 * Math.sin(T * 6));
  const cx = r.x + gl.x * r.w, cy = r.y + gl.y * r.h, rx = gl.rx * r.w, ry = gl.ry * r.h;
  g.save(); g.globalCompositeOperation = 'multiply'; g.globalAlpha = a * 0.9;
  g.translate(cx, cy); g.scale(1, ry / rx);
  const gr = g.createRadialGradient(0, 0, 0, 0, 0, rx); const c = COL[gl.color || 'red'];
  gr.addColorStop(0, c); gr.addColorStop(0.65, c); gr.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = gr; g.beginPath(); g.arc(0, 0, rx, 0, Math.PI * 2); g.fill(); g.restore();
  if (gl.name) { // étiquette avec point + trait
    const lx = cx + (gl.side === 'left' ? -1 : 1) * (rx + 120), ly = cy - ry - 30;
    g.save(); g.globalAlpha = clamp(k / 0.3); g.strokeStyle = '#fff'; g.lineWidth = 3; g.beginPath(); g.moveTo(cx, cy); g.lineTo(lx, ly); g.stroke();
    g.beginPath(); g.arc(cx, cy, 9, 0, Math.PI * 2); g.fillStyle = c; g.fill();
    g.font = FONT(700, 40); g.textAlign = gl.side === 'left' ? 'right' : 'left'; g.textBaseline = 'middle';
    g.fillStyle = '#fff'; g.fillText(gl.name, lx + (gl.side === 'left' ? -12 : 12), ly); g.restore();
  }
}
function label(txt, u) { // étiquette « #1. Lateral Raise »
  if (u <= 0) return;
  g.save(); g.translate(W / 2, 200); g.scale(back(u), back(u)); g.font = FONT(800, 54);
  const tw = g.measureText(txt).width + 60; g.fillStyle = '#fff'; g.fillRect(-tw / 2, -46, tw, 92);
  g.strokeStyle = '#000'; g.lineWidth = 4; g.strokeRect(-tw / 2 + 8, -38, tw - 16, 76);
  g.fillStyle = '#000'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(txt, 0, 4); g.restore();
}
function keyword(txt, u, col = '#fff', y = 200) { // mot clé en italique en haut
  if (u <= 0) return;
  g.save(); g.globalAlpha = clamp(u * 3); g.translate(W / 2, y); const s = 0.8 + 0.2 * back(u); g.scale(s, s); g.transform(1, 0, -0.2, 1, 0, 0);
  g.font = FONT(900, 96); g.textAlign = 'center'; g.textBaseline = 'middle'; g.lineJoin = 'round';
  g.lineWidth = 16; g.strokeStyle = '#000'; g.strokeText(txt, 0, 0); g.fillStyle = col; g.fillText(txt, 0, 0); g.restore();
}
function icon(kind, x, y, u) {
  if (u <= 0) return;
  g.save(); g.translate(x, y); g.scale(back(u), back(u));
  g.beginPath(); g.arc(0, 0, 80, 0, Math.PI * 2); g.fillStyle = kind === 'x' ? RED : GREEN; g.fill();
  g.lineWidth = 8; g.strokeStyle = '#fff'; g.stroke(); g.lineWidth = 16; g.lineCap = 'round'; g.beginPath();
  if (kind === 'x') { g.moveTo(-32, -32); g.lineTo(32, 32); g.moveTo(32, -32); g.lineTo(-32, 32); } else { g.moveTo(-36, 0); g.lineTo(-10, 28); g.lineTo(38, -28); }
  g.stroke(); g.restore();
}

function draw(T) {
  T = clamp(T, 0, DUR - 1e-4);
  g.fillStyle = '#000'; g.fillRect(0, 0, W, H);
  let i = SC.length - 1; for (let k = 0; k < SC.length; k++) if (T < (SC[k + 1] ? SC[k + 1].t0 - 0.12 : 1e9)) { i = k; break; }
  const s = SC[i], local = T - (s.t0 - 0.12);
  // image : fixe ou boucle de 2 poses (mouvement de répétition)
  const names = s.loop || [s.img];
  const per = s.period || 0.75;
  let a = 0, b = 0, mix = 0;
  if (names.length > 1) { const ph = (local / per) % 2; a = ph < 1 ? 0 : 1; b = 1 - a; mix = ss(0.75, 1, ph % 1); }
  const im = IMG[names[a]];
  if (im) {
    const r = place(im, T, s), cut = clamp(local / 0.18);
    drawImg(im, r, cut * (1 - mix));
    if (mix > 0 && IMG[names[b]]) drawImg(IMG[names[b]], place(IMG[names[b]], T, s), cut * mix);
    (s.glow || []).forEach((gl) => glow(r, gl, T, s));
    if (s.lineY !== undefined && T > at(s, s.lineAt ?? 0.2)) { // ligne « hauteur des épaules »
      g.save(); g.setLineDash([22, 16]); g.strokeStyle = GREEN; g.lineWidth = 5; const y = r.y + s.lineY * r.h;
      g.beginPath(); g.moveTo(r.x + 40, y); g.lineTo(r.x + r.w - 40, y); g.stroke(); g.restore();
    }
    if (s.arrows) { // flèches « large »
      const u = ss(at(s, 0.3), at(s, 0.5), T), y = r.y + (s.arrowY || 0.3) * r.h, w = 330 + 40 * Math.sin(T * 5);
      g.save(); g.globalAlpha = u; g.strokeStyle = GOLD; g.fillStyle = GOLD; g.lineWidth = 10;
      for (const d of [-1, 1]) { g.beginPath(); g.moveTo(W / 2 + d * 120, y); g.lineTo(W / 2 + d * w, y); g.stroke(); g.beginPath(); g.moveTo(W / 2 + d * (w + 30), y); g.lineTo(W / 2 + d * w, y - 26); g.lineTo(W / 2 + d * w, y + 26); g.fill(); }
      g.restore();
    }
  }
  if (s.label) label(s.label, (T - s.t0) / 0.35);
  if (s.key) keyword(s.key, (T - at(s, s.keyAt ?? 0.3)) / 0.35, s.keyColor ? COL[s.keyColor] : '#fff', s.label ? 360 : 200);
  if (s.icon) icon(s.icon, 880, 1300, (T - at(s, s.iconAt ?? 0.5)) / 0.3);
  caption(s, T);
  if (s.flash && local < 0.25) { g.save(); g.globalAlpha = (1 - local / 0.25) * 0.5; g.fillStyle = COL[s.flash] || '#fff'; g.fillRect(0, 0, W, H); g.restore(); }
  g.save(); g.font = FONT(700, 34); g.textAlign = 'right'; g.fillStyle = 'rgba(255,255,255,0.7)'; g.fillText(CFG.pseudo || '', W - 40, H - 60); g.restore();
}

await document.fonts.load('900 80px Montserrat');
await document.fonts.load('400 80px "Noto Color Emoji"').catch(() => {});
window.renderAt = (T) => draw(T);
document.body.classList.add('ready');
if (!Q.has('manual')) { const t0 = performance.now(); const loop = () => { draw(((performance.now() - t0) / 1000) % DUR); requestAnimationFrame(loop); }; loop(); }
