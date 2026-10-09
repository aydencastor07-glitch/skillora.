// Vidéo « quiz de couple » au format TikTok (1080×1920), dessinée image par image.
// Les textes et le rythme viennent de SCRIPT ; window.EVENTS sert à poser les sons.
// ?manual : rendu piloté (window.renderAt(T))
const Q = new URLSearchParams(location.search);
const PSEUDO = Q.get('pseudo') || '@tonpseudo';

const SCRIPT = {
  hook: 'Réponds honnêtement… 😏',
  title: ['Ta copine', 'a le droit de… ?'],
  tag: 'HARDCORE EDITION 🔥',
  questions: [
    { e: '🌙', q: 'Sortir tard *le soir* ?', c: ['#1d2b64', '#4b2c83'] },
    { e: '🍷', q: 'Dîner seule *avec un ami* ?', c: ['#5b1a3a', '#a83256'] },
    { e: '💔', q: 'Garder contact *avec son ex* ?', c: ['#3a0d0d', '#9b1c1c'] },
    { e: '📱', q: 'Liker les photos *d\'autres mecs* ?', c: ['#0f3443', '#34a0a4'] },
    { e: '✈️', q: 'Partir en vacances *sans toi* ?', c: ['#0b486b', '#3b8d99'] },
    { e: '🎉', q: 'Aller en soirée *chez un gars* ?', c: ['#41295a', '#e0457b'] },
    { e: '⏳', q: 'Ne pas te répondre *pendant 24h* ?', c: ['#232526', '#6b5b95'] },
    { e: '🔍', q: 'Fouiller *dans ton téléphone* ?', c: ['#1e130c', '#9a8478'] },
  ],
  mid: ['Enregistre la vidéo', 'et fais le test', 'avec ton/ta partenaire 💞'],
  end: ['Combien de OUI ? 🤔', 'Dis-le en commentaire 👇', 'Partie 2 → abonne-toi'],
};

// ---------- Chronologie ----------
const INTRO = 3.2, QD = 5.4, MID = 3.4, END = 4.6, MID_AFTER = 4;
const blocks = [];
let t = 0;
blocks.push({ k: 'intro', t0: t, d: INTRO }); t += INTRO;
SCRIPT.questions.forEach((q, i) => {
  blocks.push({ k: 'q', i, t0: t, d: QD }); t += QD;
  if (i + 1 === MID_AFTER) { blocks.push({ k: 'mid', t0: t, d: MID }); t += MID; }
});
blocks.push({ k: 'end', t0: t, d: END }); t += END;
const DUR = t;
const EVENTS = [];
for (const b of blocks) {
  EVENTS.push({ t: b.t0, type: 'whoosh' });
  if (b.k === 'q') { EVENTS.push({ t: b.t0 + 0.08, type: 'pop' }); for (let s = 0; s < 3; s++) EVENTS.push({ t: b.t0 + 1.2 + s, type: 'tick' }); EVENTS.push({ t: b.t0 + 4.2, type: 'ding' }); }
  if (b.k === 'mid' || b.k === 'end') b.k === 'mid' ? SCRIPT.mid.forEach((_, j) => EVENTS.push({ t: b.t0 + 0.2 + j * 0.7, type: 'pop' })) : SCRIPT.end.forEach((_, j) => EVENTS.push({ t: b.t0 + 0.2 + j * 0.9, type: 'pop' }));
  if (b.k === 'intro') EVENTS.push({ t: 0.9, type: 'pop' }, { t: 1.6, type: 'pop' });
}
Object.assign(window, { DUR, EVENTS, SCRIPT });

// ---------- Outils ----------
const cv = document.getElementById('c'), g = cv.getContext('2d');
const W = 1080, H = 1920;
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const ss = (a, b, x) => { const u = clamp((x - a) / (b - a)); return u * u * (3 - 2 * u); };
const back = (u) => { u = clamp(u); const c = 1.9; return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2; };
const FONT = (w, s) => `${w} ${s}px Montserrat, "Noto Color Emoji", sans-serif`;
let seed = 7;
const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
const HEARTS = Array.from({ length: 26 }, () => ({ x: rnd() * W, s: 18 + rnd() * 40, v: 40 + rnd() * 70, p: rnd() * 10, a: 0.05 + rnd() * 0.12 }));

