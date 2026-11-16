// « Die letzte U-Bahn – Teil 2 » : histoire d'horreur au « tu », quai de métro la nuit, personnage réaliste
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
// la feuille des règles (scotchée au mur, x = -4.2) — partie 2 : une 3e règle apparaît, écrite à la main
let ruleHi = 0, rule3 = 0;
const paper = canvasTex(768, 1024, (g, w, h) => {
  g.fillStyle = '#e9e0c6'; g.fillRect(0, 0, w, h);
  const r2 = (s => () => (s = (s * 16807) % 2147483647) / 2147483647)(11);
  for (let i = 0; i < 900; i++) { g.fillStyle = `rgba(120,95,50,${r2() * 0.06})`; g.fillRect(r2() * w, r2() * h, 6 + r2() * 30, 3 + r2() * 10); }
  g.fillStyle = '#1b1b1b'; g.textAlign = 'center'; g.font = 'bold 74px Arial'; g.fillText('NACHTREGELN', w / 2, 105);
  g.font = 'bold 38px Arial'; g.fillText('NUR FÜR PERSONAL', w / 2, 160); g.fillRect(90, 186, w - 180, 5);
  g.textAlign = 'left';
  const rule = (y, title, lines, col) => {
    g.fillStyle = col; g.font = 'bold 46px Arial'; g.fillText(title, 80, y);
    g.font = '40px Arial'; lines.forEach((l, i) => g.fillText(l, 80, y + 54 + i * 50));
  };
  rule(270, 'REGEL Nr. 1:', ['Kommt um 01:13 eine Bahn', 'ohne Fahrer: NICHT EINSTEIGEN.'], '#1b1b1b');
  rule(470, 'REGEL Nr. 2:', ['Flüstert jemand deinen Namen:', 'dreh dich NIEMALS um.'], '#1b1b1b');
  if (rule3 > 0) {   // écrite au feutre rouge, qui apparaît lettre par lettre
    g.save(); g.beginPath(); g.rect(0, 0, 60 + (w - 60) * Math.min(1, rule3 * 1.5), h); g.rect(0, 0, w, 760 + 230 * Math.max(0, rule3 * 1.5 - 0.6)); g.clip();
    g.translate(30, 0); g.rotate(-0.025);
    g.fillStyle = '#b0120d'; g.font = 'bold 58px "Comic Sans MS", "Marker Felt", cursive'; g.fillText('REGEL Nr. 3:', 60, 700);
    g.font = 'bold 54px "Comic Sans MS", "Marker Felt", cursive'; g.fillText('Wer einsteigt,', 60, 775); g.fillText('steigt nie wieder aus.', 60, 845);
    g.restore();
  }
  g.fillStyle = 'rgba(150,140,110,0.75)'; g.fillRect(260, -10, 250, 70);
});
const paperM = new THREE.Mesh(new THREE.PlaneGeometry(0.6, 0.8), new THREE.MeshStandardMaterial({ map: paper, roughness: 0.9, emissive: '#ffffff', emissiveMap: paper, emissiveIntensity: 0.12 }));
paperM.position.set(-4.2, 1.55, 6.98); paperM.rotation.set(0, Math.PI, 0.03); scene.add(paperM);
const paperLight = new THREE.SpotLight('#ffe9c2', 6, 5, 0.45, 0.7, 1.5); paperLight.position.set(-4.2, 3.6, 5.6); paperLight.target = paperM; scene.add(paperLight);
function setRule3(p) { p = Math.round(p * 40) / 40; if (p !== rule3) { rule3 = p; const u = paper.userData; u.draw(u.g, u.c.width, u.c.height); paper.needsUpdate = true; } }

