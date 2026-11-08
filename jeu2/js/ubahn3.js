// « Die letzte U-Bahn – Teil 3 » : histoire d'horreur au « tu », quai de métro la nuit, personnage réaliste
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
box(0.3, 4.6, 13, M({ color: '#020203' }), 30, 2.1, 0.8, scene, false);
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
// ---------- le tunnel (x < -30) : passerelle de service au niveau du quai, voies, lampes, câbles ----------
const tunMat = M({ color: '#2a2b2e', roughness: 0.95 }), conc = M({ color: '#3b3c40', roughness: 1 });
box(0.3, 4.6, 6.3, M({ color: '#1b1c1f' }), -30, 2.1, 4.2, scene, false);          // mur de bout de station, au-dessus de la passerelle
box(0.3, 2.2, 3.6, M({ color: '#1b1c1f' }), -30, 3.3, -2.6, scene, false);         // linteau au-dessus des voies
box(80, 0.3, 1.5, conc, -70, -0.15, 0.6);                                           // passerelle
box(80, 1.2, 0.2, conc, -70, -0.6, -0.1);
box(80, 0.2, 6, M({ color: '#151412' }), -70, -1.3, -3);                            // fond des voies
for (const z of [-1.6, -3.2]) box(80, 0.12, 0.09, M({ color: '#6d6a66', metalness: 0.9, roughness: 0.35 }), -70, -1.12, z, scene, false);
for (let x = -110; x < -30; x += 0.9) box(0.25, 0.08, 2.6, M({ color: '#231e19' }), x, -1.18, -2.4, scene, false);
box(80, 5.2, 0.3, tunMat, -70, 1.4, 1.5);                                            // mur côté passerelle
box(80, 5.2, 0.3, tunMat, -70, 1.4, -5.6);                                           // mur côté opposé
box(80, 0.3, 7.4, tunMat, -70, 3.9, -2.1, scene, false);                             // voûte
for (let x = -108; x < -30; x += 2.5) { const c = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 80, 6), M({ color: '#111' })); }
for (const y of [2.3, 2.45, 2.6]) { const c = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, 80, 6), M({ color: '#0e0e0e', roughness: 0.6 })); c.rotation.z = Math.PI / 2; c.position.set(-70, y, 1.3); scene.add(c); }
const tLamps = [];
for (let x = -36; x > -110; x -= 7) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.14, 0.14), new THREE.MeshBasicMaterial({ color: '#ffcf8a', toneMapped: false })); m.position.set(x, 2.0, 1.32); scene.add(m);
  const l = new THREE.PointLight('#ffb764', 3.2, 6.5, 1.8); l.position.set(x, 1.85, 1.0); scene.add(l); tLamps.push({ m, l, x });
}

