// « Ich bin's. Mach auf. » – TEIL 2 : histoire d'horreur interactive au « tu ». Maison la nuit, couloir, porte d'entrée,
// le fils (Rocketbox « kid », expressions faciales) et le faux père (Rocketbox « judge », sourire forcé au-delà du modèle).
// Marche : motion capture CMU corrigée (jambes parallèles). Chronologie calée sur la voix off (T en secondes).
// ?manual : rendu image par image (window.renderAt(T)).
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
renderer.toneMappingExposure = 1.1;
renderer.outputColorSpace = THREE.SRGBColorSpace;

const scene = new THREE.Scene();
scene.background = new THREE.Color('#030407');
scene.fog = new THREE.Fog('#05070c', 6, 16);
const hemi = new THREE.HemisphereLight('#6f86b0', '#1a140e', 0.32); scene.add(hemi);
const camera = new THREE.PerspectiveCamera(42, 9 / 16, 0.03, 60);
const fillL = new THREE.SpotLight('#b9c8e6', 2.2, 5, 0.55, 0.9, 1.6); scene.add(fillL, fillL.target);

// ---------- textures dessinées ----------
function canvasTex(w, h, draw) {
  const c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d'); draw(g, w, h);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; t.userData = { c, g, draw }; return t;
}
const rnd = (s => () => (s = (s * 16807) % 2147483647) / 2147483647)(11);
const paper = canvasTex(512, 512, (g, w, h) => {
  g.fillStyle = '#8c826e'; g.fillRect(0, 0, w, h);
  for (let x = 0; x < w; x += 32) { g.fillStyle = 'rgba(255,240,210,0.07)'; g.fillRect(x, 0, 12, h); g.fillStyle = 'rgba(60,40,20,0.06)'; g.fillRect(x + 16, 0, 3, h); }
  for (let i = 0; i < 40; i++) { g.fillStyle = `rgba(70,55,30,${0.02 + rnd() * 0.05})`; g.beginPath(); g.arc(rnd() * w, rnd() * h, 10 + rnd() * 60, 0, 7); g.fill(); }
});
paper.wrapS = paper.wrapT = THREE.RepeatWrapping; paper.repeat.set(3, 1.4);
const planks = canvasTex(512, 512, (g, w, h) => {
  for (let y = 0; y < h; y += 64) { const v = 70 + rnd() * 25 | 0; g.fillStyle = `rgb(${v + 22},${v},${v - 18})`; g.fillRect(0, y, w, 64);
    g.fillStyle = 'rgba(20,12,6,0.55)'; g.fillRect(0, y, w, 3); const cut = rnd() * w; g.fillRect(cut, y, 3, 64);
    for (let k = 0; k < 14; k++) { g.fillStyle = `rgba(30,18,8,${rnd() * 0.12})`; g.fillRect(0, y + rnd() * 64, w, 1 + rnd() * 2); } }
});
planks.wrapS = planks.wrapT = THREE.RepeatWrapping; planks.repeat.set(1, 6);
const M = (o) => new THREE.MeshStandardMaterial({ roughness: 0.85, metalness: 0, ...o });
const box = (w, h, d, mat, x, y, z, parent = scene, shadow = true) => {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); m.position.set(x, y, z); m.castShadow = shadow; m.receiveShadow = true; parent.add(m); return m;
};
const V = (x, y, z) => new THREE.Vector3(x, y, z);