// ---------- la rame, avec un vrai intérieur (plancher au niveau du quai, y = 0) ----------
const train = new THREE.Group(); scene.add(train);
const TL = 36, ZN = -1.0, ZF = -3.8, ZC = -2.4;
const body = M({ color: '#b9bec4', metalness: 0.55, roughness: 0.45 }), inner = M({ color: '#5c636b', roughness: 0.7 });
const DOORS_X = [-11.5, -1.2, 7.5], DW = 0.78;
box(TL, 0.55, 2.8, body, 0, -0.33, ZC, train);                                       // dessous
box(TL, 0.12, 2.8, M({ color: '#1b4e9e' }), 0, -0.5, ZC, train, false);               // bande bleue
box(TL, 0.1, 2.76, M({ color: '#2b2d31', roughness: 0.9 }), 0, -0.05, ZC, train);    // plancher
box(TL, 0.14, 2.8, body, 0, 2.38, ZC, train);                                        // toit
box(TL, 0.02, 2.7, inner, 0, 2.3, ZC, train, false);                                 // plafond intérieur
for (const x of [-TL / 2, TL / 2]) box(0.12, 2.5, 2.8, body, x, 1.1, ZC, train);      // bouts
const glass = new THREE.MeshPhysicalMaterial({ color: '#9fb4c8', transparent: true, opacity: 0.16, roughness: 0.05, metalness: 0, depthWrite: false });
function sideWall(z, gaps) {
  // panneau bas, haut, montants, vitres ; gaps = ouvertures de portes [x0, x1]
  const segs = []; let x = -TL / 2;
  for (const [a, b] of gaps) { segs.push([x, a]); x = b; } segs.push([x, TL / 2]);
  for (const [a, b] of segs) {
    const L = b - a, c = (a + b) / 2; if (L < 0.05) continue;
    box(L, 1.0, 0.08, body, c, 0.45, z, train); box(L, 0.5, 0.08, body, c, 2.11, z, train);
    const g = new THREE.Mesh(new THREE.PlaneGeometry(L, 0.9), glass); g.position.set(c, 1.4, z); train.add(g);
    for (let px = a; px <= b + 0.01; px += Math.max(0.3, L / Math.max(1, Math.round(L / 2.4)))) box(0.12, 0.92, 0.09, body, Math.min(b - 0.06, Math.max(a + 0.06, px)), 1.4, z, train, false);
  }
}
sideWall(ZN, DOORS_X.map(x => [x - DW, x + DW]));
sideWall(ZF, []);
const doors = [];
for (const x of DOORS_X) {
  const mk = (dx) => { const g = new THREE.Group(); train.add(g); g.position.set(x + dx, 1.0, ZN + 0.02);
    const dm = M({ color: '#a7adb4', metalness: 0.6 });
    box(0.78, 1.1, 0.05, dm, 0, -0.45, 0, g, false); box(0.78, 0.2, 0.05, dm, 0, 0.9, 0, g, false);
    for (const sx of [-1, 1]) box(0.14, 0.9, 0.05, dm, sx * 0.32, 0.35, 0, g, false);
    const gl = new THREE.Mesh(new THREE.PlaneGeometry(0.5, 0.9), glass); gl.position.set(0, 0.35, 0); g.add(gl); return g; };
  doors.push({ x, L: mk(-0.39), R: mk(0.39) });
}
// banquettes, barres, néons de secours
const seatM = M({ color: '#24406e', roughness: 0.8 });
for (const [a, b] of [[-TL / 2 + 0.3, DOORS_X[0] - DW - 0.1], [DOORS_X[0] + DW + 0.1, DOORS_X[1] - DW - 0.1], [DOORS_X[1] + DW + 0.1, DOORS_X[2] - DW - 0.1], [DOORS_X[2] + DW + 0.1, TL / 2 - 0.3]]) {
  for (const z of [ZN - 0.32, ZF + 0.32]) { box(b - a, 0.12, 0.48, seatM, (a + b) / 2, 0.46, z, train); box(b - a, 0.5, 0.1, seatM, (a + b) / 2, 0.75, z + (z > ZC ? 0.22 : -0.22), train, false); box(b - a, 0.42, 0.4, inner, (a + b) / 2, 0.2, z, train, false); }
}
const poleM = M({ color: '#c9ccd0', metalness: 0.9, roughness: 0.25 });
for (let x = -TL / 2 + 2; x < TL / 2 - 1; x += 3.4) { const p = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 2.3, 10), poleM); p.position.set(x, 1.15, ZC + 0.35); train.add(p); }
for (const z of [ZN - 0.55, ZF + 0.55]) { const r = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, TL - 1, 8), poleM); r.rotation.z = Math.PI / 2; r.position.set(0, 1.98, z); train.add(r); }
const strips = [];
for (const z of [ZC + 0.45, ZC - 0.45]) { const mat = new THREE.MeshStandardMaterial({ color: '#cfe3ff', emissive: '#9fc3ff', emissiveIntensity: 0.4 }); box(TL - 2, 0.04, 0.12, mat, 0, 2.27, z, train, false); strips.push(mat); }
const inLights = []; for (let x = -12; x <= 12; x += 6) { const l = new THREE.PointLight('#8fb4ff', 1.2, 7, 1.8); l.position.set(x, 2.0, ZC); train.add(l); inLights.push(l); }
// affichage au-dessus de la porte du héros (vu de l'intérieur)
let dispOn = 0;
const disp = canvasTex(1024, 256, (g, w, h) => {
  g.fillStyle = '#050505'; g.fillRect(0, 0, w, h);
  if (dispOn) { g.fillStyle = '#ff9a1a'; g.font = 'bold 64px "Courier New", monospace'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText('NÄCHSTER HALT:', w / 2, 80); g.font = 'bold 88px "Courier New", monospace'; g.fillText('LINDENPLATZ', w / 2, 180); }
});
const dispG = new THREE.Group(); train.add(dispG); dispG.position.set(DOORS_X[1], 2.13, ZN - 0.09);
box(1.5, 0.4, 0.06, M({ color: '#111' }), 0, 0, 0.02, dispG, false);
const dispP = new THREE.Mesh(new THREE.PlaneGeometry(1.4, 0.35), new THREE.MeshBasicMaterial({ map: disp, toneMapped: false })); dispP.position.z = -0.015; dispP.rotation.y = Math.PI; dispG.add(dispP);
const dispL = new THREE.PointLight('#ff9a3a', 0, 2.5, 2); dispL.position.set(DOORS_X[1], 1.95, ZN - 0.4); train.add(dispL);
function setDisp(on) { on = on ? 1 : 0; if (on !== dispOn) { dispOn = on; const u = disp.userData; u.draw(u.g, u.c.width, u.c.height); disp.needsUpdate = true; } }
// frein d'urgence (à droite de la porte, à l'intérieur)
const nbTex = canvasTex(256, 256, (g, w, h) => { g.fillStyle = '#ffd400'; g.fillRect(0, 0, w, h); g.fillStyle = '#111'; for (let i = -w; i < w; i += 40) { g.beginPath(); g.moveTo(i, 0); g.lineTo(i + 20, 0); g.lineTo(i + 20 + h, h); g.lineTo(i + h, h); g.fill(); }
  g.fillStyle = '#ffd400'; g.fillRect(20, 90, w - 40, 76); g.fillStyle = '#c40000'; g.font = 'bold 46px Arial'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText('NOTBREMSE', w / 2, 129); });
