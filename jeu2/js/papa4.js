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

// ---------- le téléphone (tenu DANS la paume : il suit l'os de la main) ----------
const phone = new THREE.Group(); scene.add(phone);
box(0.074, 0.152, 0.009, M({ color: '#4a4f58', roughness: 0.28, metalness: 0.75 }), 0, 0, 0, phone, false);   // dos métallisé (lisible comme un téléphone)
box(0.078, 0.156, 0.006, M({ color: '#1a1c20', roughness: 0.4, metalness: 0.6 }), 0, 0, -0.0015, phone, false);
for (const [x, y] of [[-0.02, 0.055], [-0.02, 0.035], [0.0, 0.055]]) { const l = new THREE.Mesh(new THREE.CylinderGeometry(0.007, 0.007, 0.004, 16), M({ color: '#0a0a0c', roughness: 0.2, metalness: 0.9 })); l.rotation.x = Math.PI / 2; l.position.set(x, y, -0.0065); phone.add(l); }
const scrTex = canvasTex(540, 1110, () => {});
let scrState = '';
function drawScreen(state) {
  if (state === scrState) return; scrState = state; const { g, c } = scrTex.userData, w = c.width, h = c.height;
  const gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, '#1b2a44'); gr.addColorStop(1, '#070a12'); g.fillStyle = gr; g.fillRect(0, 0, w, h);
  g.fillStyle = '#e9edf3'; g.font = '600 30px Arial'; g.textAlign = 'left'; g.fillText('02:31', 36, 52);
  g.textAlign = 'center'; g.fillStyle = '#9fb0c8'; g.font = '38px Arial'; g.fillText('Anruf · ' + state, w / 2, 190);
  g.fillStyle = '#3a6fd8'; g.beginPath(); g.arc(w / 2, 380, 120, 0, 7); g.fill(); g.fillStyle = '#fff'; g.font = 'bold 120px Arial'; g.fillText('P', w / 2, 422);
  g.font = 'bold 76px Arial'; g.fillText('Papa', w / 2, 600);
  g.fillStyle = '#e0352b'; g.beginPath(); g.arc(w / 2, 940, 72, 0, 7); g.fill(); g.fillStyle = '#fff'; g.fillRect(w / 2 - 32, 932, 64, 16);
  scrTex.needsUpdate = true;
}
const scr = new THREE.Mesh(new THREE.PlaneGeometry(0.068, 0.14), new THREE.MeshBasicMaterial({ map: scrTex, toneMapped: false }));
scr.position.z = 0.0047; phone.add(scr);
const phoneL = new THREE.PointLight('#9fc0ff', 0, 0.9, 2); scene.add(phoneL);

// ---------- personnages ----------
await RealHuman.loadClips(['idle', 'slowwalk', 'run2', 'explain'], './mocap/');
const ENV = await (await fetch('./mocap/voice_p4.json')).json();
const HERO = await RealHuman.create('./models/kid.glb', { heightM: 1.72, seed: 2 });
const PAPA = await RealHuman.create('./models/judge.glb', { heightM: 1.86, seed: 7 });
for (const H of [HERO, PAPA]) { scene.add(H.root); H.root.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } }); }

