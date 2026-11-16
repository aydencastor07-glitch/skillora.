// « Die letzte U-Bahn » : histoire d'horreur au « tu », quai de métro la nuit, personnage réaliste
// (Rocketbox + motion capture CMU), rame sans conducteur, silhouette derrière lui.
// Chronologie calée sur la voix off (temps T en secondes). ?manual : rendu image par image (window.renderAt(T)).
import * as THREE from 'three';
import { RealHuman } from './rig.js';

const Q = new URLSearchParams(location.search);
const MANUAL = Q.has('manual');
const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.outputColorSpace = THREE.SRGBColorSpace;

const scene = new THREE.Scene();
scene.background = new THREE.Color('#05070b');
scene.fog = new THREE.Fog('#06080d', 14, 46);
const hemi = new THREE.HemisphereLight('#9fb3cc', '#1a1712', 0.35);
scene.add(hemi);
const camera = new THREE.PerspectiveCamera(42, 9 / 16, 0.03, 120);
const fillL = new THREE.SpotLight('#c9d8f0', 4.5, 7, 0.5, 0.9, 1.6); scene.add(fillL, fillL.target);

// ---------- textures dessinées ----------
function canvasTex(w, h, draw) {
  const c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d'); draw(g, w, h);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; t.userData = { c, g, draw }; return t;
}
const rnd = (s => () => (s = (s * 16807) % 2147483647) / 2147483647)(7);
const tiles = canvasTex(512, 512, (g, w, h) => {
  g.fillStyle = '#8f958f'; g.fillRect(0, 0, w, h);
  for (let y = 0; y < 8; y++) for (let x = 0; x < 4; x++) {
    const v = 168 + rnd() * 22 | 0; g.fillStyle = `rgb(${v - 6},${v},${v - 4})`; g.fillRect(x * 128 + 3, y * 64 + 3, 122, 58);
    if (rnd() < 0.25) { g.fillStyle = 'rgba(70,60,40,0.18)'; g.fillRect(x * 128 + 3, y * 64 + 30 + rnd() * 20, 122, 30); }
  }
});
tiles.wrapS = tiles.wrapT = THREE.RepeatWrapping; tiles.repeat.set(16, 2.2);
const floorTex = canvasTex(512, 512, (g, w, h) => {
  g.fillStyle = '#4a4a4c'; g.fillRect(0, 0, w, h);
  for (let i = 0; i < 2600; i++) { const v = 55 + rnd() * 40 | 0; g.fillStyle = `rgba(${v},${v},${v + 3},0.5)`; g.fillRect(rnd() * w, rnd() * h, 2 + rnd() * 3, 2 + rnd() * 3); }
  g.strokeStyle = 'rgba(20,20,22,0.6)'; g.lineWidth = 3; for (let x = 0; x <= w; x += 128) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, h); g.stroke(); } for (let y = 0; y <= h; y += 128) { g.beginPath(); g.moveTo(0, y); g.lineTo(w, y); g.stroke(); }
});
floorTex.wrapS = floorTex.wrapT = THREE.RepeatWrapping; floorTex.repeat.set(30, 4);
const M = (o) => new THREE.MeshStandardMaterial({ roughness: 0.85, metalness: 0, ...o });
const box = (w, h, d, mat, x, y, z, parent = scene, shadow = true) => {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); m.position.set(x, y, z); m.castShadow = shadow; m.receiveShadow = true; parent.add(m); return m;
};