const NB = new THREE.Group(); train.add(NB); NB.position.set(DOORS_X[1] + DW + 0.3, 1.55, ZN - 0.06);
const nbP = new THREE.Mesh(new THREE.PlaneGeometry(0.3, 0.3), new THREE.MeshStandardMaterial({ map: nbTex, emissive: '#ffffff', emissiveMap: nbTex, emissiveIntensity: 0.25 })); nbP.rotation.y = Math.PI; NB.add(nbP);
box(0.2, 0.05, 0.05, M({ color: '#d10f0f', roughness: 0.4 }), 0, -0.2, -0.04, NB, false);
for (const s of [-1, 1]) box(0.03, 0.08, 0.05, M({ color: '#d10f0f' }), s * 0.085, -0.17, -0.03, NB, false);
// lampes du tunnel (les deux côtés, hors de la station)
const tunLamps = [];
const lampM = new THREE.MeshBasicMaterial({ color: '#ffd9a0', toneMapped: false });
for (const sgn of [-1, 1]) for (let x = 36; x < 300; x += 11) for (const z of [0.6, -5.2]) { const m = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.12, 0.12), lampM); m.position.set(sgn * x, 1.5, z); scene.add(m); tunLamps.push(sgn * x); }
const flashL = new THREE.PointLight('#ffd9a0', 0, 5, 1.5); scene.add(flashL);