// ---------- outils ----------
const ss = (a, b, x) => { const u = Math.min(1, Math.max(0, (x - a) / (b - a))); return u * u * (3 - 2 * u); };
const lerp = (a, b, u) => a + (b - a) * u;
const inR = (T, a, b) => T >= a && T < b;
const inAny = (T, L) => L.some(([a, b]) => inR(T, a, b));
const FULL = { pelvis: 1, spineAbs: 1, legs: 1, arms: 1, root: 1, headAbs: 0.4 };
const IDLEW = { legs: 1, root: 1, pelvis: 0.5, spineAbs: 0.5, arms: 1 };
const dur = (c) => RealHuman.clips[c].frames / RealHuman.clips[c].fps;
const loopT = (c, x) => ((x % dur(c)) + dur(c)) % dur(c);
const IDLE = (t) => [{ clip: 'idle', mode: 'abs', t: loopT('idle', t), k: 1, w: IDLEW }];
const IDLEM = (t) => [{ clip: 'idle', mode: 'abs', t: loopT('idle', t), k: 1, w: { legs: 1, root: 1, pelvis: 0.1, spineAbs: 0.1, arms: 1 } }];   // le corps suit bien l'orientation
const CLIP = (c, t, k = 1) => [{ clip: c, mode: 'abs', t: loopT(c, t), k, w: FULL }];
const TALKING = (t, k = 1) => [...IDLEM(t), { clip: 'explain', mode: 'abs', t: loopT('explain', t * 0.9 + 1.5), k, w: { arms: 1, spineAbs: 0.35, headAbs: 0.25 } }];   // gestes en parlant
const FEAR = { maxM: 1.5, raw: { EyeWideLeft: 1.4, EyeWideRight: 1.4, BrowInnerUp: 1.3, BrowOuterUpLeft: 1.1, BrowOuterUpRight: 1.1, JawOpen: 0.38, MouthStretchLeft: 0.8, MouthStretchRight: 0.8, MouthLowerDownLeft: 0.5, MouthLowerDownRight: 0.5 } };
const WORRY = { maxM: 1.2, raw: { EyeWideLeft: 0.6, EyeWideRight: 0.6, BrowInnerUp: 0.9, BrowOuterUpLeft: 0.3, BrowOuterUpRight: 0.3, MouthPressLeft: 0.4, MouthPressRight: 0.4 } };
const SHOCK = { maxM: 1.6, raw: { EyeWideLeft: 1.6, EyeWideRight: 1.6, BrowInnerUp: 1.4, BrowOuterUpLeft: 1.3, BrowOuterUpRight: 1.3, JawOpen: 0.55, MouthLowerDownLeft: 0.6, MouthLowerDownRight: 0.6 } };
const GRIN = { maxM: 2, raw: { MouthSmileLeft: 1.9, MouthSmileRight: 1.9, CheekSquintLeft: 0.6, CheekSquintRight: 0.6, MouthStretchLeft: 0.9, MouthStretchRight: 0.9, MouthUpperUpLeft: 0.5, MouthUpperUpRight: 0.5, EyeWideLeft: 1.2, EyeWideRight: 1.2, MouthLowerDownLeft: 0.4, MouthLowerDownRight: 0.4 } };
const WARM = { maxM: 1.2, raw: { BrowInnerUp: 0.6, MouthSmileLeft: 0.5, MouthSmileRight: 0.5, EyeSquintLeft: 0.25, EyeSquintRight: 0.25 } };
const HESIT = { maxM: 1.2, raw: { BrowDownLeft: 0.5, BrowDownRight: 0.5, MouthPressLeft: 0.5, MouthPressRight: 0.5, EyeSquintLeft: 0.4, EyeSquintRight: 0.4 } };
const mix = (a, b, u) => { const r = {}; for (const k of new Set([...Object.keys(a.raw || {}), ...Object.keys(b.raw || {})])) r[k] = lerp((a.raw || {})[k] || 0, (b.raw || {})[k] || 0, u); return { maxM: Math.max(a.maxM || 1, b.maxM || 1), raw: r }; };
// lèvres pilotées par le volume réel de la voix (30 valeurs / s)
const env = (T) => { const i = Math.floor(T * 30); return ENV[Math.max(0, Math.min(ENV.length - 1, i))] || 0; };
const lips = (f, T) => { const e = env(T), e2 = env(T + 0.05); return { maxM: f.maxM || 1, raw: { ...f.raw, JawOpen: Math.min(0.75, 0.05 + 0.6 * e), MouthLowerDownLeft: 0.25 * e2, MouthLowerDownRight: 0.25 * e2, MouthFunnel: 0.25 * Math.max(0, e2 - e) * 4, MouthSmileLeft: (f.raw.MouthSmileLeft || 0) * (1 - 0.4 * e), MouthSmileRight: (f.raw.MouthSmileRight || 0) * (1 - 0.4 * e) } }; };
const _hw = new THREE.Vector3(), _pw = new THREE.Vector3();
const wp = (o) => o.getWorldPosition(new THREE.Vector3());
const yOut = (z) => (z > -1.98 ? 0 : z > -2.4 ? -0.16 : z > -2.8 ? -0.32 : -0.48);