// ---------- la station (voies le long de X, quai z ∈ [0, 7]) ----------
box(80, 0.4, 7.2, M({ map: floorTex, roughness: 0.75 }), 0, -0.2, 3.6);                 // quai
box(80, 0.06, 0.45, M({ color: '#c9a92a', roughness: 0.6 }), 0, 0.005, 0.32, scene, false);   // bande jaune
box(80, 1.2, 0.2, M({ color: '#2c2c2e' }), 0, -0.8, -0.1);                               // bord du quai
box(80, 0.2, 6, M({ color: '#1c1a18', roughness: 1 }), 0, -1.3, -3);                     // fond des voies
for (const z of [-1.6, -3.2]) box(80, 0.12, 0.09, M({ color: '#7d7a76', metalness: 0.9, roughness: 0.35 }), 0, -1.12, z, scene, false);
for (let x = -40; x < 40; x += 0.9) box(0.25, 0.08, 2.6, M({ color: '#2a241e' }), x, -1.18, -2.4, scene, false);
const wallMat = M({ map: tiles, roughness: 0.55 });
box(80, 4.6, 0.3, wallMat, 0, 2.1, 7.15);                                                 // mur du fond (derrière le quai)
box(80, 5.4, 0.3, M({ map: tiles, color: '#9aa0a0', roughness: 0.6 }), 0, 1.4, -5.6);   // mur en face, au-delà des voies
box(80, 0.3, 13.2, M({ color: '#2a2c30', roughness: 0.95 }), 0, 4.4, 0.8, scene, false); // plafond
for (const x of [-30, 30]) box(0.3, 4.6, 13, M({ color: '#020203' }), x, 2.1, 0.8, scene, false);
// piliers
for (let x = -24; x <= 24; x += 8) box(0.55, 4.4, 0.55, M({ map: tiles, color: '#b8b2a2' }), x, 2.2, 3.4);
// banc
const bench = new THREE.Group(); scene.add(bench); bench.position.set(-8, 0, 6.3);
box(2.4, 0.08, 0.5, M({ color: '#5a3d26' }), 0, 0.48, 0, bench); box(2.4, 0.5, 0.08, M({ color: '#5a3d26' }), 0, 0.8, 0.22, bench);
for (const x of [-1, 1]) box(0.08, 0.48, 0.45, M({ color: '#222', metalness: 0.6 }), x, 0.24, 0, bench);
// tubes fluorescents + lumières (vacillement piloté par T)
const tubes = [];
for (let x = -26; x <= 26; x += 6.5) {
  const mat = new THREE.MeshStandardMaterial({ color: '#dfe9f2', emissive: '#d8ecff', emissiveIntensity: 2.2 });
  box(2.2, 0.08, 0.16, mat, x, 4.2, 2.6, scene, false);
  const l = new THREE.PointLight('#cfe2ff', 9, 13, 1.6); l.position.set(x, 3.95, 2.6); scene.add(l);
  tubes.push({ mat, l, x });
}
const key = new THREE.SpotLight('#d6e6ff', 30, 26, 0.75, 0.6, 1.4);
key.position.set(-2, 4.1, 3.6); key.target.position.set(-2, 0, 2); key.castShadow = true; key.shadow.mapSize.set(1024, 1024); key.shadow.bias = -0.0005;
scene.add(key, key.target);
// panneau de station
const sign = canvasTex(1024, 192, (g, w, h) => {
  g.fillStyle = '#123a8a'; g.fillRect(0, 0, w, h); g.strokeStyle = '#ffffff'; g.lineWidth = 10; g.strokeRect(14, 14, w - 28, h - 28);
  g.fillStyle = '#fff'; g.font = 'bold 110px Arial, sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText('Lindenplatz', w / 2, h / 2 + 6);
});
const signM = new THREE.Mesh(new THREE.PlaneGeometry(3.2, 0.6), new THREE.MeshStandardMaterial({ map: sign, emissive: '#ffffff', emissiveMap: sign, emissiveIntensity: 0.35 }));
signM.position.set(-1.2, 2.85, 6.99); signM.rotation.y = Math.PI; scene.add(signM);
const sign2 = signM.clone(); sign2.position.set(-1.2, 2.85, -5.44); sign2.rotation.y = 0; scene.add(sign2);
// tableau d'affichage (heure)
let boardTime = '00:47';
const board = canvasTex(768, 256, (g, w, h) => {
  g.fillStyle = '#060606'; g.fillRect(0, 0, w, h);
  g.fillStyle = '#ffae1a'; g.font = 'bold 54px "Courier New", monospace'; g.textBaseline = 'middle';
  g.fillText('NÄCHSTE BAHN', 40, 70); g.font = 'bold 120px "Courier New", monospace'; g.textAlign = 'right'; g.fillText(boardTime, w - 40, 170);
  g.textAlign = 'left'; g.font = 'bold 54px "Courier New", monospace'; g.fillText('—', 40, 170);
});
const boardG = new THREE.Group(); scene.add(boardG); boardG.position.set(2.6, 3.25, 1.4);
box(2.5, 0.92, 0.18, M({ color: '#151515', metalness: 0.5 }), 0, 0, 0, boardG, false);
for (const sz of [1, -1]) {
  const p = new THREE.Mesh(new THREE.PlaneGeometry(2.3, 0.77), new THREE.MeshBasicMaterial({ map: board, toneMapped: false }));
  p.position.z = sz * 0.095; if (sz < 0) p.rotation.y = Math.PI; boardG.add(p);
}
box(0.04, 1.0, 0.04, M({ color: '#333' }), -0.8, 0.95, 0, boardG, false); box(0.04, 1.0, 0.04, M({ color: '#333' }), 0.8, 0.95, 0, boardG, false);
function setBoard(s) { if (s !== boardTime) { boardTime = s; const u = board.userData; u.draw(u.g, u.c.width, u.c.height); board.needsUpdate = true; } }
// sortie avec grille qui descend (x = 6..9)
box(3.0, 3.2, 0.32, M({ color: '#0b0b0d' }), 7.5, 1.6, 7.16, scene, false);
const gateTex = canvasTex(256, 256, (g, w, h) => { g.clearRect(0, 0, w, h); g.strokeStyle = '#b9bcc0'; g.lineWidth = 7; for (let i = -w; i < w * 2; i += 36) { g.beginPath(); g.moveTo(i, 0); g.lineTo(i + h, h); g.stroke(); g.beginPath(); g.moveTo(i, h); g.lineTo(i + h, 0); g.stroke(); } });
gateTex.wrapS = gateTex.wrapT = THREE.RepeatWrapping; gateTex.repeat.set(3, 3);
const gate = new THREE.Mesh(new THREE.PlaneGeometry(3.0, 3.2), new THREE.MeshStandardMaterial({ map: gateTex, transparent: true, alphaTest: 0.3, metalness: 0.8, roughness: 0.4, side: THREE.DoubleSide }));
gate.position.set(7.5, 4.8, 6.95); scene.add(gate);
const exitSign = canvasTex(256, 96, (g, w, h) => { g.fillStyle = '#0c7a3b'; g.fillRect(0, 0, w, h); g.fillStyle = '#fff'; g.font = 'bold 56px Arial'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText('AUSGANG', w / 2, h / 2); });
const ex = new THREE.Mesh(new THREE.PlaneGeometry(1.4, 0.52), new THREE.MeshBasicMaterial({ map: exitSign, toneMapped: false })); ex.position.set(7.5, 3.55, 6.98); ex.rotation.y = Math.PI; scene.add(ex);
// la feuille des règles (scotchée au mur, x = -4.2)
let ruleHi = 0;
const paper = canvasTex(768, 1024, (g, w, h) => {
  g.fillStyle = '#e9e0c6'; g.fillRect(0, 0, w, h);
  for (let i = 0; i < 900; i++) { g.fillStyle = `rgba(120,95,50,${rnd() * 0.06})`; g.fillRect(rnd() * w, rnd() * h, 6 + rnd() * 30, 3 + rnd() * 10); }
  g.fillStyle = '#1b1b1b'; g.textAlign = 'center'; g.font = 'bold 78px Arial'; g.fillText('NACHTREGELN', w / 2, 120);
  g.font = 'bold 40px Arial'; g.fillText('NUR FÜR PERSONAL', w / 2, 180); g.fillRect(90, 210, w - 180, 5);
  g.textAlign = 'left';
  const rule = (y, title, lines, on) => {
    if (on) { g.fillStyle = 'rgba(200,30,30,0.13)'; g.fillRect(60, y - 60, w - 120, 70 + lines.length * 58); }
    g.fillStyle = on ? '#a3130f' : '#1b1b1b'; g.font = 'bold 50px Arial'; g.fillText(title, 80, y);
    g.font = '44px Arial'; lines.forEach((l, i) => g.fillText(l, 80, y + 62 + i * 56));
  };
  rule(320, 'REGEL Nr. 1:', ['Kommt um 01:13 eine Bahn', 'ohne Fahrer:', 'NICHT EINSTEIGEN.'], ruleHi === 1);
  rule(620, 'REGEL Nr. 2:', ['Flüstert jemand deinen', 'Namen: dreh dich', 'NIEMALS um.'], ruleHi === 2);
  g.fillStyle = 'rgba(150,140,110,0.75)'; g.fillRect(260, -10, 250, 70);
});
const paperM = new THREE.Mesh(new THREE.PlaneGeometry(0.6, 0.8), new THREE.MeshStandardMaterial({ map: paper, roughness: 0.9, emissive: '#ffffff', emissiveMap: paper, emissiveIntensity: 0.12 }));
paperM.position.set(-4.2, 1.55, 6.98); paperM.rotation.set(0, Math.PI, 0.03); scene.add(paperM);
const paperLight = new THREE.SpotLight('#ffe9c2', 6, 5, 0.45, 0.7, 1.5); paperLight.position.set(-4.2, 3.6, 5.6); paperLight.target = paperM; scene.add(paperLight);
function setRule(k) { if (k !== ruleHi) { ruleHi = k; const u = paper.userData; u.draw(u.g, u.c.width, u.c.height); paper.needsUpdate = true; } }

