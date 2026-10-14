// Vidéo YouTube format long (1920×1080), style « croquis manga sur fond noir ».
// Personnages détourés (PNG transparents) : entrées animées, caméra qui se déplace
// et zoome sur les muscles, répétitions en boucle (2 poses), muscle qui s'allume
// (fondu vers la version coloriée), étiquettes d'exercice, peu de texte (moments forts).
const Q = new URLSearchParams(location.search);
const BASE = './youtube/';
const CFG = await (await fetch(`${BASE}${Q.get('v') || 'v1/long'}.json`)).json();
const cv = document.getElementById('c'), g = cv.getContext('2d');
const V = !!CFG.vertical; // Short 9:16 : personnage centré, textes en haut, rien sur les côtés
const W = V ? 1080 : 1920, H = V ? 1920 : 1080, DUR = CFG.dur, SC = CFG.scenes;
const TW = W - 160; // largeur max d'une ligne de texte
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
  for (const k of ['img', 'alt', 'hl', 'medal']) if (s[k]) names.add(s[k]);
  if (s.next) names.add(s.next.img);
  (s.seq || []).forEach((q) => { names.add(q.img); if (q.hl) names.add(q.hl); });
}
await Promise.all([...names].map((n) => new Promise((res) => { const im = new Image(); im.onload = () => { IMG[n] = im; res(); }; im.onerror = res; im.src = `${BASE}${CFG.png || 'png'}/${n}.png`; })));

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
  if (full > TW) { BIG = Math.max(V ? 96 : 110, Math.floor(BIG * TW / full)); g.font = FONT(800, BIG, 'italic'); }
  const sp = g.measureText(' ').width;
  const words = txt.split(/\s+/).map((w) => ({ hot: /^\*.*\*[.,!?]*$/.test(w), w: w.replace(/\*/g, '').toUpperCase() }));
  const lines = [[]]; let lw = 0;
  for (const w of words) { w.wd = g.measureText(w.w).width; if (lw && lw + sp + w.wd > TW) { lines.push([]); lw = 0; } lines.at(-1).push(w); lw += (lw ? sp : 0) + w.wd; }
  lines.forEach((l, i) => { const tw = l.reduce((a, w) => a + w.wd, 0) + sp * (l.length - 1); let x = (s.sayX ?? 0.5) * W - tw / 2;
    for (const w of l) { w.x = x + w.wd / 2; w.line = i; x += w.wd + sp; } });
  g.restore(); return (s[key] = { words, n: lines.length, BIG });
}
function bigText(s, T) {
  const txt = s.say || s.big; if (!txt) return;
  const L = layout(s, txt), BIG = L.BIG, ts = s.say ? wordTimes(s) : null, y0 = (V ? 0.1 : (s.sayY ?? 0.24)) * H - (L.n - 1) * BIG * 0.55;
  g.save(); g.font = FONT(800, BIG, 'italic'); g.textAlign = 'center'; g.textBaseline = 'middle';
  L.words.forEach((w, i) => {
    const t = ts ? ts[i] : at(s, s.bigAt ?? 0.15), k = (T - t) / 0.18; if (k <= 0) return;
    g.save(); g.translate(w.x, y0 + w.line * BIG * 1.1); const sc = 0.6 + 0.4 * back(k); g.scale(sc, sc); g.globalAlpha = clamp(k * 1.5);
    g.fillStyle = w.hot ? COL.yellow : '#fff'; g.fillText(w.w, 0, 0); g.restore();
  });
  g.restore();
}

