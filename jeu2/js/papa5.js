// « Ich bin's. Mach auf. » – TEIL 5 : la rue la nuit (appel à la police), la maison de la voisine Frau Weber (couloir, chambre, cave).
// Le fils (Rocketbox « kid »), le faux père (« judge »), Frau Weber (Rocketbox femme, cheveux gris + chignon).
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
const wallM = M({ map: paper, color: '#b9c7a8', roughness: 0.9 });   // papier peint vert pâle : la maison de Frau Weber
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
const glass = new THREE.Mesh(new THREE.PlaneGeometry(0.54, 0.56), new THREE.MeshBasicMaterial({ map: glassTex, toneMapped: false, color: '#9aa7bd', side: THREE.DoubleSide }));
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
box(1.0, 0.1, 2.0, M({ color: '#5a4a3a' }), BX + 0.55, 0.4, 2.0); for (const [dx, dz] of [[-0.45, -0.95], [0.45, -0.95], [-0.45, 0.95], [0.45, 0.95]]) box(0.06, 0.4, 0.06, M({ color: '#4a3a2c' }), BX + 0.55 + dx, 0.2, 2.0 + dz);
box(0.96, 0.15, 1.96, M({ color: '#c9c3b8' }), BX + 0.55, 0.52, 2.0);
box(1.06, 0.2, 1.4, M({ color: '#7a5566' }), BX + 0.55, 0.58, 2.3);
// LE FUSIL sous le lit (crosse en bois, canon, couvert de poussière)
const rifle = new THREE.Group(); scene.add(rifle); rifle.position.set(BX + 0.62, 0.05, 1.95); rifle.rotation.y = 0.12;
box(0.05, 0.11, 0.42, M({ color: '#8a5a32', roughness: 0.45 }), 0, 0.03, -0.42, rifle); box(0.04, 0.06, 0.3, M({ color: '#2b2b2e', metalness: 0.7, roughness: 0.4 }), 0, 0.05, -0.08, rifle);
const barrel = new THREE.Mesh(new THREE.CylinderGeometry(0.011, 0.011, 0.72, 12), M({ color: '#3a3b40', metalness: 0.85, roughness: 0.35 })); barrel.rotation.x = Math.PI / 2; barrel.position.set(0, 0.06, 0.42); rifle.add(barrel);
box(0.035, 0.03, 0.4, M({ color: '#8a5a32', roughness: 0.45 }), 0, 0.035, 0.22, rifle);
const rifleL = new THREE.PointLight('#a8bce6', 0, 2.2, 1.4); rifleL.position.set(BX + 1.3, 0.3, 2.2); scene.add(rifleL); box(0.5, 0.12, 0.35, M({ color: '#e8e4dc' }), BX + 0.55, 0.65, 1.15);
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

// ---------- décor en plus : fenêtre allumée chez Frau Weber, 2e réverbère, cave ----------
const facadeWin = new THREE.Mesh(new THREE.PlaneGeometry(0.9, 0.8), new THREE.MeshBasicMaterial({ color: '#ffcf8a', toneMapped: false }));
facadeWin.position.set(1.55, 1.55, -0.235); facadeWin.rotation.y = Math.PI; scene.add(facadeWin);
box(0.04, 0.8, 0.04, M({ color: '#ddd' }), 1.55, 1.55, -0.25, scene, false); box(0.9, 0.04, 0.04, M({ color: '#ddd' }), 1.55, 1.55, -0.25, scene, false);
const winL = new THREE.PointLight('#ffbf70', 2.5, 5, 1.5); winL.position.set(1.55, 1.5, -0.8); scene.add(winL);
box(0.1, 4.2, 0.1, M({ color: '#222' }), 6.6, 1.6, -11.3, scene, false);
const sLamp2 = new THREE.Mesh(new THREE.SphereGeometry(0.15, 12, 8), new THREE.MeshBasicMaterial({ color: '#ffcf8a', toneMapped: false })); sLamp2.position.set(6.4, 3.6, -11.3); scene.add(sLamp2);
const sL2 = new THREE.PointLight('#ffb062', 12, 12, 1.4); sL2.position.set(6.4, 3.5, -11.3); scene.add(sL2);
for (let i = 0; i < 6; i++) { const car = new THREE.Group(); scene.add(car); car.position.set(-9 + i * 4.2 + (i > 2 ? 6 : 0), -0.5, -14.4); if (i === 3 || i === 4) continue;
  box(1.8, 0.55, 4.0 / 2.2, M({ color: ['#2a2f3a', '#40302a', '#1d2a22', '#3a3a3e', '#2c2c34', '#302630'][i], roughness: 0.4, metalness: 0.5 }), 0, 0.45, 0, car); box(1.1, 0.4, 1.6, M({ color: '#151820', roughness: 0.2, metalness: 0.6 }), 0.1, 0.9, 0, car); car.rotation.y = Math.PI / 2; }