// ---------- la rame (avance le long de X, côté voies z = -2.4) ----------
const train = new THREE.Group(); scene.add(train);
const TL = 36, body = M({ color: '#b9bec4', metalness: 0.55, roughness: 0.45 });
box(TL, 2.9, 2.8, body, 0, 0.35, -2.4, train);
box(TL, 0.25, 2.82, M({ color: '#1b4e9e' }), 0, -0.2, -2.4, train, false);
const winMat = new THREE.MeshStandardMaterial({ color: '#05070a', roughness: 0.1, metalness: 0.3 });
for (let x = -TL / 2 + 2; x < TL / 2 - 1; x += 3) box(1.9, 0.95, 0.04, winMat, x, 1.05, -0.99, train, false);
const doors = [];
for (const x of [-TL / 2 + 6.5, -6.5 + 5.3, 7.5]) {
  const L = box(0.75, 2.05, 0.06, M({ color: '#a7adb4', metalness: 0.6 }), x - 0.38, 0.4, -0.97, train, false);
  const R = box(0.75, 2.05, 0.06, M({ color: '#a7adb4', metalness: 0.6 }), x + 0.38, 0.4, -0.97, train, false);
  for (const d of [L, R]) box(0.5, 0.8, 0.02, winMat, 0, 0.35, 0.035, d, false);
  doors.push({ x, L, R });
}
// intérieur sombre derrière les portes
box(TL - 0.4, 2.4, 2.6, new THREE.MeshStandardMaterial({ color: '#030405', side: THREE.BackSide }), 0, 0.5, -2.4, train, false);
// cabine à l'avant (vers -X)
box(0.06, 1.1, 2.0, winMat, -TL / 2 - 0.01, 1.0, -2.4, train, false);
const nose = box(0.4, 2.9, 2.8, body, -TL / 2 - 0.18, 0.35, -2.4, train);
const headL = []; for (const z of [-3.4, -1.4]) { const m = new THREE.Mesh(new THREE.CircleGeometry(0.13, 20), new THREE.MeshBasicMaterial({ color: '#222' })); m.position.set(-TL / 2 - 0.39, -0.35, z); m.rotation.y = -Math.PI / 2; train.add(m); headL.push(m); }
const tailL = []; for (const z of [-3.4, -1.4]) { const m = new THREE.Mesh(new THREE.CircleGeometry(0.12, 20), new THREE.MeshBasicMaterial({ color: '#ff2a1a', toneMapped: false })); m.position.set(TL / 2 + 0.01, -0.35, z); m.rotation.y = Math.PI / 2; train.add(m); tailL.push(m); }

