// « Zwei Väter » v2 (45 s, une seule question) – nouvelle histoire (compte allemand horreur), même formule que « Ich bin's. Mach auf. » Teil 3.
// LE MATIN : cuisine ensoleillée, porte de la cave ouverte sur un escalier qui descend vers une porte fermée à clé.
// Deux personnages : le fils (Rocketbox « kid ») et le père (« judge ») ; l'autre père est seulement derrière la porte.
// Contrôles : lèvres par sons (visèmes à partir du texte), objets tenus dans la paume (tasse, téléphone, clés),
// montre au poignet DROIT, caméra continue par lieu et bornée dans les pièces (jamais dans un mur ou un meuble).
// ?manual : rendu image par image (window.renderAt(T)).
import * as THREE from 'three';
import { RealHuman } from './rig.js';

const Q = new URLSearchParams(location.search);
const MANUAL = Q.has('manual');
const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1); renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.05; renderer.outputColorSpace = THREE.SRGBColorSpace;
const scene = new THREE.Scene(); scene.background = new THREE.Color('#b9cbe0');
const camera = new THREE.PerspectiveCamera(40, 9 / 16, 0.03, 60);
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const rnd = (s => () => (s = (s * 16807) % 2147483647) / 2147483647)(5);
function canvasTex(w, h, draw) { const c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d'); draw(g, w, h); const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; t.userData = { c, g }; return t; }
const M = (o) => new THREE.MeshStandardMaterial({ roughness: 0.85, metalness: 0, ...o });
const box = (w, h, d, mat, x, y, z, parent = scene, shadow = true) => { const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); m.position.set(x, y, z); m.castShadow = shadow; m.receiveShadow = true; parent.add(m); return m; };
const cyl = (r, h, mat, x, y, z, parent = scene, seg = 20) => { const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, seg), mat); m.position.set(x, y, z); m.castShadow = true; m.receiveShadow = true; parent.add(m); return m; };

// ---------- textures ----------
const tiles = canvasTex(512, 512, (g, w, h) => { g.fillStyle = '#d9d2c4'; g.fillRect(0, 0, w, h); for (let y = 0; y < 4; y++) for (let x = 0; x < 4; x++) { const v = 205 + rnd() * 25 | 0; g.fillStyle = `rgb(${v},${v - 6},${v - 16})`; g.fillRect(x * 128 + 3, y * 128 + 3, 122, 122); } });
tiles.wrapS = tiles.wrapT = THREE.RepeatWrapping; tiles.repeat.set(4, 4);
const wallT = canvasTex(256, 256, (g, w, h) => { g.fillStyle = '#ece3cf'; g.fillRect(0, 0, w, h); for (let i = 0; i < 300; i++) { g.fillStyle = `rgba(120,100,70,${rnd() * 0.04})`; g.fillRect(rnd() * w, rnd() * h, 3, 3); } });
wallT.wrapS = wallT.wrapT = THREE.RepeatWrapping; wallT.repeat.set(3, 2);
const stoneT = canvasTex(512, 512, (g, w, h) => { g.fillStyle = '#5c5850'; g.fillRect(0, 0, w, h); for (let y = 0; y < h; y += 46) for (let x = -(y / 46 % 2) * 40; x < w; x += 80) { const v = 78 + rnd() * 30 | 0; g.fillStyle = `rgb(${v + 6},${v + 2},${v - 4})`; g.fillRect(x + 3, y + 3, 74, 40); } });
stoneT.wrapS = stoneT.wrapT = THREE.RepeatWrapping; stoneT.repeat.set(2, 2);
const woodT = canvasTex(256, 512, (g, w, h) => { for (let x = 0; x < w; x += 32) { const v = 95 + rnd() * 25 | 0; g.fillStyle = `rgb(${v + 30},${v + 8},${v - 20})`; g.fillRect(x, 0, 32, h); g.fillStyle = 'rgba(30,15,5,0.5)'; g.fillRect(x, 0, 2, h); } });