// ---------- le couloir (porte d'entrée en z = 0, couloir vers +z, escalier au fond) ----------
const HW = 0.95, HL = 8.2, HH = 2.6;
const wallM = M({ map: paper, roughness: 0.9 });
box(2 * HW + 0.4, 0.1, HL + 1, M({ map: planks, roughness: 0.7 }), 0, -0.05, HL / 2);                 // sol
box(2 * HW + 0.4, 0.1, 6.1, M({ color: '#bdb6aa', roughness: 1 }), 0, HH + 0.05, 2.55, scene, false);   // plafond (ouvert au-dessus de l'escalier)
box(HW + 0.2, 0.1, 3.2, M({ color: '#bdb6aa', roughness: 1 }), 0.03 + (HW + 0.2) / 2, HH + 0.05, 7.2, scene, false);
box(0.1, HH, HL, wallM, -HW - 0.05, HH / 2, HL / 2);                                                     // mur gauche
box(0.1, HH, 2.9, wallM, HW + 0.05, HH / 2, 1.45);                                                       // mur droit (avant le salon)
box(0.1, 0.5, 1.2, wallM, HW + 0.05, HH - 0.25, 3.5);                                                    // linteau de la porte du salon
box(0.1, HH, HL - 4.1, wallM, HW + 0.05, HH / 2, 4.1 + (HL - 4.1) / 2);
for (const s of [-1, 1]) box(0.03, 0.12, HL, M({ color: '#d9d3c4' }), s * (HW - 0.01), 0.06, HL / 2, scene, false);   // plinthes
// mur de la porte d'entrée
box(HW - 0.48, HH, 0.12, wallM, -(0.48 + (HW - 0.48) / 2), HH / 2, -0.06); box(HW - 0.48, HH, 0.12, wallM, 0.48 + (HW - 0.48) / 2, HH / 2, -0.06);
box(0.96, HH - 2.12, 0.12, wallM, 0, 2.12 + (HH - 2.12) / 2, -0.06);
// la porte : panneaux, verre dépoli en haut (lumière froide de la rue), judas, poignée
const hinge = new THREE.Group(); scene.add(hinge); hinge.position.set(-0.47, 0, 0);
const door = new THREE.Group(); hinge.add(door); door.position.set(0.47, 0, 0);
const doorM = M({ color: '#4a2f1d', roughness: 0.6 });
box(0.94, 1.32, 0.05, doorM, 0, 0.66, 0.0, door); box(0.94, 0.24, 0.05, doorM, 0, 2.0, 0.0, door);
box(0.2, 0.56, 0.05, doorM, -0.37, 1.6, 0.0, door); box(0.2, 0.56, 0.05, doorM, 0.37, 1.6, 0.0, door);
for (const y of [0.35, 0.95]) box(0.62, 0.42, 0.012, M({ color: '#3e2716', roughness: 0.65 }), 0, y, 0.03, door, false);
const glassTex = canvasTex(256, 384, () => {});
let glassSil = -1;
function drawGlass(sil) {
  sil = Math.round(sil * 10) / 10; if (sil === glassSil) return; glassSil = sil;
  const { g, c } = glassTex.userData, w = c.width, h = c.height; const R = (s => () => (s = (s * 16807) % 2147483647) / 2147483647)(5);
  const gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, '#7f99c4'); gr.addColorStop(1, '#4b5f86'); g.fillStyle = gr; g.fillRect(0, 0, w, h);
  for (let i = 0; i < 900; i++) { g.fillStyle = `rgba(255,255,255,${R() * 0.06})`; g.fillRect(R() * w, R() * h, 3, 3); }
  if (sil > 0) {   // silhouette floue de quelqu'un derrière la porte
    g.filter = 'blur(22px)'; g.fillStyle = `rgba(10,13,22,${0.55 * sil})`;
    g.beginPath(); g.ellipse(w * 0.52, h * 0.3, 46, 58, 0, 0, 7); g.fill(); g.beginPath(); g.ellipse(w * 0.5, h * 0.95, 110, 150, 0, 0, 7); g.fill(); g.filter = 'none';
  }
  glassTex.needsUpdate = true;
}
drawGlass(1);
const glass = new THREE.Mesh(new THREE.PlaneGeometry(0.54, 0.56), new THREE.MeshBasicMaterial({ map: glassTex, toneMapped: false, color: '#9aa7bd' }));
glass.position.set(0, 1.6, 0.0); door.add(glass);
const peep = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.02, 16), M({ color: '#b08d4a', metalness: 0.9, roughness: 0.3 })); peep.rotation.x = Math.PI / 2; peep.position.set(0, 1.56, 0.03); door.add(peep);
const knob = new THREE.Mesh(new THREE.SphereGeometry(0.03, 16, 12), M({ color: '#c2a061', metalness: 0.9, roughness: 0.25 })); knob.position.set(0.36, 1.02, 0.06); door.add(knob);
box(0.03, 0.15, 0.01, M({ color: '#c2a061', metalness: 0.9, roughness: 0.3 }), 0.36, 1.0, 0.03, door, false);
box(1.04, 0.05, 0.08, M({ color: '#d9d3c4' }), 0, 2.14, 0.02, scene, false); for (const s of [-1, 1]) box(0.05, 2.14, 0.08, M({ color: '#d9d3c4' }), s * 0.5, 1.07, 0.02, scene, false);
const streetL = new THREE.SpotLight('#8fa9d8', 7, 6, 0.6, 0.8, 1.4); streetL.position.set(0, 1.7, -0.3); streetL.target.position.set(0, 0.2, 3); scene.add(streetL, streetL.target);
// paillasson, portemanteau, chaussures, commode avec bol à clés et réveil
box(0.8, 0.02, 0.5, M({ color: '#4d3b26', roughness: 1 }), 0, 0.01, 0.45, scene, false);
box(0.05, 0.06, 1.1, M({ color: '#5a4030' }), HW - 0.03, 1.75, 1.2, scene, false);
for (let i = 0; i < 4; i++) {
  const z = 0.8 + i * 0.27; const c = box(0.16, 0.85, 0.24, M({ color: ['#2b2f38', '#4a3a2c', '#1f2a24', '#3a2a2e'][i], roughness: 0.95 }), HW - 0.12, 1.32, z, scene, true);
  c.rotation.z = 0.04 * (i % 2 ? 1 : -1);
}
for (let i = 0; i < 3; i++) box(0.12, 0.1, 0.28, M({ color: ['#222', '#6b5a48', '#3b3b3b'][i] }), HW - 0.2 - (i % 2) * 0.15, 0.05, 0.6 + i * 0.32, scene, true);
const chest = new THREE.Group(); scene.add(chest); chest.position.set(-HW + 0.22, 0, 1.6);
box(0.4, 0.8, 0.9, M({ color: '#6b4a32', roughness: 0.7 }), 0, 0.4, 0, chest); box(0.42, 0.03, 0.92, M({ color: '#5a3c28' }), 0, 0.81, 0, chest);
box(0.18, 0.04, 0.18, M({ color: '#2d3e52', roughness: 0.4 }), 0.02, 0.84, 0.25, chest);   // bol à clés
let clockTxt = '';
const clockTex = canvasTex(256, 96, () => {});
function setClock(s) {
  if (s === clockTxt) return; clockTxt = s; const { g, c } = clockTex.userData;
  g.fillStyle = '#060202'; g.fillRect(0, 0, c.width, c.height); g.fillStyle = '#ff2a1a'; g.shadowColor = '#ff2a1a'; g.shadowBlur = 14;
  g.font = 'bold 74px "Courier New", monospace'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(s, c.width / 2, c.height / 2 + 4); g.shadowBlur = 0; clockTex.needsUpdate = true;
}
setClock('02:00');
const clockG = new THREE.Group(); chest.add(clockG); clockG.position.set(0.05, 0.88, -0.2); clockG.rotation.y = Math.PI / 2;
box(0.22, 0.09, 0.07, M({ color: '#111', roughness: 0.4 }), 0, 0, 0, clockG, false);
const clockFace = new THREE.Mesh(new THREE.PlaneGeometry(0.19, 0.07), new THREE.MeshBasicMaterial({ map: clockTex, toneMapped: false })); clockFace.position.z = 0.036; clockG.add(clockFace);
const clockL = new THREE.PointLight('#ff3020', 0.35, 0.8, 2); clockL.position.set(-HW + 0.45, 0.92, 1.4); scene.add(clockL);
// cadres photo
const photo = canvasTex(256, 192, (g, w, h) => {
  const gr = g.createLinearGradient(0, 0, w, h); gr.addColorStop(0, '#9b8a6a'); gr.addColorStop(1, '#5d6b72'); g.fillStyle = gr; g.fillRect(0, 0, w, h);
  g.filter = 'blur(6px)'; g.fillStyle = '#e6c9a8'; for (const [x, y, r] of [[90, 80, 26], [160, 70, 30]]) { g.beginPath(); g.arc(x, y, r, 0, 7); g.fill(); }
  g.fillStyle = '#3b4b5a'; g.fillRect(55, 105, 70, 90); g.fillStyle = '#5a3a2a'; g.fillRect(125, 100, 75, 95); g.filter = 'none';
});
for (const [z, y, s] of [[2.6, 1.6, 1], [3.3, 1.45, 0.8], [4.6, 1.65, 1.1]]) {
  const f = box(0.03, 0.34 * s, 0.44 * s, M({ color: '#2a1d14' }), -HW + 0.015, y, z, scene, false);
  const p = new THREE.Mesh(new THREE.PlaneGeometry(0.38 * s, 0.28 * s), M({ map: photo, roughness: 0.4 })); p.position.set(-HW + 0.035, y, z); p.rotation.y = Math.PI / 2; scene.add(p);
}
// salon (ouverture à droite) : lumière de télé qui vacille
box(4, 0.1, 3, M({ color: '#3a2c22' }), HW + 2, -0.05, 3.5, scene, false);
box(0.1, HH, 3, M({ color: '#3b3a40' }), HW + 3, HH / 2, 3.5, scene, false);
const tvL = new THREE.PointLight('#7fa2ff', 3, 5, 1.6); tvL.position.set(HW + 1.8, 1.0, 3.2); scene.add(tvL);
// escalier au fond à gauche (monte vers +z)
const stairM = M({ color: '#5b4331', roughness: 0.75 });
for (let i = 0; i < 12; i++) box(0.95, 0.19, 0.27, stairM, -HW + 0.48, 0.095 + i * 0.19, 6.0 + i * 0.27);
box(0.05, 1.0, 3.4, M({ color: '#4a3526' }), -HW + 0.98, 1.6, 7.5).rotation.x = -0.6;
box(0.05, 0.9, 0.05, M({ color: '#4a3526' }), -HW + 0.98, 0.45, 5.95);
box(HW - 0.03, HH, 0.1, wallM, 0.03 + (HW - 0.03) / 2, HH / 2, HL + 0.05);
// cage d'escalier : murs qui montent à l'étage, palier, lumière chaude en haut
box(0.1, 3.2, 5.0, wallM, -HW - 0.05, HH + 1.6, 7.9, scene, false); box(0.06, 3.2, 4.8, wallM, 0.03, HH + 1.65, 8.0, scene, false);
box(0.06, HH, 2.2, wallM, 0.03, HH / 2, 9.35, scene, false); box(0.95, 0.1, 1.3, stairM, -HW + 0.48, 2.33, 9.75); box(1.2, 6, 0.1, wallM, -HW + 0.48, 3, 10.4, scene, false);
box(1.3, 0.1, 5.2, M({ color: '#8f8a80' }), -HW + 0.48, 5.3, 8.0, scene, false); box(1.0, 0.1, 0.5, wallM, -HW + 0.48, HH + 0.3, 5.6, scene, false); box(1.0, 2.7, 0.06, wallM, -HW + 0.48, HH + 1.65, 5.42, scene, false);
const upL = new THREE.PointLight('#ffb36b', 5, 7, 1.5); upL.position.set(-HW + 0.48, 4.3, 9.6); scene.add(upL);
// lumières
const moon = new THREE.DirectionalLight('#7f97c9', 0.35); moon.position.set(2, 4, -3); moon.target.position.set(0, 0, 3); scene.add(moon, moon.target);
const lamp = new THREE.PointLight('#ffb36b', 0.9, 3.2, 1.8); lamp.position.set(-HW + 0.3, 1.05, 1.9); lamp.castShadow = true; lamp.shadow.mapSize.set(512, 512); scene.add(lamp);
const underL = new THREE.SpotLight('#a9b8e0', 0, 3.2, 0.5, 0.6, 1.5); scene.add(underL, underL.target);   // lumière par en dessous sur le faux père