// ---------- personnages ----------
await RealHuman.loadClips(['idle', 'walk', 'explain'], './mocap/');
const HERO = await RealHuman.create('./models/' + (Q.get('m') || 'g_Male_Adult_04') + '.glb', { heightM: 1.8, seed: 1 });
scene.add(HERO.root);
HERO.root.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
const SHADOW = await RealHuman.create('./models/g_Male_Adult_09.glb', { heightM: 1.95, seed: 3 });
SHADOW.root.traverse(o => { if (o.isMesh) { o.material = new THREE.MeshBasicMaterial({ color: '#000000', skinning: true }); o.castShadow = false; } });
scene.add(SHADOW.root);
const eyes = []; for (const s of [-1, 1]) { const e = new THREE.Mesh(new THREE.SphereGeometry(0.009, 10, 8), new THREE.MeshBasicMaterial({ color: '#e8f0ff', toneMapped: false })); scene.add(e); eyes.push([e, s]); }
// téléphone
const phoneScr = canvasTex(256, 512, (g, w, h) => {
  g.fillStyle = '#0b0d12'; g.fillRect(0, 0, w, h); g.fillStyle = '#fff'; g.font = 'bold 44px Arial'; g.textAlign = 'center'; g.fillText('00:47', w / 2, 120);
  g.strokeStyle = '#e8352b'; g.lineWidth = 8; g.strokeRect(68, 250, 110, 56); g.fillStyle = '#e8352b'; g.fillRect(182, 266, 10, 24); g.fillRect(76, 258, 8, 40);
  g.font = 'bold 54px Arial'; g.fillText('2%', w / 2, 390);
});
const phone = new THREE.Group(); scene.add(phone);
box(0.075, 0.155, 0.009, M({ color: '#111', metalness: 0.7, roughness: 0.3 }), 0, 0, 0, phone, false);
const scr = new THREE.Mesh(new THREE.PlaneGeometry(0.068, 0.145), new THREE.MeshBasicMaterial({ map: phoneScr, toneMapped: false })); scr.position.z = 0.0052; phone.add(scr);
const phoneLight = new THREE.PointLight('#bcd2ff', 0.0, 1.2, 2); scene.add(phoneLight);