// la cave (x = -14..-10) : murs de pierre, ampoule qui pend, vieille porte en planches entrouverte (noir derrière)
const stone = canvasTex(512, 512, (g, w, h) => {
  g.fillStyle = '#3d3a35'; g.fillRect(0, 0, w, h);
  for (let y = 0; y < h; y += 46) for (let x = -(y / 46 % 2) * 40; x < w; x += 80) { const v = 60 + rnd() * 30 | 0; g.fillStyle = `rgb(${v + 6},${v + 2},${v - 4})`; g.fillRect(x + 3, y + 3, 74, 40); }
  for (let i = 0; i < 60; i++) { g.fillStyle = `rgba(20,30,10,${rnd() * 0.12})`; g.beginPath(); g.arc(rnd() * w, rnd() * h, 10 + rnd() * 40, 0, 7); g.fill(); }
});
stone.wrapS = stone.wrapT = THREE.RepeatWrapping; stone.repeat.set(2, 1);
const KX = -12, stoneM = M({ map: stone, roughness: 1 });
box(4, 0.1, 4, M({ color: '#2b2925', roughness: 1 }), KX, -0.05, 2); box(4, 0.1, 4, M({ color: '#2a2724' }), KX, 2.3, 2, scene, false);
box(0.1, 2.3, 4, stoneM, KX - 2, 1.15, 2); box(0.1, 2.3, 4, stoneM, KX + 2, 1.15, 2); box(4, 2.3, 0.1, stoneM, KX, 1.15, 0);
box(1.3, 2.3, 0.1, stoneM, KX - 1.35, 1.15, 4); box(1.8, 2.3, 0.1, stoneM, KX + 1.1, 1.15, 4); box(0.9, 0.35, 0.1, stoneM, KX - 0.25, 2.12, 4);
box(0.9, 2.0, 0.05, M({ color: '#020203' }), KX - 0.25, 0.97, 4.12, scene, false);   // le noir derrière la porte
const kHinge = new THREE.Group(); scene.add(kHinge); kHinge.position.set(KX - 0.7, 0, 3.95);
const kDoorM = M({ color: '#4b3a28', roughness: 0.9 });
for (let i = 0; i < 6; i++) box(0.145, 1.92, 0.05, kDoorM, 0.08 + i * 0.15, 0.97, 0, kHinge);
for (const y of [0.35, 1.6]) box(0.88, 0.1, 0.03, kDoorM, 0.45, y, -0.04, kHinge);
box(0.88, 0.1, 0.03, kDoorM, 0.45, 0.97, -0.04, kHinge).rotation.z = 0.95;
const shelf = new THREE.Group(); scene.add(shelf); shelf.position.set(KX + 0.75, 0, 3.6);   // étagère poussée de côté (la porte était cachée)
for (const y of [0.4, 0.9, 1.4]) box(0.9, 0.04, 0.35, M({ color: '#5a4630' }), 0, y, 0, shelf);
for (const s of [-1, 1]) box(0.04, 1.6, 0.35, M({ color: '#5a4630' }), s * 0.43, 0.8, 0, shelf);
for (let i = 0; i < 5; i++) { const j = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.16, 10), M({ color: ['#6b4a2a', '#8a6a3a', '#5a2a2a', '#3a4a2a', '#7a5a2a'][i], roughness: 0.3 })); j.position.set(-0.3 + i * 0.15, 0.5 + (i % 2) * 0.5, 0); shelf.add(j); }
const bulbW = new THREE.Group(); scene.add(bulbW); bulbW.position.set(KX + 0.1, 2.25, 2.4);
const wire = box(0.008, 0.45, 0.008, M({ color: '#111' }), 0, -0.22, 0, bulbW, false);
const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.04, 12, 8), new THREE.MeshBasicMaterial({ color: '#ffd9a0', toneMapped: false })); bulb.position.y = -0.47; bulbW.add(bulb);
const kL = new THREE.PointLight('#ffb36b', 3, 5, 1.5); bulbW.add(kL); kL.position.y = -0.5; kL.castShadow = true; kL.shadow.mapSize.set(512, 512);
const coldL = new THREE.PointLight('#7f9ccf', 0, 2.5, 1.5); coldL.position.set(KX - 0.25, 1.0, 4.5); scene.add(coldL);
// le téléphone dans la poche du manteau de l'homme (s'allume quand il sonne)
const pocketPh = new THREE.Group(); scene.add(pocketPh);
box(0.07, 0.14, 0.01, M({ color: '#16181c', roughness: 0.3, metalness: 0.6 }), 0, 0, 0, pocketPh, false);
const pScr = new THREE.Mesh(new THREE.PlaneGeometry(0.064, 0.13), new THREE.MeshBasicMaterial({ color: '#9fc6ff', toneMapped: false })); pScr.position.z = 0.0055; pocketPh.add(pScr);
const pocketL = new THREE.PointLight('#8fb8ff', 0, 1.2, 2); scene.add(pocketL);
function drawScreenP(name, sub, col) {
  const st = name + sub; if (st === scrState) return; scrState = st; const { g, c } = scrTex.userData, w = c.width, h = c.height;
  const gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, '#1b2a44'); gr.addColorStop(1, '#070a12'); g.fillStyle = gr; g.fillRect(0, 0, w, h);
  g.fillStyle = '#e9edf3'; g.font = '600 30px Arial'; g.textAlign = 'left'; g.fillText('02:47', 36, 52);
  g.textAlign = 'center'; g.fillStyle = '#9fb0c8'; g.font = '38px Arial'; g.fillText(sub, w / 2, 190);
  g.fillStyle = col; g.beginPath(); g.arc(w / 2, 380, 120, 0, 7); g.fill(); g.fillStyle = '#fff'; g.font = 'bold 110px Arial'; g.fillText(name[0], w / 2, 418);
  g.font = 'bold 76px Arial'; g.fillText(name, w / 2, 600);
  if (sub !== 'Anruf beendet') { g.fillStyle = '#e0352b'; g.beginPath(); g.arc(w / 2, 940, 72, 0, 7); g.fill(); g.fillStyle = '#fff'; g.fillRect(w / 2 - 32, 932, 64, 16); }
  scrTex.needsUpdate = true;
}

// ---------- personnages ----------
await RealHuman.loadClips(['idle', 'slowwalk', 'run2', 'explain'], './mocap/');
const ENV = await (await fetch('./mocap/voice_p5.json')).json();
const HERO = await RealHuman.create('./models/kid.glb', { heightM: 1.72, seed: 2 });
const PAPA = await RealHuman.create('./models/judge.glb', { heightM: 1.86, seed: 7 });
const WEB = await RealHuman.create('./models/g_Female_Adult_02.glb', { heightM: 1.63, seed: 5, glasses: true,
  look: { hair: { sample: [0.2, 0.88], color: '#bdbab4', loose: true }, clothes: [{ kind: 'hue', h: [185, 250], s: 0.2, color: '#8a7f9a' }], volume: { type: 'bun', color: '#c4c1bb' } } });
WEB.root.traverse(o => { if (!o.isMesh) return; for (const m of (Array.isArray(o.material) ? o.material : [o.material])) if (/opacity/.test(m.name) && m.map) {   // queue de cheval : gris
  const im = m.map.image, cv = document.createElement('canvas'); cv.width = im.width; cv.height = im.height; const g = cv.getContext('2d'); g.drawImage(im, 0, 0);
  const id = g.getImageData(0, 0, cv.width, cv.height), d = id.data; for (let i = 0; i < d.length; i += 4) { const l = (d[i] + d[i + 1] + d[i + 2]) / 3; const k = 0.75 + 0.35 * Math.min(1, l / 90); d[i] = 196 * k; d[i + 1] = 193 * k; d[i + 2] = 187 * k; }
  g.putImageData(id, 0, 0); const t = new THREE.CanvasTexture(cv); t.flipY = m.map.flipY; t.colorSpace = m.map.colorSpace; m.map = t; m.needsUpdate = true; } });