// ---------- dehors : perron, allée, rue (vu par le judas) ----------
const outM = M({ color: '#3a3d44', roughness: 0.95 });
box(2.6, HH + 0.6, 0.1, outM, -1.78, (HH + 0.6) / 2, -0.17); box(2.6, HH + 0.6, 0.1, outM, 1.78, (HH + 0.6) / 2, -0.17); box(0.96, 0.9, 0.1, outM, 0, 2.6, -0.17);
box(3.2, 0.16, 1.8, M({ color: '#55534f', roughness: 1 }), 0, -0.08, -1.1);                       // perron
box(2.4, 0.16, 0.4, M({ color: '#4c4a46' }), 0, -0.24, -2.2); box(2.4, 0.16, 0.4, M({ color: '#4c4a46' }), 0, -0.4, -2.6);
box(30, 0.1, 30, M({ color: '#15190f', roughness: 1 }), 0, -0.55, -16, scene, false);            // pelouse
box(1.1, 0.02, 9, M({ color: '#3b3a37' }), 0, -0.49, -7.2, scene, false);                           // allée
box(30, 0.05, 4, M({ color: '#1d1e21', roughness: 0.6 }), 0, -0.5, -13, scene, false);             // rue
for (const x of [-1.5, 1.5]) for (let i = 0; i < 3; i++) { const b = new THREE.Mesh(new THREE.IcosahedronGeometry(0.42 + i * 0.05, 1), M({ color: '#16220f' })); b.position.set(x * (1 + i * 0.25), -0.15, -1.6 - i * 1.1); scene.add(b); }
for (let x = -8; x <= 8; x += 0.35) if (Math.abs(x) > 0.7) box(0.06, 0.8, 0.06, M({ color: '#2d2a26' }), x, -0.1, -10.5, scene, false);
box(16, 0.06, 0.06, M({ color: '#2d2a26' }), 0, 0.25, -10.5, scene, false);
const pole = box(0.1, 4.2, 0.1, M({ color: '#222' }), 3.2, 1.6, -11.5, scene, false);
const sLamp = new THREE.Mesh(new THREE.SphereGeometry(0.16, 12, 8), new THREE.MeshBasicMaterial({ color: '#ffcf8a', toneMapped: false })); sLamp.position.set(3.0, 3.6, -11.5); scene.add(sLamp);
const sL = new THREE.PointLight('#ffb062', 18, 18, 1.4);
const outMoon = new THREE.DirectionalLight('#5f78b0', 0.5); outMoon.position.set(-3, 5, -12); outMoon.target.position.set(0, 0, -2); scene.add(outMoon, outMoon.target); sL.position.set(3.0, 3.5, -11.5); scene.add(sL);
const porchBulb = new THREE.Mesh(new THREE.SphereGeometry(0.06, 12, 8), new THREE.MeshBasicMaterial({ color: '#ffd9a0', toneMapped: false })); porchBulb.position.set(0.72, 2.15, -0.3); scene.add(porchBulb);
const porchL = new THREE.PointLight('#ffc27a', 7, 7, 1.5); porchL.position.set(0.72, 2.05, -0.45); scene.add(porchL);