// ---------- outils de chronologie ----------
const ss = (a, b, x) => { const u = Math.min(1, Math.max(0, (x - a) / (b - a))); return u * u * (3 - 2 * u); };
const lerp = (a, b, u) => a + (b - a) * u;
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const CLIP = { idle: 18, walk: 0.93, explain: 8 };
const loopT = (c, x) => ((x % CLIP[c]) + CLIP[c]) % CLIP[c];
const FULL = { pelvis: 1, spineAbs: 1, legs: 1, arms: 1, root: 1 };
const IDLEW = { legs: 1, root: 1, pelvis: 0.5, spineAbs: 0.5, arms: 1 };
const W = JSON.parse(Q.get('w') || 'null') || window.WORDS_T || {};   // repères (mots) passés par l'URL
const t_ = (k, d) => (W[k] ?? d);

// repères temporels (secondes de voix) — valeurs par défaut = alignement de la voix finale
const K = {
  ubahn: t_('ubahn', 2.33), null_: t_('null', 3.08), gitter: t_('gitter', 6.27), akku: t_('akku', 8.6), dann: t_('dann', 10.38), zettel: t_('nacht', 12.37),
  regel1: t_('regel1', 14.7), regel2: t_('regel2', 20.29), lachst: t_('du_lachst', 24.97), um: t_('um', 26.0), drei: t_('dreizehn', 26.81),
  kommt: t_('kommt', 27.89), keine: t_('keine', 29.17), tueren: t_('die_tueren', 31.08), und: t_('und', 32.44), flue: t_('fluestert', 33.46), ganz: t_('ganz', 35.19),
  also: t_('also', 36.17), eins: t_('eins', 37.82), zwei: t_('zwei', 39.69), schreib: t_('schreib', 41.52), end: t_('end', 45.4),
};
const HPOS = V(-2.0, 0, 4.6), PAPER_STAND = V(-3.5, 0, 6.05), DOOR_X = -1.2, DOOR_STAND = V(DOOR_X, 0, 1.25);
let camPos = V(0, 1.6, 4), camTgt = V(0, 1.2, 0), lastShot = -1;