// ---------- la rame, arrêtée dans le tunnel ----------
const train = new THREE.Group(); scene.add(train);
const TL = 36, ZN = -1.0, ZF = -3.8, ZC = -2.4;
const body = M({ color: '#b9bec4', metalness: 0.55, roughness: 0.45 }), inner = M({ color: '#5c636b', roughness: 0.7 });
const DOORS_X = [-11.5, -1.2, 7.5], DW = 0.78;
box(TL, 0.55, 2.8, body, 0, -0.33, ZC, train); box(TL, 0.12, 2.8, M({ color: '#1b4e9e' }), 0, -0.5, ZC, train, false);
box(TL, 0.1, 2.76, M({ color: '#2b2d31', roughness: 0.9 }), 0, -0.05, ZC, train); box(TL, 0.14, 2.8, body, 0, 2.38, ZC, train);
box(TL, 0.02, 2.7, inner, 0, 2.3, ZC, train, false);
for (const x of [-TL / 2, TL / 2]) box(0.12, 2.5, 2.8, body, x, 1.1, ZC, train);
const glass = new THREE.MeshPhysicalMaterial({ color: '#9fb4c8', transparent: true, opacity: 0.16, roughness: 0.05, depthWrite: false });
function sideWall(z, gaps) {
  const segs = []; let x = -TL / 2;
  for (const [a, b] of gaps) { segs.push([x, a]); x = b; } segs.push([x, TL / 2]);
  for (const [a, b] of segs) {
    const L = b - a, c = (a + b) / 2; if (L < 0.05) continue;
    box(L, 1.0, 0.08, body, c, 0.45, z, train); box(L, 0.5, 0.08, body, c, 2.11, z, train);
    const g = new THREE.Mesh(new THREE.PlaneGeometry(L, 0.9), glass); g.position.set(c, 1.4, z); train.add(g);
    for (let px = a; px <= b + 0.01; px += Math.max(0.3, L / Math.max(1, Math.round(L / 2.4)))) box(0.12, 0.92, 0.09, body, Math.min(b - 0.06, Math.max(a + 0.06, px)), 1.4, z, train, false);
  }
}
sideWall(ZN, DOORS_X.map(x => [x - DW, x + DW])); sideWall(ZF, []);
const doors = [];
for (const x of DOORS_X) {
  const mk = (dx) => { const g = new THREE.Group(); train.add(g); g.position.set(x + dx, 1.0, ZN + 0.02); const dm = M({ color: '#a7adb4', metalness: 0.6 });
    box(0.78, 1.1, 0.05, dm, 0, -0.45, 0, g, false); box(0.78, 0.2, 0.05, dm, 0, 0.9, 0, g, false);
    for (const sx of [-1, 1]) box(0.14, 0.9, 0.05, dm, sx * 0.32, 0.35, 0, g, false);
    const gl = new THREE.Mesh(new THREE.PlaneGeometry(0.5, 0.9), glass); gl.position.set(0, 0.35, 0); g.add(gl); return g; };
  doors.push({ x, L: mk(-0.39), R: mk(0.39) });
}
const seatM = M({ color: '#24406e', roughness: 0.8 });
for (const [a, b] of [[-TL / 2 + 0.3, DOORS_X[0] - DW - 0.1], [DOORS_X[0] + DW + 0.1, DOORS_X[1] - DW - 0.1], [DOORS_X[1] + DW + 0.1, DOORS_X[2] - DW - 0.1], [DOORS_X[2] + DW + 0.1, TL / 2 - 0.3]])
  for (const z of [ZN - 0.32, ZF + 0.32]) { box(b - a, 0.12, 0.48, seatM, (a + b) / 2, 0.46, z, train); box(b - a, 0.5, 0.1, seatM, (a + b) / 2, 0.75, z + (z > ZC ? 0.22 : -0.22), train, false); box(b - a, 0.42, 0.4, inner, (a + b) / 2, 0.2, z, train, false); }
const poleM = M({ color: '#c9ccd0', metalness: 0.9, roughness: 0.25 });
for (let x = -TL / 2 + 2; x < TL / 2 - 1; x += 3.4) { const p = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 2.3, 10), poleM); p.position.set(x, 1.15, ZC + 0.35); train.add(p); }
for (const z of [ZN - 0.55, ZF + 0.55]) { const r = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, TL - 1, 8), poleM); r.rotation.z = Math.PI / 2; r.position.set(0, 1.98, z); train.add(r); }
const strips = [];
for (const z of [ZC + 0.45, ZC - 0.45]) { const mat = new THREE.MeshStandardMaterial({ color: '#cfe3ff', emissive: '#9fc3ff', emissiveIntensity: 0.4 }); box(TL - 2, 0.04, 0.12, mat, 0, 2.27, z, train, false); strips.push(mat); }
const redL = []; for (let x = -12; x <= 12; x += 6) { const l = new THREE.PointLight('#ff1a12', 0, 8, 1.6); l.position.set(x, 2.0, ZC); train.add(l); redL.push(l); }
const redOut = new THREE.PointLight('#ff1a12', 0, 9, 1.6); scene.add(redOut);
// frein d'urgence à côté de la porte avant
const nbTex = canvasTex(256, 256, (g, w, h) => { g.fillStyle = '#ffd400'; g.fillRect(0, 0, w, h); g.fillStyle = '#111'; for (let i = -w; i < w; i += 40) { g.beginPath(); g.moveTo(i, 0); g.lineTo(i + 20, 0); g.lineTo(i + 20 + h, h); g.lineTo(i + h, h); g.fill(); }
  g.fillStyle = '#ffd400'; g.fillRect(20, 90, w - 40, 76); g.fillStyle = '#c40000'; g.font = 'bold 46px Arial'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText('NOTBREMSE', w / 2, 129); });
