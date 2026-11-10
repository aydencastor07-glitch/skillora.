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
  const gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, '#1b2a44'); gr.addColorStop(1, '#070a12'); g.fillStyle = state === 'off' ? '#020203' : gr; g.fillRect(0, 0, w, h);
  if (state === 'off') { scrTex.needsUpdate = true; return; }
  g.fillStyle = '#e9edf3'; g.font = '600 30px Arial'; g.textAlign = 'left'; g.fillText('02:27', 36, 52);
  g.textAlign = 'center'; g.fillStyle = '#9fb0c8'; g.font = '38px Arial'; g.fillText(state === 'call' ? 'Eingehender Anruf' : 'Anruf · 00:0' + state.slice(-1), w / 2, 190);
  g.fillStyle = '#3a6fd8'; g.beginPath(); g.arc(w / 2, 380, 120, 0, 7); g.fill(); g.fillStyle = '#fff'; g.font = 'bold 120px Arial'; g.fillText('P', w / 2, 422);
  g.font = 'bold 76px Arial'; g.fillText('Papa', w / 2, 600);
  if (state === 'call') {
    g.fillStyle = '#e0352b'; g.beginPath(); g.arc(w / 2 - 140, 940, 72, 0, 7); g.fill(); g.fillStyle = '#2fbf5b'; g.beginPath(); g.arc(w / 2 + 140, 940, 72, 0, 7); g.fill();
    g.fillStyle = '#fff'; g.fillRect(w / 2 - 172, 932, 64, 16); g.fillRect(w / 2 + 108, 932, 64, 16); g.fillRect(w / 2 + 132, 908, 16, 64);
  }
  scrTex.needsUpdate = true;
}
drawScreen('off');
const scr = new THREE.Mesh(new THREE.PlaneGeometry(0.068, 0.14), new THREE.MeshBasicMaterial({ map: scrTex, toneMapped: false }));
scr.position.z = 0.0047; phone.add(scr);
const phoneL = new THREE.PointLight('#9fc0ff', 0, 0.9, 2); scene.add(phoneL);

// ---------- personnages ----------
await RealHuman.loadClips(['idle', 'slowwalk', 'run2', 'backaway'], './mocap/');
const HERO = await RealHuman.create('./models/kid.glb', { heightM: 1.72, seed: 2 });
const PAPA = await RealHuman.create('./models/judge.glb', { heightM: 1.86, seed: 4 });    // celui de l'escalier
const PAPA2 = await RealHuman.create('./models/judge.glb', { heightM: 1.86, seed: 7 });   // celui qui le tient
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
const RELIEF = { maxM: 1.2, raw: { MouthSmileLeft: 0.45, MouthSmileRight: 0.45, BrowInnerUp: 1.0, EyeSquintLeft: 0.4, EyeSquintRight: 0.4, JawOpen: 0.15 } };
const GRIN = { maxM: 2, raw: { MouthSmileLeft: 1.9, MouthSmileRight: 1.9, CheekSquintLeft: 0.6, CheekSquintRight: 0.6, MouthStretchLeft: 0.9, MouthStretchRight: 0.9, MouthUpperUpLeft: 0.5, MouthUpperUpRight: 0.5, EyeWideLeft: 1.2, EyeWideRight: 1.2, MouthLowerDownLeft: 0.4, MouthLowerDownRight: 0.4 } };
const DADOK = { maxM: 1.2, raw: { BrowInnerUp: 0.5, MouthSmileLeft: 0.45, MouthSmileRight: 0.45, EyeSquintLeft: 0.2, EyeSquintRight: 0.2 } };
const mix = (a, b, u) => { const r = {}; for (const k of new Set([...Object.keys(a.raw || {}), ...Object.keys(b.raw || {})])) r[k] = lerp((a.raw || {})[k] || 0, (b.raw || {})[k] || 0, u); return { maxM: Math.max(a.maxM || 1, b.maxM || 1), raw: r }; };
const talk = (f, T, on) => (on ? { maxM: f.maxM || 1, raw: { ...f.raw, JawOpen: 0.12 + 0.3 * Math.abs(Math.sin(T * 12.5)) * (0.6 + 0.4 * Math.sin(T * 4.1)) } } : f);
const _hw = new THREE.Vector3(), _pw = new THREE.Vector3(), _p2w = new THREE.Vector3();
const wp = (o) => o.getWorldPosition(new THREE.Vector3());
const yS = (z) => (z < 5.865 ? 0 : Math.min(2.38, ((z - 5.865) / 0.27) * 0.19 + 0.04));      // escalier
const yOut = (z) => (z > -1.98 ? 0 : z > -2.4 ? -0.16 : z > -2.8 ? -0.32 : -0.48);           // perron, marches, allée