// ---------- la chambre (décalée en x = 10..14) : lit, fenêtre, armoire à lamelles ----------
const BX = 10, BW = 4, BD = 4.1;
const bWall = M({ map: paper, color: '#8e9bb0', roughness: 0.9 });
box(BW, 0.1, BD, M({ map: planks, roughness: 0.7 }), BX + BW / 2, -0.05, BD / 2);
box(BW, 0.1, BD, M({ color: '#9fa4ae' }), BX + BW / 2, HH + 0.05, BD / 2, scene, false);
box(0.1, HH, BD, bWall, BX - 0.05, HH / 2, BD / 2); box(BW, HH, 0.1, bWall, BX + BW / 2, HH / 2, BD + 0.05);
box(0.1, 0.9, BD, bWall, BX + BW + 0.05, 0.45, BD / 2); box(0.1, 0.6, BD, bWall, BX + BW + 0.05, HH - 0.3, BD / 2);
box(0.1, 1.1, 1.2, bWall, BX + BW + 0.05, 1.45, 0.6); box(0.1, 1.1, 1.6, bWall, BX + BW + 0.05, 1.45, 3.3);
const win = new THREE.Mesh(new THREE.PlaneGeometry(1.3, 1.1), new THREE.MeshBasicMaterial({ color: '#1a2a4a', toneMapped: false })); win.position.set(BX + BW + 0.1, 1.45, 1.85); win.rotation.y = -Math.PI / 2; scene.add(win);
box(0.06, 1.1, 0.05, M({ color: '#ddd' }), BX + BW + 0.04, 1.45, 1.85, scene, false);
// mur avec la porte de la chambre (z = 0), porte entre x = 10.75 et 11.65
box(0.75, HH, 0.1, bWall, BX + 0.375, HH / 2, -0.05); box(BW - 1.65, HH, 0.1, bWall, BX + 1.65 + (BW - 1.65) / 2, HH / 2, -0.05); box(0.9, HH - 2.1, 0.1, bWall, BX + 1.2, 2.1 + (HH - 2.1) / 2, -0.05);
const bHinge = new THREE.Group(); scene.add(bHinge); bHinge.position.set(BX + 0.77, 0, 0.02);
box(0.86, 2.06, 0.04, M({ color: '#e2ddd2', roughness: 0.6 }), 0.43, 1.03, 0, bHinge);
// palier derrière la porte (lumière chaude)
box(3, 0.1, 2.5, M({ map: planks }), BX + 1.2, -0.05, -1.3); box(3, HH, 0.1, M({ map: paper }), BX + 1.2, HH / 2, -2.5);
const hallL = new THREE.PointLight('#ffb36b', 0, 4.5, 1.6); hallL.position.set(BX + 1.2, 2.2, -1.2); scene.add(hallL);
// lit, bureau
box(1.0, 0.45, 2.0, M({ color: '#5a4a3a' }), BX + 0.55, 0.22, 2.0); box(0.96, 0.15, 1.96, M({ color: '#c9c3b8' }), BX + 0.55, 0.52, 2.0);
box(0.9, 0.18, 1.3, M({ color: '#4f5f7a' }), BX + 0.6, 0.62, 2.3); box(0.5, 0.12, 0.35, M({ color: '#e8e4dc' }), BX + 0.55, 0.65, 1.15);
box(1.1, 0.75, 0.55, M({ color: '#6b5a48' }), BX + 3.2, 0.37, 0.4); box(0.45, 0.3, 0.05, M({ color: '#111' }), BX + 3.2, 0.95, 0.3);
// l'armoire (x 12.4..13.4, z 3.45..4.05), portes à lamelles
const WX0 = BX + 2.4, WX1 = BX + 3.4, WZ = 3.45, WH = 2.1;
const wM = M({ color: '#4a3527', roughness: 0.7 });
box(0.04, WH, 0.62, wM, WX0 - 0.02, WH / 2, WZ + 0.3); box(0.04, WH, 0.62, wM, WX1 + 0.02, WH / 2, WZ + 0.3); box(1.08, 0.04, 0.62, wM, (WX0 + WX1) / 2, WH, WZ + 0.3);
box(1.0, 0.04, 0.6, wM, (WX0 + WX1) / 2, 0.02, WZ + 0.3);
for (let i = 0; i < 0; i++) box(0.12, 0.8 - i * 0.05, 0.4, M({ color: ['#3b4a63', '#6b3a3a', '#2f3a2f', '#5a5048', '#22252c'][i] }), WX0 + 0.08 + i * 0.07, 1.5, WZ + 0.38, scene, true);
for (let i = 0; i < 4; i++) box(0.12, 0.9, 0.4, M({ color: ['#4a4a52', '#2a3550', '#5c4632', '#30302f'][i] }), WX1 - 0.08 - i * 0.07, 1.45, WZ + 0.38, scene, true);
const leaves = [];
for (const side of [0, 1]) {
  const g = new THREE.Group(); scene.add(g); g.position.set(side ? WX1 : WX0, 0, WZ); leaves.push(g); const sx = side ? -1 : 1;
  box(0.04, WH - 0.06, 0.03, wM, sx * 0.02, WH / 2, 0, g); box(0.04, WH - 0.06, 0.03, wM, sx * 0.48, WH / 2, 0, g);
  box(0.5, 0.06, 0.03, wM, sx * 0.25, 0.06, 0, g); box(0.5, 0.06, 0.03, wM, sx * 0.25, WH - 0.06, 0, g);
  for (let y = 0.14; y < WH - 0.1; y += 0.068) { const sl = box(0.44, 0.038, 0.008, wM, sx * 0.25, y, 0, g); sl.rotation.x = 0.55; }
}
const slatL = new THREE.SpotLight('#9fb4e0', 9, 6, 0.5, 0.5, 1.4); slatL.position.set(BX + 2.6, 2.0, 1.2); slatL.target.position.set(WX0 + 0.27, 1.5, 3.8);
slatL.castShadow = true; slatL.shadow.mapSize.set(1024, 1024); slatL.shadow.bias = -0.0004; scene.add(slatL, slatL.target);
const roomMoon = new THREE.PointLight('#6f8fd0', 4.5, 6, 1.4); roomMoon.position.set(BX + 3.6, 1.8, 1.9); scene.add(roomMoon);

// ---------- le téléphone ----------
const phone = new THREE.Group(); scene.add(phone);
box(0.074, 0.152, 0.009, M({ color: '#0d0d10', roughness: 0.3, metalness: 0.5 }), 0, 0, 0, phone, false);
const scrTex = canvasTex(540, 1110, () => {});
let scrState = '';
function drawScreen(state) {
  if (state === scrState) return; scrState = state; const { g, c } = scrTex.userData, w = c.width, h = c.height;
  g.fillStyle = state === 'off' ? '#020203' : '#0b0e14'; g.fillRect(0, 0, w, h);
  if (state === 'off') { scrTex.needsUpdate = true; return; }
  g.fillStyle = '#e9edf3'; g.font = '600 30px Arial'; g.textAlign = 'left'; g.fillText(state === 'hook' ? '02:21' : '02:24', 36, 52);
  g.fillStyle = '#161b25'; g.fillRect(0, 80, w, 120); g.fillStyle = '#3a6fd8'; g.beginPath(); g.arc(80, 140, 38, 0, 7); g.fill();
  g.fillStyle = '#fff'; g.font = 'bold 40px Arial'; g.textAlign = 'center'; g.fillText('P', 80, 154); g.textAlign = 'left'; g.font = 'bold 40px Arial'; g.fillText('Papa', 140, 135);
  g.fillStyle = '#8b95a7'; g.font = '28px Arial'; g.fillText('online', 140, 175);
  let y = 250;
  const bub = (txt, mine, hot) => { g.font = 'bold 46px Arial'; const words = txt.split(' '); const lines = []; let cur = '';
    for (const wd of words) { const tt = cur ? cur + ' ' + wd : wd; if (g.measureText(tt).width > 400 && cur) { lines.push(cur); cur = wd; } else cur = tt; } lines.push(cur);
    const tw = Math.max(...lines.map(l => g.measureText(l).width)) + 56, th = 34 + lines.length * 56; const x = mine ? w - tw - 30 : 30;
    g.fillStyle = mine ? '#2f6fe0' : (hot ? '#3a4254' : '#262d3a'); g.beginPath(); g.roundRect(x, y, tw, th, 30); g.fill(); g.fillStyle = '#f5f7fa';
    lines.forEach((l, i) => g.fillText(l, x + 28, y + 62 + i * 56)); y += th + 26; };
  bub('Papa??', true);
  bub('Ich steh vor der Tür. Mach mir auf.', false, state === 'hook');
  if (state === 'final') bub('Der an der Tür bin nicht ich. Lauf.', false, true);
  scrTex.needsUpdate = true;
}
drawScreen('off');
const scr = new THREE.Mesh(new THREE.PlaneGeometry(0.068, 0.14), new THREE.MeshBasicMaterial({ map: scrTex, toneMapped: false }));
scr.position.z = 0.0047; phone.add(scr);
const phoneL = new THREE.PointLight('#9fc0ff', 0, 0.9, 2); scene.add(phoneL);

// ---------- personnages ----------
await RealHuman.loadClips(['idle', 'slowwalk', 'walk2', 'run2', 'backaway'], './mocap/');
const HERO = await RealHuman.create('./models/kid.glb', { heightM: 1.72, seed: 2 });
const PAPA = await RealHuman.create('./models/judge.glb', { heightM: 1.86, seed: 4 });    // celui de la chambre
const PAPA2 = await RealHuman.create('./models/judge.glb', { heightM: 1.86, seed: 7 });   // celui de la porte
for (const H of [HERO, PAPA, PAPA2]) { scene.add(H.root); H.root.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } }); }

