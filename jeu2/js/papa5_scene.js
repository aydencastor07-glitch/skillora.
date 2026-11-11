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