function heroState(T) {
  // renvoie { pos, yaw, walk, face, look, phone }
  const s = { pos: HPOS.clone(), yaw: Math.PI, walk: 0, face: {}, look: null, phone: 0, speed: 1 };
  if (T < K.null_ + 0.3) {           // arrive en marchant vers la droite, trop tard
    const u = ss(0, K.null_ + 0.2, T);
    s.pos = V(lerp(-9, HPOS.x, u), 0, lerp(2.4, HPOS.z, u)); s.yaw = Math.atan2(HPOS.x + 9, HPOS.z - 2.4); s.walk = 1 - ss(K.null_ - 0.3, K.null_ + 0.3, T); s.speed = 1.25;
    s.look = V(20, 1.3, -2); s.face = { browUp: 0.3, open: 0.15 };
  } else if (T < K.dann) {            // regarde le panneau, la grille, puis son téléphone
    s.yaw = lerp(Math.PI * 0.85, Math.PI * 0.55, ss(K.gitter - 0.3, K.gitter + 0.4, T)) - ss(K.akku - 0.4, K.akku + 0.2, T) * Math.PI * 0.4;
    s.look = T < K.gitter - 0.2 ? V(2.6, 3.2, 1.4) : T < K.akku - 0.3 ? V(7.5, 1.5, 7) : null;
    s.phone = ss(K.akku - 0.5, K.akku, T); s.face = { sad: 0.3 + 0.3 * s.phone, browUp: 0.2 };
  } else if (T < K.zettel) {          // marche jusqu'à la feuille
    const u = ss(K.dann, K.zettel - 0.1, T);
    s.pos = V(lerp(HPOS.x, PAPER_STAND.x, u), 0, lerp(HPOS.z, PAPER_STAND.z, u)); s.yaw = Math.atan2(PAPER_STAND.x - HPOS.x, PAPER_STAND.z - HPOS.z) * (1 - ss(K.zettel - 0.5, K.zettel, T));
    s.walk = 1 - ss(K.zettel - 0.4, K.zettel, T); s.look = V(-4.2, 1.55, 7); s.face = { squint: 0.3 };
  } else if (T < K.um) {              // lit la feuille, puis rigole
    s.pos = PAPER_STAND.clone(); s.yaw = -0.75; s.look = V(-4.2, T < K.regel2 ? 1.7 : 1.45, 7);
    s.face = T > K.lachst - 0.1 ? { smile: 1.0 * ss(K.lachst - 0.1, K.lachst + 0.3, T), squint: 0.5, open: 0.12 } : { squint: 0.4, browUp: 0.2 * ss(K.regel2, K.regel2 + 1, T) };
  } else if (T < K.tueren - 0.6) {    // va au bord du quai en regardant le tableau puis le tunnel
    const u = ss(K.um, K.kommt, T);
    s.pos = V(lerp(PAPER_STAND.x, DOOR_X, u), 0, lerp(PAPER_STAND.z, DOOR_STAND.z, u)); s.yaw = lerp(Math.PI * 0.8, Math.PI, ss(K.kommt - 0.5, K.kommt, T));
    s.walk = 1 - ss(K.kommt - 0.4, K.kommt, T); s.look = T < K.kommt ? V(2.6, 3.2, 1.4) : V(30, 0.6, -2.4);
    s.face = { browUp: 0.5, wide: 0.3 + 0.4 * ss(K.keine, K.keine + 1, T) };
  } else {                             // devant les portes, la silhouette derrière lui
    s.pos = DOOR_STAND.clone(); s.yaw = Math.PI;
    s.look = T < K.und ? V(DOOR_X, 1.0, -2.5) : V(DOOR_X + lerp(0.0, 0.9, ss(K.flue, K.ganz, T)), 1.5, 0);
    const fear = ss(K.flue - 0.2, K.ganz, T);
    s.face = { wide: 0.5 + 0.5 * fear, browUp: 0.5 + 0.5 * fear, open: 0.15 + 0.35 * fear, sad: 0.3 * fear };
  }
  return s;
}

function shadowState(T) {
  // invisible jusqu'au chuchotement, puis avance derrière lui
  if (T < K.und - 0.4) return null;
  const u = ss(K.und - 0.4, K.ganz + 0.2, T);
  return { pos: V(lerp(-1.6, DOOR_X + 0.15, u), 0, lerp(6.6, DOOR_STAND.z + 0.62, u)), yaw: Math.PI, walk: 1 - ss(K.ganz - 0.2, K.ganz + 0.4, T) };
}

function trainX(T) {
  // départ (s'en va vers +X dans le tunnel) puis arrivée (depuis +X, s'arrête porte face au héros)
  if (T < K.null_ + 1.5) return lerp(-3, 60, Math.pow(ss(-1, K.null_ + 1.5, T), 1.6));
  if (T < K.kommt - 0.3) return 200;
  const stop = DOOR_X - doors[1].x;                     // la 2e porte s'arrête devant le héros
  const u = ss(K.kommt - 0.3, K.tueren - 0.15, T); return lerp(stop + 70, stop, 1 - Math.pow(1 - u, 2.2));
}