// ---------- chronologie (temps de la voix, words.json) ----------
const HG = V(0.1, 0, 1.42), PIN = V(0.0, 0, 0.93), PST = V(-HW + 0.48, yS(7.0), 7.0);
const RUN = [V(0.1, 0, 1.42), V(0.6, 0, 1.05), V(0.1, 0, -0.3), V(0.0, 0, -1.9), V(0.0, 0, -2.9), V(0.15, 0, -9.0)];
const RUN0 = 32.6, END = 46.6;
const RUNV = RealHuman.clips.run2.speed * 0.9, WALKV = RealHuman.clips.slowwalk.speed * 0.9;
const RUNL = RUN.slice(1).map((p, i) => p.distanceTo(RUN[i])), RUNT = RUNL.reduce((a, b) => a + b, 0);
const GATE = RUN[RUN.length - 1];
function runAt(T) {          // position et direction le long du trajet de fuite
  let d = Math.max(0, (T - RUN0) * RUNV);
  if (d >= RUNT) return { pos: GATE.clone(), dir: GATE.clone().sub(RUN[RUN.length - 2]).normalize(), done: true };
  for (let i = 0; i < RUNL.length; i++) { if (d <= RUNL[i]) { const p = RUN[i].clone().lerp(RUN[i + 1], d / RUNL[i]); return { pos: p, dir: RUN[i + 1].clone().sub(RUN[i]).normalize(), done: false }; } d -= RUNL[i]; }
}
function heroState(T) {
  const s = { pos: HG.clone(), yaw: Math.PI, layers: IDLE(T), face: RELIEF, look: 'papa2', phone: 0 };
  if (T < 32.0) {
    // dans les bras : sonnerie (téléphone dans la main), il décroche, l'oreille ; il raccroche dans la mauvaise fin
    if (inR(T, 2.1, 3.25)) { s.phone = 'hand'; s.look = 'phone'; s.face = mix(RELIEF, WORRY, ss(2.3, 3.0, T)); }
    else if (T >= 3.25 && !inR(T, 26.6, 31.3)) { s.phone = 'ear'; s.face = mix(WORRY, FEAR, ss(4.8, 6.8, T)); s.look = T < 7.4 ? null : 'papa2'; }
    else if (T >= 26.6) { s.phone = 'hand'; s.face = mix(FEAR, { maxM: 1.2, raw: { ...FEAR.raw, EyeBlinkLeft: 0.3, EyeBlinkRight: 0.3 } }, ss(29.4, 30.5, T)); s.look = 'papa2'; }
    if (inR(T, 7.4, 26.0)) s.face = FEAR;
    if (inR(T, 17.7, 21.3)) s.look = null;   // il fixe le vide pendant qu'on lui parle à l'oreille
    if (inR(T, 21.3, 25.9)) { s.look = null; s.eyeY = 0.28 * Math.sin((T - 21.3) * 2.0); }
    return s;
  }
  if (T < RUN0) {           // il se dégage
    const u = ss(32.0, 32.6, T); s.pos = HG.clone().add(V(0.12 * u, 0, 0.1 * u)); s.layers = [{ clip: 'backaway', mode: 'abs', t: (T - 32.0) * 0.6, k: 1, w: FULL }]; s.face = FEAR; s.look = 'papa2'; s.phone = 'hand';
    return s;
  }
  const r = runAt(T);
  s.pos = r.pos.clone(); s.pos.y = yOut(r.pos.z); s.yaw = Math.atan2(r.dir.x, r.dir.z); s.face = FEAR; s.look = null;
  if (!r.done) { s.layers = CLIP('run2', T); s.phone = 'hand'; return s; }
  s.yaw = Math.PI; s.layers = IDLE(T * 0.7); s.phone = T > 35.9 ? 'ear' : 'hand';
  if (T > 41.0) s.eyeY = 0.3 * Math.sin((T - 41.0) * 2.4);
  return s;
}
function papa2State(T) {    // celui qui le tient
  if (T < 32.0) {
    const lean = ss(17.9, 19.6, T) * (1 - ss(21.2, 21.9, T)), tight = ss(29.4, 30.3, T);
    let face = mix(DADOK, GRIN, ss(8.8, 10.3, T));
    if (inR(T, 11.3, 17.7)) face = GRIN;
    face = talk(face, T, inR(T, 20.38, 21.1) || inR(T, 28.62, 29.3));
    return { pos: PIN, yaw: 0, layers: IDLE(2 + T * 0.3), face, hug: 1, tight, tilt: 0.12 * ss(9.0, 10.3, T) + 0.18 * lean, lean: 0.35 * lean + 0.15 * tight, look: lean > 0.3 ? 'ear' : 'hero' };
  }
  if (T < 38.0) { const r = ss(32.0, 32.9, T); return { pos: PIN, yaw: lerp(0, 2.6, r), layers: IDLE(9), face: GRIN, hug: 1 - ss(32.0, 32.4, T), tilt: 0.15, look: 'hero' }; }
  const z = Math.max(-7.6, -0.4 - WALKV * (T - 38.0)), pos = V(0.05, yOut(z), z);
  return { pos, yaw: Math.PI, layers: z > -7.6 ? CLIP('slowwalk', T) : IDLE(9 + T * 0.3), face: GRIN, tilt: 0.16, look: 'hero' };
}
function papaState(T) {     // celui de l'escalier
  if (!inR(T, 12.4, 15.6)) return null;
  return { pos: PST, yaw: Math.PI, layers: IDLE(5 + T * 0.4), face: GRIN, tilt: 0.14, look: 'hero' };
}
const screenState = (T) => (T < 2.1 ? 'off' : T < 3.25 ? 'call' : T < 26.6 ? 'off' : T < 31.3 ? 'call' : 'off');