// ---------- personnages ----------
await RealHuman.loadClips(['idle', 'walk'], './mocap/');
const HERO = await RealHuman.create('./models/' + (Q.get('m') || 'g_Male_Adult_04') + '.glb', { heightM: 1.8, seed: 1 });
scene.add(HERO.root);
HERO.root.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
const SHADOW = await RealHuman.create('./models/g_Male_Adult_09.glb', { heightM: 1.85, seed: 3 });
SHADOW.root.traverse(o => { if (o.isMesh) { o.material = new THREE.MeshBasicMaterial({ color: '#000000' }); o.castShadow = false; } });
scene.add(SHADOW.root);
const glowM = new THREE.MeshBasicMaterial({ color: '#eef4ff', toneMapped: false });
const eyes = []; for (const s of [-1, 1]) { const e = new THREE.Mesh(new THREE.SphereGeometry(0.009, 10, 8), glowM); scene.add(e); eyes.push([e, s]); }
const smile = new THREE.Mesh(new THREE.TorusGeometry(0.036, 0.0035, 6, 24, Math.PI * 0.9), glowM); scene.add(smile);

// ---------- chronologie ----------
const ss = (a, b, x) => { const u = Math.min(1, Math.max(0, (x - a) / (b - a))); return u * u * (3 - 2 * u); };
const lerp = (a, b, u) => a + (b - a) * u;
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const CLIP = { idle: 18, walk: 0.93 };
const loopT = (c, x) => ((x % CLIP[c]) + CLIP[c]) % CLIP[c];
const FULL = { pelvis: 1, spineAbs: 1, legs: 1, arms: 1, root: 1 };
const IDLEW = { legs: 1, root: 1, pelvis: 0.5, spineAbs: 0.5, arms: 1 };
const WALK_SPEED = 0.78;   // m/s qui correspondent à la marche capturée (cycle de 0,93 s) : pas de glissement
const K = { umdrehst: 3.31, du_drehst: 4.29, und: 6.19, ganz: 7.38, laechelt: 8.36, dann: 9.24, licht: 9.94, aus: 10.22, falsche: 10.96, spulen: 11.94,
  diesmal: 13.04, tueren: 14.78, wagen: 16.73, bahn: 17.95, ohne: 19.30, in_: 20.27, dann2: 21.30, leuchtet: 21.46, naechster: 23.15, aber: 24.79,
  haelt: 27.39, bahnsteig: 28.51, zettel: 29.98, nur: 31.20, wer: 33.73, und2: 36.15, also: 38.33, eins: 39.88, zwei: 42.15, schreib: 45.00, end: 49.2 };
const DX = DOORS_X[1], HX = DX + 0.39, HP = V(DX, 0, 1.25), IN_Z = -2.1, WALK0 = V(HX, 0, 0.3);
let camPos = V(0, 1.6, 4), camTgt = V(0, 1.2, 0), lastShot = -1;
const _hw = new THREE.Vector3(), _sw = new THREE.Vector3();