// ---------- la cuisine : x -2.2..2.2, z 0..4.4 (mur de la cave en z = 0), y 0..2.6 ----------
const KW = 2.2, KD = 4.4, KH = 2.6;
const wallM = M({ map: wallT, roughness: 0.92 });
box(2 * KW, 0.1, KD, M({ map: tiles, roughness: 0.55 }), 0, -0.05, KD / 2);
box(2 * KW, 0.1, KD, M({ color: '#f4efe6' }), 0, KH + 0.05, KD / 2, scene, false);
box(2 * KW, KH, 0.1, wallM, 0, KH / 2, KD + 0.05);                               // mur du fond (plan de travail)
box(0.1, KH, KD, wallM, KW + 0.05, KH / 2, KD / 2);                                // mur droit
// mur gauche avec la grande fenêtre (soleil du matin)
box(0.1, 0.9, KD, wallM, -KW - 0.05, 0.45, KD / 2); box(0.1, 0.5, KD, wallM, -KW - 0.05, KH - 0.25, KD / 2);
box(0.1, 1.2, 1.4, wallM, -KW - 0.05, 1.5, 0.7); box(0.1, 1.2, 1.2, wallM, -KW - 0.05, 1.5, KD - 0.6);
const sky = new THREE.Mesh(new THREE.PlaneGeometry(1.8, 1.2), new THREE.MeshBasicMaterial({ color: '#dceaf7', toneMapped: false })); sky.position.set(-KW - 0.3, 1.5, 2.3); sky.rotation.y = Math.PI / 2; scene.add(sky);
for (const z of [1.4, 2.3, 3.2]) box(0.06, 1.2, 0.05, M({ color: '#f7f7f2' }), -KW - 0.02, 1.5, z, scene, false);
box(0.06, 0.05, 1.8, M({ color: '#f7f7f2' }), -KW - 0.02, 1.5, 2.3, scene, false);
for (const z of [1.25, 3.35]) { const c = box(0.04, 1.7, 0.35, M({ color: '#c9a97a', roughness: 1 }), -KW + 0.05, 1.45, z, scene, false); c.rotation.y = 0.15; }   // rideaux
// mur de la cave (z = 0) avec l'ouverture de la porte de la cave (x 0.85..1.75)
box(KW + 0.85, KH, 0.1, wallM, (-KW + 0.85) / 2, KH / 2, -0.05); box(KW - 1.75, KH, 0.1, wallM, (1.75 + KW) / 2, KH / 2, -0.05); box(0.9, KH - 2.05, 0.1, wallM, 1.3, 2.05 + (KH - 2.05) / 2, -0.05);
box(1.0, 0.05, 0.12, M({ color: '#fff' }), 1.3, 2.07, 0.0, scene, false); for (const s of [-1, 1]) box(0.05, 2.07, 0.12, M({ color: '#fff' }), 1.3 + s * 0.475, 1.035, 0.0, scene, false);
const cHinge = new THREE.Group(); scene.add(cHinge); cHinge.position.set(1.75, 0, 0.02); cHinge.rotation.y = 1.9;   // porte du haut, grande ouverte côté cuisine
box(0.88, 2.02, 0.04, M({ map: woodT, color: '#a88a6a' }), -0.44, 1.01, 0, cHinge);
// plan de travail, placards, évier, machine à café, frigo
box(3.0, 0.88, 0.62, M({ color: '#f1ece2' }), -0.4, 0.44, KD - 0.31); box(3.04, 0.04, 0.66, M({ color: '#6f5c48', roughness: 0.45 }), -0.4, 0.9, KD - 0.31);
for (let i = 0; i < 5; i++) box(0.56, 0.7, 0.01, M({ color: '#e7e0d3' }), -1.6 + i * 0.6, 0.45, KD - 0.615, scene, false);
box(3.0, 0.7, 0.35, M({ color: '#f1ece2' }), -0.4, 1.95, KD - 0.18);
box(0.5, 0.04, 0.38, M({ color: '#b8bcc2', metalness: 0.7, roughness: 0.3 }), 0.2, 0.92, KD - 0.31);
const cm = box(0.24, 0.36, 0.3, M({ color: '#222', roughness: 0.4 }), -1.3, 1.1, KD - 0.3); box(0.1, 0.12, 0.1, M({ color: '#ddd' }), -1.3, 0.98, KD - 0.47, scene, false);
box(0.7, 1.9, 0.65, M({ color: '#eceae6', roughness: 0.4 }), 1.65, 0.95, KD - 0.36);
const clockT = canvasTex(128, 128, (g, w) => { g.fillStyle = '#fff'; g.beginPath(); g.arc(64, 64, 60, 0, 7); g.fill(); g.strokeStyle = '#222'; g.lineWidth = 4; g.stroke(); g.beginPath(); g.moveTo(64, 64); g.lineTo(64 + 34 * Math.sin(-0.3), 64 - 34 * Math.cos(-0.3)); g.moveTo(64, 64); g.lineTo(64 + 46 * Math.sin(4.4), 64 - 46 * Math.cos(4.4)); g.stroke(); });
const wc = new THREE.Mesh(new THREE.CircleGeometry(0.16, 32), M({ map: clockT })); wc.position.set(KW - 0.01, 2.0, 2.2); wc.rotation.y = -Math.PI / 2; scene.add(wc);
// table et chaises (à droite du père), la tasse et le sucrier sur la table
const TX = -0.45, TZ = 3.05;
box(1.1, 0.04, 0.75, M({ map: woodT, color: '#b08a62', roughness: 0.5 }), TX, 0.76, TZ);
for (const [dx, dz] of [[-0.5, -0.32], [0.5, -0.32], [-0.5, 0.32], [0.5, 0.32]]) box(0.05, 0.74, 0.05, M({ color: '#7a5a3c' }), TX + dx, 0.37, TZ + dz);
for (const dx of [-0.75, 0.75]) { const ch = new THREE.Group(); scene.add(ch); ch.position.set(TX + dx, 0, TZ); box(0.42, 0.04, 0.42, M({ color: '#8a6a48' }), 0, 0.46, 0, ch); box(0.42, 0.45, 0.04, M({ color: '#8a6a48' }), 0, 0.7, (dx > 0 ? 1 : -1) * 0.2, ch); }
const sugar = cyl(0.045, 0.07, M({ color: '#f2f2f2', roughness: 0.3 }), TX + 0.2, 0.815, TZ - 0.18);
box(0.24, 0.015, 0.24, M({ color: '#ddd' }), TX - 0.2, 0.785, TZ + 0.05, scene, false);   // assiette
const mug = new THREE.Group(); scene.add(mug);
{ const body = cyl(0.04, 0.095, M({ color: '#2f5f8a', roughness: 0.35 }), 0, 0, 0, mug, 24); const coffee = cyl(0.036, 0.004, M({ color: '#2a1608', roughness: 0.2 }), 0, 0.044, 0, mug, 24);
  const handle = new THREE.Mesh(new THREE.TorusGeometry(0.025, 0.007, 8, 16, Math.PI), M({ color: '#2f5f8a' })); handle.rotation.z = -Math.PI / 2; handle.position.x = 0.04; mug.add(handle); }
const MUG0 = V(TX + 0.32, 0.828, TZ - 0.28);

// ---------- l'escalier de la cave : x 0.85..1.75, descend de z 0 à z -3.0 (12 marches de 0.2), palier y -2.4, porte en z -4.2 ----------
const SX = 1.3, NST = 12;
const stM = M({ map: woodT, color: '#8f7356', roughness: 0.7 });
for (let i = 0; i < NST; i++) box(0.9, 0.2, 0.25, stM, SX, -(i + 1) * 0.2 - 0.1, -i * 0.25 - 0.125);   // marche i : dessus à y = -(i+1)*0.2
const stW = M({ map: stoneT, roughness: 1 });
box(0.1, 5.2, 4.4, stW, SX - 0.5, 0.1, -2.1); box(0.1, 5.2, 4.4, stW, SX + 0.5, 0.1, -2.1);
box(1.1, 0.1, 1.4, M({ color: '#4a4640', roughness: 1 }), SX, -2.45, -3.6);               // sol du palier
box(1.1, 0.1, 4.4, M({ color: '#d8d0c0' }), SX, 2.66, -2.1, scene, false);                // plafond
// la porte de la cave (fermée à clé de l'extérieur) : planches, poignée, trou de serrure
const DZ = -4.2;
box(1.1, 3.0, 0.1, stW, SX, -0.9, DZ - 0.05);
const kHinge = new THREE.Group(); scene.add(kHinge); kHinge.position.set(SX - 0.4, -2.4, DZ + 0.03);
const kM = M({ color: '#5b4632', roughness: 0.9 });
for (let i = 0; i < 6; i++) box(0.13, 1.95, 0.05, kM, 0.07 + i * 0.133, 0.975, 0, kHinge);
for (const y of [0.35, 1.6]) box(0.8, 0.1, 0.03, M({ color: '#4a3826' }), 0.4, y, 0.04, kHinge);
const knob = cyl(0.025, 0.07, M({ color: '#9a8a6a', metalness: 0.8, roughness: 0.35 }), 0.68, 1.0, 0.07, kHinge); knob.rotation.x = Math.PI / 2;
box(0.05, 0.13, 0.012, M({ color: '#7a6a4a', metalness: 0.8, roughness: 0.4 }), 0.68, 0.92, 0.035, kHinge, false);
const keyhole = box(0.012, 0.03, 0.004, M({ color: '#050505' }), 0.68, 0.9, 0.043, kHinge, false);
const underL = new THREE.Mesh(new THREE.PlaneGeometry(0.78, 0.02), new THREE.MeshBasicMaterial({ color: '#ffcf8a', toneMapped: false })); underL.position.set(SX, -2.39, DZ + 0.06); scene.add(underL);
const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.04, 12, 8), new THREE.MeshBasicMaterial({ color: '#ffe0b0', toneMapped: false })); bulb.position.set(SX, -0.6, -3.5); scene.add(bulb);
const bulbL = new THREE.PointLight('#ffc98a', 3.5, 6, 1.5); bulbL.position.set(SX, -0.7, -3.4); bulbL.castShadow = true; bulbL.shadow.mapSize.set(1024, 1024); scene.add(bulbL);
const faceL = new THREE.PointLight('#ffe9cf', 2.2, 3, 1.5); faceL.position.set(SX, 1.4, -1.0); scene.add(faceL);
const topL = new THREE.SpotLight('#fff1d8', 14, 7, 0.6, 0.6, 1.4); topL.position.set(SX, 2.3, 0.6); topL.target.position.set(SX, -1.5, -2.5); scene.add(topL, topL.target);