// ---------- caméra continue par lieu ----------
const FOC = {
  hero: () => _hw.clone(), papa: () => _pw.clone(), papa2: () => _p2w.clone(), mid: () => _hw.clone().lerp(_p2w, 0.5),
  door: () => wp(glass).add(V(0, -0.1, 0)), phone: () => phone.position.clone(), feet: () => HERO.root.position.clone().add(V(0, 0.2, 0)),
};
const CAM = [
  // A — le câlin, l'appel, la révélation (d'un seul mouvement)
  { t: 0.0, f: 'mid', az: 34, el: 8, d: 1.55, fov: 46 },
  { t: 1.3, f: 'mid', az: 48, el: 12, d: 1.2, fov: 44 },
  { t: 2.15, f: 'phone', az: 25, el: 50, d: 0.42, fov: 40 },
  { t: 2.95, f: 'hero', az: 128, el: 12, d: 0.75, fov: 40 },
  { t: 4.6, f: 'hero', az: 150, el: 9, d: 0.7, fov: 36 },
  { t: 6.4, f: 'hero', az: 165, el: 8, d: 0.62, fov: 34 },
  { t: 7.45, f: 'papa2', az: 28, el: 2, d: 0.95, fov: 36 },
  { t: 9.3, f: 'papa2', az: 14, el: 0, d: 0.62, fov: 31 },
  { t: 11.36, f: 'papa2', az: 8, el: -1, d: 0.45, fov: 28 },
  // B — « Teil drei » : son visage, puis le plan large
  { t: 11.37, cut: 1, f: 'hero', az: 128, el: 10, d: 0.8, fov: 36 },
  { t: 12.45, f: 'mid', az: 28, el: 22, d: 1.9, fov: 46 },
  { t: 13.95, f: 'mid', az: 18, el: 26, d: 2.3, fov: 46 },
  // C — celui de l'escalier
  { t: 13.97, cut: 1, p: () => V(0.5, 1.35, 3.6), l: () => FOC.papa(), fov: 40 },
  { t: 15.54, p: () => V(0.42, 1.4, 4.2), l: () => FOC.papa(), fov: 32 },
  // D — la porte : quelqu'un dehors
  { t: 15.56, cut: 1, f: 'door', az: 62, el: 2, d: 0.95, fov: 44 },
  { t: 17.7, f: 'door', az: 50, el: 0, d: 0.7, fov: 38 },
  // E — il se penche à son oreille
  { t: 17.74, cut: 1, f: 'hero', az: 122, el: 8, d: 0.85, fov: 38 },
  { t: 19.7, f: 'hero', az: 140, el: 7, d: 0.6, fov: 34 },
  { t: 21.3, f: 'hero', az: 146, el: 7, d: 0.52, fov: 32 },
  // F — le choix : son visage
  { t: 21.34, cut: 1, f: 'hero', az: 150, el: 8, d: 0.74, fov: 30 },
  { t: 25.9, f: 'hero', az: 156, el: 7, d: 0.66, fov: 26 },
  // G — mauvaise fin
  { t: 25.96, cut: 1, f: 'mid', az: 110, el: 8, d: 1.2, fov: 40 },
  { t: 27.4, f: 'papa2', az: 34, el: 2, d: 0.7, fov: 34 },
  { t: 28.6, f: 'papa2', az: 24, el: 1, d: 0.5, fov: 30 },
  { t: 29.4, f: 'mid', az: 90, el: 14, d: 1.4, fov: 42 },
  { t: 31.0, f: 'mid', az: 80, el: 20, d: 2.0, fov: 44 },
  // H — il se dégage et court vers la porte
  { t: 32.0, cut: 1, f: 'mid', az: 72, el: 8, d: 1.6, fov: 46 },
  { t: 32.9, f: 'hero', az: 40, el: 8, d: 1.5, fov: 50 },
  { t: 33.88, f: 'hero', az: 12, el: 8, d: 1.6, fov: 52 },
  // I — « Barfuß »
  { t: 33.91, cut: 1, f: 'hero', az: 180, el: -4, d: 1.9, fov: 48 },
  { t: 34.67, f: 'hero', az: 172, el: -2, d: 1.7, fov: 46 },
  // J — la rue vide
  { t: 34.69, cut: 1, f: 'hero', az: 10, el: 12, d: 2.4, fov: 52 },
  { t: 36.06, f: 'hero', az: 18, el: 10, d: 2.1, fov: 50 },
  // K — au téléphone : « Ich seh dich »
  { t: 36.08, cut: 1, f: 'hero', az: 180, el: 4, d: 0.95, fov: 32 },
  { t: 38.29, f: 'hero', az: 186, el: 3, d: 0.78, fov: 30 },
  // L — derrière lui : quelqu'un sort de la maison
  { t: 38.31, cut: 1, p: () => V(1.25, 0.75, -6.4), l: () => FOC.papa2().add(V(0, -0.3, 0)), fov: 40 },
  { t: 41.25, p: () => V(1.1, 0.7, -6.0), l: () => FOC.papa2().add(V(0, -0.2, 0)), fov: 30 },
  // M — le dernier choix : son visage, la silhouette derrière
  { t: 41.27, cut: 1, f: 'hero', az: 176, el: 3, d: 1.05, fov: 30 },
  { t: 46.6, f: 'hero', az: 180, el: 2, d: 0.72, fov: 26 },
];
const HIDE_HERO = [[13.97, 17.73], [38.31, 41.26]];
const DEG = Math.PI / 180;
function keyVec(k) {
  if (k.p) { const F = k.p(), L = k.l(); return [F.x, F.y, F.z, 0, 0, 0, L.x, L.y, L.z, k.fov]; }
  const F = FOC[k.f](), L = k.lk ? FOC[k.lk]() : F.clone(); L.y += k.h || 0;
  return [F.x, F.y, F.z, k.az, k.el, k.d, L.x, L.y, L.z, k.fov];
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
  return { pos: V(v[0] + Math.sin(az) * Math.cos(el) * d, v[1] + Math.sin(el) * d, v[2] + Math.cos(az) * Math.cos(el) * d), tgt: V(v[6], v[7], v[8]), fov: v[9] };
}
function posePapa(P, ps, out, T) {
  P.root.position.copy(ps.pos); P.root.rotation.y = ps.yaw;
  const ear = _hw.clone().add(V(0.06, 0.0, 0.02));
  const look = ps.look === 'hero' ? _hw : ps.look === 'ear' ? ear : null;
  const pose = { mo: ps.layers, lookW: 1, headZ: ps.tilt || 0, spineX: ps.lean || 0 };
  if (ps.hug > 0) {     // les bras autour du fils (plus serrés dans la mauvaise fin)
    const tg = ps.tight || 0;
    Object.assign(pose, { rW: ps.hug, rwx: HG.x + 0.2 - 0.05 * tg, rwy: 1.12 + 0.12 * tg, rwz: HG.z + 0.2, rCurl: 0.3 + 0.4 * tg, lW: ps.hug, lwx: HG.x - 0.2 + 0.05 * tg, lwy: 1.04 + 0.14 * tg, lwz: HG.z + 0.2, lCurl: 0.3 + 0.4 * tg });
  }
  P.setPose(pose, ps.face, look, T); P.headWorld(out);
}