function trainX(T) {
  if (T < K.bahn) return 0;
  if (T < 24.2) { const t = T - K.bahn; return -(0.9 * t * t + Math.max(0, t - 2.5) * 30); }        // démarre puis file dans le tunnel (-X)
  const u = ss(24.2, K.haelt + 0.4, T); return lerp(260, 0, 1 - Math.pow(1 - u, 2.4));              // revient par l'autre tunnel (+X) et s'arrête
}
function doorsOpen(T) { return T < K.tueren ? 1 : 1 - ss(K.tueren + 0.1, K.tueren + 1.3, T); }
function heroState(T, tx) {
  const s = { pos: HP.clone(), yaw: Math.PI, walk: 0, rate: 1, face: {}, look: null, hands: 0 };
  if (T < K.du_drehst + 0.1) {                    // devant les portes ouvertes, terrifié, la silhouette derrière lui
    s.look = V(DX, 1.3, -2.5); s.face = { wide: 0.7, browUp: 0.8, open: 0.2, sad: 0.3 };
  } else if (T < K.falsche) {                      // il se retourne (gros plan, les pieds hors champ)
    s.yaw = lerp(Math.PI, 0.05, ss(K.du_drehst + 0.15, K.und - 0.1, T));
    const terror = ss(K.und, K.ganz, T);
    s.look = terror > 0 ? V(DX, 1.75, 1.9) : null; s.face = { wide: 0.6 + 0.4 * terror, browUp: 0.7 + 0.3 * terror, open: 0.25 + 0.5 * terror, sad: 0.4 * terror };
  } else if (T < K.diesmal - 0.15) {               // noir / rembobinage : position de départ
    s.pos = WALK0.clone();
  } else if (T < K.tueren + 0.4) {                 // il monte dans la rame, vitesse = celle de la marche capturée
    const t0 = K.diesmal - 0.15, d = WALK0.z - IN_Z, dur = d / 0.95;
    const u = Math.min(1, Math.max(0, (T - t0) / dur));
    s.pos = V(HX, 0, WALK0.z - d * u);
    s.walk = (1 - ss(t0 + dur - 0.35, t0 + dur + 0.05, T)) * ss(t0, t0 + 0.15, T); s.rate = 0.95 / WALK_SPEED;
    s.look = V(tx + HX, 1.4, -3.6); s.face = { browUp: 0.4, wide: 0.2 };
  } else if (T < K.bahn + 1.35) {                  // dans la rame, face à l'intérieur ; se retourne vers la porte (gros plan)
    s.pos = V(HX, 0, IN_Z); s.yaw = lerp(Math.PI, 0.0, ss(K.bahn + 0.1, K.bahn + 1.3, T));
    s.look = T < K.bahn ? V(tx + DX + 6, 1.3, ZC) : null; s.face = { browUp: 0.5, wide: 0.3 };
  } else {                                          // face à la porte
    const step = ss(K.und2 - 0.2, K.und2 + 0.8, T);
    s.pos = V(HX, 0, IN_Z + 0.78 * step); s.yaw = 0; s.walk = Math.min(1, Math.sin(Math.PI * step) * 2); s.rate = 1.0;
    s.look = T > K.dann2 && T < K.aber + 1 ? V(tx + DX, 2.13, ZN) : T > K.zwei ? V(tx + HX, 1.62, 3) : V(tx + DX - 0.2, 1.4, 6);
    const scared = ss(K.aber, K.aber + 1, T);
    s.face = T > K.zwei + 0.6 && T < K.schreib ? { closed: ss(K.zwei + 0.6, K.zwei + 1.0, T), squint: ss(K.zwei + 0.6, K.zwei + 1.0, T), sad: 0.7, browUp: 0.6 } : { browUp: 0.5 + 0.4 * scared, wide: 0.3 + 0.5 * scared, open: 0.1 + 0.25 * ss(K.und2, K.und2 + 1, T), squint: T > K.dann2 && T < K.aber ? 0.3 : 0 };
    s.hands = ss(K.und2 + 0.5, K.und2 + 0.9, T) * (1 - ss(K.eins - 0.2, K.eins + 0.2, T));
  }
  if (T >= K.diesmal - 0.15) s.pos.x += tx;
  return s;
}
function shadowState(T) {
  if (T < K.falsche) return { pos: V(DX + 0.03, 0, 1.9), yaw: Math.PI };
  if (T >= K.schreib - 0.2) return { pos: V(HX - 0.32, 0, ZC - 0.15), yaw: 0.1 };
  return null;
}
function shot(T, tx) {
  const H = _hw;
  if (T < K.du_drehst) { const u = ss(0, K.du_drehst, T); return [V(DX - 0.05, 1.62, lerp(-0.2, 0.25, u)), V(DX + 0.05, 1.66, 1.6), lerp(40, 33, u)]; }
  if (T < K.und) return [V(DX + 0.85, 1.64, 1.05), V(H.x, H.y - 0.04, H.z), 38];
  if (T < K.laechelt) { const u = ss(K.und, K.laechelt, T); return [V(DX + lerp(0.62, 0.48, u), 1.72, lerp(0.45, 0.7, u)), _sw.clone(), lerp(42, 32, u)]; }
  if (T < K.dann) { const u = ss(K.laechelt, K.dann, T); return [_sw.clone().add(V(0.02, -0.02, -lerp(0.85, 0.7, u))), _sw.clone().add(V(0, -0.05, 0)), 34]; }
  if (T < K.diesmal - 0.15) return [V(DX + 0.42, 1.72, 0.5), _sw.clone(), 40];
  if (T < K.tueren + 0.1) { const p = HERO.root.position; return [V(p.x + 0.35, 1.72, p.z + 1.5), V(p.x, 1.3, p.z - 1.6), 44]; }
  if (T < K.wagen) return [V(tx + HX - 0.35, 1.52, ZF + 0.45), V(H.x, H.y - 0.15, H.z), 46];
  if (T < K.bahn) return [V(tx + DX + 7.5, 1.75, ZC - 0.1), V(tx + DX - 2, 1.2, ZC + 0.2), 46];
  if (T < K.ohne) return [V(tx + HX + 0.45, 1.62, IN_Z + 0.5), V(H.x, H.y - 0.02, H.z), 36];
  if (T < K.dann2) { const u = ss(K.ohne, K.dann2, T); return [V(tx + HX + lerp(1.9, 1.5, u), 1.55, ZN - 0.25), V(H.x, H.y - 0.1, H.z), 42]; }
  if (T < K.naechster) return [V(tx + HX - 0.75, 1.45, IN_Z + 0.15), V(tx + DX, 2.08, ZN), 62];
  if (T < K.aber) return [V(tx + HX + 0.1, 1.58, IN_Z + 0.6), V(H.x, H.y + 0.03, H.z), 36];
  if (T < K.haelt) { const u = ss(K.aber, K.haelt, T); return [V(tx + HX - 0.35, 1.62, lerp(IN_Z + 0.7, IN_Z + 0.5, u)), V(H.x, H.y, H.z), lerp(38, 30, u)]; }
  if (T < K.bahnsteig) return [V(-6.5, 1.5, 2.8), V(-1.5, 0.9, -2.0), 44];
  if (T < K.zettel) return [V(HX, 1.45, ZN - 0.25), V(DX - 0.6, 1.9, 6.9), 48];
  if (T < K.nur) return [V(-4.25, 1.56, 5.75), V(-4.2, 1.55, 7), 46];
  if (T < K.wer - 0.2) { const u = ss(K.nur, K.wer - 0.2, T); return [V(-4.2, lerp(1.56, 1.42, u), lerp(5.75, 6.15, u)), V(-4.2, lerp(1.55, 1.4, u), 7), lerp(46, 50, u)]; }
  if (T < K.und2) { const u = ss(K.wer - 0.2, K.und2, T); return [V(-4.18, 1.36, lerp(6.25, 6.4, u)), V(-4.18, 1.36, 7), 54]; }
  if (T < K.eins) { const u = ss(K.und2, K.eins, T); return [V(HX + 0.04, 1.58, lerp(1.2, 0.6, u)), V(HX, 1.58, ZN - 0.4), lerp(42, 32, u)]; }
  if (T < K.zwei) { const n = NB.getWorldPosition(new THREE.Vector3()); return [n.clone().add(V(-0.45, 0.08, -0.85)), n.clone().add(V(0, -0.05, 0)), 40]; }
  if (T < K.schreib) return [H.clone().add(V(0, 0.0, 0.05)), V(tx + HX - 0.1, 1.5, 3), 50];   // vue subjective : ses paupières se ferment (montage)
  const u = ss(K.schreib, K.end, T); return [V(HX + 0.02, 1.62, lerp(1.4, 0.75, u)), V(HX - 0.12, 1.66, -2.0), lerp(40, 30, u)];
}
const SHOTS = [K.du_drehst, K.und, K.laechelt, K.dann, K.diesmal - 0.15, K.tueren + 0.1, K.wagen, K.bahn, K.ohne, K.dann2, K.naechster, K.aber, K.haelt, K.bahnsteig, K.zettel, K.nur, K.wer - 0.2, K.und2, K.eins, K.zwei, K.schreib];