// ---------- lumières du matin ----------
scene.add(new THREE.HemisphereLight('#e8f0fa', '#9a8466', 0.9));
const sun = new THREE.DirectionalLight('#ffe7c4', 3.4); sun.position.set(-6, 4.2, 1.2); sun.target.position.set(0.5, 0.4, 2.4); sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048); Object.assign(sun.shadow.camera, { left: -3.5, right: 3.5, top: 3.5, bottom: -3.5, near: 1, far: 15 }); sun.shadow.bias = -0.0004; scene.add(sun, sun.target);
const bounce = new THREE.PointLight('#ffe9cf', 1.6, 7, 1.4); bounce.position.set(0.8, 1.9, 2.4); scene.add(bounce);
const fillL = new THREE.SpotLight('#f3f0ea', 1.2, 5, 0.6, 0.9, 1.6); scene.add(fillL, fillL.target);

// ---------- objets tenus : téléphone (fils), montre + clés (père) ----------
const phone = new THREE.Group(); scene.add(phone);
box(0.074, 0.152, 0.009, M({ color: '#3a3f47', roughness: 0.28, metalness: 0.75 }), 0, 0, 0, phone, false);
const scrTex = canvasTex(540, 1110, () => {}); let scrState = '';
function drawScreen(st) {
  if (st === scrState) return; scrState = st; const { g, c } = scrTex.userData, w = c.width, h = c.height;
  g.fillStyle = st === 'off' ? '#050608' : '#f2f3f5'; g.fillRect(0, 0, w, h); if (st === 'off') { scrTex.needsUpdate = true; return; }
  g.fillStyle = '#1d2a3c'; g.fillRect(0, 0, w, 150); g.fillStyle = '#fff'; g.font = '600 30px Arial'; g.textAlign = 'left'; g.fillText('07:42', 36, 50);
  g.fillStyle = '#3a6fd8'; g.beginPath(); g.arc(80, 108, 30, 0, 7); g.fill(); g.fillStyle = '#fff'; g.font = 'bold 34px Arial'; g.textAlign = 'center'; g.fillText('P', 80, 120);
  g.textAlign = 'left'; g.font = 'bold 40px Arial'; g.fillText('Papa', 130, 122);
  if (st !== 'empty') {
    g.fillStyle = '#e4e6ea'; g.beginPath(); g.roundRect(30, 230, 440, 230, 30); g.fill(); g.fillStyle = '#111'; g.font = '38px Arial';
    ['Ich bin im Keller', 'eingesperrt.', 'Mach mir auf.'].forEach((l, i) => g.fillText(l, 60, 295 + i * 60));
    g.fillStyle = '#888'; g.font = '26px Arial'; g.fillText('07:42', 60, 492);
    if (st === 'msg2') { g.fillStyle = '#e4e6ea'; g.beginPath(); g.roundRect(30, 540, 440, 170, 30); g.fill(); g.fillStyle = '#111'; g.font = '38px Arial';
      ['Er hat den Schlüssel.', 'In seiner Tasche.'].forEach((l, i) => g.fillText(l, 60, 605 + i * 60)); g.fillStyle = '#888'; g.font = '26px Arial'; g.fillText('07:44', 60, 742); }
  }
  scrTex.needsUpdate = true;
}
const scr = new THREE.Mesh(new THREE.PlaneGeometry(0.068, 0.14), new THREE.MeshBasicMaterial({ map: scrTex, toneMapped: false })); scr.position.z = 0.0047; phone.add(scr);
const phoneL = new THREE.PointLight('#dfe8ff', 0, 0.45, 2); scene.add(phoneL);
const watch = new THREE.Group(); scene.add(watch);
{ const band = new THREE.Mesh(new THREE.CylinderGeometry(0.031, 0.031, 0.018, 24, 1, true), M({ color: '#2a2622', roughness: 0.55, side: THREE.DoubleSide })); band.rotation.x = Math.PI / 2; band.position.y = -0.024; watch.add(band); }
const wdial = canvasTex(64, 64, (g) => { g.fillStyle = '#efe9da'; g.beginPath(); g.arc(32, 32, 30, 0, 7); g.fill(); g.strokeStyle = '#222'; g.lineWidth = 3; g.beginPath(); g.moveTo(32, 32); g.lineTo(32, 12); g.moveTo(32, 32); g.lineTo(46, 36); g.stroke(); });
const wfaceTop = new THREE.Mesh(new THREE.CircleGeometry(0.0115, 24), new THREE.MeshStandardMaterial({ map: wdial, roughness: 0.3 })); wfaceTop.rotation.x = -Math.PI / 2; wfaceTop.position.y = 0.0042; watch.add(wfaceTop);
const wface = cyl(0.0135, 0.007, M({ color: '#c9c3b5', metalness: 0.8, roughness: 0.25 }), 0, 0.008, 0, watch, 24);
const keys = new THREE.Group(); scene.add(keys);
{ const ring = new THREE.Mesh(new THREE.TorusGeometry(0.018, 0.0025, 8, 20), M({ color: '#b9b4a8', metalness: 0.9, roughness: 0.3 })); keys.add(ring);
  for (let i = 0; i < 3; i++) { const k = new THREE.Group(); k.position.set(Math.sin(i * 1.2 - 1.2) * 0.012, -0.018, Math.cos(i * 1.2) * 0.005); k.rotation.z = (i - 1) * 0.35; keys.add(k);
    box(0.012, 0.055, 0.003, M({ color: ['#c8a85a', '#b9b9b9', '#a89a72'][i], metalness: 0.9, roughness: 0.3 }), 0, -0.03, 0, k, false); } }