const hallTop = new THREE.PointLight('#ffd2a0', 2.2, 4, 1.5); hallTop.position.set(0.1, 2.3, 1.9); scene.add(hallTop);
outMoon.intensity = 0.9;
for (const H of [HERO, PAPA, WEB]) { scene.add(H.root); H.root.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } }); }

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
const IDLEM = (t) => [{ clip: 'idle', mode: 'abs', t: loopT('idle', t), k: 1, w: { legs: 1, root: 1, pelvis: 0.1, spineAbs: 0.1, arms: 1 } }];
const CLIP = (c, t, k = 1) => [{ clip: c, mode: 'abs', t: loopT(c, t), k, w: FULL }];
const TALKING = (t, k = 1, sp = 0.9) => [...IDLEM(t), { clip: 'explain', mode: 'abs', t: loopT('explain', t * sp + 1.5), k, w: { arms: 1, spineAbs: 0.35, headAbs: 0.25 } }];
const FEAR = { maxM: 1.5, raw: { EyeWideLeft: 1.4, EyeWideRight: 1.4, BrowInnerUp: 1.3, BrowOuterUpLeft: 1.1, BrowOuterUpRight: 1.1, JawOpen: 0.38, MouthStretchLeft: 0.8, MouthStretchRight: 0.8, MouthLowerDownLeft: 0.5, MouthLowerDownRight: 0.5 } };
const WORRY = { maxM: 1.2, raw: { EyeWideLeft: 0.6, EyeWideRight: 0.6, BrowInnerUp: 0.9, BrowOuterUpLeft: 0.3, BrowOuterUpRight: 0.3, MouthPressLeft: 0.4, MouthPressRight: 0.4 } };
const SHOCK = { maxM: 1.6, raw: { EyeWideLeft: 1.6, EyeWideRight: 1.6, BrowInnerUp: 1.4, BrowOuterUpLeft: 1.3, BrowOuterUpRight: 1.3, JawOpen: 0.55, MouthLowerDownLeft: 0.6, MouthLowerDownRight: 0.6 } };
const GRIN = { maxM: 2, raw: { MouthSmileLeft: 1.9, MouthSmileRight: 1.9, CheekSquintLeft: 0.6, CheekSquintRight: 0.6, MouthStretchLeft: 0.9, MouthStretchRight: 0.9, MouthUpperUpLeft: 0.5, MouthUpperUpRight: 0.5, EyeWideLeft: 1.2, EyeWideRight: 1.2, MouthLowerDownLeft: 0.4, MouthLowerDownRight: 0.4 } };
const WARM = { maxM: 1.2, raw: { BrowInnerUp: 0.6, MouthSmileLeft: 0.5, MouthSmileRight: 0.5, EyeSquintLeft: 0.25, EyeSquintRight: 0.25 } };
const mix = (a, b, u) => { const r = {}; for (const k of new Set([...Object.keys(a.raw || {}), ...Object.keys(b.raw || {})])) r[k] = lerp((a.raw || {})[k] || 0, (b.raw || {})[k] || 0, u); return { maxM: Math.max(a.maxM || 1, b.maxM || 1), raw: r }; };
const env = (T) => { const i = Math.floor(T * 30); return ENV[Math.max(0, Math.min(ENV.length - 1, i))] || 0; };
const lips = (f, T) => { const e = env(T), e2 = env(T + 0.05); return { maxM: f.maxM || 1, raw: { ...f.raw, JawOpen: Math.min(0.75, 0.05 + 0.6 * e), MouthLowerDownLeft: 0.25 * e2, MouthLowerDownRight: 0.25 * e2, MouthFunnel: 0.25 * Math.max(0, e2 - e) * 4, MouthSmileLeft: (f.raw.MouthSmileLeft || 0) * (1 - 0.4 * e), MouthSmileRight: (f.raw.MouthSmileRight || 0) * (1 - 0.4 * e) } }; };
const _hw = new THREE.Vector3(), _pw = new THREE.Vector3(), _ww = new THREE.Vector3();
const yOut = (z) => (z > -1.98 ? 0 : z > -2.4 ? -0.16 : z > -2.8 ? -0.32 : -0.48);
const yawTo = (a, b) => Math.atan2(b.x - a.x, b.z - a.z);
const path = (pts, u) => {   // point le long d'une ligne brisée (u 0..1 en distance)
  const L = []; let tot = 0; for (let i = 1; i < pts.length; i++) { const d = pts[i].distanceTo(pts[i - 1]); L.push(d); tot += d; }
  let s = Math.min(1, Math.max(0, u)) * tot; for (let i = 0; i < L.length; i++) { if (s <= L[i] || i === L.length - 1) { const p = pts[i].clone().lerp(pts[i + 1], Math.min(1, s / L[i])); return { p, yaw: yawTo(pts[i], pts[i + 1]) }; } s -= L[i]; }
};

// ---------- chronologie (voix de la partie 5, words.json) ----------
const ZS = -12.3;                                 // la rue, devant le portail de Frau Weber
const KS = V(0.9, -0.48, ZS);                     // le fils pendant l'appel
const MS = V(4.6, -0.48, ZS), MS2 = V(3.4, -0.48, ZS), MG = V(0.4, -0.48, -10.15);   // l'homme : loin, plus près, au portail
const KD = V(0.05, 0, -0.42);                     // le fils devant la porte de Frau Weber
const WD = V(0.05, 0, 0.42), WI = V(-0.28, 0, 1.25), KI = V(0.32, 0, 1.62);   // Frau Weber à la porte / dans le couloir ; le fils dans le couloir
const MD = V(0.08, 0, -0.78);                     // l'homme devant la porte (sur le perron)
const END = 80.2;
const RUNV = RealHuman.clips.run2.speed * 0.9, WALKV = RealHuman.clips.slowwalk.speed;
// téléphone du fils (main GAUCHE) : 'low' (bras le long du corps), 'hand' (devant lui, il regarde l'écran), 'ear' (près de l'oreille, sans la toucher)
const PHK = [[0, 'low'], [2.62, 'ear'], [20.45, 'hand'], [21.55, 'low'], [32.6, 'hand'], [33.75, 'ear'], [36.95, 'low']];
const PHTR = 0.5;
function phoneModes(T) {
  let i = 0; while (i < PHK.length - 1 && PHK[i + 1][0] <= T) i++;
  const prev = i > 0 ? PHK[i - 1][1] : PHK[0][1]; const u = ss(PHK[i][0], PHK[i][0] + PHTR, T);
  return { a: u < 1 ? prev : PHK[i][1], b: PHK[i][1], u };
}
const PH_SCREEN = (T) => (T < 20.45 ? ['Polizei', '110 · verbunden', '#2b6cd6'] : T < 32.6 ? ['Polizei', 'Anruf beendet', '#2b6cd6'] : T < 33.75 ? ['Polizei', '110 · wählen …', '#2b6cd6'] : ['Polizei', '110 · Anruf …', '#2b6cd6']);