// ---------- outils ----------
const ss = (a, b, x) => { const u = Math.min(1, Math.max(0, (x - a) / (b - a))); return u * u * (3 - 2 * u); };
const lerp = (a, b, u) => a + (b - a) * u;
const inR = (T, a, b) => T >= a && T < b;
const FULL = { pelvis: 1, spineAbs: 1, legs: 1, arms: 1, root: 1, headAbs: 0.4 };
const IDLEW = { legs: 1, root: 1, pelvis: 0.5, spineAbs: 0.5, arms: 1 };
const dur = (c) => RealHuman.clips[c].frames / RealHuman.clips[c].fps;
const loopT = (c, x) => ((x % dur(c)) + dur(c)) % dur(c);
const IDLE = (t) => [{ clip: 'idle', mode: 'abs', t: loopT('idle', t), k: 1, w: IDLEW }];
const CLIP = (c, t, k = 1) => [{ clip: c, mode: 'abs', t: loopT(c, t), k, w: FULL }];
const FEAR = { maxM: 1.5, raw: { EyeWideLeft: 1.4, EyeWideRight: 1.4, BrowInnerUp: 1.3, BrowOuterUpLeft: 1.1, BrowOuterUpRight: 1.1, JawOpen: 0.42, MouthStretchLeft: 0.8, MouthStretchRight: 0.8, MouthLowerDownLeft: 0.5, MouthLowerDownRight: 0.5 } };
const WORRY = { maxM: 1.2, raw: { EyeWideLeft: 0.6, EyeWideRight: 0.6, BrowInnerUp: 0.9, BrowOuterUpLeft: 0.3, BrowOuterUpRight: 0.3, MouthPressLeft: 0.4, MouthPressRight: 0.4 } };
const CALM = { raw: { BrowInnerUp: 0.2, MouthSmileLeft: 0.2, MouthSmileRight: 0.2 } };
const RELIEF = { maxM: 1.2, raw: { MouthSmileLeft: 0.45, MouthSmileRight: 0.45, BrowInnerUp: 1.0, EyeSquintLeft: 0.4, EyeSquintRight: 0.4, JawOpen: 0.15 } };
const GRIN = { maxM: 2, raw: { MouthSmileLeft: 1.9, MouthSmileRight: 1.9, CheekSquintLeft: 0.6, CheekSquintRight: 0.6, MouthStretchLeft: 0.9, MouthStretchRight: 0.9, MouthUpperUpLeft: 0.5, MouthUpperUpRight: 0.5, EyeWideLeft: 1.2, EyeWideRight: 1.2, MouthLowerDownLeft: 0.4, MouthLowerDownRight: 0.4 } };
const SMILE = { raw: { MouthSmileLeft: 0.6, MouthSmileRight: 0.6 } };
const DADOK = { maxM: 1.2, raw: { BrowInnerUp: 0.8, MouthSmileLeft: 0.3, MouthSmileRight: 0.3, EyeWideLeft: 0.3, EyeWideRight: 0.3 } };
const mix = (a, b, u) => { const r = {}; for (const k of new Set([...Object.keys(a.raw || {}), ...Object.keys(b.raw || {})])) r[k] = lerp((a.raw || {})[k] || 0, (b.raw || {})[k] || 0, u); return { maxM: Math.max(a.maxM || 1, b.maxM || 1), raw: r }; };
const talk = (f, T, on) => (on ? { maxM: f.maxM || 1, raw: { ...f.raw, JawOpen: 0.12 + 0.3 * Math.abs(Math.sin(T * 12.5)) * (0.6 + 0.4 * Math.sin(T * 4.1)) } } : f);
const _hw = new THREE.Vector3(), _pw = new THREE.Vector3(), _p2w = new THREE.Vector3();
const wp = (o) => o.getWorldPosition(new THREE.Vector3());
const yS = (z) => (z < 5.865 ? 0 : Math.min(2.38, ((z - 5.865) / 0.27) * 0.19 + 0.04));   // hauteur du sol dans l'escalier

// ---------- chronologie (temps de la voix, words.json) ----------
const BS = V(BX + 2.75, 0, 2.92), BP = V(BX + 2.7, 0, 2.14);            // accroche : le fils devant l'armoire, le père face à lui
const WPOS = V(WX0 + 0.27, 0, 3.8), PR = V(BX + 2.2, 0, 1.5), BN = V(WX0 + 0.3, 0, WZ - 0.62), BEXIT = V(BX + 1.3, 0, 0.5);
const HD = V(0.05, 0, 1.2), HG = V(0.1, 0, 1.42), POUT = V(0.0, 0, -0.62), PIN = V(0.0, 0, 0.93), PEND = V(-0.62, 0, 4.7);
const SX = -HW + 0.48;
const POUND = [12.3, 12.55, 12.8, 13.05, 13.5, 13.75, 14.0, 14.5, 14.75, 15.0];
const END = 48.3;
const RUNV = RealHuman.clips.run2.speed * 0.9, WALKV = RealHuman.clips.slowwalk.speed * 0.97;