function shot(T) {
  // caméras (position, cible, focale)
  const hs = heroState(T); HERO.headWorld(_hw);
  if (T < K.null_) return [V(-12, 1.5, 5.6), V(2, 1.0, 1.2), 46];
  if (T < K.gitter) { const u = ss(K.null_, K.gitter, T); return [V(-1.0, lerp(1.2, 1.5, u), lerp(-1.6, -0.6, u)), V(-0.4, lerp(2.4, 2.1, u), 6.5), 44]; }
  if (T < K.akku - 0.15) return [V(0.8, 1.5, 2.0), V(7.5, 1.4, 7.0), 40];
  if (T < K.dann) { const f = V(Math.sin(hs.yaw), 0, Math.cos(hs.yaw)), r = V(f.z, 0, -f.x); const d = _hw.clone().sub(_ph).normalize(); return [_ph.clone().addScaledVector(d, 0.26).add(V(0, 0.02, 0)), _ph.clone(), 46]; }
  if (T < K.zettel) { const p = HERO.root.position; return [V(p.x + 1.2, 1.7, p.z - 2.2), V(-4.2, 1.4, 7), 44]; }
  if (T < K.regel1) return [V(-4.3, 1.58, 5.55), V(-4.2, 1.55, 7), 46];
  if (T < K.regel2 - 1.6) { const u = ss(K.regel1, K.regel2 - 1.6, T); return [V(-4.2, 1.7, lerp(6.0, 6.2, u)), V(-4.2, 1.7, 7), 56]; }
  if (T < K.regel2) return [_hw.clone().add(V(-0.45, -0.02, 0.5)), _hw.clone(), 36];                 // son visage qui lit
  if (T < K.lachst) { const u = ss(K.regel2, K.lachst, T); return [V(-4.2, 1.42, lerp(6.0, 6.2, u)), V(-4.2, 1.42, 7), 56]; }
  if (T < K.um) return [_hw.clone().add(V(-0.45, -0.02, 0.45)), _hw.clone(), 34];
  if (T < K.kommt) return [V(2.6, 2.4, -0.6), V(2.6, 3.25, 1.4), 40];                // tableau 01:13
  if (T < K.keine) return [V(-8, 1.05, 0.55), V(30, 0.2, -2.4), 40];                 // tunnel, la rame arrive
  if (T < K.tueren) return [V(DOOR_X - 6.5, 1.55, 3.0), V(DOOR_X - 1, 0.9, -2.0), 44];
  if (T < K.und) return [V(DOOR_X + 0.35, 1.65, 3.3), V(DOOR_X, 1.0, -1.2), 42];   // par-dessus son épaule : les portes s'ouvrent
  if (T < K.also) { const u = ss(K.und, K.ganz + 0.4, T); return [V(DOOR_X - 0.08, 1.62, lerp(-0.7, 0.35, u)), V(DOOR_X + 0.1, 1.62, 2.0), lerp(42, 34, u)]; }
  if (T < K.schreib) return [V(-6.2, 1.5, 1.7), V(DOOR_X, 1.15, 1.4), 40];          // plan large : la rame ouverte / la silhouette
  const u = ss(K.schreib, K.end, T); return [V(DOOR_X - lerp(1.0, 0.7, u), 1.66, lerp(0.55, 0.8, u)), V(DOOR_X + 0.05, 1.68, 1.6), lerp(38, 30, u)];
}
const _hw = new THREE.Vector3(), _ph = new THREE.Vector3(), _q = new THREE.Quaternion();