const DX = DOORS_X[2];
const NB = new THREE.Group(); train.add(NB); NB.position.set(DX + DW + 0.3, 1.55, ZN - 0.06);
const nbP = new THREE.Mesh(new THREE.PlaneGeometry(0.3, 0.3), new THREE.MeshStandardMaterial({ map: nbTex, emissive: '#ffffff', emissiveMap: nbTex, emissiveIntensity: 0.3 })); nbP.rotation.y = Math.PI; NB.add(nbP);
const handle = new THREE.Group(); NB.add(handle); handle.position.set(0, -0.2, -0.04);
box(0.2, 0.05, 0.05, M({ color: '#d10f0f', roughness: 0.4 }), 0, 0, 0, handle, false);
for (const s of [-1, 1]) box(0.03, 0.08, 0.05, M({ color: '#d10f0f' }), s * 0.085, 0.03, 0.01, handle, false);
// étincelles sous la rame (freinage)
const sparks = []; const spM = new THREE.MeshBasicMaterial({ color: '#ffd27a', toneMapped: false });
for (let i = 0; i < 70; i++) { const m = new THREE.Mesh(new THREE.BoxGeometry(0.015, 0.015, 0.12), spM); scene.add(m); sparks.push(m); }

// ---------- personnages ----------
await RealHuman.loadClips(['idle', 'walk', 'run', 'sprint', 'duck', 'getup', 'stumble', 'backaway'], './mocap/');
const HERO = await RealHuman.create('./models/g_Male_Adult_04.glb', { heightM: 1.8, seed: 1 });
const TWIN = await RealHuman.create('./models/g_Male_Adult_04.glb', { heightM: 1.8, seed: 5 });
for (const H of [HERO, TWIN]) { scene.add(H.root); H.root.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } }); }
const SHADOW = await RealHuman.create('./models/g_Male_Adult_09.glb', { heightM: 1.85, seed: 3 });
SHADOW.root.traverse(o => { if (o.isMesh) { o.material = new THREE.MeshBasicMaterial({ color: '#000000' }); o.castShadow = false; } }); scene.add(SHADOW.root);
const glowM = new THREE.MeshBasicMaterial({ color: '#eef4ff', toneMapped: false });
const eyes = []; for (const s of [-1, 1]) { const e = new THREE.Mesh(new THREE.SphereGeometry(0.012, 10, 8), glowM); scene.add(e); eyes.push([e, s]); }
const twinEyes = []; for (const s of [-1, 1]) { const e = new THREE.Mesh(new THREE.SphereGeometry(0.004, 8, 6), glowM); scene.add(e); twinEyes.push([e, s]); }
const underL = new THREE.SpotLight('#c9d6ff', 0, 3, 0.5, 0.6, 1.5); scene.add(underL, underL.target);   // lumière par en dessous sur le double

// ---------- chronologie (voix calée) ----------
const ss = (a, b, x) => { const u = Math.min(1, Math.max(0, (x - a) / (b - a))); return u * u * (3 - 2 * u); };
const lerp = (a, b, u) => a + (b - a) * u;
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const FULL = { pelvis: 1, spineAbs: 1, legs: 1, arms: 1, root: 1, headAbs: 0.5 };
const IDLEW = { legs: 1, root: 1, pelvis: 0.5, spineAbs: 0.5, arms: 1 };
const dur = (c) => RealHuman.clips[c].frames / RealHuman.clips[c].fps;
const loopT = (c, x) => ((x % dur(c)) + dur(c)) % dur(c);
const HIP = 0.95;   // m par « hauteur de hanche » (vitesse des clips → m/s)
const K = { ziehst: 1.35, bahn: 2.85, fliegst: 5.59, rotes: 6.34, alarm: 7.37, tueren: 8.18, aber: 9.74, sondern: 11.44, rennst: 12.89, hinter: 13.75, schneller: 15.48,
  vorne: 16.82, eine: 18.18, schild: 19.21, schon: 21.18, auf: 22.15, er_traegt: 25.13, dreht: 26.49, und: 27.58, gesicht: 28.29, laechelt: 28.99, jetzt: 30.34, also: 31.62,
  eins: 33.25, zwei: 35.72, schreib: 37.56, end: 41.6 };