function frame(T) {
  // porte d'entrée : fermée, puis ouverte quand il s'enfuit ; silhouette derrière le verre pendant l'appel
  hinge.rotation.y = -1.56 * ss(32.75, 33.15, T);
  drawGlass(inR(T, 3.2, 32.8) ? 1 : 0); setClock('02:27');
  const op = 1; leaves[0].rotation.y = -1.45 * op; leaves[1].rotation.y = 1.45 * op; bHinge.rotation.y = -1.2; hallL.intensity = 5;
  // les deux hommes d'abord (le fils regarde celui qui le tient)
  const ps = papaState(T); PAPA.root.visible = !!ps; if (ps) posePapa(PAPA, ps, _pw, T);
  // le fils
  const h = heroState(T);
  HERO.root.position.copy(h.pos); HERO.root.rotation.y = h.yaw;
  const fwd = V(Math.sin(h.yaw), 0, Math.cos(h.yaw)), side = V(-Math.cos(h.yaw), 0, Math.sin(h.yaw));   // side : côté de la main droite
  const pose = { mo: h.layers, lookW: 0.85 };
  const lookOf = (k) => (k === 'papa2' ? _p2w.clone() : k === 'phone' ? phone.position.clone() : k);
  HERO.setPose(pose, { ...h.face, eyeY: h.eyeY || 0 }, lookOf(h.look), T); HERO.headWorld(_hw);
  phone.visible = !!h.phone; phoneL.intensity = 0;
  if (h.phone) {
    let p;
    if (h.phone === 'ear') { p = _hw.clone().addScaledVector(side, -0.08).addScaledVector(fwd, -0.04).add(V(0, -0.04, 0)); phone.position.copy(p); phone.lookAt(_hw.clone().add(V(0, -0.035, 0))); }
    else {
      p = h.pos.clone().addScaledVector(fwd, 0.3).addScaledVector(side, 0.08).add(V(0, h.pos.y > -0.1 ? 1.12 : 1.12, 0));
      if (inR(T, 2.1, 3.25)) p.add(V(Math.sin(T * 90) * 0.003, 0, Math.cos(T * 80) * 0.003));   // vibration
      phone.position.copy(p); phone.lookAt(_hw);
    }
    drawScreen(screenState(T));
    if (h.phone === 'ear') { const out = side.clone().multiplyScalar(-0.03); Object.assign(pose, { lW: 1, lwx: p.x + out.x, lwy: p.y - 0.05, lwz: p.z + out.z, lCurl: 0.55, lWrX: -0.4 }); }
    else { const out = fwd.clone().multiplyScalar(0.045); Object.assign(pose, { rW: 1, rwx: p.x + out.x, rwy: p.y - 0.11, rwz: p.z + out.z, rCurl: 0.55, rWrX: -0.4 }); }
    phoneL.position.copy(p).addScaledVector(fwd, 0.1); phoneL.intensity = screenState(T) !== 'off' ? 1.3 : 0;
    HERO.setPose(pose, { ...h.face, eyeY: h.eyeY || 0 }, lookOf(h.look), T); HERO.headWorld(_hw);
  }
  const p2 = papa2State(T); PAPA2.root.visible = !!p2; if (p2) posePapa(PAPA2, p2, _p2w, T);
  // lumières : plus sombres pendant la mauvaise fin
  const dim = 1 - 0.85 * ss(29.6, 30.9, T) * (T < 32 ? 1 : 0);
  underL.intensity = (p2 ? 7 : 0) * dim; if (p2) { const f = V(Math.sin(p2.yaw), 0, Math.cos(p2.yaw)); underL.position.copy(_p2w).add(V(0, -0.8, 0)).addScaledVector(f, 0.35); underL.target.position.copy(_p2w); }
  tvL.intensity = dim * (2.2 + 1.2 * Math.sin(T * 13) * Math.sin(T * 5.3)); tvL.color.setHSL(0.6 + 0.04 * Math.sin(T * 3), 0.6, 0.6);
  lamp.intensity = 0.6 * dim; streetL.intensity = 3 * dim; porchL.intensity = 7; hemi.intensity = 0.32 * dim; moon.intensity = 0.35 * dim;
  upL.intensity = 5 * dim;
  // caméra
  const c = camAt(T);
  if (c.pos.z > -0.1 && c.pos.z < 8.2 && c.pos.x < 3) { c.pos.x = Math.max(-0.82, Math.min(0.82, c.pos.x)); c.pos.y = Math.min(2.4, c.pos.y); }   // reste dans le couloir
  const run = inR(T, RUN0, 36.1);
  const hand = run ? 0.014 : T < 11.4 ? 0.006 : 0.004;
  camera.position.copy(c.pos).add(V(Math.sin(T * 7.1) * hand + (run ? Math.sin(T * 19) * 0.01 : 0), Math.sin(T * 9.3) * hand + (run ? Math.abs(Math.sin(T * 8.6)) * 0.02 : 0), Math.sin(T * 5.7) * hand));
  camera.up.set(0, 1, 0); camera.lookAt(c.tgt); camera.fov = c.fov;
  HERO.root.visible = camera.position.distanceTo(_hw) > 0.2 && !HIDE_HERO.some(([a, b]) => inR(T, a, b));
  if (p2) PAPA2.root.visible = camera.position.distanceTo(_p2w) > 0.2;
  fillL.position.copy(camera.position).add(V(0, 0.2, 0)); fillL.target.position.copy(c.tgt); fillL.intensity = (T > 34 ? 1.2 : 1.8) * dim;
  const w2 = innerWidth, h2 = innerHeight;
  if (canvas.width !== w2) renderer.setSize(w2, h2, false);
  camera.aspect = w2 / h2; camera.updateProjectionMatrix();
  renderer.render(scene, camera);
}
window.renderAt = (T) => frame(T);
window.dbg = (T) => { frame(T); const r = (v) => [v.x, v.y, v.z].map(x => +x.toFixed(2)); return { cam: r(camera.position), hero: r(_hw), p2: r(_p2w), heroPos: r(HERO.root.position) }; };
window.READY = true;
if (!MANUAL) { const c0 = performance.now(); const loop = () => { frame(((performance.now() - c0) / 1000) % END); requestAnimationFrame(loop); }; loop(); }
else frame(0);