function heroState(T) {
  const s = { pos: BS.clone(), yaw: Math.PI, layers: IDLE(T), face: CALM, look: null, phone: 0, pdist: 0.27, py: 1.2, mouth: 0, reach: 0 };
  if (T < 9.2) {                                                    // accroche : face au père, le téléphone s'allume
    const dn = ss(0.8, 1.02, T) * (1 - ss(3.45, 3.8, T));           // il baisse vite la tête, puis la relève
    s.phone = 1; s.py = lerp(1.02, 1.24, ss(0.8, 1.1, T));
    s.lookMix = dn; s.lookA = 'papa'; s.face = T < 0.85 ? CALM : mix(mix(CALM, WORRY, ss(0.9, 1.6, T)), FEAR, ss(3.45, 4.1, T));
  } else if (T < 25.31) {                                           // caché dans l'armoire
    s.pos = WPOS.clone(); s.layers = IDLE(T * 0.6); s.face = FEAR; s.look = V(BX + 2.2, 1.55, 1.2); s.mouth = 1; s.eyeY = 0.25 * Math.sin(T * 2.1);
  } else if (T < 26.27) {                                           // il sort en courant
    const d = BEXIT.clone().sub(WPOS), L = d.length(), u = Math.min(1, ((T - 25.36) * RUNV * 1.08) / L); s.pos = WPOS.clone().addScaledVector(d, Math.max(0, u));
    s.yaw = Math.atan2(d.x, d.z); s.layers = CLIP('run2', T); s.face = FEAR;
  } else if (T < 27.6) {                                            // l'escalier, en descendant
    const z = lerp(9.3, 5.6, (T - 26.2) / 1.4); s.pos = V(SX, yS(z), z); s.layers = CLIP('run2', T * 0.9); s.face = FEAR;
    if (T > 27.25) s.look = V(SX, 4, 9.6);
  } else if (T < 30.45) {                                           // en bas : il recule, les yeux sur l'escalier
    const u = ss(27.6, 30.3, T); s.pos = V(lerp(SX, -0.2, u), 0, lerp(5.6, 4.0, u)); s.layers = u < 1 ? [{ clip: 'backaway', mode: 'abs', t: (T - 27.6) * 0.5, k: 1, w: FULL }] : IDLE(T);
    s.face = FEAR; s.look = 'papa';
  } else if (T < 31.2) {                                            // il fonce vers la porte
    const u = Math.min(1, ((T - 30.45) * RUNV) / 2.8); s.pos = V(lerp(-0.2, HD.x, u), 0, lerp(4.0, HD.z, u)); s.layers = u < 1 ? CLIP('run2', T) : IDLE(T); s.face = FEAR; s.look = V(0, 1.5, 0);
  } else if (T < 34.9) {                                            // il ouvre : Papa
    s.pos = HD.clone().lerp(HG, ss(31.3, 32.0, T)); s.reach = ss(31.15, 31.35, T) * (1 - ss(31.7, 32.1, T)); s.look = 'papa2';
    s.face = mix(FEAR, RELIEF, ss(32.1, 33.0, T));
  } else {                                                          // dans ses bras, le téléphone vibre
    s.pos = HG.clone(); s.phone = T > 36.35 ? 1 : 0; s.ppos = HG.clone().add(V(-0.3, 1.0, -0.1)).lerp(HG.clone().add(V(-0.37, 1.5, -0.4)), ss(36.5, 37.0, T));
    const rd = ss(36.6, 37.0, T) * (1 - ss(41.2, 41.7, T)); s.lookMix = rd; s.lookA = 'out';
    s.face = T < 36.6 ? { maxM: 1.2, raw: { ...RELIEF.raw, EyeBlinkLeft: 0.9 * ss(35.6, 35.9, T), EyeBlinkRight: 0.9 * ss(35.6, 35.9, T) } } : mix(mix(RELIEF, WORRY, ss(36.6, 37.2, T)), FEAR, ss(39.4, 40.6, T));
    if (T > 41.7) s.eyeY = 0.3 * Math.sin((T - 41.7) * 2.2);
  }
  return s;
}
function papaState(T) {     // celui de la chambre
  if (T < 9.2) return { pos: BP, yaw: 0, layers: IDLE(4 + T), face: talk(mix(SMILE, GRIN, ss(4.0, 5.4, T)), T, T < 0.8), tilt: 0.14 * ss(4.6, 5.8, T), look: 'hero' };
  if (T < 21.05) {
    const toW = Math.atan2(WPOS.x - PR.x, WPOS.z - PR.z), turn = ss(11.2, 12.0, T);
    return { pos: PR, yaw: lerp(-2.2, toW, turn), layers: IDLE(9 + T), face: talk(mix(SMILE, GRIN, ss(15.0, 16.3, T)), T, inR(T, 15.15, 16.35)), tilt: 0.12 * ss(15.2, 16.2, T), look: turn > 0.3 ? 'ward' : null };
  }
  if (T < 25.31) {
    const u = Math.min(1, ((T - 21.1) * WALKV) / PR.distanceTo(BN)), pos = PR.clone().lerp(BN, Math.max(0, u));
    return { pos, yaw: Math.atan2(WPOS.x - pos.x, WPOS.z - pos.z + 0.4), layers: u > 0 && u < 1 ? CLIP('slowwalk', T) : IDLE(9), face: talk(GRIN, T, inR(T, 24.2, 24.8)), tilt: 0.2 * ss(22.6, 23.8, T), lean: 0.5 * ss(22.7, 23.9, T), look: 'herohead' };
  }
  if (T < 26.27) return { pos: PR, yaw: Math.atan2(WPOS.x - PR.x, WPOS.z - PR.z) - 1.6 * ss(25.5, 26.2, T), layers: IDLE(9), face: GRIN, tilt: 0.1, look: 'hero' };
  if (T < 27.15) return null;
  if (T < 34.9) {           // il descend l'escalier, lentement
    const z = Math.max(4.9, 9.5 - WALKV * 0.95 * (T - 27.2)); return { pos: V(SX, yS(z), z), yaw: Math.PI, layers: z > 4.9 ? CLIP('slowwalk', T) : IDLE(9), face: GRIN, tilt: 0.16, look: 'hero' };
  }
  return { pos: PEND, yaw: Math.PI + 0.25, layers: IDLE(9 + T * 0.5), face: GRIN, tilt: 0.2, look: 'hero' };
}
function papa2State(T) {    // celui de la porte
  if (T < 31.0) return null;
  const u = ss(34.8, 35.75, T), pos = POUT.clone().lerp(PIN, u);
  return { pos, yaw: 0, layers: u > 0 && u < 1 ? CLIP('walk2', T) : IDLE(2 + Math.min(T, 36.1)), face: talk(DADOK, T, inR(T, 32.75, 34.85)), hug: ss(35.45, 36.1, T), look: 'hero' };
}
let T_ = 0;
function placePhone(h) {
  const fy = h.yaw; const fwd = V(Math.sin(fy), 0, Math.cos(fy)), right = V(Math.cos(fy), 0, -Math.sin(fy));
  const p = h.ppos ? h.ppos.clone() : h.pos.clone().addScaledVector(fwd, h.pdist).addScaledVector(right, -0.06).add(V(0, h.py, 0));
  if (inR(T_, 0.8, 1.5) || inR(T_, 36.55, 37.3)) p.add(V(Math.sin(T_ * 90) * 0.003, 0, Math.cos(T_ * 80) * 0.003));   // vibration
  phone.position.copy(p); phone.lookAt(h.pos.clone().add(V(0, 1.6, 0)).addScaledVector(fwd, 0.05));
  return p;
}
const screenState = (T) => (T < 0.82 ? 'off' : T < 30 ? 'hook' : T < 36.58 ? 'off' : 'final');