function rr(x, y, w, h, r) { g.beginPath(); g.roundRect(x, y, w, h, r); }
function heart(x, y, s) {
  g.beginPath(); g.moveTo(x, y + s * 0.3);
  g.bezierCurveTo(x, y, x - s * 0.5, y, x - s * 0.5, y + s * 0.3);
  g.bezierCurveTo(x - s * 0.5, y + s * 0.6, x, y + s * 0.8, x, y + s);
  g.bezierCurveTo(x, y + s * 0.8, x + s * 0.5, y + s * 0.6, x + s * 0.5, y + s * 0.3);
  g.bezierCurveTo(x + s * 0.5, y, x, y, x, y + s * 0.3); g.fill();
}
// texte avec contour + ombre ; *mot* = mot clé surligné
function richText(str, cx, cy, size, maxW, alpha = 1, hl = 1) {
  g.font = FONT(900, size);
  const words = str.split(' ');
  const lines = []; let cur = [];
  for (const w of words) { const test = [...cur, w].join(' ').replace(/\*/g, ''); if (g.measureText(test).width > maxW && cur.length) { lines.push(cur); cur = [w]; } else cur.push(w); }
  if (cur.length) lines.push(cur);
  const lh = size * 1.18;
  let inKey = false;
  lines.forEach((ln, li) => {
    const segs = ln.map((w) => { const s0 = w.startsWith('*'), s1 = w.endsWith('*'); const key = inKey || s0; if (s0) inKey = true; if (s1) inKey = false; return { w: w.replace(/\*/g, ''), key }; });
    const full = segs.map((s) => s.w).join(' ');
    let x = cx - g.measureText(full).width / 2;
    const y = cy + (li - (lines.length - 1) / 2) * lh;
    segs.forEach((s, si) => {
      const txt = s.w + (si < segs.length - 1 ? ' ' : '');
      const ww = g.measureText(s.w).width;
      if (s.key) {
        g.save(); g.globalAlpha = alpha;
        g.fillStyle = '#ff2e63'; rr(x - 10, y - size * 0.62, (ww + 20) * hl, size * 1.18, 16); g.fill();
        g.restore();
      }
      g.save(); g.globalAlpha = alpha; g.textBaseline = 'middle';
      g.lineJoin = 'round'; g.lineWidth = size * 0.16; g.strokeStyle = 'rgba(20,6,30,0.85)';
      if (!s.key) g.strokeText(s.w, x, y);
      g.shadowColor = 'rgba(0,0,0,0.35)'; g.shadowBlur = 12; g.shadowOffsetY = 6;
      g.fillStyle = s.key ? '#fff' : '#fff'; g.fillText(s.w, x, y);
      g.restore();
      x += g.measureText(txt).width;
    });
  });
}
function plain(str, cx, cy, size, color = '#fff', alpha = 1, weight = 900) {
  g.save(); g.globalAlpha = alpha; g.font = FONT(weight, size); g.textAlign = 'center'; g.textBaseline = 'middle';
  g.lineJoin = 'round'; g.lineWidth = size * 0.16; g.strokeStyle = 'rgba(20,6,30,0.85)'; g.strokeText(str, cx, cy);
  g.shadowColor = 'rgba(0,0,0,0.35)'; g.shadowBlur = 12; g.shadowOffsetY = 6; g.fillStyle = color; g.fillText(str, cx, cy);
  g.restore();
}

// ---------- Décor ----------
function background(T) {
  const a = T * 0.15;
  const gr = g.createLinearGradient(W / 2 + Math.cos(a) * 600, 0, W / 2 - Math.cos(a) * 600, H);
  gr.addColorStop(0, '#2b0a4f'); gr.addColorStop(0.55, '#7b1fa2'); gr.addColorStop(1, '#ff4f8b');
  g.fillStyle = gr; g.fillRect(0, 0, W, H);
  // lueur douce
  const rg = g.createRadialGradient(W / 2, H * 0.42, 50, W / 2, H * 0.42, 900);
  rg.addColorStop(0, 'rgba(255,255,255,0.16)'); rg.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = rg; g.fillRect(0, 0, W, H);
  // cœurs qui montent
  for (const h of HEARTS) {
    const y = H + 60 - ((T * h.v + h.p * 300) % (H + 160));
    g.fillStyle = `rgba(255,255,255,${h.a})`;
    heart(h.x + Math.sin(T + h.p) * 30, y, h.s);
  }
}
function progress(T, qi, local) {
  const n = SCRIPT.questions.length, pad = 60, gap = 12, w = (W - pad * 2 - gap * (n - 1)) / n;
  for (let i = 0; i < n; i++) {
    rr(pad + i * (w + gap), 110, w, 14, 7); g.fillStyle = 'rgba(255,255,255,0.25)'; g.fill();
    const f = i < qi ? 1 : i === qi ? clamp(local / QD) : 0;
    if (f > 0) { rr(pad + i * (w + gap), 110, w * f, 14, 7); g.fillStyle = '#ffd23f'; g.fill(); }
  }
  plain(`QUESTION ${qi + 1}/${n}`, W / 2, 185, 44, '#ffd23f', 1, 800);
}
function watermark() {
  g.save(); g.globalAlpha = 0.85; g.font = FONT(800, 40); g.textAlign = 'center'; g.fillStyle = '#fff';
  g.fillText(PSEUDO, W / 2, H - 150); g.restore();
}