// ---------- chronologie (temps de la voix, words.json) ----------
const SP = V(0.15, -0.48, -9.0);              // le fils dans la rue, face à la maison
const MP = V(0.15, -0.48, -8.63), MP2 = V(0.15, -0.48, -7.72), MP3 = V(0.15, -0.48, -8.3);
const M_TALK = [[15.41, 17.0], [20.72, 24.25], [36.13, 36.62], [44.39, 47.0]];   // l'homme parle à l'écran
const H_TALK = [[27.88, 28.95], [30.44, 32.65]];                               // le fils pose ses questions
const END = 69.7;
const RUNV = RealHuman.clips.run2.speed * 0.9, WALKV = RealHuman.clips.slowwalk.speed * 0.9;

function heroState(T) {
  const s = { pos: SP.clone(), yaw: 0, layers: IDLE(T * 0.8), face: FEAR, look: 'papa', phone: 'ear', push: 0 };
  if (T < 7.15) { s.face = T < 3.3 ? mix(WORRY, FEAR, ss(1.0, 2.6, T)) : SHOCK; s.look = T < 3.3 ? null : 'papa'; return s; }
  if (inR(T, 8.26, 10.52)) {                  // rappel : il court dans l'allée vers la rue
    const z = Math.max(-8.9, -2.0 - RUNV * (T - 8.26)); s.pos = V(0.1, yOut(z), z); s.yaw = Math.PI; s.layers = CLIP('run2', T); s.phone = 'hand'; s.look = null; return s;
  }
  if (T < 12.8) { s.phone = 'hand'; return s; }
  if (inR(T, 17.0, 18.4)) { s.push = ss(17.05, 17.35, T) * (1 - ss(17.7, 18.3, T)); s.phone = 'low'; s.face = SHOCK; }
  if (T >= 18.4) { s.phone = 'low'; s.face = FEAR; }
  if (inAny(T, H_TALK)) { s.face = lips(WORRY, T); }
  if (inR(T, 36.4, 41.0) || inR(T, 49.9, 57.5)) s.phone = 'ear';
  if (inR(T, 47.3, 49.9)) s.face = SHOCK;
  if (inR(T, 52.3, 57.5)) { s.face = SHOCK; s.look = null; s.eyeY = 0.25 * Math.sin((T - 52.3) * 2.6); }
  if (T > 57.5) { s.phone = 'low'; s.eyeY = 0.3 * Math.sin((T - 57.5) * 2.2); }
  return s;
}
function papaState(T) {
  const s = { pos: MP.clone(), yaw: Math.PI, layers: IDLEM(4 + T * 0.4), face: WARM, look: 'hero', hug: 0, handsUp: 0, tilt: 0.06, shoulder: 0 };
  if (T < 7.15) { s.hug = 1; s.face = mix(WARM, GRIN, ss(3.6, 5.2, T)); s.tilt = 0.06 + 0.12 * ss(4.0, 5.5, T); s.look = 'hero'; return s; }
  if (inR(T, 7.15, 8.26)) { s.hug = 1; s.face = GRIN; return s; }
  if (inR(T, 8.26, 10.52)) return null;
  if (inR(T, 10.52, 12.8)) { const z = -0.4 - WALKV * 1.5 * (T - 10.52); s.pos = V(0.05, yOut(z), z); s.layers = CLIP('slowwalk', T * 1.5); s.face = GRIN; s.look = null; return s; }
  if (T < 17.07) { s.hug = 1 - ss(16.95, 17.15, T); s.face = WARM; if (inAny(T, M_TALK)) s.face = lips(WARM, T); return s; }
  const back = ss(17.15, 17.75, T); s.pos = MP.clone().lerp(MP2, back);
  s.handsUp = ss(18.7, 19.6, T) * (1 - ss(20.6, 21.0, T));
  s.face = T < 20.7 ? WARM : WARM;
  if (inR(T, 20.72, 24.25)) s.layers = TALKING(T, ss(20.7, 21.0, T) * (1 - ss(24.0, 24.3, T)));
  if (inR(T, 33.0, 40.4)) s.face = mix(WARM, GRIN, ss(35.0, 35.6, T));
  if (inR(T, 40.4, 44.4)) { s.face = HESIT; if (T > 43.0) s.look = 'phone'; }
  if (inR(T, 44.39, 47.0)) { s.face = WARM; s.layers = TALKING(T, ss(44.35, 44.6, T) * (1 - ss(46.8, 47.1, T))); }
  if (T > 47.0) s.face = mix(WARM, GRIN, ss(48.0, 49.5, T));
  if (T > 57.5) { const u = ss(64.2, 66.2, T); s.pos = MP2.clone().lerp(MP3, u); if (u > 0 && u < 1) s.layers = CLIP('slowwalk', T * 0.7); s.face = GRIN; s.tilt = 0.18; }
  if (T > 67.4) s.shoulder = ss(67.4, 68.6, T);
  if (inAny(T, M_TALK)) s.face = lips(s.face, T);
  return s;
}
const screenState = (T) => '00:' + String(Math.floor(T + 12)).padStart(2, '0');