function frame(T) {
  // lumières : vacillement après 01:13 et au chuchotement
  const flick = (a) => (Math.sin(T * 37 + a) > 0.2 || Math.sin(T * 13 + a * 3) > 0.6 ? 1 : 0.15);
  const bad = ss(K.drei, K.drei + 0.2, T) * (1 - ss(K.kommt + 0.5, K.kommt + 1, T)) + ss(K.flue - 0.2, K.flue, T);
  tubes.forEach((tb, i) => { const f = bad > 0 && i % 2 === 0 ? lerp(1, flick(i), Math.min(1, bad)) : 1; const dim = T > K.und ? 0.6 : 1; tb.mat.emissiveIntensity = 2.2 * f * dim; tb.l.intensity = 9 * f * dim; });
  setBoard(T < K.drei - 0.05 ? (T < K.um - 0.3 ? '00:47' : '01:12') : '01:13');
  setRule(T >= K.regel1 && T < K.regel2 ? 1 : T >= K.regel2 && T < K.um ? 2 : 0);
  gate.position.y = lerp(4.8, 1.6, ss(K.gitter, K.akku - 0.4, T));
  // rame
  train.position.x = trainX(T);
  tailL.forEach(m => (m.visible = T < K.null_ + 2));
  const op = ss(K.tueren, K.tueren + 1.1, T);
  for (const d of doors) { d.L.position.x = d.x - 0.38 - op * 0.72; d.R.position.x = d.x + 0.38 + op * 0.72; }
  // héros
  const h = heroState(T);
  HERO.root.position.copy(h.pos); HERO.root.rotation.y = h.yaw;
  const mo = [{ clip: 'walk', mode: 'abs', t: loopT('walk', T * h.speed), k: h.walk, w: { ...FULL, arms: 0.85 } },
              { clip: 'idle', mode: 'abs', t: loopT('idle', T + 3), k: 1 - h.walk, w: IDLEW }];
  const pose = { mo, lookW: 0.85 };
  if (h.phone > 0) {   // main droite qui tient le téléphone devant la poitrine
    const p = V(0.06, 1.22, 0.3).applyAxisAngle(V(0, 1, 0), h.yaw).add(h.pos);
    Object.assign(pose, { rW: h.phone, rwx: p.x, rwy: p.y, rwz: p.z, rWrX: -0.4, rCurl: 0.9 });
  }
  HERO.setPose(pose, h.face, h.look || (h.phone > 0.5 ? null : null), T);
  if (h.phone > 0.5) HERO.setPose(pose, h.face, V(0.06, 1.2, 0.32).applyAxisAngle(V(0, 1, 0), h.yaw).add(h.pos), T);
  phone.visible = h.phone > 0.05; HERO.headWorld(_hw);
  if (phone.visible) {
    HERO.handPoint('r', _ph); _ph.addScaledVector(_hw.clone().sub(_ph).normalize(), 0.05).add(V(0, 0.07, 0)); phone.position.copy(_ph);
    phone.lookAt(_hw);
    phoneLight.position.copy(_ph).add(V(0, 0.05, 0).add(V(0, 0, 0.12).applyAxisAngle(V(0, 1, 0), h.yaw))); phoneLight.intensity = 0.8 * h.phone;
  } else phoneLight.intensity = 0;
  // silhouette
  const sh = shadowState(T);
  SHADOW.root.visible = !!sh;
  eyes.forEach(([e]) => (e.visible = !!sh && T > K.ganz - 0.3));
  if (sh) {
    SHADOW.root.position.copy(sh.pos); SHADOW.root.rotation.y = sh.yaw;
    SHADOW.setPose({ mo: [{ clip: 'walk', mode: 'abs', t: loopT('walk', T * 0.7), k: sh.walk, w: FULL }, { clip: 'idle', mode: 'abs', t: loopT('idle', T), k: 1 - sh.walk, w: IDLEW }], lookW: 0.9, headX: 0.25 }, {}, HERO.headWorld(new THREE.Vector3()), T);
    const hw = SHADOW.headWorld(new THREE.Vector3());
    SHADOW.bones[SHADOW.B.head].getWorldQuaternion(_q);
    eyes.forEach(([e, s]) => { e.position.copy(hw).add(V(s * 0.032, 0.0, -0.075)); });
  }
  // caméra
  HERO.headWorld(_hw);
  const [p, tgt, fov] = shot(T);
  const sid = [K.null_, K.gitter, K.akku - 0.15, K.dann, K.zettel, K.regel1, K.regel2 - 1.6, K.regel2, K.lachst, K.um, K.kommt, K.keine, K.tueren, K.und, K.also, K.schreib].filter(x => x <= T).length;
  if (sid !== lastShot) { camPos.copy(p); camTgt.copy(tgt); lastShot = sid; } else { camPos.lerp(p, 0.3); camTgt.lerp(tgt, 0.3); }
  const shake = T > K.flue ? 0.004 : 0.0015;
  camera.position.copy(camPos).add(V(Math.sin(T * 1.3) * shake, Math.sin(T * 1.7) * shake, 0));
  camera.lookAt(camTgt); camera.fov = fov;
  fillL.position.copy(camera.position).add(V(0, 0.25, 0)); fillL.target.position.copy(camTgt); fillL.intensity = T > K.und ? 3.0 : 4.5;
  const w2 = innerWidth, h2 = innerHeight;
  if (canvas.width !== w2) renderer.setSize(w2, h2, false);
  camera.aspect = w2 / h2; camera.updateProjectionMatrix();
  renderer.render(scene, camera);
}
window.renderAt = (T) => frame(T);
window.READY = true;
if (!MANUAL) { const c0 = performance.now(); const loop = () => { frame(((performance.now() - c0) / 1000) % 46); requestAnimationFrame(loop); }; loop(); }
else frame(0);