// ---------- Scènes ----------
function intro(T) {
  plain(SCRIPT.hook, W / 2, 330, 58, '#ffd23f', ss(0.1, 0.5, T));
  // grand cœur qui bat
  const s = back((T - 0.2) / 0.6) * (1 + 0.06 * Math.sin(T * 9));
  g.save(); g.translate(W / 2, 640); g.scale(s, s);
  g.shadowColor = 'rgba(255,46,99,0.8)'; g.shadowBlur = 60; g.fillStyle = '#ff2e63'; heart(0, -170, 340); g.restore();
  g.save(); g.font = FONT(400, 160); g.textAlign = 'center'; g.textBaseline = 'middle'; g.globalAlpha = ss(0.5, 0.8, T); g.fillText('🤭', W / 2, 640); g.restore();
  const t1 = back((T - 0.9) / 0.5), t2 = back((T - 1.6) / 0.5);
  g.save(); g.translate(W / 2, 1010); g.scale(t1, t1); plain(SCRIPT.title[0], 0, 0, 104); plain(SCRIPT.title[1], 0, 120, 104); g.restore();
  g.save(); g.translate(W / 2, 1260); g.rotate(-0.04); g.scale(t2, t2);
  g.font = FONT(900, 58); const tw = g.measureText(SCRIPT.tag).width + 70;
  rr(-tw / 2, -50, tw, 100, 50); g.fillStyle = '#ffd23f'; g.fill();
  g.fillStyle = '#2b0a4f'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(SCRIPT.tag, 0, 4); g.restore();
}
function question(T, i) {
  const q = SCRIPT.questions[i];
  progress(T, i, T);
  // carte qui surgit avec léger balancement 3D
  const pop = back(T / 0.45), sway = Math.sin(T * 1.6) * 0.025;
  const cw = 680, ch = 820, cx = W / 2, cy = 720;
  g.save(); g.translate(cx, cy); g.rotate(sway); g.scale(pop, pop);
  g.shadowColor = 'rgba(0,0,0,0.45)'; g.shadowBlur = 60; g.shadowOffsetY = 30;
  const gr = g.createLinearGradient(-cw / 2, -ch / 2, cw / 2, ch / 2); gr.addColorStop(0, q.c[0]); gr.addColorStop(1, q.c[1]);
  rr(-cw / 2, -ch / 2, cw, ch, 60); g.fillStyle = gr; g.fill();
  g.shadowColor = 'transparent'; g.lineWidth = 10; g.strokeStyle = 'rgba(255,255,255,0.9)'; g.stroke();
  // reflet
  const sh = g.createLinearGradient(-cw / 2, -ch / 2, cw / 2, 0); sh.addColorStop(0, 'rgba(255,255,255,0.22)'); sh.addColorStop(0.5, 'rgba(255,255,255,0)');
  rr(-cw / 2, -ch / 2, cw, ch, 60); g.fillStyle = sh; g.fill();
  g.font = FONT(400, 330); g.textAlign = 'center'; g.textBaseline = 'middle';
  const bob = Math.sin(T * 3) * 14;
  g.fillText(q.e, 0, bob + 10);
  g.restore();
  // question (le mot clé se surligne)
  const ta = ss(0.25, 0.55, T);
  g.save(); g.translate(0, (1 - ta) * 40);
  richText(q.q, W / 2, 1280, 78, 940, ta, ss(0.5, 0.9, T)); g.restore();
  // compte à rebours 3-2-1
  const cd = T - 1.2;
  if (cd > -0.2 && cd < 3.3) {
    const n = Math.max(1, 3 - Math.floor(clamp(cd, 0, 2.999))), f = clamp(cd - Math.floor(clamp(cd, 0, 2.999)));
    const a = ss(-0.2, 0.1, cd) * (1 - ss(3.0, 3.3, cd)), r = 82, y = 1530, pul = 1 + 0.12 * Math.max(0, 1 - f * 4);
    g.save(); g.globalAlpha = a; g.translate(W / 2, y); g.scale(pul, pul);
    g.beginPath(); g.arc(0, 0, r, 0, Math.PI * 2); g.fillStyle = '#14061e'; g.fill();
    g.beginPath(); g.arc(0, 0, r - 12, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * (1 - f)); g.lineWidth = 12; g.lineCap = 'round'; g.strokeStyle = '#ffd23f'; g.stroke();
    g.font = FONT(900, 84); g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillStyle = '#fff'; g.fillText(String(n), 0, 6);
    g.restore();
  }
  // OUI / NON après le compte à rebours
  const yn = back((T - 4.2) / 0.4);
  if (T > 4.2) {
    for (const [k, lab, col] of [[-1, 'OUI ✅', '#22c55e'], [1, 'NON ❌', '#ef4444']]) {
      g.save(); g.translate(W / 2 + k * 230, 1530); const s = yn * (1 + 0.05 * Math.sin(T * 10 + k)); g.scale(s, s);
      rr(-190, -70, 380, 140, 70); g.fillStyle = col; g.shadowColor = 'rgba(0,0,0,0.35)'; g.shadowBlur = 20; g.shadowOffsetY = 10; g.fill();
      g.shadowColor = 'transparent'; g.font = FONT(900, 62); g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillStyle = '#fff'; g.fillText(lab, 0, 4);
      g.restore();
    }
  }
}
function lines(T, arr, step, y0, size, icon) {
  const iu = back((T - 0.05) / 0.5);
  g.save(); g.translate(W / 2, y0 - 330); g.scale(iu * (1 + 0.05 * Math.sin(T * 6)), iu * (1 + 0.05 * Math.sin(T * 6)));
  g.font = FONT(400, 260); g.textAlign = 'center'; g.textBaseline = 'middle'; g.shadowColor = 'rgba(0,0,0,0.35)'; g.shadowBlur = 30; g.fillText(icon, 0, 0); g.restore();
  arr.forEach((s, j) => {
    const u = back((T - 0.2 - j * step) / 0.45);
    if (u <= 0.001) return;
    g.font = FONT(900, size); const fit = Math.min(1, 920 / g.measureText(s).width);
    g.save(); g.translate(W / 2, y0 + j * size * 1.6); g.scale(u * fit, u * fit); plain(s, 0, 0, size, j === 0 ? '#ffd23f' : '#fff'); g.restore();
  });
}