// ---------- texte qui s'écrit pendant que la voix parle ----------
const NUM = { 1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five', 30: 'thirty', 45: 'forty-five' };
const norm = (w) => { w = w.toLowerCase().replace(/[^a-z0-9'-]/g, ''); return NUM[w] || w; };
function voiceWords(s) { // mots prononcés dans la scène, avec leur instant (∝ lettres, sur les morceaux de voix)
  const words = (s.voice || s.spoken || '').split(/\s+/).filter(Boolean), parts = s.parts || [[s.t0, s.t1]];
  const tot = parts.reduce((a, p) => a + p[1] - p[0], 0), chars = words.reduce((a, w) => a + w.length + 1, 0) || 1;
  let c = 0; return words.map((w) => { const f = c / chars; c += w.length + 1; let x = f * tot;
    for (const p of parts) { if (x <= p[1] - p[0]) return { w: norm(w), t: p[0] + x }; x -= p[1] - p[0]; } return { w: norm(w), t: parts.at(-1)[1] }; });
}
function typeTimes(s, txt) { // chaque mot du texte → instant où la voix le dit (sinon interpolé)
  const key = '_tt' + txt; if (s[key]) return s[key];
  if (s.slide && txt === s.text) { // glissement : le texte s'écrit pendant que le personnage se déplace (un seul mot : d'un coup)
    const t0 = at(s, s.slide.at ?? 0.1) + 0.18, n = txt.split(/\s+/).filter(Boolean).length;
    return (s[key] = Array.from({ length: n }, (_, k) => n === 1 ? t0 : t0 + k * Math.min(0.75, 0.16 * n) / (n - 1)));
  }
  const vw = voiceWords(s), tw = txt.split(/\s+/).filter(Boolean); let j = 0;
  const ts = tw.map((w) => { const n = norm(w); for (let k = j; k < vw.length; k++) if (vw[k].w === n || (n.length > 3 && vw[k].w.startsWith(n.slice(0, 4)))) { j = k + 1; return vw[k].t; } return null; });
  const t0 = s.t0 + 0.05, t1 = Math.max(t0 + 0.3, (s.parts ? s.parts.at(-1)[1] : s.t1) - 0.2);
  for (let i = 0; i < ts.length; i++) if (ts[i] === null) { // pas trouvé : entre ses voisins
    let a = i - 1; while (a >= 0 && ts[a] === null) a--; let b = i + 1; while (b < ts.length && ts[b] === null) b++;
    const ta = a >= 0 ? ts[a] : t0, tb = b < ts.length ? ts[b] : t1; ts[i] = ta + (tb - ta) * (i - a) / (b - a); }
  for (let i = 1; i < ts.length; i++) ts[i] = Math.max(ts[i], ts[i - 1] + 0.06);
  return (s[key] = ts);
}
function typed(s, txt, x, y, size, T, fade = 1) { // texte italique qui s'écrit mot à mot (aligné à gauche, ne bouge pas)
  const ts = typeTimes(s, txt), words = txt.split(/\s+/).filter(Boolean);
  g.save(); g.font = FONT(500, size, 'italic'); g.textBaseline = 'middle'; g.textAlign = 'left';
  const sp = g.measureText(' ').width, ws = words.map((w) => g.measureText(w).width);
  const lines = [[]]; let lw = 0; // coupe en plusieurs lignes si ça dépasse
  ws.forEach((wd, i) => { if (lw && lw + sp + wd > TW) { lines.push([]); lw = 0; } lines.at(-1).push(i); lw += (lw ? sp : 0) + wd; });
  g.lineWidth = 10; g.lineJoin = 'round'; g.strokeStyle = '#000'; g.fillStyle = '#fff';
  lines.forEach((l, li) => { const fw = l.reduce((a, i) => a + ws[i], 0) + sp * (l.length - 1), ly = y + (li - (lines.length - 1) / 2) * size * 1.25;
    let cx = clamp(x - fw / 2, 60, W - 60 - fw);
    l.forEach((i) => { const a = clamp((T - ts[i]) / 0.12) * fade; if (a > 0) { g.globalAlpha = a; g.strokeText(words[i], cx, ly); g.fillText(words[i], cx, ly); } cx += ws[i] + sp; }); });
  g.restore();
}

// règle : phrase longue (≥ 4 mots) → s'écrit ; phrase courte → déjà écrite une fois sur deux
{ let short = 0; for (const s of SC) { const t = s.card || s.text; if (!t || s.instant !== undefined) continue;
  if (s.slide && !s.card) { s.instant = false; continue; }
  const n = t.split(/\s+/).filter(Boolean).length; s.instant = n <= 3 ? (short++ % 2 === 0) : false; } }

const EVENTS = [];
const ev = (t, type) => EVENTS.push({ t, type });
SC.forEach((s, i) => {
  if (i && !(s.enter && s.enter !== 'fade') && !s.card && !s.medal) ev(s.t0 - 0.12, 'cut');      // changement de plan : petit clic
  if (s.cam && s.cam[3] / s.cam[0] >= 1.25) ev(s.t0 + 0.05, 'zoom');      // la caméra zoome sur le personnage
  if (s.enter && s.enter !== 'fade') ev(s.t0 - 0.05, 'swish');           // le personnage entre
  if (s.card) ev(s.t0 + 0.02, 'glitch');                                  // écran noir + phrase
  if (s.medal) ev(s.t0 + 0.05, 'hit');
  if (s.next) { ev(s.t0 + 0.05, 'swish'); typeTimes(s, s.next.title).forEach((t) => ev(t, 'tap')); }
  if (s.subscribe) { ev(at(s, s.clickAt ?? 0.35), 'click'); ev(at(s, s.clickAt ?? 0.35) + 0.12, 'ding'); }                                    // médaillon d'exercice
  if (s.label || s.reps) ev(s.t0 + 0.05, 'pop');
  if (s.text) (s.instant ? [at(s, s.textAt ?? 0.2)] : typeTimes(s, s.text)).forEach((t, k) => ev(t, k ? 'tap' : 'click')); // texte qui s'écrit
  if (s.card && !s.instant) typeTimes(s, s.card).slice(1).forEach((t) => ev(t, 'tap'));
  if (s.slide) ev(at(s, s.slide.at ?? 0.1), 'swish');
  (s.icons || []).forEach((ic) => ev(at(s, ic.at), ic.kind === 'x' ? 'tick' : 'ding'));
  if (s.hl) ev(at(s, s.hlAt ?? 0.15), 'shine');
  (s.seq || []).forEach((q) => { ev(at(s, q.at) - 0.05, 'cut'); if (q.hl) ev(at(s, q.at) + 0.1, 'shine'); });
  if (s.alt) { // répétitions : souffle à chaque mouvement, haltère qui « claque » en bas
    const per = s.period || 0.8;
    for (let t = s.t0; t < s.t1 - 0.2; t += 2 * per) {
      const f = Math.min(0.35, 0.12 / per);
      if (t + per * (1 - f) < s.t1) ev(t + per * (1 - f), 'swish');
      if (t + per * (2 - f) < s.t1) ev(t + per * (2 - f), 'swish');
      if (/bench|incl|lat|ohp|rdf/.test(s.img) && t + per * 2 < s.t1 + 0.1) ev(t + per * 2, 'clank'); // haltères seulement
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
  const size = 1000 * z * (s.scale || 1) * (V ? (String(s.img).startsWith('arm') ? 1.05 : 1.55) : 1);
  let sx = V ? 0.5 : s.x ?? 0.5; if (s.slide && !V) sx = lerp(sx, s.slide.to, eio((T - at(s, s.slide.at ?? 0.1)) / 0.7)); // glisse sur le côté
  const px = sx * W, py = V ? H * 0.53 : 540;
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
function drawChar(im, r, a = 1, rim = true) { // rim : léger halo blanc (cheveux noirs visibles sur fond noir)
  if (!im) return; g.save(); g.globalAlpha = a * r.a;
  if (rim) { g.shadowColor = '#fff'; g.shadowBlur = 7; g.drawImage(im, r.x, r.y, r.w, r.h); }
  g.drawImage(im, r.x, r.y, r.w, r.h); g.restore();
}

function dashTag(r, t, T, t0) { // « Upper - - - - - • » (texte à gauche, pointillés jusqu'au muscle)
  const k = T - t0; if (k < 0) return;
  const a = clamp(k / 0.3), cx = r.x + t.x * r.w, cy = r.y + t.y * r.h, lx = cx - (t.len ?? 360) * clamp(k / 0.45);
  g.save(); g.globalAlpha = a; g.strokeStyle = '#fff'; g.lineWidth = 3; g.setLineDash([14, 10]);
  g.beginPath(); g.moveTo(lx, cy); g.lineTo(cx - 14, cy); g.stroke(); g.setLineDash([]);
  g.beginPath(); g.arc(cx, cy, 9, 0, Math.PI * 2); g.fillStyle = COL[t.color] || '#fff'; g.fill(); g.lineWidth = 2; g.stroke();
  g.font = FONT(600, 38, 'italic'); g.textAlign = 'right'; g.textBaseline = 'middle'; g.fillStyle = '#fff'; g.fillText(t.name, lx - 16, cy + 2); g.restore();
}
function tag(r, t, T, t0) {
  if (t.style === 'dash') return dashTag(r, t, T, t0); // étiquette muscle : point coloré + trait + nom (comme la référence)
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
  g.save(); g.globalAlpha = clamp(u * 2); g.translate(W / 2, V ? 300 : 90); const s = 0.9 + 0.1 * back(u); g.scale(s, s);
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

function medal(s, T) { // médaillon rond « gravé » avec l'objet + nom de l'exercice au-dessus
  const u = (T - s.t0 + 0.1) / 0.45; if (u <= 0) return;
  const im = IMG[s.medal], R = 230, cx = W / 2, cy = H / 2 + 40, sc = 0.5 + 0.5 * back(u);
  g.save(); g.translate(cx, cy + Math.sin(T * 1.6) * 6); g.scale(sc, sc); g.globalAlpha = clamp(u * 2);
  const gr = g.createRadialGradient(-50, -60, 20, 0, 0, R); gr.addColorStop(0, '#f4f4f4'); gr.addColorStop(0.7, '#bdbdbd'); gr.addColorStop(1, '#7a7a7a');
  g.beginPath(); for (let i = 0; i <= 48; i++) { const t = i / 48 * Math.PI * 2, rr = R + (i % 2 ? 0 : 7); g.lineTo(Math.cos(t) * rr, Math.sin(t) * rr); }
  g.fillStyle = gr; g.fill(); g.lineWidth = 4; g.strokeStyle = '#555'; g.stroke();
  g.beginPath(); g.arc(0, 0, R - 26, 0, Math.PI * 2); g.lineWidth = 3; g.strokeStyle = 'rgba(0,0,0,0.35)'; g.stroke();
  if (im) { g.save(); g.beginPath(); g.arc(0, 0, R - 30, 0, Math.PI * 2); g.clip(); g.globalCompositeOperation = 'multiply';
    const z = (s.medalZoom || 1.25) * 2 * (R - 30); g.drawImage(im, -z / 2, -z / 2 + (s.medalDy || 0), z, z); g.restore(); }
  g.restore();
  if (s.name) { g.save(); g.globalAlpha = clamp((T - s.t0 - 0.15) / 0.35); g.font = FONT(700, 58, 'italic'); g.textAlign = 'center'; g.textBaseline = 'middle';
    const nw = g.measureText(s.name).width; if (nw > TW) g.font = FONT(700, Math.floor(58 * TW / nw), 'italic');
    g.fillStyle = '#fff'; g.fillText(s.name, W / 2, cy - R - 90); g.restore(); }
}
function repsCard(s, T) { // « (3) 8-12 reps » avec flèche circulaire derrière
  const u = clamp((T - s.t0 + 0.1) / 0.4); if (u <= 0) return;
  g.save(); g.translate(W / 2, H / 2); g.globalAlpha = u * 0.35; g.rotate(T * 1.2); g.strokeStyle = '#fff'; g.lineWidth = 16; g.lineCap = 'round';
  for (const a0 of [0, Math.PI]) { g.beginPath(); g.arc(0, 0, 120, a0 + 0.25, a0 + Math.PI - 0.35); g.stroke();
    const ex = Math.cos(a0 + Math.PI - 0.35) * 120, ey = Math.sin(a0 + Math.PI - 0.35) * 120, d = a0 + Math.PI - 0.35 + Math.PI / 2;
    g.beginPath(); g.moveTo(ex + Math.cos(d - 2.4) * 34, ey + Math.sin(d - 2.4) * 34); g.lineTo(ex, ey); g.lineTo(ex + Math.cos(d + 2.4) * 34, ey + Math.sin(d + 2.4) * 34); g.stroke(); }
  g.restore();
  g.save(); g.globalAlpha = u; g.font = FONT(700, 74, 'italic'); g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillStyle = '#fff';
  const sc = 0.85 + 0.15 * back(u); g.translate(W / 2, H / 2); g.scale(sc, sc); g.fillText(s.sets === 0 ? s.reps : `(${s.sets ?? 3})  ${s.reps}`, 0, 0); g.restore();
}
function dashLine(r, l, T, t0) { // ligne pointillée verte (corps bien droit), coordonnées image
  const k = clamp((T - t0) / 0.6); if (k <= 0) return;
  const x0 = r.x + l[0] * r.w, y0 = r.y + l[1] * r.h, x1 = r.x + l[2] * r.w, y1 = r.y + l[3] * r.h;
  g.save(); g.setLineDash([20, 14]); g.strokeStyle = '#36d27a'; g.lineWidth = 6; g.lineCap = 'round';
  g.beginPath(); g.moveTo(x0, y0); g.lineTo(x0 + (x1 - x0) * k, y0 + (y1 - y0) * k); g.stroke(); g.restore();
}

function rrect(x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
function nextVideo(s, T) { // fin de vidéo : « à regarder ensuite » = miniature + titre d'une autre vidéo de la chaîne
  const u = eio((T - s.t0 + 0.1) / 0.7), im = IMG[s.next.img]; if (u <= 0) return;
  const w = 880, h = 495, x = lerp(W + 40, W * 0.62 - w / 2, u), y = H * 0.44 - h / 2 + Math.sin(T * 1.4) * 5;
  g.save(); g.shadowColor = 'rgba(255,255,255,0.25)'; g.shadowBlur = 40; rrect(x, y, w, h, 22); g.fillStyle = '#111'; g.fill(); g.restore();
  if (im) { g.save(); rrect(x, y, w, h, 22); g.clip(); g.drawImage(im, x, y, w, h); g.restore(); }
  g.save(); rrect(x, y, w, h, 22); g.lineWidth = 5; g.strokeStyle = '#fff'; g.stroke(); g.restore();
  // bouton lecture
  g.save(); g.globalAlpha = 0.85 * u; g.translate(x + w - 70, y + h - 62); g.scale(0.7, 0.7); g.beginPath(); g.arc(0, 0, 52, 0, Math.PI * 2); g.fillStyle = 'rgba(220,30,40,0.92)'; g.fill();
  g.beginPath(); g.moveTo(-16, -24); g.lineTo(28, 0); g.lineTo(-16, 24); g.closePath(); g.fillStyle = '#fff'; g.fill(); g.restore();
  // étiquette « WATCH NEXT » + titre qui s'écrit
  const a = clamp((T - s.t0 - 0.4) / 0.3);
  g.save(); g.globalAlpha = a; g.font = FONT(800, 40, 'italic'); g.textAlign = 'left'; g.textBaseline = 'middle'; g.fillStyle = '#e8283a'; g.fillText('WATCH NEXT ▶', x, y - 46); g.restore();
  typed(s, s.next.title, x + w / 2, y + h + 58, 40, T);
}
function subscribe(s, T) { // bouton « S'abonner » : apparaît, le curseur clique, il devient « Subscribed » + cloche
  const u = (T - s.t0 + 0.1) / 0.4; if (u <= 0) return;
  const click = at(s, s.clickAt ?? 0.35), done = T >= click, k = clamp((T - click) / 0.25);
  const cx = W / 2, cy = H * 0.42, sc = (0.6 + 0.4 * back(clamp(u))) * (1 - 0.08 * Math.sin(Math.PI * k));
  g.save(); g.translate(cx, cy); g.scale(sc, sc);
  rrect(-260, -62, 520, 124, 62); g.fillStyle = done ? '#2b2b2b' : '#e8283a'; g.fill();
  g.font = FONT(800, 54); g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillStyle = '#fff'; g.fillText(done ? 'SUBSCRIBED' : 'SUBSCRIBE', done ? -20 : 0, 3);
  if (done) { g.save(); g.translate(205, 0); g.rotate(Math.sin((T - click) * 18) * 0.35 * Math.exp(-(T - click) * 2.5)); // cloche qui sonne
    g.beginPath(); g.moveTo(-20, 16); g.quadraticCurveTo(-20, -26, 0, -26); g.quadraticCurveTo(20, -26, 20, 16); g.closePath(); g.fillStyle = '#fff'; g.fill();
    g.fillRect(-26, 14, 52, 7); g.beginPath(); g.arc(0, 26, 7, 0, Math.PI * 2); g.fill(); g.restore(); }
  g.restore();
  // curseur qui vient cliquer
  const m = eio((T - at(s, 0.12)) / Math.max(0.3, click - at(s, 0.12))), px = lerp(W * 0.8, cx + 40, m), py = lerp(H * 0.85, cy + 20, m);
  if (T > at(s, 0.1) && T < click + 0.8) { g.save(); g.globalAlpha = clamp(1 - (T - click - 0.4) / 0.4); g.translate(px, py); const cs = done && T < click + 0.15 ? 0.85 : 1; g.scale(cs, cs);
    g.beginPath(); g.moveTo(0, 0); g.lineTo(0, 46); g.lineTo(12, 35); g.lineTo(21, 54); g.lineTo(29, 50); g.lineTo(20, 32); g.lineTo(36, 32); g.closePath();
    g.fillStyle = '#fff'; g.fill(); g.lineWidth = 3; g.strokeStyle = '#000'; g.stroke(); g.restore(); }
  if (s.text) typed(s, s.text, W / 2, H * 0.68, 46, T);
}

function draw(T) {
  T = clamp(T, 0, DUR - 1e-4);
  g.fillStyle = '#000'; g.fillRect(0, 0, W, H);
  let i = SC.length - 1; for (let k = 0; k < SC.length; k++) if (T < (SC[k + 1] ? SC[k + 1].t0 - 0.15 : 1e9)) { i = k; break; }
  const s = SC[i];
  const out = SC[i + 1] ? ss(SC[i + 1].t0 - 0.35, SC[i + 1].t0 - 0.15, T) : ss(DUR - 0.8, DUR, T);
  g.save(); g.globalAlpha = 1 - out;
  if (s.card) { // écran noir avec juste une phrase en italique
    const cs = V ? 72 : 54; if (s.instant) italic(s.card, W / 2, H / 2, cs, clamp((T - s.t0 + 0.1) / 0.4)); else typed(s, s.card, W / 2, H / 2, cs, T);
  } else if (s.next) { nextVideo(s, T); if (s.img) { const r = charRect(s, T, IMG[s.img]); drawChar(IMG[s.img], r); }
  } else if (s.subscribe) { subscribe(s, T);
  } else if (s.medal) { medal(s, T);
  } else if (s.reps) { repsCard(s, T);
  } else {
    // image courante (séquence éventuelle), répétitions en boucle, version coloriée
    let cur = { img: s.img, hl: s.hl, hlAt: s.hlAt ?? 0.15 };
    for (const q of s.seq || []) if (T >= at(s, q.at)) cur = { ...q, hlAt: q.at };
    bigText(s, T); // derrière le personnage
    const im = IMG[cur.img];
    const r = charRect(s, T, im);
    if (s.alt) {
      // passage rapide d'une pose à l'autre (≈0,12 s) : pas d'« ombre » visible
      const per = s.period || 0.8, f = Math.min(0.35, 0.12 / per), ph = ((T - s.t0) / per) % 2, mix = ph < 1 ? ss(1 - f, 1, ph) : 1 - ss(2 - f, 2, ph);
      drawChar(im, r, 1 - mix); drawChar(IMG[s.alt], r, mix);
    } else drawChar(im, r);
    if (cur.hl) { // le muscle s'allume puis pulse doucement
      const k = T - at(s, cur.hlAt); const a = clamp(k / 0.5) * (0.82 + 0.18 * Math.sin(T * 4));
      if (k > 0) drawChar(IMG[cur.hl], r, a, false);
    }
    for (const t of s.tags || []) if (t.until === undefined || T < at(s, t.until)) tag(r, t, T, at(s, t.at ?? 0.2));
    if (s.guide !== undefined && T > at(s, 0.15)) { // ligne pointillée « hauteur des épaules »
      g.save(); g.globalAlpha = clamp((T - at(s, 0.15)) / 0.4) * 0.9; g.setLineDash([18, 14]); g.strokeStyle = '#36d27a'; g.lineWidth = 4;
      const y = r.y + s.guide * r.h; g.beginPath(); g.moveTo(r.x + r.w * 0.05, y); g.lineTo(r.x + r.w * 0.95, y); g.stroke(); g.restore();
    }
    if (s.line) dashLine(r, s.line, T, at(s, s.lineAt ?? 0.2));
    if (s.text && V) { const y = 0.095; if (s.instant) italic(s.text, W / 2, y * H, 74, clamp((T - at(s, s.textAt ?? 0.2)) / 0.4)); else typed(s, s.text, W / 2, y * H, 74, T); }
    else if (s.text) { const tx = s.slide ? (s.slide.textX ?? (s.slide.to < 0.5 ? 0.7 : 0.3)) : (s.textX ?? 0.79), sz = s.slide ? 64 : 46;
      const txx = s.slide ? lerp(lerp(0.5, tx, 0.4), tx, eio((T - at(s, s.slide.at ?? 0.1)) / 0.7)) : tx; // part du centre et file de l'autre côté
      if (s.instant) italic(s.text, txx * W, (s.textY ?? 0.5) * H, sz, clamp((T - at(s, s.textAt ?? 0.2)) / 0.4)); else typed(s, s.text, txx * W, (s.textY ?? 0.5) * H, sz, T); }
  }
  for (const ic of s.icons || []) icon(ic.kind, (V ? 0.8 : ic.x ?? 0.21) * W, (V ? 0.3 : ic.y ?? 0.5) * H, (T - at(s, ic.at)) / 0.3);
  if (s.label) label(s.label, (T - s.t0 + 0.1) / 0.35);
  g.restore();
}

await document.fonts.load('italic 500 40px Montserrat');
await document.fonts.load('700 40px Montserrat');
window.renderAt = (T) => draw(T);
document.body.classList.add('ready');
if (!Q.has('manual')) { const t0 = performance.now(); const loop = () => { draw(((performance.now() - t0) / 1000) % DUR); requestAnimationFrame(loop); }; loop(); }