// ---------- caméra continue par lieu ----------
const FOC = {
  hero: () => _hw.clone(), papa: () => _pw.clone(), mid: () => _hw.clone().lerp(_pw, 0.5), chest: () => _pw.clone().add(V(0, -0.38, 0)),
  phone: () => phone.position.clone(), hands: () => _pw.clone().add(V(0, -0.15, 0)),
};
const CAM = [
  // A — l'accroche : l'appel pendant le câlin, puis le visage de l'homme (sans coupe)
  { t: 0.0, f: 'mid', az: 258, el: 8, d: 1.2, fov: 42 },
  { t: 1.7, f: 'mid', az: 240, el: 6, d: 1.0, fov: 40 },
  { t: 3.3, f: 'papa', az: 236, el: 4, d: 0.95, fov: 38 },
  { t: 4.6, f: 'papa', az: 205, el: 2, d: 0.95, fov: 36 },
  { t: 6.0, f: 'papa', az: 192, el: 1, d: 0.62, fov: 31 },
  { t: 7.13, f: 'papa', az: 186, el: 0, d: 0.5, fov: 29 },
  // B — « Teil vier » : la rue, de haut
  { t: 7.15, cut: 1, p: () => V(2.6, 2.6, -12.6), l: () => FOC.mid(), fov: 44 },
  { t: 8.24, p: () => V(2.3, 2.3, -12.0), l: () => FOC.mid(), fov: 40 },
  // C — rappel : il court vers la rue
  { t: 8.26, cut: 1, f: 'hero', az: 180, el: -2, d: 2.3, fov: 48 },
  { t: 10.5, f: 'hero', az: 172, el: 0, d: 1.8, fov: 46 },
  // D — rappel : l'homme sort de la maison
  { t: 10.52, cut: 1, p: () => V(1.25, 0.85, -4.6), l: () => FOC.papa().add(V(0, -0.2, 0)), fov: 40 },
  { t: 12.79, p: () => V(1.05, 0.8, -4.3), l: () => FOC.papa().add(V(0, -0.15, 0)), fov: 34 },
  // E — « Papas Gesicht. Papas Jacke. » puis il parle
  { t: 12.81, cut: 1, f: 'papa', az: 218, el: 3, d: 0.85, fov: 34 },
  { t: 14.25, f: 'chest', az: 228, el: 4, d: 0.95, fov: 38 },
  { t: 15.35, f: 'papa', az: 222, el: 2, d: 0.7, fov: 33 },
  { t: 17.05, f: 'papa', az: 214, el: 1, d: 0.62, fov: 31 },
  // F — il le repousse ; l'homme lève les mains et parle
  { t: 17.07, cut: 1, f: 'mid', az: 115, el: 6, d: 1.6, fov: 44 },
  { t: 18.5, f: 'mid', az: 128, el: 6, d: 2.2, fov: 44 },
  { t: 19.6, f: 'hands', az: 165, el: 2, d: 1.55, fov: 40 },
  { t: 20.7, f: 'papa', az: 172, el: 1, d: 1.15, fov: 36 },
  { t: 24.27, f: 'papa', az: 182, el: 0, d: 0.8, fov: 32 },
  // G — le premier choix : son visage
  { t: 24.29, cut: 1, f: 'hero', az: 15, el: 3, d: 0.85, fov: 32 },
  { t: 33.0, f: 'hero', az: 6, el: 2, d: 0.7, fov: 28 },
  // H — « Rex. »
  { t: 33.03, cut: 1, f: 'papa', az: 180, el: 1, d: 0.85, fov: 32 },
  { t: 36.46, f: 'papa', az: 184, el: 0, d: 0.58, fov: 29 },
  // I — le téléphone dit aussi « Rex »
  { t: 36.49, cut: 1, f: 'hero', az: 238, el: 4, d: 0.6, fov: 38 },
  { t: 40.39, f: 'hero', az: 225, el: 3, d: 0.52, fov: 36 },
  // J — il hésite, regarde le téléphone, répond
  { t: 40.41, cut: 1, f: 'mid', az: 140, el: 5, d: 2.3, fov: 40 },
  { t: 42.9, f: 'mid', az: 150, el: 4, d: 2.0, fov: 38 },
  { t: 44.3, f: 'papa', az: 176, el: 1, d: 0.8, fov: 33 },
  { t: 47.32, f: 'papa', az: 182, el: 0, d: 0.58, fov: 30 },
  // K — « Das stimmt. Sogar die Klingel. »
  { t: 47.34, cut: 1, f: 'hero', az: 10, el: 2, d: 0.75, fov: 30 },
  { t: 49.89, f: 'hero', az: 4, el: 2, d: 0.62, fov: 28 },
  // L — la voix du père panique au téléphone
  { t: 49.91, cut: 1, f: 'hero', az: 238, el: 5, d: 0.55, fov: 38 },
  { t: 52.3, f: 'hero', az: 40, el: 4, d: 0.62, fov: 34 },
  { t: 57.72, f: 'hero', az: 18, el: 3, d: 0.66, fov: 31 },
  // M — le dernier choix, l'homme qui s'approche, la main sur l'épaule
  { t: 57.74, cut: 1, f: 'mid', az: 38, el: 5, d: 2.4, fov: 40 },
  { t: 64.0, f: 'mid', az: 30, el: 4, d: 2.1, fov: 38 },
  { t: 66.64, f: 'mid', az: 26, el: 4, d: 1.9, fov: 36 },
  { t: 66.66, cut: 1, f: 'papa', az: 200, el: 4, d: 1.55, fov: 34 },
  { t: 69.7, f: 'papa', az: 190, el: 2, d: 1.15, fov: 28 },
];
const DEG = Math.PI / 180;
function keyVec(k) {
  if (k.p) { const F = k.p(), L = k.l(); return [F.x, F.y, F.z, 0, 0, 0, L.x, L.y, L.z, k.fov]; }
  const F = FOC[k.f](), L = k.lk ? FOC[k.lk]() : F.clone();
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
// repère d'un personnage : avant, côté droit (main droite), haut
const frameOf = (yaw) => ({ f: V(Math.sin(yaw), 0, Math.cos(yaw)), r: V(-Math.cos(yaw), 0, Math.sin(yaw)) });
const boneW = (H, k) => H.bones[H.B[k]].getWorldPosition(new THREE.Vector3());
function attachPhone(handKey, towards) {
  // le téléphone dans la paume : au bout de la main, aligné sur l'avant-bras, écran tourné vers « towards »
  const side = handKey[0], h = boneW(HERO, side + 'Hand'), fo = boneW(HERO, side + 'Fore');
  const dir = h.clone().sub(fo).normalize(); const p = h.clone().addScaledVector(dir, 0.075);
  const zA = towards.clone().sub(p).normalize(); const yA = dir.clone().addScaledVector(zA, -dir.dot(zA)).normalize(); const xA = new THREE.Vector3().crossVectors(yA, zA);
  phone.position.copy(p).addScaledVector(zA, 0.012); phone.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(xA, yA, zA));
  return phone.position;
}