const TX = -54.5, DOORW = TX + DX;                // porte avant, dans le tunnel
const RUN_SPEED = RealHuman.clips.sprint.speed * HIP;   // m/s réels de la course capturée
const RUN0 = K.rennst - 0.1, RUN1 = K.schild;           // il court de la porte jusqu'à la station
const PLAT = V(-14, 0, 2.0), TWINP = V(-4.5, 0, 2.6);
let camPos = V(0, 1.6, 4), camTgt = V(0, 1.2, 0), lastShot = -1;
const _hw = new THREE.Vector3(), _tw = new THREE.Vector3(), _sw = new THREE.Vector3();

function heroState(T) {
  const s = { pos: V(DOORW + 0.39, 0, -2.0), yaw: 0, layers: null, face: {}, look: null, hand: 0, vis: true };
  const idle = (t) => [{ clip: 'idle', mode: 'abs', t: loopT('idle', t), k: 1, w: IDLEW }];
  if (T < K.bahn) {                                    // il tire la poignée
    s.pos = V(DOORW + DW + 0.3 + 0.05, 0, ZN - 0.55); s.yaw = 0; s.layers = idle(T + 2);
    s.hand = ss(0.4, 1.0, T); s.look = V(DOORW + DW + 0.3, 1.4, ZN);
  } else if (T < K.fliegst - 0.1) {                    // projeté vers l'avant (trébuche)
    const u = (T - K.bahn) / (K.fliegst - 0.1 - K.bahn);
    s.pos = V(DOORW + DW + 0.35 - 3.2 * ss(0, 1, u), 0, ZN - 0.7); s.yaw = -Math.PI / 2;
    s.layers = [{ clip: 'stumble', mode: 'abs', t: 0.15 + u * 1.6, k: 1, w: FULL }];
  } else if (T < K.tueren) {                           // au sol puis se relève
    s.pos = V(DOORW - 2.3, 0, ZN - 1.1); s.yaw = -Math.PI / 2 + 0.4;
    s.layers = [{ clip: 'getup', mode: 'abs', t: lerp(0.6, 4.4, ss(K.rotes - 0.3, K.tueren, T)), k: 1, w: FULL }];
  } else if (T < RUN0) {                               // face à la porte ouverte sur le tunnel
    const u = ss(K.tueren, K.sondern, T);
    s.pos = V(DOORW + lerp(-1.6, 0.39, u), 0, lerp(ZN - 1.1, ZN - 0.45, u)); s.yaw = lerp(0.9, 0, u);
    const walking = u > 0 && u < 1; s.layers = walking ? [{ clip: 'walk', mode: 'abs', t: loopT('walk', T), k: 1, w: FULL }] : idle(T);
    s.look = V(DOORW + 0.4, 1.4, 1.5); s.face = {};
  } else if (T < RUN1 + 0.6) {                         // il court dans le tunnel vers la station (+X)
    const t = T - RUN0, x0 = DOORW + 0.39;
    s.pos = V(Math.min(PLAT.x, x0 + RUN_SPEED * t), 0, lerp(ZN + 0.5, 0.7, ss(0, 0.6, t)));
    s.yaw = Math.PI / 2 * ss(0, 0.35, t);
    const stop = ss(RUN1 - 0.2, RUN1 + 0.5, T);
    s.layers = [{ clip: 'sprint', mode: 'abs', t: loopT('sprint', t), k: 1 - stop, w: FULL }, ...idle(T).map(l => ({ ...l, k: stop }))];
    if (s.pos.x >= PLAT.x - 0.01) s.pos.x = PLAT.x;
    // regarde derrière lui par moments
    s.look = T > K.hinter && T < K.schneller + 1.0 && Math.sin(T * 2.2) > 0.3 ? V(s.pos.x - 6, 1.6, 0.8) : null;
  } else if (T < K.dreht) {                            // sur le quai, il voit le double
    s.pos = PLAT.clone().add(V(0, 0, 0.6)); s.yaw = Math.PI / 2 + 0.15; s.layers = idle(T); s.look = T > K.auf - 0.3 ? TWINP.clone().add(V(0, 1.6, 0)) : V(-1.2, 2.85, 6.99);
  } else if (T < K.eins) {                             // recule doucement (peur)
    const u = ss(K.gesicht, K.gesicht + 1.6, T);
    s.pos = PLAT.clone().add(V(-0.9 * u, 0, 0.6)); s.yaw = Math.PI / 2 + 0.15;
    s.layers = u > 0 && u < 1 ? [{ clip: 'backaway', mode: 'abs', t: loopT('backaway', T), k: 1, w: FULL }] : idle(T);
    if (u > 0 && u < 1) s.yaw += Math.PI;   // le clip « recul » est orienté dans le sens du déplacement
    s.look = TWINP.clone().add(V(0, 1.65, 0));
  } else {
    s.pos = PLAT.clone().add(V(-0.9, 0, 0.6)); s.yaw = Math.PI / 2 + 0.15; s.layers = idle(T); s.look = T < K.zwei ? V(-40, 1.4, 0.8) : TWINP.clone().add(V(0, 1.65, 0));
  }
  return s;
}
function twinState(T) {
  if (T < K.auf - 0.2) return null;
  const turn = ss(K.dreht, K.und + 0.2, T);
  const p = TWINP.clone(); if (T > K.schreib) p.x -= 1.4 * ss(K.schreib, K.end, T);
  const walking = T > K.schreib;
  return { pos: p, yaw: lerp(Math.PI / 2, -Math.PI / 2, turn) + (turn >= 1 ? 0.15 : 0), layers: walking ? [{ clip: 'walk', mode: 'abs', t: loopT('walk', T * 0.6), k: 1, w: FULL }] : [{ clip: 'idle', mode: 'abs', t: loopT('idle', T + 7), k: 1, w: { legs: 1, root: 1, pelvis: 0.2, spineAbs: 0.2, arms: 1 } }] };
}
function chaserState(T) {                              // la silhouette qui le poursuit dans le tunnel
  if (T < K.hinter - 0.3 || T > K.vorne + 0.5) return null;
  const t = T - (K.hinter - 0.3), x = DOORW - 8 + RUN_SPEED * 1.15 * t;
  return { pos: V(x, 0, 0.7), yaw: Math.PI / 2, t };
}