function heroState(T) {
  const s = { pos: KS.clone(), yaw: -Math.PI / 2, layers: IDLE(T * 0.8), face: FEAR, look: 'cam', pound: 0, vis: true, phone: true };
  if (T < 2.5) { const x = lerp(8.5, KS.x, T / 2.5); s.pos = V(x, -0.48, ZS); s.layers = CLIP('run2', T); s.face = FEAR; s.look = null; s.lookBack = T > 1.1 && T < 1.9; return s; }
  if (T < 3.2) { const u = ss(2.5, 3.2, T); s.pos = V(KS.x - 0.25 * Math.sin(u * Math.PI / 2), -0.48, ZS); s.pos.x = KS.x; s.layers = IDLE(T * 0.8); }
  if (T < 4.4) s.face = mix(WORRY, FEAR, ss(2.6, 4.0, T));
  else if (T < 7.3) s.face = SHOCK;
  s.look = T < 7.3 ? 'ahead' : 'papa';
  if (inR(T, 7.3, 21.4)) { s.look = T < 13.5 ? null : 'papa'; s.face = T > 15.3 ? SHOCK : FEAR; s.eyeY = 0.15 * Math.sin(T * 1.7); }
  if (inR(T, 21.4, 26.1)) { s.look = 'papa'; s.face = FEAR; }
  if (inR(T, 26.1, 32.6)) { s.look = T < 31.3 ? 'papa' : 'house'; s.face = WORRY; }
  if (inR(T, 32.6, 37.3)) { s.look = T < 33.8 ? 'phone' : null; s.face = T > 35.6 ? SHOCK : FEAR; }
  if (inR(T, 37.3, 39.35)) { s.look = 'pocket'; s.face = SHOCK; }
  if (inR(T, 39.35, 41.9)) {   // il court jusqu'à la porte de Frau Weber
    const u = (T - 39.35) / 2.55; const P = path([KS, V(0.15, -0.48, -11.0), V(0.05, -0.48, -2.9), V(0.05, 0, -1.9), KD], u);
    s.pos = P.p; s.pos.y = yOut(P.p.z); s.yaw = P.yaw; s.layers = CLIP('run2', T * 1.4); s.look = null; s.face = FEAR; return s;
  }
  if (inR(T, 41.9, 46.2)) {
    s.pos = KD.clone(); s.yaw = 0; s.face = FEAR; s.look = T < 42.65 ? null : inR(T, 43.3, 44.4) ? 'papa' : 'weber';
    if (T < 42.7) s.pound = 1;
  }
  if (inR(T, 46.2, 47.5)) { const u = ss(46.25, 47.1, T); const P = path([KD, V(0.12, 0, 0.3), V(0.3, 0, 0.62)], u); s.pos = P.p; s.yaw = P.yaw; if (u > 0 && u < 1) s.layers = CLIP('slowwalk', T * 1.6); s.look = 'door'; s.face = FEAR; }
  if (T >= 47.5) { const u = ss(47.6, 48.3, T); s.pos = V(0.3, 0, 0.62).lerp(KI, u); s.yaw = lerp(0, yawTo(KI, WI), ss(47.5, 48.2, T)); if (u > 0.05 && u < 0.95) s.layers = CLIP('slowwalk', T * 1.2); s.look = 'weber'; s.face = WORRY; }
  if (T >= 48.2) s.face = FEAR;
  if (inR(T, 52.8, 57.9) || T >= 68.85) { s.look = 'door'; s.face = SHOCK; s.yaw = lerp(yawTo(KI, WI), -2.75, ss(52.9, 53.5, T) * (1 - ss(57.8, 58.2, T)) + ss(68.85, 69.4, T)); }
  if (inR(T, 57.9, 59.15)) { s.look = 'weber'; s.face = lips(FEAR, T); }
  if (inR(T, 59.15, 68.85)) { s.look = 'weber'; s.face = FEAR; }
  s.phone = T < 39.35; s.vis = !(inR(T, 60.85, 63.0) || inR(T, 64.47, 66.8));
  return s;
}
function papaState(T) {
  const s = { pos: MS.clone(), yaw: -Math.PI / 2, layers: IDLEM(4 + T * 0.4), face: WARM, look: 'hero', tilt: 0.1, ring: 0 };
  if (T < 6.0) { const x = lerp(11.0, MS.x, T / 6.0); s.pos = V(x, -0.48, ZS); s.layers = CLIP('slowwalk', T * 0.97); s.face = mix(WARM, GRIN, ss(3, 6, T)); return s; }
  if (T < 21.7) { s.face = mix(WARM, GRIN, ss(5, 7, T)); return s; }
  if (T < 23.4) { const u = (T - 21.7) / 1.7; s.pos = MS.clone().lerp(MS2, u); s.layers = CLIP('slowwalk', T); s.face = GRIN; return s; }
  s.pos = MS2.clone(); s.face = GRIN;
  if (inR(T, 23.8, 25.8)) s.face = lips(GRIN, T);
  if (inR(T, 34.6, 39.3)) { s.ring = 1; s.face = GRIN; s.look = T > 37.3 ? 'hero' : 'hero'; }
  if (inR(T, 39.35, 43.2)) { const u = (T - 39.35) / 3.85; s.pos = MS2.clone().lerp(MG, u); s.yaw = yawTo(MS2, MG); s.layers = CLIP('slowwalk', T * 0.8); s.look = null; return s; }
  if (inR(T, 43.2, 52.8)) { s.pos = MG.clone(); s.yaw = 0; s.look = 'weber'; s.face = GRIN; return s; }
  if (T >= 52.8) { s.pos = MD.clone(); s.yaw = 0.55; s.look = 'door'; s.face = GRIN; s.tilt = 0.16; if (inR(T, 55.3, 57.65)) s.face = lips(GRIN, T); }
  return s;
}
function weberState(T) {
  if (T < 42.6) return null;
  const s = { pos: WD.clone(), yaw: Math.PI, layers: IDLEM(2 + T * 0.5), face: WORRY, look: 'hero', door: 0, grab: 0 };
  if (T < 46.0) { s.look = inR(T, 43.35, 46.0) ? 'papa' : 'hero'; s.face = T < 43.4 ? WORRY : T < 44.6 ? FEAR : SHOCK; return s; }
  if (T < 46.95) { s.face = lips(SHOCK, T); s.grab = ss(46.0, 46.3, T) * (1 - ss(46.7, 46.95, T)); s.look = 'hero'; const u = ss(46.3, 46.9, T); s.pos = WD.clone().lerp(V(0.12, 0, 1.0), u); return s; }
  if (T < 48.0) { const u = ss(46.95, 47.3, T); s.pos = V(0.12, 0, 1.0).lerp(V(-0.02, 0, 0.36), u); s.yaw = Math.PI; s.door = ss(46.95, 47.15, T); s.look = 'door'; s.face = FEAR; if (u > 0.05 && u < 0.95) s.layers = CLIP('slowwalk', T * 1.6); if (T > 47.75) { const v = ss(47.75, 48.0, T); s.pos = V(-0.02, 0, 0.36).lerp(WI, v); s.yaw = lerp(Math.PI, yawTo(WI, KI) + 2 * Math.PI, v); } return s; }
  s.pos = WI.clone(); s.yaw = yawTo(WI, KI); s.look = 'hero'; s.face = WORRY;
  if (inR(T, 48.2, 52.75)) { s.layers = TALKING(T, ss(48.1, 48.4, T) * (1 - ss(52.5, 52.8, T)), 0.8); s.face = lips(WORRY, T); }
  if (inR(T, 52.8, 57.9)) { s.look = 'door'; s.face = FEAR; s.yaw = lerp(yawTo(WI, KI), Math.PI, ss(52.9, 53.5, T)); }
  if (inR(T, 57.9, 59.15)) { s.look = 'hero'; s.face = FEAR; }
  if (inR(T, 59.15, 68.6)) { s.layers = TALKING(T, 1, 1.25); s.face = lips(FEAR, T); s.look = inR(T, 60.8, 62.5) ? 'up' : inR(T, 64.5, 66.4) ? 'back' : 'hero'; }
  if (T >= 68.6) { s.look = 'door'; s.face = SHOCK; s.yaw = lerp(yawTo(WI, KI), Math.PI, ss(68.7, 69.3, T)); }
  return s;
}