// ---------- caméra continue par lieu (clés : orbite f/az/el/d, vue subjective pov, ou position p / cible l) ----------
const FOC = {
  hero: () => _hw.clone(), papa: () => _pw.clone(), papa2: () => _p2w.clone(), mid: () => _hw.clone().lerp(_pw, 0.5),
  door: () => wp(glass).add(V(0, -0.1, 0)), doorway: () => V(0, 1.5, -0.2), phone: () => phone.position.clone(), eye: () => _hw.clone().add(V(0, 0.0, -0.06)),
};
const CAM = [
  // A — la chambre : l'accroche, d'un seul mouvement
  { t: 0.0, f: 'mid', az: -76, el: 2, d: 1.6, fov: 44 },
  { t: 0.7, f: 'mid', az: -100, el: 5, d: 1.25, fov: 44 },
  { t: 1.4, pov: 'phone', d: 0.31, fov: 36 },
  { t: 3.3, pov: 'phone', d: 0.25, fov: 36 },
  { t: 4.2, f: 'papa', az: 6, el: -2, d: 0.66, fov: 36 },
  { t: 5.35, f: 'papa', az: 2, el: -3, d: 0.6, fov: 34 },
  { t: 6.1, f: 'papa', az: -5, el: -3, d: 0.56, fov: 32 },
  { t: 6.55, f: 'mid', az: -92, el: 2, d: 1.75, fov: 48 },
  { t: 7.05, f: 'hero', az: 207, el: 2, d: 0.6, fov: 36 },
  { t: 8.0, f: 'hero', az: 198, el: 0, d: 0.52, fov: 34 },
  { t: 9.19, f: 'hero', az: 191, el: 0, d: 0.45, fov: 32 },
  // B — rappel : dans l'armoire
  { t: 9.2, cut: 1, f: 'hero', az: 180, el: 3, d: 0.85, fov: 24 },
  { t: 10.6, f: 'hero', az: 183, el: 2, d: 0.7, fov: 22 },
  // C — vu de l'armoire : celui de la chambre
  { t: 10.62, cut: 1, p: () => V(WPOS.x + 0.05, 1.5, WZ - 0.12), l: () => FOC.papa().add(V(0, -0.25, 0)), fov: 50 },
  { t: 12.26, p: () => V(WPOS.x - 0.05, 1.55, WZ - 0.3), l: () => FOC.papa().add(V(0, -0.1, 0)), fov: 36 },
  // D — la porte d'entrée : on cogne
  { t: 12.27, cut: 1, f: 'door', az: 9, el: 2, d: 1.7, fov: 40 },
  { t: 15.15, f: 'door', az: -1, el: 0, d: 0.9, fov: 34 },
  // E — « Ich bin dein Vater »
  { t: 15.17, cut: 1, p: () => FOC.eye(), l: () => FOC.papa(), fov: 32 },
  { t: 16.5, p: () => FOC.eye(), l: () => FOC.papa(), fov: 26 },
  // F — son visage pendant le choix
  { t: 16.52, cut: 1, f: 'hero', az: 178, el: 3, d: 0.85, fov: 24 },
  { t: 21.0, f: 'hero', az: 182, el: 3, d: 0.85, fov: 20 },
  // G — mauvaise fin : la porte de l'armoire s'ouvre
  { t: 21.02, cut: 1, p: () => FOC.eye(), l: () => FOC.papa(), fov: 52 },
  { t: 22.4, p: () => FOC.eye(), l: () => FOC.papa(), fov: 48 },
  { t: 23.7, p: () => FOC.eye(), l: () => FOC.papa(), fov: 42 },
  { t: 24.84, p: () => FOC.eye(), l: () => FOC.papa(), fov: 26 },
  // H — il sort en courant
  { t: 25.31, cut: 1, f: 'hero', az: 150, el: 8, d: 1.7, fov: 50 },
  { t: 26.26, f: 'hero', az: 118, el: 4, d: 1.25, fov: 50 },
  // I — l'escalier, puis celui qui descend
  { t: 26.27, cut: 1, f: 'hero', az: 180, el: -6, d: 1.0, fov: 46 },
  { t: 27.15, f: 'hero', az: 186, el: -4, d: 0.8, fov: 44 },
  { t: 27.95, p: () => V(0.5, 1.3, 3.3), l: () => FOC.papa(), fov: 42 },
  { t: 29.2, p: () => V(0.45, 1.2, 3.5), l: () => FOC.papa(), fov: 34 },
  { t: 30.6, p: () => V(0.35, 1.15, 3.9), l: () => FOC.papa(), fov: 26 },
  // J — la porte : Papa, l'étreinte, le message — sans coupe
  { t: 30.7, cut: 1, f: 'hero', az: 15, el: 6, d: 1.0, lk: 'doorway', fov: 48 },
  { t: 31.5, f: 'hero', az: 28, el: 8, d: 1.0, lk: 'doorway', fov: 46 },
  { t: 32.3, f: 'papa2', az: 6, el: -2, d: 0.95, fov: 36 },
  { t: 34.6, f: 'papa2', az: -4, el: -2, d: 0.62, fov: 32 },
  { t: 34.94, f: 'papa2', az: -6, el: -2, d: 0.58, fov: 32 },
  { t: 34.95, cut: 1, f: 'hero', az: 126, el: 10, d: 0.58, fov: 46 },
  { t: 36.25, f: 'hero', az: 150, el: 10, d: 0.85, fov: 38 },
  { t: 37.3, f: 'hero', az: 148, el: 9, d: 0.72, fov: 32 },
  { t: 38.6, pov: 'phone', d: 0.27, fov: 36 },
  { t: 41.0, pov: 'phone', d: 0.22, fov: 36 },
  { t: 42.0, f: 'hero', az: 149, el: 9, d: 0.76, fov: 36 },
  { t: 48.3, f: 'hero', az: 148, el: 8, d: 0.74, fov: 24 },
];
const HIDE_HERO = [[1.25, 3.75], [10.6, 12.27], [15.15, 16.51], [21.0, 25.3], [38.1, 41.45]];
const DEG = Math.PI / 180;
function keyVec(k) {
  if (k.pov) {
    const n = V(0, 0, 1).applyQuaternion(phone.quaternion), up = V(0, 1, 0).applyQuaternion(phone.quaternion), F = phone.position.clone();
    const az = Math.atan2(n.x, n.z) / DEG, el = Math.asin(Math.max(-1, Math.min(1, n.y))) / DEG, L = F.clone().addScaledVector(up, 0.012);
    return [F.x, F.y, F.z, az, el, k.d, L.x, L.y, L.z, k.fov, 1];
  }
  if (k.p) { const F = k.p(), L = k.l(); return [F.x, F.y, F.z, 0, 0, 0, L.x, L.y, L.z, k.fov, 0]; }
  const F = FOC[k.f](), L = k.lk ? FOC[k.lk]() : F.clone(); L.y += k.h || 0;
  return [F.x, F.y, F.z, k.az, k.el, k.d, L.x, L.y, L.z, k.fov, 0];
}
function camAt(T) {
  let i = 0; while (i < CAM.length - 1 && CAM[i + 1].t <= T) i++;
  let s0 = i; while (s0 > 0 && !CAM[s0].cut) s0--;
  let s1 = i; while (s1 < CAM.length - 1 && !CAM[s1 + 1].cut) s1++;
  const ids = [Math.max(s0, i - 1), i, Math.min(s1, i + 1), Math.min(s1, i + 2)];
  const Vs = ids.map(j => keyVec(CAM[j]));
  const same = (a, b) => (a.pov && b.pov) || (a.p && b.p);
  if (same(CAM[ids[1]], CAM[ids[2]])) { Vs[0] = Vs[1]; Vs[3] = Vs[2]; }
  const ty = (k) => (k.pov ? 'v' : k.p ? 'p' : 'o');   // pas de tangente tirée par une clé d'un autre type (cible parfois hors champ)
  if (ty(CAM[ids[0]]) !== ty(CAM[ids[1]])) Vs[0] = Vs[1];
  if (ty(CAM[ids[3]]) !== ty(CAM[ids[2]])) Vs[3] = Vs[2];
  for (let j = 1; j < 4; j++) { while (Vs[j][3] - Vs[j - 1][3] > 180) Vs[j][3] -= 360; while (Vs[j][3] - Vs[j - 1][3] < -180) Vs[j][3] += 360; }
  const t0 = CAM[ids[1]].t, t1 = CAM[ids[2]].t; const u = ids[2] === ids[1] ? 0 : Math.min(1, Math.max(0, (T - t0) / (t1 - t0)));
  const cr = (a, b, c, d) => 0.5 * ((2 * b) + (-a + c) * u + (2 * a - 5 * b + 4 * c - d) * u * u + (-a + 3 * b - 3 * c + d) * u * u * u);
  const v = Vs[0].map((_, j) => cr(Vs[0][j], Vs[1][j], Vs[2][j], Vs[3][j]));
  const az = v[3] * DEG, el = v[4] * DEG, d = Math.max(0, v[5]);
  const pos = V(v[0] + Math.sin(az) * Math.cos(el) * d, v[1] + Math.sin(el) * d, v[2] + Math.cos(az) * Math.cos(el) * d);
  const up = V(0, 1, 0); const w = Math.min(1, Math.max(0, v[10]));
  if (w > 0) up.lerp(V(0, 1, 0).applyQuaternion(phone.quaternion), w).normalize();
  return { pos, tgt: V(v[6], v[7], v[8]), fov: v[9], up };
}
function posePapa(P, ps, out, T) {
  P.root.position.copy(ps.pos); P.root.rotation.y = ps.yaw;
  const look = ps.look === 'hero' || ps.look === 'herohead' ? _hw : ps.look === 'ward' ? V(WPOS.x, 1.55, WPOS.z) : null;
  const pose = { mo: ps.layers, lookW: 1, headZ: ps.tilt || 0, spineX: ps.lean || 0 };
  if (ps.hug > 0) {     // les bras autour du fils
    Object.assign(pose, { rW: ps.hug, rwx: HG.x + 0.2, rwy: 1.12, rwz: HG.z + 0.2, rCurl: 0.3, lW: ps.hug, lwx: HG.x - 0.2, lwy: 1.04, lwz: HG.z + 0.2, lCurl: 0.3 });
  }
  P.setPose(pose, ps.face, look, T); P.headWorld(out);
}