// ---------- Rendu ----------
function draw(T) {
  T = clamp(T, 0, DUR - 1e-4);
  background(T);
  const b = blocks.find((x) => T >= x.t0 && T < x.t0 + x.d) || blocks[blocks.length - 1];
  const L = T - b.t0;
  // transition : glissement + fondu
  const tin = ss(0, 0.25, L), tout = ss(b.d - 0.2, b.d, L);
  g.save(); g.globalAlpha = tin * (1 - tout); g.translate((1 - tin) * 120 - tout * 120, 0);
  if (b.k === 'intro') intro(L);
  else if (b.k === 'q') question(L, b.i);
  else if (b.k === 'mid') lines(L, SCRIPT.mid, 0.7, 980, 68, '📌');
  else lines(L, SCRIPT.end, 0.9, 980, 66, '💬');
  g.restore();
  watermark();
  // grain léger
  g.save(); g.globalAlpha = 0.04; g.fillStyle = '#000'; for (let k = 0; k < 300; k++) g.fillRect(rnd() * W, rnd() * H, 2, 2); g.restore();
}

await document.fonts.load('900 80px Montserrat');
await document.fonts.load('400 80px "Noto Color Emoji"').catch(() => {});
const MANUAL = Q.has('manual');
if (MANUAL) document.body.classList.add('render');
window.renderAt = (T) => draw(T);
document.body.classList.add('ready');
if (!MANUAL) { const t0 = performance.now(); const loop = () => { draw(((performance.now() - t0) / 1000) % DUR); requestAnimationFrame(loop); }; loop(); }