// ---------- personnages ----------
await RealHuman.loadClips(['idle', 'slowwalk', 'run2', 'explain'], './mocap/');
const ENV = await (await fetch('./mocap/voice_zv2.json')).json();
const WORDS = await (await fetch('./mocap/words_zv2.json')).json();
const HERO = await RealHuman.create('./models/kid.glb', { heightM: 1.66, seed: 2 });
const PAPA = await RealHuman.create('./models/judge.glb', { heightM: 1.86, seed: 7 });
for (const H of [HERO, PAPA]) { scene.add(H.root); H.root.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } }); }

// ---------- outils ----------
const ss = (a, b, x) => { const u = Math.min(1, Math.max(0, (x - a) / (b - a))); return u * u * (3 - 2 * u); };
const lerp = (a, b, u) => a + (b - a) * u;
const inR = (T, a, b) => T >= a && T < b;
const FULL = { pelvis: 1, spineAbs: 1, legs: 1, arms: 1, root: 1, headAbs: 0.4 };
const dur = (c) => RealHuman.clips[c].frames / RealHuman.clips[c].fps;
const loopT = (c, x) => ((x % dur(c)) + dur(c)) % dur(c);
const IDLEM = (t) => [{ clip: 'idle', mode: 'abs', t: loopT('idle', t), k: 1, w: { legs: 1, root: 1, pelvis: 0.1, spineAbs: 0.1, arms: 1 } }];
const CLIP = (c, t, k = 1) => [{ clip: c, mode: 'abs', t: loopT(c, t), k, w: FULL }];
const TALKING = (t, k = 1) => [...IDLEM(t), { clip: 'explain', mode: 'abs', t: loopT('explain', t * 0.8 + 1.5), k: 0.55 * k, w: { arms: 1, spineAbs: 0.3, headAbs: 0.2 } }];
const FEAR = { maxM: 1.5, raw: { EyeWideLeft: 1.3, EyeWideRight: 1.3, BrowInnerUp: 1.2, BrowOuterUpLeft: 1.0, BrowOuterUpRight: 1.0, JawOpen: 0.25, MouthStretchLeft: 0.6, MouthStretchRight: 0.6 } };
const WORRY = { maxM: 1.2, raw: { EyeWideLeft: 0.5, EyeWideRight: 0.5, BrowInnerUp: 0.9, BrowOuterUpLeft: 0.3, BrowOuterUpRight: 0.3, MouthPressLeft: 0.4, MouthPressRight: 0.4 } };
const SHOCK = { maxM: 1.6, raw: { EyeWideLeft: 1.6, EyeWideRight: 1.6, BrowInnerUp: 1.4, BrowOuterUpLeft: 1.3, BrowOuterUpRight: 1.3, JawOpen: 0.45, MouthLowerDownLeft: 0.5, MouthLowerDownRight: 0.5 } };
const WARM = { maxM: 1.2, raw: { BrowInnerUp: 0.4, MouthSmileLeft: 0.55, MouthSmileRight: 0.55, EyeSquintLeft: 0.25, EyeSquintRight: 0.25, CheekSquintLeft: 0.2, CheekSquintRight: 0.2 } };
const GRIN = { maxM: 2, raw: { MouthSmileLeft: 1.7, MouthSmileRight: 1.7, CheekSquintLeft: 0.6, CheekSquintRight: 0.6, MouthStretchLeft: 0.7, MouthStretchRight: 0.7, MouthUpperUpLeft: 0.4, MouthUpperUpRight: 0.4, EyeWideLeft: 1.0, EyeWideRight: 1.0 } };
const mix = (a, b, u) => { const r = {}; for (const k of new Set([...Object.keys(a.raw || {}), ...Object.keys(b.raw || {})])) r[k] = lerp((a.raw || {})[k] || 0, (b.raw || {})[k] || 0, u); return { maxM: Math.max(a.maxM || 1, b.maxM || 1), raw: r }; };
const env = (T) => { const i = Math.floor(T * 30); return ENV[Math.max(0, Math.min(ENV.length - 1, i))] || 0; };
// lèvres par SONS : chaque mot est découpé en sons (voyelles / m-b-p / f-v-w / autres), chaque son a sa forme de bouche
const VIS = { A: { JawOpen: 0.55, MouthLowerDownLeft: 0.25, MouthLowerDownRight: 0.25 }, E: { JawOpen: 0.28, MouthStretchLeft: 0.45, MouthStretchRight: 0.45 },
  O: { JawOpen: 0.38, MouthFunnel: 0.65 }, U: { JawOpen: 0.18, MouthPucker: 0.75, MouthFunnel: 0.3 }, M: { MouthClose: 0.5, MouthPressLeft: 0.45, MouthPressRight: 0.45 },
  F: { JawOpen: 0.08, MouthShrugLower: 0.6, MouthUpperUpLeft: 0.2, MouthUpperUpRight: 0.2 }, C: { JawOpen: 0.14 } };