function frame(T) {
  T_ = T;
  // porte d'entrée : coups, ouverture
  let shake = 0; for (const k of POUND) if (T > k && T < k + 0.12) shake = Math.max(shake, (1 - (T - k) / 0.12) * 1.8);
  hinge.rotation.y = -1.56 * ss(31.25, 31.85, T); door.position.z = -0.006 * shake; door.rotation.y = 0.004 * shake;
  drawGlass(inR(T, 9, 31.6) ? 1 : 0); setClock('02:21');
  // armoire : ouverte pendant l'accroche, fermée ensuite, s'ouvre pour la mauvaise fin, puis d'un coup quand il sort
  const op = T < 9.2 ? 1 : T < 25.3 ? ss(22.5, 23.7, T) : ss(25.31, 25.5, T);
  leaves[0].rotation.y = -1.45 * op; leaves[1].rotation.y = 1.45 * op;
  bHinge.rotation.y = -1.2; hallL.intensity = 5;
  // le fils
  const h = heroState(T);
  HERO.root.position.copy(h.pos); HERO.root.rotation.y = h.yaw;
  phone.visible = h.phone > 0; phoneL.intensity = 0;
  const pose = { mo: h.layers, lookW: 0.85 };
  let look = h.look === 'papa' ? _pw.clone() : h.look === 'papa2' ? _p2w.clone() : h.look;
  if (h.phone) {
    const p = placePhone(h); drawScreen(screenState(T));
    const fy = h.yaw, back = V(Math.sin(fy), 0, Math.cos(fy)).multiplyScalar(0.045);
    Object.assign(pose, { rW: 1, rwx: p.x + back.x, rwy: p.y - 0.115, rwz: p.z + back.z, rCurl: 0.55, rWrX: -0.4 });
    const lit = screenState(T) !== 'off';
    phoneL.position.copy(p).add(V(0, 0.1, 0)).addScaledVector(V(Math.sin(fy), 0, Math.cos(fy)), -0.12); phoneL.intensity = lit ? 1.3 : 0;
    const other = h.lookA === 'papa' ? _pw.clone() : _p2w.clone().add(V(0.3, -0.1, 0));
    look = other.lerp(p, h.lookMix ?? 1);
  }
  if (h.reach > 0) { const k = wp(knob); Object.assign(pose, { rW: h.reach, rwx: k.x + 0.02, rwy: k.y, rwz: k.z + 0.1, rCurl: 0.4 }); }
  HERO.setPose(pose, { ...h.face, eyeY: h.eyeY || 0 }, look, T);
  HERO.headWorld(_hw);
  if (h.mouth > 0) {   // main sur la bouche
    const f = V(Math.sin(h.yaw), 0, Math.cos(h.yaw)), m = _hw.clone().addScaledVector(f, 0.1).add(V(0, -0.115, 0));
    Object.assign(pose, { lW: h.mouth, lwx: m.x, lwy: m.y, lwz: m.z, lCurl: 0.25 });
    HERO.setPose(pose, { ...h.face, eyeY: h.eyeY || 0 }, look, T); HERO.headWorld(_hw);
  }
  // les deux pères
  const ps = papaState(T); PAPA.root.visible = !!ps; if (ps) posePapa(PAPA, ps, _pw, T);
  const p2 = papa2State(T); PAPA2.root.visible = !!p2; if (p2) posePapa(PAPA2, p2, _p2w, T);
  if (ps && T < 9.2) { HERO.setPose(pose, { ...h.face, eyeY: h.eyeY || 0 }, look, T); HERO.headWorld(_hw); }   // (le regard du fils dépend de la tête du père)
  underL.intensity = ps ? (T > 34.9 ? 5 : 9) : 0;
  if (ps) { const f = V(Math.sin(ps.yaw), 0, Math.cos(ps.yaw)); underL.position.copy(_pw).add(V(0, -0.8, 0)).addScaledVector(f, 0.35); underL.target.position.copy(_pw); }
  // lumières
  tvL.intensity = 2.2 + 1.2 * Math.sin(T * 13) * Math.sin(T * 5.3); tvL.color.setHSL(0.6 + 0.04 * Math.sin(T * 3), 0.6, 0.6);
  lamp.intensity = 0.6; streetL.intensity = T > 31.3 ? 2 : 3; porchL.intensity = 7; upL.intensity = inR(T, 27, 31) && Math.sin(T * 29) * Math.sin(T * 7) > 0.6 ? 1.5 : 5;
  // caméra
  const c = camAt(T);
  const run = inR(T, 25.31, 27.6) || inR(T, 30.45, 31.3);
  const hand = run ? 0.014 : T < 9.2 ? 0.007 : 0.004;
  let kick = 0; for (const k of POUND) if (T > k && T < k + 0.15) kick = Math.max(kick, 1 - (T - k) / 0.15);
  camera.position.copy(c.pos).add(V(Math.sin(T * 7.1) * hand + Math.sin(T * 41) * kick * 0.01 + (run ? Math.sin(T * 19) * 0.01 : 0), Math.sin(T * 9.3) * hand + Math.cos(T * 37) * kick * 0.008 + (run ? Math.abs(Math.sin(T * 8.6)) * 0.02 : 0), Math.sin(T * 5.7) * hand));
  camera.up.copy(c.up); camera.lookAt(c.tgt); camera.fov = c.fov;
  HERO.root.visible = camera.position.distanceTo(_hw) > 0.2 && !HIDE_HERO.some(([a, b]) => inR(T, a, b));
  if (ps) PAPA.root.visible = camera.position.distanceTo(_pw) > 0.2;
  if (p2) PAPA2.root.visible = camera.position.distanceTo(_p2w) > 0.2;
  fillL.position.copy(camera.position).add(V(0, 0.2, 0)); fillL.target.position.copy(c.tgt); fillL.intensity = inR(T, 9.2, 25.3) ? 0.6 : inR(T, 27.6, 30.7) ? 0.5 : 1.8;
  const w2 = innerWidth, h2 = innerHeight;
  if (canvas.width !== w2) renderer.setSize(w2, h2, false);
  camera.aspect = w2 / h2; camera.updateProjectionMatrix();
  renderer.render(scene, camera);
}
window.renderAt = (T) => frame(T);
window.READY = true;
if (!MANUAL) { const c0 = performance.now(); const loop = () => { frame(((performance.now() - c0) / 1000) % END); requestAnimationFrame(loop); }; loop(); }
else frame(0);