// ---------- caméra : continue dans chaque lieu ; on coupe seulement quand on change de lieu ----------
const FOC = {
  hero: () => _hw.clone(), papa: () => _pw.clone(), weber: () => _ww.clone(), mid: () => _hw.clone().lerp(_pw, 0.5), mid2: () => _hw.clone().lerp(_ww, 0.5),
  phone: () => phone.position.clone(), pocket: () => pocketPh.position.clone(), door: () => V(0, 1.55, 0.0), glass: () => V(0, 1.62, 0.0),
  rifle: () => V(BX + 0.62, 0.08, 1.95), cellar: () => V(KX - 0.25, 1.0, 4.0), street: () => V(2.5, 0.6, ZS),
};
const CAM = [
  // A — accroche : il court vers nous dans la rue, l'homme derrière ; téléphone à l'oreille ; on se rapproche de son visage
  { t: 0.0, f: 'hero', az: 262, el: 6, d: 2.6, fov: 46, lk: 'mid' },
  { t: 1.4, f: 'hero', az: 250, el: 10, d: 2.2, fov: 44, lk: 'mid' },
  { t: 2.7, f: 'hero', az: 236, el: 6, d: 1.6, fov: 42 },
  { t: 4.4, f: 'hero', az: 285, el: 3, d: 1.05, fov: 38 },
  { t: 6.1, f: 'hero', az: 272, el: 2, d: 0.62, fov: 33 },
  { t: 7.3, f: 'hero', az: 268, el: 1, d: 0.5, fov: 30 },
  // B — « Teil fünf » : vue d'en haut de la rue
  { t: 7.36, cut: 1, f: 'mid', az: 245, el: 42, d: 5.4, fov: 44 },
  { t: 8.45, f: 'mid', az: 258, el: 34, d: 4.8, fov: 42 },
  // C — la policière au téléphone : la caméra tourne autour du fils (devant, côté, derrière vers l'homme)
  { t: 8.47, cut: 1, f: 'hero', az: 300, el: 4, d: 0.75, fov: 36 },
  { t: 11.0, f: 'hero', az: 250, el: 6, d: 0.95, fov: 38 },
  { t: 13.4, f: 'hero', az: 225, el: 8, d: 1.1, fov: 40 },
  { t: 14.4, f: 'hero', az: 165, el: 8, d: 0.95, fov: 40 },
  { t: 15.4, f: 'hero', az: 100, el: 6, d: 0.75, fov: 40, lk: 'papa' },
  { t: 17.2, f: 'hero', az: 300, el: 2, d: 0.62, fov: 33 },
  { t: 19.9, f: 'hero', az: 275, el: 1, d: 0.5, fov: 30 },
  { t: 20.6, f: 'hero', az: 225, el: 18, d: 0.55, fov: 34, lk: 'phone' },
  { t: 21.6, f: 'hero', az: 215, el: 22, d: 0.6, fov: 34, lk: 'phone' },
  // D — l'homme sourit, s'approche, parle
  { t: 21.62, cut: 1, f: 'papa', az: 300, el: 4, d: 1.6, fov: 38 },
  { t: 23.6, f: 'papa', az: 265, el: 2, d: 0.85, fov: 34 },
  { t: 26.1, f: 'papa', az: 255, el: 1, d: 0.6, fov: 30 },
  // E — premier choix : vue d'en haut puis de côté, la maison de Frau Weber (fenêtre allumée) au fond
  { t: 26.12, cut: 1, f: 'hero', az: 235, el: 45, d: 3.2, fov: 42, lk: 'mid' },
  { t: 29.0, f: 'hero', az: 205, el: 18, d: 2.6, fov: 42 },
  { t: 32.6, f: 'hero', az: 215, el: 6, d: 1.4, fov: 40 },
  // F — mauvaise fin : il rappelle… et ça sonne dans la poche de l'homme
  { t: 32.62, cut: 1, f: 'hero', az: 240, el: 14, d: 0.6, fov: 36, lk: 'phone' },
  { t: 34.2, f: 'hero', az: 290, el: 3, d: 0.65, fov: 34 },
  { t: 37.25, f: 'hero', az: 268, el: 1, d: 0.5, fov: 30 },
  { t: 37.27, cut: 1, f: 'pocket', az: 262, el: 12, d: 0.5, fov: 38 },
  { t: 38.3, f: 'pocket', az: 262, el: 30, d: 0.9, fov: 38, lk: 'papa' },
  { t: 39.3, f: 'papa', az: 268, el: 3, d: 0.6, fov: 30 },
  // G — il court chez Frau Weber, tape à la porte, elle ouvre
  { t: 39.33, cut: 1, f: 'hero', az: 150, el: 12, d: 3.0, fov: 46 },
  { t: 40.6, f: 'hero', az: 190, el: 10, d: 2.4, fov: 44 },
  { t: 41.9, p: () => V(0.85, 1.55, -1.95), l: () => FOC.door(), fov: 40 },
  { t: 42.7, p: () => V(0.75, 1.6, -1.6), l: () => FOC.door(), fov: 38 },
  { t: 43.33, p: () => V(0.62, 1.62, -1.3), l: () => FOC.weber(), fov: 34 },
  // H — dans l'entrée : elle voit l'homme au portail, elle blêmit, « Rein. Schnell. », elle ferme à clé, elle raconte
  { t: 43.35, cut: 1, p: () => V(0.22, 1.86, 1.5), l: () => FOC.papa(), fov: 28 },
  { t: 44.5, p: () => V(0.62, 1.56, 0.2), l: () => FOC.weber(), fov: 32 },
  { t: 45.8, p: () => V(0.55, 1.52, 0.18), l: () => FOC.weber(), fov: 29 },
  { t: 46.9, p: () => V(0.75, 1.75, 2.3), l: () => FOC.mid2(), fov: 44 },
  { t: 48.3, p: () => V(0.74, 1.62, 2.45), l: () => FOC.weber(), fov: 38 },
  { t: 52.7, p: () => V(0.6, 1.58, 2.2), l: () => FOC.weber(), fov: 34 },
  { t: 53.7, p: () => V(0.0, 2.35, 2.9), l: () => FOC.glass(), fov: 42 },
  { t: 55.28, p: () => V(0.05, 1.7, 2.0), l: () => FOC.glass(), fov: 34 },
  // I — dehors : l'homme devant la porte, il parle
  { t: 55.3, cut: 1, f: 'papa', az: 70, el: 4, d: 0.8, fov: 34 },
  { t: 57.85, f: 'papa', az: 40, el: 2, d: 0.55, fov: 30 },
  // J — dedans : « Was machen wir ?! » ; elle panique
  { t: 57.88, cut: 1, p: () => V(0.12, 1.52, 0.62), l: () => FOC.hero(), fov: 34 },
  { t: 59.0, p: () => V(0.3, 1.52, 0.55), l: () => FOC.hero(), fov: 33 },
  { t: 59.9, p: () => V(0.78, 1.6, 1.1), l: () => FOC.weber(), fov: 36 },
  { t: 60.83, p: () => V(0.7, 1.55, 2.1), l: () => FOC.weber(), fov: 31 },
  // K — le fusil sous le lit
  { t: 60.85, cut: 1, p: () => V(BX + 1.05, 0.11, 2.45), l: () => FOC.rifle(), fov: 50 },
  { t: 62.98, p: () => V(BX + 0.95, 0.1, 2.2), l: () => FOC.rifle(), fov: 46 },
  // L — elle encore
  { t: 63.0, cut: 1, p: () => V(0.72, 1.55, 2.15), l: () => FOC.weber(), fov: 33 },
  { t: 64.45, p: () => V(0.6, 1.5, 1.95), l: () => FOC.weber(), fov: 30 },
  // M — la porte secrète dans la cave
  { t: 64.47, cut: 1, p: () => V(KX + 0.8, 1.4, 1.2), l: () => FOC.cellar(), fov: 46 },
  { t: 66.78, p: () => V(KX + 0.15, 1.2, 2.7), l: () => FOC.cellar(), fov: 40 },
  // N — dernier choix : tous les deux face à la porte, la silhouette derrière le verre ; la caméra passe devant, au-dessus, derrière
  { t: 66.8, cut: 1, p: () => V(0.7, 1.55, 2.1), l: () => FOC.weber(), fov: 33 },
  { t: 68.9, p: () => V(0.7, 1.75, 2.55), l: () => FOC.mid2(), fov: 40 },
  { t: 70.2, p: () => V(0.1, 2.35, 1.5), l: () => FOC.mid2(), fov: 42 },
  { t: 71.6, p: () => V(-0.55, 1.6, 0.32), l: () => FOC.mid2(), fov: 40 },
  { t: 73.0, p: () => V(-0.1, 2.38, 1.2), l: () => FOC.mid2(), fov: 44 },
  { t: 74.6, p: () => V(0.0, 2.35, 2.75), l: () => FOC.glass(), fov: 42 },
  { t: 77.2, p: () => V(0.05, 1.9, 2.4), l: () => FOC.glass(), fov: 38 },
  { t: 80.2, p: () => V(0.03, 1.68, 0.75), l: () => FOC.glass(), fov: 34 },
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
  const pos = V(v[0] + Math.sin(az) * Math.cos(el) * d, v[1] + Math.sin(el) * d, v[2] + Math.cos(az) * Math.cos(el) * d);
  if (T >= 55.3 && T < 57.88) pos.z = Math.min(pos.z, -0.25);
  if (INSIDE.some(([a, b]) => T >= a && T < b)) { pos.x = Math.max(-0.8, Math.min(0.8, pos.x)); pos.z = Math.max(0.15, pos.z); pos.y = Math.min(2.4, pos.y); }   // jamais dans les murs du couloir
  return { pos, tgt: V(v[6], v[7], v[8]), fov: v[9] };
}
const INSIDE = [[43.35, 55.3], [57.88, 60.85], [63.0, 64.47], [66.8, 80.3]];
const frameOf = (yaw) => ({ f: V(Math.sin(yaw), 0, Math.cos(yaw)), r: V(-Math.cos(yaw), 0, Math.sin(yaw)) });
const boneW = (H, k) => H.bones[H.B[k]].getWorldPosition(new THREE.Vector3());
function headBasis(H, hf) {   // repère de la tête (yeux) : centre, axe latéral, avant, haut ; côté de la main GAUCHE
  const le = boneW(H, 'lEye'), re = boneW(H, 'rEye'); const mid = le.clone().add(re).multiplyScalar(0.5);
  let lat = re.clone().sub(le).normalize(); const lc = boneW(H, 'lClav'), nk = boneW(H, 'neck'); if (lat.dot(lc.clone().sub(nk)) < 0) lat.negate();   // lat pointe vers le côté GAUCHE du corps
  let fwd = new THREE.Vector3().crossVectors(lat, V(0, 1, 0)).normalize(); if (fwd.dot(hf.f) < 0) fwd.negate();
  const up = new THREE.Vector3().crossVectors(fwd, lat).normalize(); if (up.y < 0) up.negate();
  return { mid, lat, fwd, up };
}
function wristFor(mode, h, hf, T) {   // cible du poignet gauche pour chaque position du téléphone
  if (mode === 'ear') { const E = headBasis(HERO, hf); return E.mid.clone().addScaledVector(E.lat, 0.15 + 0.008 * Math.sin(T * 2.3)).addScaledVector(E.up, -0.13 + 0.006 * Math.sin(T * 1.7)).addScaledVector(E.fwd, -0.02); }
  if (mode === 'hand') return h.pos.clone().addScaledVector(hf.f, 0.3).addScaledVector(hf.r, -0.08).add(V(0, 1.06 + 0.01 * Math.sin(T * 2), 0));
  return h.pos.clone().addScaledVector(hf.f, 0.08).addScaledVector(hf.r, -0.22).add(V(0, 0.82, 0));
}
const _knob = new THREE.Vector3();
function frame(T) {
  // porte d'entrée : fermée, elle s'ouvre (42.6), se referme (46.95-47.3), puis tremble quand l'homme essaie d'entrer
  let dA = 0; if (inR(T, 42.6, 47.3)) dA = -1.25 * ss(42.6, 43.05, T) * (1 - ss(46.95, 47.3, T));
  if (T > 55.3) dA += 0.012 * Math.sin(T * 31) * (inAny(T, [[55.4, 56.0], [70.2, 70.9], [72.2, 72.8], [74.6, 75.3], [76.9, 77.6], [79.0, 80.2]]) ? 1 : 0);
  hinge.rotation.y = dA; knob.rotation.z = T > 69 ? 0.5 * Math.sin(T * 9) * (inAny(T, [[70.2, 70.9], [74.6, 75.3], [79.0, 80.2]]) ? 1 : 0) : 0;
  drawGlass(T > 52.9 ? Math.min(1, ss(52.95, 53.6, T)) : 0); setClock('02:47');
  leaves[0].rotation.y = -0.2; leaves[1].rotation.y = 0.2; bHinge.rotation.y = 0; hallL.intensity = 0;
  kHinge.rotation.y = -0.55 - 0.03 * Math.sin(T * 0.9); bulbW.rotation.z = 0.12 * Math.sin(T * 1.9); bulbW.rotation.x = 0.06 * Math.sin(T * 1.3);
  kL.intensity = 6 * (Math.sin(T * 41) * Math.sin(T * 13) > 0.85 ? 0.25 : 1); coldL.intensity = 2.4;
  rifleL.intensity = inR(T, 60.5, 63.2) ? 3.5 : 0; rifleL.position.set(BX + 0.75, 0.27, 2.05);
  const c = camAt(T);
  const ps = papaState(T), h = heroState(T), ws = weberState(T);
  HERO.root.position.copy(h.pos); HERO.root.rotation.y = h.yaw;
  PAPA.root.position.copy(ps.pos); PAPA.root.rotation.y = ps.yaw; PAPA.root.updateMatrixWorld(true); PAPA.headWorld(_pw);
  if (ws) { WEB.root.position.copy(ws.pos); WEB.root.rotation.y = ws.yaw; WEB.root.updateMatrixWorld(true); WEB.headWorld(_ww); } else _ww.set(0.05, 1.55, 0.6);
  const hf = frameOf(h.yaw);
  const lookOf = (k) => k === 'papa' ? _pw.clone() : k === 'weber' ? _ww.clone() : k === 'door' ? V(0, 1.5, 0) : k === 'house' ? V(1.55, 1.55, -0.3) : k === 'phone' ? phone.position.clone()
    : k === 'ahead' ? h.pos.clone().addScaledVector(hf.f, 3).add(V(0, 1.5, 0)) : k === 'pocket' ? pocketPh.position.clone() : k === 'cam' ? camera.position.clone() : k === 'up' ? V(-0.6, 3.5, 6) : k === 'back' ? V(0.2, 1.0, 8) : null;
  // pose du fils (2 passes : la tête d'abord, puis le poignet calé sur la tête)
  const pose = { mo: h.layers, lookW: 0.85 };
  let look = lookOf(h.look); if (h.lookBack) look = h.pos.clone().add(V(4, 1.5, -1.5));
  HERO.setPose(pose, { ...h.face, eyeY: h.eyeY || 0 }, look, T); HERO.headWorld(_hw);
  const run = !!h.layers[0] && h.layers[0].clip === 'run2';
  if (h.phone) {
    const pm = phoneModes(T); const wa = wristFor(pm.a, h, hf, T), wb = wristFor(pm.b, h, hf, T); const wr = wa.lerp(wb, pm.u);
    if (pm.a !== pm.b) wr.addScaledVector(hf.f, 0.08 * Math.sin(pm.u * Math.PI));   // petit arc : le bras passe devant, pas à travers la tête
    Object.assign(pose, { lW: run ? 0.55 : 1, lwx: wr.x, lwy: wr.y, lwz: wr.z, lCurl: 0.75, lWrX: 0 });
  }
  if (h.pound > 0) { const hit = 0.5 + 0.5 * Math.sin(T * 2 * Math.PI * 3.2); const p = V(0.12, 1.42 + 0.05 * hit, -0.07 - 0.12 * hit); Object.assign(pose, { rW: 1, rwx: p.x, rwy: p.y, rwz: p.z, rCurl: 1 }); }
  HERO.setPose(pose, { ...h.face, eyeY: h.eyeY || 0 }, look, T); HERO.headWorld(_hw);
  HERO.root.visible = h.vis && camera.position.distanceTo(_hw) > 0.2;
  phone.visible = h.phone && h.vis;
  if (phone.visible) {
    const pm = phoneModes(T); const E = headBasis(HERO, hf);
    const lh = boneW(HERO, 'lHand'), lf = boneW(HERO, 'lFore'); const dir = lh.clone().sub(lf).normalize();
    const p = lh.clone().addScaledVector(dir, 0.06);
    const earU = (pm.a === 'ear' ? 1 - pm.u : 0) + (pm.b === 'ear' ? pm.u : 0);
    // écran : vers le visage quand il le regarde, vers l'oreille (de côté) quand il écoute ; le téléphone suit la main
    const toFace = _hw.clone().addScaledVector(hf.f, 0.12).sub(p).normalize(), toEar = E.lat.clone().negate();
    const zA = toFace.lerp(toEar, earU).normalize(); const yA = dir.clone().lerp(E.up.clone().addScaledVector(E.fwd, 0.35), earU).addScaledVector(zA, -0.0).normalize();
    const y2 = yA.clone().addScaledVector(zA, -yA.dot(zA)).normalize(); const xA = new THREE.Vector3().crossVectors(y2, zA);
    phone.position.copy(p).addScaledVector(zA, 0.015); phone.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(xA, y2, zA));
    const sc = PH_SCREEN(T); drawScreenP(sc[0], sc[1], sc[2]); phoneL.position.copy(phone.position).addScaledVector(zA, 0.08); phoneL.intensity = 0.12 + 0.6 * (1 - earU);
  } else phoneL.intensity = 0;
  // l'homme
  const pf = frameOf(ps.yaw); const pose2 = { mo: ps.layers, lookW: 1, headZ: ps.tilt || 0 };
  const plook = ps.look === 'hero' ? _hw.clone() : ps.look === 'weber' ? _ww.clone() : ps.look === 'door' ? V(0, 1.6, 0.2) : null;
  PAPA.setPose(pose2, ps.face, plook, T); PAPA.headWorld(_pw);
  const th = boneW(PAPA, 'rThigh'); pocketPh.position.copy(th).addScaledVector(pf.r, 0.09).addScaledVector(pf.f, 0.12).add(V(0, 0.07, 0)); pocketPh.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(pf.r.clone().negate(), V(0, 1, 0), pf.f));
  const buzz = ps.ring ? (Math.floor(T * 1.25) % 2 === 0 ? 1 : 0.3) : 0; pocketPh.visible = ps.ring > 0; pScr.material.color.set(buzz > 0.5 ? '#bfe0ff' : '#5a7aa8');
  pocketL.position.copy(pocketPh.position).addScaledVector(pf.r, 0.06); pocketL.intensity = 1.6 * buzz;
  PAPA.root.visible = camera.position.distanceTo(_pw) > 0.2 && h.vis && !inR(T, 43.35, 43.36 - 1);
  // Frau Weber
  WEB.root.visible = !!ws && h.vis;
  if (ws) {
    const wf = frameOf(ws.yaw); const pose3 = { mo: ws.layers, lookW: 1, headZ: 0.05 };
    if (ws.grab > 0) { const s_ = _hw.clone().add(V(0, -0.24, 0)).addScaledVector(hf.r, 0.17); Object.assign(pose3, { rW: ws.grab, rwx: s_.x, rwy: s_.y, rwz: s_.z, rCurl: 0.7 }); }
    if (ws.door > 0) { knob.getWorldPosition(_knob); Object.assign(pose3, { rW: ws.door, rwx: _knob.x, rwy: _knob.y, rwz: _knob.z + 0.05, rCurl: 0.8 }); }
    const wl = ws.look === 'hero' ? _hw.clone() : ws.look === 'papa' ? _pw.clone() : ws.look === 'door' ? V(0, 1.6, 0) : ws.look === 'up' ? V(-0.6, 3.6, 6) : ws.look === 'back' ? V(0.2, 1.0, 8) : null;
    WEB.setPose(pose3, ws.face, wl, T); WEB.headWorld(_ww);
    WEB.root.visible = WEB.root.visible && camera.position.distanceTo(_ww) > 0.2;
  }
  // lumières
  const outside = c.pos.z < -0.05;
  tvL.intensity = 1.6 + 0.8 * Math.sin(T * 13) * Math.sin(T * 5.3); lamp.intensity = 0.9; streetL.intensity = 3; porchL.intensity = 7; upL.intensity = 4;
  underL.intensity = (T < 39.35 || inR(T, 55.3, 57.9)) && camera.position.distanceTo(_pw) < 2.2 ? 5 : 0; underL.position.copy(_pw).add(V(0, -0.8, 0)).addScaledVector(pf.f, 0.35); underL.target.position.copy(_pw);
  winL.intensity = outside ? 2.5 : 0;
  // caméra (légère main portée, plus forte quand il court)
  const shake = inR(T, 0, 2.6) || inR(T, 39.35, 41.9) ? 0.012 : 0.004;
  camera.position.copy(c.pos).add(V(Math.sin(T * 7.1) * shake, Math.sin(T * 9.3) * shake + (shake > 0.01 ? Math.abs(Math.sin(T * 8.6)) * 0.015 : 0), Math.sin(T * 5.7) * shake));
  camera.up.set(0, 1, 0); camera.lookAt(c.tgt); camera.fov = c.fov;
  fillL.position.copy(camera.position).add(V(0, 0.2, 0)); fillL.target.position.copy(c.tgt); fillL.intensity = 1.6 * Math.max(1, (camera.position.distanceTo(c.tgt) / 1.1) ** 2);
  const w2 = innerWidth, h2 = innerHeight;
  if (canvas.width !== w2) renderer.setSize(w2, h2, false);
  camera.aspect = w2 / h2; camera.updateProjectionMatrix();
  renderer.render(scene, camera);
}
window.renderAt = (T) => frame(T);
window.dbg = (T) => { frame(T); const r = (v) => [v.x, v.y, v.z].map(x => +x.toFixed(2)); const c = camAt(T); return { cam: r(camera.position), tgt: r(c.tgt), fov: c.fov, hero: r(_hw), papa: r(_pw), weber: r(_ww), phone: r(phone.position) }; };
window.READY = true;
if (!MANUAL) { const c0 = performance.now(); const loop = () => { frame(((performance.now() - c0) / 1000) % END); requestAnimationFrame(loop); }; loop(); }
else frame(0);