function phones(w) {
  w = w.toLowerCase().replace(/[^a-zäöüß]/g, ''); const out = []; let i = 0;
  while (i < w.length) {
    const two = w.slice(i, i + 2);
    if (['au', 'ei', 'ie', 'eu', 'äu'].includes(two)) { out.push(two === 'au' ? 'A' : two === 'ie' ? 'E' : two === 'eu' || two === 'äu' ? 'O' : 'A'); i += 2; continue; }
    const ch = w[i]; i++;
    if ('aä'.includes(ch)) out.push('A'); else if ('eiy'.includes(ch)) out.push('E'); else if ('oö'.includes(ch)) out.push('O'); else if ('uü'.includes(ch)) out.push('U');
    else if ('mbp'.includes(ch)) out.push('M'); else if ('fvw'.includes(ch)) out.push('F'); else if (out[out.length - 1] !== 'C') out.push('C');
  }
  return out.length ? out : ['C'];
}
function mouthAt(T) {
  for (const [w, a, b] of WORDS) if (T >= a - 0.03 && T < b + 0.03) { const ph = phones(w), u = Math.min(0.999, Math.max(0, (T - a) / Math.max(0.05, b - a))), k = u * ph.length, i = Math.floor(k), f = k - i;
    const A = VIS[ph[i]], B = VIS[ph[Math.min(ph.length - 1, i + 1)]], r = {}; for (const key of new Set([...Object.keys(A), ...Object.keys(B)])) r[key] = lerp(A[key] || 0, B[key] || 0, ss(0.55, 1, f)); return r; }
  return {};
}
const lips = (f, T) => { const m = mouthAt(T), e = Math.min(1, env(T) * 1.6), r = { ...f.raw }; for (const k in m) r[k] = Math.max(r[k] || 0, m[k] * (0.4 + 0.6 * e)); r.MouthSmileLeft = (r.MouthSmileLeft || 0) * (1 - 0.35 * e); r.MouthSmileRight = (r.MouthSmileRight || 0) * (1 - 0.35 * e); return { maxM: f.maxM || 1, raw: r }; };
const _hw = new THREE.Vector3(), _pw = new THREE.Vector3();
const frameOf = (yaw) => ({ f: V(Math.sin(yaw), 0, Math.cos(yaw)), r: V(-Math.cos(yaw), 0, Math.sin(yaw)) });
const boneW = (H, k) => H.bones[H.B[k]].getWorldPosition(new THREE.Vector3());
const bn = (H, n) => H.bones[n].getWorldPosition(new THREE.Vector3());
function palm(H, s) {   // centre de la paume, direction des doigts, normale de la paume (s : 'L' ou 'R')
  const h = bn(H, `Bip01_${s}_Hand`), f2 = bn(H, `Bip01_${s}_Finger2`), f1 = bn(H, `Bip01_${s}_Finger1`), f4 = bn(H, `Bip01_${s}_Finger4`);
  const fd = f2.clone().sub(h).normalize(), ac = f1.clone().sub(f4).normalize(); return { c: h.clone().lerp(f2, 0.55), fd, n: new THREE.Vector3().crossVectors(fd, ac).normalize(), h };
}
function palmIn(H, s) {   // normale tournée côté paume (vers le pouce) : là où se pose un objet tenu
  const P = palm(H, s), th = bn(H, `Bip01_${s}_Finger0`); if (P.n.dot(th.clone().sub(P.c)) < 0) P.n.negate(); return P;
}
const yawTo = (a, b) => Math.atan2(b.x - a.x, b.z - a.z);

// ---------- chronologie (voix v2, words.json) ----------
const KS = V(0.24, 0, 1.95), FS = V(-0.14, 0, 1.95);        // le câlin : le fils regarde vers -x, le père vers +x (dos à la fenêtre)
const K2 = V(0.44, 0, 1.95), F2 = V(-0.2, 0, 1.95);          // après le câlin : un pas d'écart
const END = 38.25;
const KNOCKS = [21.25, 21.75, 22.5];                          // trois coups dans la cave, lents
function heroState(T) {
  const s = { pos: KS.clone(), yaw: -Math.PI / 2, layers: IDLEM(T * 0.8), face: WORRY, look: 'papa', phone: 'side', read: 0, vis: true };
  if (T < 2.1) { s.face = { raw: { EyeSquintLeft: 0.2, EyeSquintRight: 0.2, MouthSmileLeft: 0.2, MouthSmileRight: 0.2 } }; s.look = null; return s; }
  if (T < 10.55) { s.phone = 'read'; s.read = ss(2.15, 2.75, T); s.face = T < 3.7 ? WORRY : T < 7.0 ? FEAR : SHOCK; s.look = 'phone'; return s; }
  s.phone = 'read'; s.read = 1 - ss(10.6, 11.2, T);
  const u = ss(10.6, 11.4, T); s.pos = KS.clone().lerp(K2, u); if (u > 0 && u < 1) s.layers = CLIP('slowwalk', -T * 0.8); s.face = FEAR;
  if (inR(T, 12.3, 16.6)) { s.face = T < 14.9 ? WORRY : mix(WORRY, WARM, 0.35); s.look = 'papa'; s.eyeX = 0.08 * Math.sin(T * 2.1); }
  if (inR(T, 16.6, 19.7)) { s.look = 'watch'; s.face = FEAR; }
  if (inR(T, 19.7, 23.5)) { s.look = 'floor'; s.face = SHOCK; }
  if (inR(T, 23.5, 25.1)) { s.look = 'papa'; s.face = FEAR; }
  if (inR(T, 25.1, 29.0)) { s.read = ss(25.2, 25.8, T) * (1 - ss(28.6, 29.1, T)); s.look = T < 28.7 ? 'phone' : 'papa'; s.face = T < 26.7 ? WORRY : FEAR; }
  if (inR(T, 29.0, 31.9)) { s.look = 'keys'; s.face = SHOCK; }
  if (T >= 31.9) { s.look = 'papa'; s.face = FEAR; s.eyeX = 0.12 * Math.sin(T * 2.6); }
  return s;
}
function papaState(T) {
  const s = { pos: FS.clone(), yaw: Math.PI / 2, layers: [{ ...IDLEM(4 + T * 0.4)[0], w: { legs: 1, root: 1, pelvis: 0.1, spineAbs: 0.1, arms: 0.35 } }], face: WARM, look: 'hero', hug: 0, mug: 'table', pocket: true, tilt: 0.05, vis: true };
  if (T < 10.55) { s.hug = 1; s.pocket = false; s.face = T < 7.0 ? WARM : mix(WARM, GRIN, ss(7.3, 8.6, T)); s.look = T < 7.0 ? null : 'cam'; return s; }
  s.hug = 1 - ss(10.6, 11.0, T); s.pocket = T > 10.9;
  const u = ss(10.6, 11.3, T); s.pos = FS.clone().lerp(F2, u);
  if (inR(T, 11.6, 12.7)) s.face = mix(WARM, GRIN, 0.35);
  if (inR(T, 12.7, 13.8)) { s.face = lips(WARM, T); s.layers = TALKING(T, ss(12.65, 12.85, T) * (1 - ss(13.6, 13.8, T))); }
  if (inR(T, 16.6, 20.4)) {   // il prend sa tasse sur la table (main droite, la montre se voit), la repose
    s.mug = 'hand'; s.drink = 0; s.reach = 1 - ss(16.6, 17.1, T) + ss(19.5, 20.2, T);
    if (T < 17.1 || T > 20.2) s.mug = 'table';
  }
  if (inR(T, 19.7, 23.5)) { s.face = mix(WARM, GRIN, 0.25); s.look = 'hero'; }
  if (inR(T, 23.5, 24.75)) { s.face = lips(mix(WARM, GRIN, 0.55), T); s.look = 'hero'; }
  if (inR(T, 24.75, 31.9)) { s.face = mix(WARM, GRIN, 0.45); s.look = 'hero'; }
  if (T >= 31.9) { s.face = mix(WARM, GRIN, ss(32.0, 33.2, T)); s.tilt = 0.05 + 0.1 * ss(32.5, 34.0, T); s.look = T > 36.6 ? 'cam' : 'hero'; }
  return s;
}