function frame(T) {
  // lumières de la station : le noir total à « das Licht aus », retour quand il remonte le temps
  const offL = T >= K.licht && T < K.diesmal - 0.15; const off_ = offL;
  const offK = offL ? ss(K.licht, K.aus + 0.15, T) : 0;
  tubes.forEach((tb, i) => { const out = offL && (T > K.licht + i * 0.04 || offK > 0.9); const f = out ? 0 : (Math.sin(T * 31 + i) > 0.85 && T > K.du_drehst && T < K.licht ? 0.25 : 1); tb.mat.emissiveIntensity = 2.2 * f * 0.75; tb.l.intensity = 9 * f * 0.75; });
  key.intensity = offL ? 0 : 22; hemi.intensity = offL ? 0.0 : 0.3; paperLight.intensity = offL ? 0 : 6;
  setBoard('01:13'); gate.position.y = 1.6;
  // rame
  const tx = trainX(T); train.position.x = tx;
  const op = doorsOpen(T); for (const d of doors) { d.L.position.x = d.x - 0.39 - op * 0.75; d.R.position.x = d.x + 0.39 + op * 0.75; }
  const inside = T >= K.diesmal; const emer = inside ? (T > K.schreib ? 1.8 : 1) : 0.35;
  strips.forEach(m => (m.emissiveIntensity = 0.45 * emer)); inLights.forEach(l => (l.intensity = offL ? 0 : 1.4 * emer));
  setDisp(T > K.leuchtet && !(T < K.leuchtet + 0.6 && Math.sin(T * 60) > 0)); dispL.intensity = dispOn ? 1.6 : 0;
  setRule3(ss(K.wer - 0.1, K.und2 - 0.2, T) * (T > K.nur ? 1 : 0));
  // lampes du tunnel qui défilent : éclair sur le visage du héros
  let fl = 0; if (Math.abs(tx) > 32) for (const lx of tunLamps) { const d = lx - (tx + DX); if (Math.abs(d) < 4) fl += Math.exp(-d * d * 1.6); }
  flashL.position.set(tx + DX, 1.6, 0.3); flashL.intensity = Math.min(1.5, fl) * 6;
  // héros
  const h = heroState(T, tx);
  HERO.root.position.copy(h.pos); HERO.root.rotation.y = h.yaw; HERO.root.visible = !(T >= K.laechelt && T < K.dann) && !(T >= K.zwei && T < K.schreib);
  const pose = { mo: [{ clip: 'walk', mode: 'abs', t: loopT('walk', T * h.rate), k: h.walk, w: { ...FULL, arms: 0.9 } }, { clip: 'idle', mode: 'abs', t: loopT('idle', T > K.und2 ? 2 + (T - K.und2) * 0.3 : T + 3), k: 1 - h.walk, w: T > K.und2 ? { legs: 1, root: 1, pelvis: 0.15, spineAbs: 0.15, arms: 1 } : IDLEW }], lookW: 0.9 };
  if (h.hands > 0) {   // mains à plat sur la porte fermée
    const l = V(tx + HX + 0.2, 1.52, ZN - 0.03), r = V(tx + HX - 0.2, 1.48, ZN - 0.03);
    Object.assign(pose, { lW: h.hands, lwx: l.x, lwy: l.y, lwz: l.z, rW: h.hands, rwx: r.x, rwy: r.y, rwz: r.z, lCurl: 0.1, rCurl: 0.1 });
  }
  HERO.setPose(pose, h.face, h.look, T);
  HERO.headWorld(_hw);
  // silhouette
  const sh = shadowState(T); SHADOW.root.visible = !!sh;
  const glow = !!sh && (T > K.und - 0.4 || T >= K.schreib);
  eyes.forEach(([e]) => (e.visible = glow)); smile.visible = !!sh && T > K.laechelt - 0.1 && T < K.diesmal;
  if (sh) {
    SHADOW.root.position.copy(sh.pos); SHADOW.root.rotation.y = sh.yaw;
    SHADOW.setPose({ mo: [{ clip: 'idle', mode: 'abs', t: loopT('idle', T), k: 1, w: IDLEW }], lookW: 0.9 }, {}, _hw, T);
    SHADOW.headWorld(_sw);
    const f = _hw.clone().sub(_sw).setY(0).normalize(), r = V(f.z, 0, -f.x);
    eyes.forEach(([e, s]) => e.position.copy(_sw).addScaledVector(r, s * 0.032).addScaledVector(f, 0.075));
    const sp = ss(K.laechelt - 0.1, K.laechelt + 0.5, T);
    smile.position.copy(_sw).addScaledVector(f, 0.085).add(V(0, -0.075, 0)); smile.lookAt(_sw.clone().addScaledVector(f, 2).add(V(0, -0.075, 0)));
    smile.rotateZ(Math.PI + 0.15); smile.scale.setScalar(0.3 + 0.7 * sp);
    const big = T >= K.schreib ? 2.6 : 1; eyes.forEach(([e]) => e.scale.setScalar(big));
  }
  // caméra : coupe nette à chaque plan, puis légère caméra portée
  const [p, tgt, fov] = shot(T, tx);
  const sid = SHOTS.filter(x => x <= T).length;
  // dans la rame qui roule, la caméra suit le wagon (lissage en coordonnées du wagon, sinon elle reste en arrière)
  const off = V(T >= K.tueren + 0.1 && T < K.haelt + 0.5 ? tx : 0, 0, 0); p.sub(off); tgt.sub(off);
  if (sid !== lastShot) { camPos.copy(p); camTgt.copy(tgt); lastShot = sid; } else { camPos.lerp(p, 0.35); camTgt.lerp(tgt, 0.35); }
  camPos.add(off); camTgt.add(off);
  const shake = (T > K.ganz && T < K.falsche) || (T > K.und2 && T < K.eins) ? 0.006 : 0.0022;
  camera.position.copy(camPos).add(V(Math.sin(T * 1.3) * shake + Math.sin(T * 7.1) * shake * 0.3, Math.sin(T * 1.7) * shake, 0));
  camera.lookAt(camTgt); camera.fov = fov; camPos.sub(off); camTgt.sub(off);
  fillL.position.copy(camera.position).add(V(0, 0.25, 0)); fillL.target.position.copy(camTgt).add(off); fillL.intensity = offL ? 0 : (inside ? 3.2 : 4.0);
  const w2 = innerWidth, h2 = innerHeight;
  if (canvas.width !== w2) renderer.setSize(w2, h2, false);
  camera.aspect = w2 / h2; camera.updateProjectionMatrix();
  renderer.render(scene, camera);
}
window.renderAt = (T) => frame(T);
window.READY = true;
if (!MANUAL) { const c0 = performance.now(); const loop = () => { frame(((performance.now() - c0) / 1000) % 49); requestAnimationFrame(loop); }; loop(); }
else frame(0);