function shot(T) {
  const H = _hw;
  if (T < 0.45) return [H.clone().add(V(-0.1, -0.02, 0.3)), H.clone(), 36];                         // gros plan visage rouge : accroche
  if (T < K.bahn) { const n = NB.getWorldPosition(new THREE.Vector3()); return [n.clone().add(V(-0.25, 0.02, -0.45)), n.clone().add(V(0, -0.15, 0)), 42]; }   // la main tire la poignée
  if (T < K.fliegst - 0.1) { const p = HERO.root.position; return [V(p.x - 3.2, 1.35, ZN - 0.6), V(p.x, 1.0, ZN - 0.7), 50]; }   // il est projeté
  if (T < K.rotes) return [V(DOORW - 2.0, 2.05, ZN - 0.6), V(DOORW - 2.4, 0.15, ZN - 1.4), 62];      // au sol
  if (T < K.tueren) { const u = ss(K.rotes, K.tueren, T); return [V(DOORW - 3.8, lerp(0.8, 1.5, u), ZN - 0.4), V(DOORW - 2.3, lerp(0.4, 1.3, u), ZN - 1.1), 48]; }
  if (T < K.aber) return [V(DOORW - 3.4, 1.55, ZC - 0.3), V(DOORW + 0.2, 1.15, ZN), 50];                     // les portes s'ouvrent
  if (T < K.sondern) return [V(DOORW + 0.2, 1.6, ZN - 0.3), V(DOORW + 3, 1.25, 1.4), 54];                // vue subjective : le tunnel
  if (T < RUN0) return [V(DOORW + 0.6, 1.2, 1.25), H.clone(), 40];                                          // depuis le tunnel : lui dans la porte, rouge
  if (T < K.hinter) { const p = HERO.root.position; return [V(p.x - 2.2, 1.45, 1.05), V(p.x + 1, 1.2, 0.7), 50]; }   // derrière lui, il court
  if (T < K.schneller) { const p = HERO.root.position; return [V(p.x + 0.4, 1.8, 1.25), V(p.x - 10, 1.4, 0.7), 46]; } // regard en arrière : la silhouette
  if (T < K.vorne) { const p = HERO.root.position; return [V(p.x + 2.6, 1.55, 0.95), H.clone().add(V(0, -0.15, 0)), 40]; }   // devant lui, panique
  if (T < K.schild) { const p = HERO.root.position; return [V(p.x - 1.0, 1.5, 0.85), V(p.x + 14, 1.4, 1.5), 52]; }  // la lumière de la station devant
  if (T < K.schon) return [V(-6, 2.6, 3.8), V(-1.2, 2.85, 6.99), 40];                                       // panneau Lindenplatz
  if (T < K.auf) return [H.clone().add(V(0.45, 0.0, 0.3)), H.clone(), 34];                                  // « schon wieder »
  if (T < K.er_traegt) return [V(PLAT.x - 1.2, 1.55, 2.9), TWINP.clone().add(V(0, 1.2, 0)), 42];            // le double, de dos
  if (T < K.dreht) return [_tw.clone().add(V(-0.75, -0.25, 0.05)), _tw.clone().add(V(0, -0.3, 0)), 38];    // sa veste
  if (T < K.gesicht + 0.4) { const u = ss(K.dreht, K.gesicht, T); return [_tw.clone().add(V(lerp(-1.2, -0.62, u), 0.0, 0.08)), _tw.clone(), lerp(40, 30, u)]; }   // il se retourne
  if (T < K.laechelt) return [H.clone().add(V(0.42, 0, 0.2)), H.clone(), 32];                               // réaction : son visage
  if (T < K.also) { const u = ss(K.laechelt, K.also, T); return [_tw.clone().add(V(-lerp(0.55, 0.36, u), -0.06, 0.03)), _tw.clone(), lerp(32, 26, u)]; }   // « Jetzt bin ich dran »
  if (T < K.eins) return [V(PLAT.x - 1.4, 1.78, 3.35), TWINP.clone().add(V(0, 1.45, 0)), 40];                                      // les deux face à face
  if (T < K.zwei) return [V(PLAT.x - 1.2, 1.5, 1.0), V(-40, 1.2, 0.7), 46];                                 // le tunnel noir derrière lui
  if (T < K.schreib) return [H.clone().add(V(-0.7, 0.05, 0.35)), _tw.clone(), 36];                          // par-dessus son épaule : le double
  const u = ss(K.schreib, K.end, T); return [_tw.clone().add(V(-lerp(1.4, 0.5, u), -0.05, 0.02)), _tw.clone(), lerp(40, 30, u)];   // le double s'approche
}
const SHOTS = [0.45, K.bahn, K.fliegst - 0.1, K.rotes, K.tueren, K.aber, K.sondern, RUN0, K.hinter, K.schneller, K.vorne, K.schild, K.schon, K.auf, K.er_traegt, K.dreht, K.gesicht + 0.4, K.laechelt, K.also, K.eins, K.zwei, K.schreib];