function earBasis(hf) {   // repère de la TÊTE (à partir des yeux) : oreille droite, axe latéral, avant, haut
  const le = HERO.bones[HERO.B.lEye].getWorldPosition(new THREE.Vector3()), re = HERO.bones[HERO.B.rEye].getWorldPosition(new THREE.Vector3());
  const mid = le.clone().add(re).multiplyScalar(0.5), lat = re.clone().sub(le).normalize();
  let fwd = new THREE.Vector3().crossVectors(lat, V(0, 1, 0)).normalize(); if (fwd.dot(hf.f) < 0) fwd.negate();
  const up = new THREE.Vector3().crossVectors(fwd, lat).normalize(); if (up.y < 0) up.negate();
  return { ear: mid.clone().addScaledVector(lat, 0.072).addScaledVector(fwd, -0.085).addScaledVector(up, -0.035), lat, fwd, up };
}
function frame(T) {
  hinge.rotation.y = -1.56; drawGlass(0); setClock('02:31');
  leaves[0].rotation.y = -1.45; leaves[1].rotation.y = 1.45; bHinge.rotation.y = -1.2; hallL.intensity = 5;
  const c = camAt(T);
  // --- l'homme d'abord (position), puis le fils, puis l'homme avec les cibles des mains sur le dos du fils
  const ps = papaState(T), h = heroState(T);
  HERO.root.position.copy(h.pos); HERO.root.rotation.y = h.yaw;
  if (ps) { PAPA.root.position.copy(ps.pos); PAPA.root.rotation.y = ps.yaw; PAPA.root.updateMatrixWorld(true); PAPA.headWorld(_pw); }
  const hf = frameOf(h.yaw);
  // pose du fils
  const pose = { mo: h.layers, lookW: 0.85 };
  const lookOf = (k) => (k === 'papa' ? _pw.clone() : k);
  HERO.setPose(pose, { ...h.face, eyeY: h.eyeY || 0 }, lookOf(h.look), T); HERO.headWorld(_hw);
  if (h.phone === 'ear') {   // main gauche à l'oreille gauche
    const E = earBasis(hf); const hnd = E.ear.clone().addScaledVector(E.lat, 0.035).addScaledVector(E.up, -0.075).addScaledVector(E.fwd, 0.01);   // main DROITE derrière le téléphone, oreille droite
    Object.assign(pose, { rW: 1, rwx: hnd.x, rwy: hnd.y, rwz: hnd.z, rCurl: 0.8, rWrX: -0.4 });
  } else if (h.phone === 'hand') { const p = h.pos.clone().addScaledVector(hf.f, 0.28).addScaledVector(hf.r, -0.1).add(V(0, 1.05, 0)); Object.assign(pose, { lW: 1, lwx: p.x, lwy: p.y, lwz: p.z, lCurl: 0.6 }); }
  else if (h.phone === 'low') { const p = h.pos.clone().addScaledVector(hf.f, 0.12).addScaledVector(hf.r, -0.2).add(V(0, 0.85, 0)); Object.assign(pose, { lW: 0.8, lwx: p.x, lwy: p.y, lwz: p.z, lCurl: 0.6 }); }
  if (h.push > 0 && ps) { const ch = ps.pos.clone().add(V(0, 1.25, 0)).addScaledVector(frameOf(ps.yaw).f, 0.16); Object.assign(pose, { rW: h.push, rwx: ch.x + 0.05, rwy: ch.y, rwz: ch.z, rCurl: 0.2 }); }
  HERO.setPose(pose, { ...h.face, eyeY: h.eyeY || 0 }, lookOf(h.look), T); HERO.headWorld(_hw);
  phone.visible = h.phone !== 'none';
  if (phone.visible) {
    let p;
    if (h.phone === 'ear') {   // contre la joue, vertical, la main qui l'entoure
      const E = earBasis(hf); p = E.ear.clone().addScaledVector(E.lat, 0.012).addScaledVector(E.fwd, 0.035).addScaledVector(E.up, -0.03);
      const zA = E.lat.clone().negate(), yA = E.up.clone().multiplyScalar(0.9).addScaledVector(E.fwd, -0.42).normalize(); const xA = new THREE.Vector3().crossVectors(yA, zA).normalize(); const y2 = new THREE.Vector3().crossVectors(zA, xA);
      phone.position.copy(p); phone.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(xA, y2, zA));
    } else p = attachPhone('l', _hw.clone().addScaledVector(hf.f, 0.1));
    drawScreen(screenState(T)); phoneL.position.copy(p).addScaledVector(hf.f, 0.08); phoneL.intensity = h.phone === 'ear' ? 0.5 : 1.2;
  }
  // pose de l'homme
  PAPA.root.visible = !!ps;
  if (ps) {
    const pf = frameOf(ps.yaw); const pose2 = { mo: ps.layers, lookW: 1, headZ: ps.tilt || 0 };
    if (ps.hug > 0) {   // mains POSÉES sur le dos du fils (à la surface, pas dedans)
      const back = h.pos.clone().add(V(0, 1.18, 0)).addScaledVector(hf.f, -0.16);
      const r = back.clone().addScaledVector(hf.r, -0.1).add(V(0, 0.06, 0)), l = back.clone().addScaledVector(hf.r, 0.12).add(V(0, -0.06, 0));
      Object.assign(pose2, { rW: ps.hug, rwx: r.x, rwy: r.y, rwz: r.z, rCurl: 0.25, lW: ps.hug, lwx: l.x, lwy: l.y, lwz: l.z, lCurl: 0.25, spineX: 0.08 });
    }
    if (ps.handsUp > 0) {   // mains levées, paumes vers le fils
      const r = ps.pos.clone().add(V(0, 1.5, 0)).addScaledVector(pf.f, 0.22).addScaledVector(pf.r, 0.3), l = ps.pos.clone().add(V(0, 1.5, 0)).addScaledVector(pf.f, 0.22).addScaledVector(pf.r, -0.3);
      Object.assign(pose2, { rW: ps.handsUp, rwx: r.x, rwy: r.y, rwz: r.z, rCurl: 0.05, rWrX: -1.1, lW: ps.handsUp, lwx: l.x, lwy: l.y, lwz: l.z, lCurl: 0.05, lWrX: -1.1 });
    }
    if (ps.shoulder > 0) { const s_ = _hw.clone().add(V(0, -0.2, 0)).addScaledVector(hf.r, -0.16).addScaledVector(hf.f, 0.02); Object.assign(pose2, { rW: ps.shoulder, rwx: s_.x, rwy: s_.y + 0.04, rwz: s_.z, rCurl: 0.45 }); }
    const look = ps.look === 'cam' ? c.pos : ps.look === 'phone' ? phone.position.clone() : ps.look === 'hero' ? _hw : null;
    PAPA.setPose(pose2, ps.face, look, T); PAPA.headWorld(_pw);
    const f = pf.f; underL.intensity = 6; underL.position.copy(_pw).add(V(0, -0.8, 0)).addScaledVector(f, 0.35); underL.target.position.copy(_pw);
  } else underL.intensity = 0;
  // lumières
  tvL.intensity = 2.2 + 1.2 * Math.sin(T * 13) * Math.sin(T * 5.3); lamp.intensity = 0.6; streetL.intensity = 3; porchL.intensity = 7; upL.intensity = 5;
  // caméra
  const run = inR(T, 8.26, 10.52);
  const hand = run ? 0.014 : T < 7.2 ? 0.006 : 0.004;
  camera.position.copy(c.pos).add(V(Math.sin(T * 7.1) * hand + (run ? Math.sin(T * 19) * 0.01 : 0), Math.sin(T * 9.3) * hand + (run ? Math.abs(Math.sin(T * 8.6)) * 0.02 : 0), Math.sin(T * 5.7) * hand));
  camera.up.set(0, 1, 0); camera.lookAt(c.tgt); camera.fov = c.fov;
  HERO.root.visible = camera.position.distanceTo(_hw) > 0.2 && !inR(T, 10.52, 12.8);
  if (ps) PAPA.root.visible = camera.position.distanceTo(_pw) > 0.2;
  fillL.position.copy(camera.position).add(V(0, 0.2, 0)); fillL.target.position.copy(c.tgt); fillL.intensity = 1.6 * Math.max(1, (camera.position.distanceTo(c.tgt) / 1.1) ** 2);
  const w2 = innerWidth, h2 = innerHeight;
  if (canvas.width !== w2) renderer.setSize(w2, h2, false);
  camera.aspect = w2 / h2; camera.updateProjectionMatrix();
  renderer.render(scene, camera);
}
window.renderAt = (T) => frame(T);
window.dbg = (T) => { frame(T); const r = (v) => [v.x, v.y, v.z].map(x => +x.toFixed(2)); const c = camAt(T); return { cam: r(camera.position), tgt: r(c.tgt), fov: c.fov, hero: r(_hw), papa: r(_pw) }; };
window.READY = true;
if (!MANUAL) { const c0 = performance.now(); const loop = () => { frame(((performance.now() - c0) / 1000) % END); requestAnimationFrame(loop); }; loop(); }
else frame(0);