// ---------- caméra : continue dans chaque lieu ; on coupe seulement quand on change de lieu ----------
const FOC = {
  hero: () => _hw.clone(), papa: () => _pw.clone(), mid: () => _hw.clone().lerp(_pw, 0.5), phone: () => phone.position.clone(), watch: () => watch.position.clone(),
  door: () => V(SX, -1.55, DZ + 0.05), keys: () => keys.position.clone(), floor: () => V(0.1, 0.05, 1.95), mug: () => mug.position.clone(),
};
const CAM = [
  // A — l'accroche : le câlin, le téléphone vibre, le message, puis le visage du père par-dessus l'épaule
  { t: 0.0, f: 'mid', az: 20, el: 6, d: 1.5, fov: 40 },
  { t: 2.0, f: 'mid', az: 45, el: 6, d: 1.3, fov: 38 },
  { t: 3.3, f: 'phone', az: 62, el: 22, d: 0.62, fov: 36, lk: 'phone' },
  { t: 6.6, f: 'phone', az: 70, el: 20, d: 0.5, fov: 32, lk: 'phone' },
  { t: 7.1, f: 'papa', az: 105, el: 3, d: 0.72, fov: 34 },
  { t: 10.4, f: 'papa', az: 92, el: 1, d: 0.48, fov: 28 },
  // B — il le lâche, sourit, « Was ist los, Kumpel? » ; le visage du fils
  { t: 10.45, cut: 1, f: 'mid', az: 30, el: 8, d: 1.8, fov: 40 },
  { t: 12.4, f: 'papa', az: 75, el: 3, d: 0.85, fov: 34 },
  { t: 14.0, f: 'papa', az: 88, el: 2, d: 0.6, fov: 30 },
  { t: 14.9, p: () => V(-0.52, 1.72, 2.27), l: () => FOC.hero(), fov: 32 },
  { t: 16.5, p: () => V(-0.5, 1.7, 2.2), l: () => FOC.hero(), fov: 29 },
  // C — la montre au mauvais poignet (il prend sa tasse)
  { t: 16.9, f: 'watch', az: 55, el: 22, d: 0.6, fov: 34 },
  { t: 19.5, f: 'watch', az: 45, el: 18, d: 0.45, fov: 30 },
  // D — « Unter deinen Füßen » : au ras du sol
  { t: 19.8, f: 'floor', az: 320, el: 38, d: 1.25, fov: 46 },
  { t: 21.15, f: 'floor', az: 340, el: 30, d: 1.1, fov: 44 },
  // E — les trois coups : la porte de la cave, en bas de l'escalier
  { t: 21.2, cut: 1, p: () => V(SX + 0.2, 0.1, -1.2), l: () => FOC.door(), fov: 46 },
  { t: 23.48, p: () => V(SX + 0.1, -0.4, -1.8), l: () => FOC.door(), fov: 40 },
  // F — « Das ist nur die Heizung. » ; 2e message ; la poche qui tinte ; la question
  { t: 23.52, cut: 1, f: 'papa', az: 80, el: 3, d: 0.75, fov: 34 },
  { t: 25.0, f: 'papa', az: 90, el: 2, d: 0.6, fov: 30 },
  { t: 25.2, f: 'phone', az: 70, el: 30, d: 0.5, fov: 38, lk: 'phone' },
  { t: 28.6, f: 'phone', az: 82, el: 26, d: 0.4, fov: 34, lk: 'phone' },
  { t: 29.0, f: 'keys', az: 45, el: 12, d: 0.6, fov: 36 },
  { t: 31.6, f: 'keys', az: 25, el: 8, d: 0.45, fov: 32 },
  { t: 32.0, f: 'papa', az: 95, el: 2, d: 0.78, fov: 34 },
  { t: 34.0, f: 'mid', az: 12, el: 8, d: 1.9, fov: 40 },
  { t: 36.7, f: 'papa', az: 62, el: 3, d: 0.55, fov: 30 },
  { t: 38.25, f: 'papa', az: 66, el: 2, d: 0.5, fov: 28 },
];
const DEG = Math.PI / 180;
function keyVec(k) {
  if (k.p) { const F = k.p(), L = k.l(); return [F.x, F.y, F.z, 0, 0, 0, L.x, L.y, L.z, k.fov]; }
  const F = FOC[k.f](), L = k.lk ? FOC[k.lk]() : F.clone(); return [F.x, F.y, F.z, k.az, k.el, k.d, L.x, L.y, L.z, k.fov];
}
// lieux : la caméra ne sort jamais de la pièce où elle est
const ROOM = (T) => (inR(T, 21.2, 23.52) ? 'stairs' : 'kitchen');
function clampCam(p, T) {
  if (ROOM(T) === 'kitchen') { p.x = Math.max(-KW + 0.25, Math.min(KW - 0.2, p.x)); p.z = Math.max(0.25, Math.min(KD - 0.75, p.z)); p.y = Math.max(0.12, Math.min(KH - 0.15, p.y)); }
  else { p.x = Math.max(SX - 0.38, Math.min(SX + 0.38, p.x)); p.z = Math.max(DZ + 0.2, Math.min(0.6, p.z)); p.y = Math.min(2.4, p.y); }
  return p;
}
function camAt(T) {
  let i = 0; while (i < CAM.length - 1 && CAM[i + 1].t <= T) i++;
  let s0 = i; while (s0 > 0 && !CAM[s0].cut) s0--;
  let s1 = i; while (s1 < CAM.length - 1 && !CAM[s1 + 1].cut) s1++;
  const ids = [Math.max(s0, i - 1), i, Math.min(s1, i + 1), Math.min(s1, i + 2)];
  const Vs = ids.map(j => keyVec(CAM[j]));
  const ty = (k) => (k.p ? 'p' : 'o');
  if (ty(CAM[ids[0]]) !== ty(CAM[ids[1]]) || (CAM[ids[1]].p && CAM[ids[2]].p)) Vs[0] = Vs[1];
  if (ty(CAM[ids[3]]) !== ty(CAM[ids[2]]) || (CAM[ids[1]].p && CAM[ids[2]].p)) Vs[3] = Vs[2];
  for (let j = 1; j < 4; j++) { while (Vs[j][3] - Vs[j - 1][3] > 180) Vs[j][3] -= 360; while (Vs[j][3] - Vs[j - 1][3] < -180) Vs[j][3] += 360; }
  const t0 = CAM[ids[1]].t, t1 = CAM[ids[2]].t; const u = ids[2] === ids[1] ? 0 : Math.min(1, Math.max(0, (T - t0) / (t1 - t0)));
  const cr = (a, b, c, d) => 0.5 * ((2 * b) + (-a + c) * u + (2 * a - 5 * b + 4 * c - d) * u * u + (-a + 3 * b - 3 * c + d) * u * u * u);
  const v = Vs[0].map((_, j) => cr(Vs[0][j], Vs[1][j], Vs[2][j], Vs[3][j]));
  const az = v[3] * DEG, el = v[4] * DEG, d = Math.max(0, v[5]);
  return { pos: clampCam(V(v[0] + Math.sin(az) * Math.cos(el) * d, v[1] + Math.sin(el) * d, v[2] + Math.cos(az) * Math.cos(el) * d), T), tgt: V(v[6], v[7], v[8]), fov: v[9] };
}