function frame(T) {
  // station : lumière normale ; tunnel : lampes jaunes ; alarme rouge qui clignote
  const alarm = T < RUN0 + 2.5 ? (Math.sin(T * 9) > 0 ? 1 : 0.15) : 0;
  tubes.forEach((tb) => { tb.mat.emissiveIntensity = 1.6; tb.l.intensity = 7; });
  key.intensity = 20;
  setBoard('01:13'); gate.position.y = 1.6;
  train.position.x = TX;
  const op = ss(K.tueren, K.tueren + 1.1, T); doors.forEach((d, i) => { const o = i === 2 ? op : 0; d.L.position.x = d.x - 0.39 - o * 0.75; d.R.position.x = d.x + 0.39 + o * 0.75; });
  strips.forEach(m => (m.emissiveIntensity = T < K.bahn ? 0.5 : 0.08));
  redL.forEach(l => (l.intensity = 9 * alarm)); redOut.position.set(DOORW, 1.8, 0.6); redOut.intensity = 6 * alarm * (T > K.tueren ? 1 : 0);
  handle.position.y = -0.2 - 0.12 * ss(0.85, 1.15, T); handle.rotation.x = 0.5 * ss(0.85, 1.15, T);
  // étincelles pendant le freinage
  const brake = T > K.ziehst && T < K.fliegst + 0.4;
  sparks.forEach((m, i) => { m.visible = brake; if (!brake) return; const ph = (T * 7 + i * 0.137) % 1, side = i % 2 ? -1.15 : -3.65;
    m.position.set(TX + (i % 7) * 5 - 15 + ph * 1.2, -0.55 + Math.sin(i) * 0.05 + ph * 0.35, side + (i % 3) * 0.05); m.rotation.set(0, 0.6, ph); });
  tLamps.forEach((L, i) => { const f = T > K.hinter && T < K.vorne && Math.sin(T * 23 + i * 3) > 0.7 ? 0.1 : 1; L.l.intensity = 3.2 * f; L.m.visible = f > 0.5; });
  // héros
  const h = heroState(T); HERO.root.visible = h.vis;
  HERO.root.position.copy(h.pos); HERO.root.rotation.y = h.yaw;
  const pose = { mo: h.layers, lookW: 0.85 };
  if (h.hand > 0) { const n = NB.getWorldPosition(new THREE.Vector3()).add(V(0, -0.2 - 0.12 * ss(0.85, 1.15, T), -0.05)); Object.assign(pose, { rW: h.hand, rwx: n.x, rwy: n.y, rwz: n.z, rCurl: 1.0 }); }
  HERO.setPose(pose, h.face, h.look, T);
  HERO.headWorld(_hw);
  // double
  const tw = twinState(T); TWIN.root.visible = !!tw; twinEyes.forEach(([e]) => (e.visible = false));
  if (tw) { TWIN.root.position.copy(tw.pos); TWIN.root.rotation.y = tw.yaw; TWIN.setPose({ mo: tw.layers, lookW: 0.95 }, {}, T > K.und ? _hw : null, T); TWIN.headWorld(_tw);
    const glint = false; if (glint) { const f = _hw.clone().sub(_tw).setY(0).normalize(), r = V(f.z, 0, -f.x); twinEyes.forEach(([e, s]) => { e.visible = true; e.position.copy(_tw).addScaledVector(r, s * 0.031).addScaledVector(f, 0.085).add(V(0, 0.005, 0)); }); } }
  underL.intensity = tw && T > K.dreht ? 14 : 0; if (tw) { underL.position.copy(_tw).add(V(-0.35, -0.75, 0)); underL.target.position.copy(_tw); }
  // silhouette qui le poursuit
  const ch = chaserState(T); SHADOW.root.visible = !!ch; eyes.forEach(([e]) => (e.visible = !!ch));
  if (ch) { SHADOW.root.position.copy(ch.pos); SHADOW.root.rotation.y = ch.yaw; SHADOW.setPose({ mo: [{ clip: 'run', mode: 'abs', t: loopT('run', ch.t), k: 1, w: FULL }] }, {}, null, T);
    SHADOW.headWorld(_sw); eyes.forEach(([e, s]) => e.position.copy(_sw).add(V(0.08, 0.0, s * 0.035))); }
  // caméra
  const [p, tgt, fov] = shot(T);
  const sid = SHOTS.filter(x => x <= T).length;
  if (sid !== lastShot) { camPos.copy(p); camTgt.copy(tgt); lastShot = sid; } else { camPos.lerp(p, 0.4); camTgt.lerp(tgt, 0.4); }
  const run = T > RUN0 && T < K.schild;
  const shake = T > K.bahn && T < K.rotes ? 0.025 * (1 - ss(K.bahn, K.rotes, T)) + 0.004 : run ? 0.012 : (T > K.dreht && T < K.also ? 0.004 : 0.002);
  camera.position.copy(camPos).add(V(Math.sin(T * 17) * shake, Math.sin(T * 23) * shake + (run ? Math.abs(Math.sin(T * 8.5)) * 0.03 : 0), Math.sin(T * 13) * shake));
  camera.lookAt(camTgt); camera.fov = fov;
  fillL.position.copy(camera.position).add(V(0, 0.25, 0)); fillL.target.position.copy(camTgt); fillL.intensity = run ? 2.2 : 3.2;
  fillL.color.set(alarm > 0.5 ? '#ff6a5a' : '#c9d8f0');
  const w2 = innerWidth, h2 = innerHeight;
  if (canvas.width !== w2) renderer.setSize(w2, h2, false);
  camera.aspect = w2 / h2; camera.updateProjectionMatrix();
  renderer.render(scene, camera);
}
window.renderAt = (T) => frame(T);
window.READY = true;
if (!MANUAL) { const c0 = performance.now(); const loop = () => { frame(((performance.now() - c0) / 1000) % 42); requestAnimationFrame(loop); }; loop(); }
else frame(0);