function frame(T) {
  const c = camAt(T);
  const ps = papaState(T), h = heroState(T);
  HERO.root.position.copy(h.pos); HERO.root.rotation.y = h.yaw;
  PAPA.root.position.copy(ps.pos); PAPA.root.rotation.y = ps.yaw; PAPA.root.updateMatrixWorld(true); PAPA.headWorld(_pw);
  const hf = frameOf(h.yaw), pf = frameOf(ps.yaw);
  const lookPt = (k, who) => k === 'papa' ? _pw.clone() : k === 'hero' ? _hw.clone() : k === 'phone' ? phone.position.clone() : k === 'watch' ? watch.position.clone() : k === 'floor' ? V(h.pos.x, 0, h.pos.z).addScaledVector(hf.f, 0.4)
    : k === 'door' ? V(SX + 0.1, -1.4, DZ) : k === 'keys' ? keys.position.clone() : k === 'cam' ? camera.position.clone() : null;
  // --- le fils
  const pose = { mo: h.layers, lookW: 0.85 };
  HERO.setPose(pose, { ...h.face, eyeX: h.eyeX || 0 }, lookPt(h.look), T); HERO.headWorld(_hw);
  if (h.phone === 'read' || h.phone === 'low' || h.phone === 'side') {   // main GAUCHE : le long du corps -> devant le visage (par-dessus l'épaule du père pendant le câlin)
    const low = h.pos.clone().addScaledVector(hf.f, 0.06).addScaledVector(hf.r, -0.22).add(V(0, 0.8, 0));
    const up = T < 12 ? FS.clone().add(V(0.04, 1.4, 0)).addScaledVector(hf.r, -0.3) : _hw.clone().addScaledVector(hf.f, 0.3).addScaledVector(hf.r, -0.06).add(V(0, -0.14, 0));   // pendant le câlin : à côté de l'épaule du père ; après : devant son visage
    const k = h.phone === 'read' ? h.read : 0; const w = low.lerp(up, k).addScaledVector(hf.f, 0.06 * Math.sin(k * Math.PI));
    Object.assign(pose, { lW: 1, lwx: w.x, lwy: w.y, lwz: w.z, lCurl: 0.75 });
  }
  if (false && h.handle) { const kb = FOC.knob().add(V(-0.02, 0.0, 0.07 + 0.01 * Math.sin(T * 40))); Object.assign(pose, { rW: 1, rwx: kb.x, rwy: kb.y + 0.01 * Math.sin(T * 31), rwz: kb.z, rCurl: 0.85 }); }
  if (h.lean) Object.assign(pose, { spineX: 0.18, headX: 0.1 });
  HERO.setPose(pose, { ...h.face, eyeX: h.eyeX || 0 }, lookPt(h.look), T); HERO.headWorld(_hw);
  HERO.root.visible = h.vis && camera.position.distanceTo(_hw) > 0.22;
  phone.visible = h.vis && h.phone !== 'none';
  if (phone.visible) {   // téléphone dans la paume gauche, écran vers son visage
    const P = palm(HERO, 'L'); let n = P.n.clone(); if (n.dot(_hw.clone().sub(P.c)) < 0) n.negate();
    let yv = P.fd.clone().addScaledVector(n, -P.fd.dot(n)).normalize();
    if (T > 12 && h.read > 0.3) { n = _hw.clone().sub(P.c).normalize(); yv = V(0, 1, 0).addScaledVector(n, -n.y).normalize(); }   // 2e lecture : l'écran face à ses yeux
    const xv = new THREE.Vector3().crossVectors(yv, n);
    const buzz = inR(T, 2.08, 3.3) ? 0.004 * Math.sin(T * 160) : 0;
    phone.position.copy(P.c).addScaledVector(n, 0.017).addScaledVector(xv, buzz); phone.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(xv, yv, n));
    if (T > 12 && h.read > 0.3) phone.position.addScaledVector(yv, 0.075).addScaledVector(n, 0.012);   // la main tient le bas du téléphone : on lit tout le message
    const buzz2 = inR(T, 25.16, 26.0) ? 0.004 * Math.sin(T * 160) : 0; phone.position.addScaledVector(xv, buzz2);
    drawScreen(T < 2.08 ? 'off' : T < 3.0 ? 'empty' : T < 26.6 ? 'msg' : 'msg2'); phoneL.position.copy(phone.position).addScaledVector(n, 0.1); phoneL.intensity = 0;
  } else phoneL.intensity = 0;
  // --- le père
  PAPA.root.visible = ps.vis;
  const pose2 = { mo: ps.layers, lookW: 1, headZ: ps.tilt || 0 };
  if (ps.hug > 0) {   // mains POSÉES sur le dos du fils
    const back = h.pos.clone().add(V(0, 1.12, 0)).addScaledVector(hf.f, -0.15);
    const r = back.clone().addScaledVector(hf.r, -0.1).add(V(0, 0.07, 0)), l = back.clone().addScaledVector(hf.r, 0.12).add(V(0, -0.07, 0));
    Object.assign(pose2, { rW: ps.hug, rwx: r.x, rwy: r.y, rwz: r.z, rCurl: 0.25, lW: ps.hug, lwx: l.x, lwy: l.y, lwz: l.z, lCurl: 0.25, spineX: 0.07 });
  }
  if (ps.mug === 'hand') {   // main DROITE : prend la tasse sur la table, la porte à la bouche
    const dr = ps.drink || 0, re = ps.reach || 0;
    const mouth = _pw.clone().addScaledVector(pf.f, 0.13).add(V(0, -0.11, 0)).addScaledVector(pf.r, 0.02);
    const chest = ps.pos.clone().add(V(0, 1.12, 0)).addScaledVector(pf.f, 0.25).addScaledVector(pf.r, 0.12);
    const table = MUG0.clone().add(V(0, 0.04, 0)).addScaledVector(pf.r, 0.06);
    const w = chest.clone().lerp(mouth, dr).lerp(table, re);
    Object.assign(pose2, { rW: 1, rwx: w.x, rwy: w.y, rwz: w.z, rCurl: 0.8 });
  }
  if (ps.shoulder > 0) { const s_ = _hw.clone().add(V(0, -0.2, 0)).addScaledVector(hf.r, 0.16).addScaledVector(hf.f, -0.02); Object.assign(pose2, { lW: ps.shoulder, lwx: s_.x, lwy: s_.y + 0.04, lwz: s_.z, lCurl: 0.45 }); }
  if (false && ps.keys) { const kl = ps.keyLift || 0; const w = ps.pos.clone().add(V(0, lerp(0.95, 1.5, kl), 0)).addScaledVector(pf.f, lerp(0.15, 0.3, kl)).addScaledVector(pf.r, lerp(0.18, 0.3, kl)); Object.assign(pose2, { rW: 1, rwx: w.x, rwy: w.y, rwz: w.z, rCurl: 0.9 }); }
  PAPA.setPose(pose2, ps.face, lookPt(ps.look), T); PAPA.headWorld(_pw);
  // tasse : sur la table, ou dans la paume droite
  if (ps.mug === 'hand') { const P = palmIn(PAPA, 'R'); mug.position.copy(P.c).addScaledVector(P.n, 0.05).add(V(0, -0.02, 0)); mug.rotation.set(0, ps.yaw + Math.PI, 0); }
  else { mug.position.copy(MUG0); mug.rotation.set(0, 0.6, 0); }
  // montre au poignet DROIT
  { const fo = boneW(PAPA, 'rFore'), hd = boneW(PAPA, 'rHand'); const dir = hd.clone().sub(fo).normalize(); watch.position.copy(fo.clone().lerp(hd, 0.93));
    const P = palmIn(PAPA, 'R'); let up = P.n.clone().negate(); up.addScaledVector(dir, -up.dot(dir)).normalize(); const x = new THREE.Vector3().crossVectors(up, dir).normalize();
    watch.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(x, up, dir)); watch.position.addScaledVector(up, 0.024); watch.visible = ps.vis; }
  keys.visible = !!ps.pocket && ps.vis;   // trousseau qui dépasse de la poche droite du pantalon ; il tinte quand on le regarde
  if (keys.visible) { const th = boneW(PAPA, 'rThigh'), ca = boneW(PAPA, 'rCalf'), pv = boneW(PAPA, 'pelvis'); const out = th.clone().sub(pv); out.y = 0; out.normalize();
    keys.scale.setScalar(1.7); keys.position.copy(th.clone().lerp(ca, 0.2)).addScaledVector(out, 0.085).addScaledVector(pf.f, 0.05);
    const jig = inR(T, 29.6, 31.7) ? 1 : 0.15; keys.rotation.set(0.35 * jig * Math.sin(T * 9.3), ps.yaw + Math.PI / 2, 0.4 * jig * Math.sin(T * 7.1)); }
  // porte de la cave : elle tremble aux coups ; lumière sous la porte (éteinte « für immer » dans la mauvaise fin)
  let sh = 0; for (const k of KNOCKS) if (inR(T, k, k + 0.18)) sh = Math.sin((T - k) * 90) * (1 - (T - k) / 0.18);
  kHinge.rotation.y = 0.012 * sh; underL.visible = true; bulbL.intensity = 3.5 * (1 - 0.6 * Math.abs(sh));
  // caméra (légère main portée, plus forte quand il court / descend)
  let shake = 0.004; for (const k of KNOCKS) if (inR(T, k, k + 0.25)) shake = 0.012;
  camera.position.copy(c.pos).add(V(Math.sin(T * 7.1) * shake, Math.sin(T * 9.3) * shake + (shake > 0.01 ? Math.abs(Math.sin(T * 9.6)) * 0.02 : 0), Math.sin(T * 5.7) * shake));
  clampCam(camera.position, T);
  camera.up.set(0, 1, 0); camera.lookAt(c.tgt); camera.fov = c.fov;
  if (PAPA.root.visible) PAPA.root.visible = camera.position.distanceTo(_pw) > 0.22;
  fillL.position.copy(camera.position).add(V(0, 0.2, 0)); fillL.target.position.copy(c.tgt); fillL.intensity = 1.0 * Math.max(1, (camera.position.distanceTo(c.tgt) / 1.1) ** 2);
  const w2 = innerWidth, h2 = innerHeight;
  if (canvas.width !== w2) renderer.setSize(w2, h2, false);
  camera.aspect = w2 / h2; camera.updateProjectionMatrix();
  renderer.render(scene, camera);
}
window.renderAt = (T) => frame(T);
window.dbg = (T) => { frame(T); const r = (v) => [v.x, v.y, v.z].map(x => +x.toFixed(2)); return { cam: r(camera.position), hero: r(_hw), papa: r(_pw), phone: r(phone.position), mug: r(mug.position), watch: r(watch.position) }; };
window.READY = true;
if (!MANUAL) { const c0 = performance.now(); const loop = () => { frame(((performance.now() - c0) / 1000) % END); requestAnimationFrame(loop); }; loop(); }
else frame(0);
window.dbg2 = (T) => { frame(T); const r = (v) => [v.x, v.y, v.z].map(x => +x.toFixed(2)); return { hero: r(_hw), papa: r(_pw), hL: r(boneW(HERO, 'lHand')), hR: r(boneW(HERO, 'rHand')), pL: r(boneW(PAPA, 'lHand')), pR: r(boneW(PAPA, 'rHand')), cam: r(camera.position) }; };
