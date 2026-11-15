// « 3:17 » – Lena et ses caméras de surveillance. Appartement : chambre (x < 0), couloir (x 0..5.4), cuisine ouverte au nord
// du couloir (x 1.6..4.0, frigo contre le mur ouest), au bout du couloir (mur est) la caméra cachée et, juste à côté, une porte noire.
// Les vues des caméras (infrarouge, grand angle, horodatage) sont rendues dans une texture puis filtrées (cctv()).
// Chronologie calée sur la voix off (horreur/de_ep07_kamera/words.json). ?manual : rendu image par image (window.renderAt(T)).
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
scene.background = new THREE.Color('#020306');
const hemi = new THREE.HemisphereLight('#6f86b0', '#1a140e', 0.2); scene.add(hemi);
const camera = new THREE.PerspectiveCamera(40, 9 / 16, 0.02, 40);
const fillL = new THREE.SpotLight('#b9c8e6', 1.5, 5, 0.6, 0.9, 1.6); scene.add(fillL, fillL.target);

// ---------- textures ----------
function canvasTex(w, h, draw) {
  const c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d'); draw(g, w, h);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; t.userData = { c, g }; return t;
}
const rnd = (s => () => (s = (s * 16807) % 2147483647) / 2147483647)(23);
const wallT = canvasTex(512, 512, (g, w, h) => {
  g.fillStyle = '#9a958c'; g.fillRect(0, 0, w, h);
  for (let i = 0; i < 2500; i++) { const v = rnd() * 30 - 15; g.fillStyle = `rgba(${128 + v},${124 + v},${116 + v},0.25)`; g.fillRect(rnd() * w, rnd() * h, 2 + rnd() * 3, 2 + rnd() * 3); }
  for (let i = 0; i < 14; i++) { g.fillStyle = `rgba(60,50,40,${0.03 + rnd() * 0.04})`; g.beginPath(); g.arc(rnd() * w, rnd() * h, 20 + rnd() * 70, 0, 7); g.fill(); }
});
wallT.wrapS = wallT.wrapT = THREE.RepeatWrapping; wallT.repeat.set(2, 1);
const planks = canvasTex(512, 512, (g, w, h) => {
  for (let y = 0; y < h; y += 64) { const v = 92 + rnd() * 25 | 0; g.fillStyle = `rgb(${v + 30},${v + 8},${v - 16})`; g.fillRect(0, y, w, 64);
    g.fillStyle = 'rgba(30,18,8,0.5)'; g.fillRect(0, y, w, 3); g.fillRect(rnd() * w, y, 3, 64);
    for (let k = 0; k < 14; k++) { g.fillStyle = `rgba(40,24,10,${rnd() * 0.12})`; g.fillRect(0, y + rnd() * 64, w, 1 + rnd() * 2); } }
});
planks.wrapS = planks.wrapT = THREE.RepeatWrapping; planks.repeat.set(1, 5);
const tiles = canvasTex(512, 512, (g, w, h) => {
  for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) { const v = 160 + rnd() * 18 | 0; g.fillStyle = `rgb(${v},${v - 4},${v - 10})`; g.fillRect(x * 64, y * 64, 64, 64); }
  g.fillStyle = 'rgba(60,55,50,0.6)'; for (let k = 0; k <= 8; k++) { g.fillRect(k * 64 - 1, 0, 3, h); g.fillRect(0, k * 64 - 1, w, 3); }
});
tiles.wrapS = tiles.wrapT = THREE.RepeatWrapping; tiles.repeat.set(4, 3);
const M = (o) => new THREE.MeshStandardMaterial({ roughness: 0.85, metalness: 0, ...o });
const box = (w, h, d, mat, x, y, z, parent = scene, shadow = true) => {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); m.position.set(x, y, z); m.castShadow = shadow; m.receiveShadow = true; parent.add(m); return m;
};
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const HH = 2.5;
const wallM = M({ map: wallT, color: '#c9c3b6' }), bedWallM = M({ map: wallT, color: '#a7b0bd' }), kitWallM = M({ map: wallT, color: '#d8d2c2' });
const ceilM = M({ color: '#b9b5ac', roughness: 1 });
const CEIL = [];
// ---------- chambre (x -3.4..0, z -1.8..1.8) ----------
box(3.4, 0.1, 3.6, M({ map: planks, roughness: 0.7 }), -1.7, -0.05, 0);
CEIL.push(box(3.4, 0.1, 3.6, ceilM, -1.7, HH + 0.05, 0, scene, false));
box(3.4, HH, 0.1, bedWallM, -1.7, HH / 2, -1.85); box(3.4, HH, 0.1, bedWallM, -1.7, HH / 2, 1.85);
// mur ouest avec fenêtre (z 0.1..1.1, y 0.9..2.1)
box(0.1, HH, 1.9, bedWallM, -3.45, HH / 2, -0.85); box(0.1, HH, 0.7, bedWallM, -3.45, HH / 2, 1.45);
box(0.1, 0.9, 1.0, bedWallM, -3.45, 0.45, 0.6); box(0.1, 0.4, 1.0, bedWallM, -3.45, 2.3, 0.6);
const sky = new THREE.Mesh(new THREE.PlaneGeometry(1.0, 1.2), new THREE.MeshBasicMaterial({ color: '#13213d' })); sky.position.set(-3.52, 1.5, 0.6); sky.rotation.y = Math.PI / 2; scene.add(sky);
for (const z of [0.12, 1.08]) box(0.08, 1.2, 0.04, M({ color: '#e6e3dc' }), -3.4, 1.5, z); box(0.08, 0.04, 1.0, M({ color: '#e6e3dc' }), -3.4, 1.5, 0.6);
for (const z of [-0.05, 1.25]) box(0.05, 2.2, 0.35, M({ color: '#4c5468', roughness: 1 }), -3.33, 1.25, z);   // rideaux
// lit (tête contre le mur nord) : couette froissée, oreillers
const bed = new THREE.Group(); scene.add(bed);
box(1.6, 0.32, 2.05, M({ color: '#5a4636', roughness: 0.7 }), -1.8, 0.16, -0.8, bed); box(1.6, 0.9, 0.06, M({ color: '#5a4636' }), -1.8, 0.75, -1.8, bed);
box(1.52, 0.18, 1.95, M({ color: '#e8e6e0' }), -1.8, 0.41, -0.8, bed);
const duvetG = new THREE.BoxGeometry(1.6, 0.12, 1.45, 16, 1, 12); { const p = duvetG.attributes.position; for (let i = 0; i < p.count; i++) { const x = p.getX(i), z = p.getZ(i); if (p.getY(i) > 0) p.setY(i, p.getY(i) + 0.05 * Math.sin(x * 7 + z * 3) + 0.04 * Math.sin(z * 9)); } duvetG.computeVertexNormals(); }
const duvet = new THREE.Mesh(duvetG, M({ color: '#8b9bb4', roughness: 0.95 })); duvet.position.set(-1.85, 0.54, -0.42); duvet.rotation.y = 0.05; duvet.castShadow = duvet.receiveShadow = true; bed.add(duvet);
for (const x of [-2.2, -1.4]) { const p = box(0.6, 0.14, 0.38, M({ color: '#f1efe9' }), x, 0.58, -1.55, bed); p.rotation.x = -0.25; }
// table de nuit, lampe éteinte, verre d'eau ; téléphone posé dessus
box(0.45, 0.55, 0.42, M({ color: '#6d5644', roughness: 0.7 }), -0.75, 0.275, -1.5);
box(0.12, 0.3, 0.12, M({ color: '#d9d2c4' }), -0.62, 0.7, -1.62);
const glass = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.03, 0.11, 16), M({ color: '#a8c0d0', roughness: 0.1, transparent: true, opacity: 0.45 })); glass.position.set(-0.88, 0.61, -1.62); scene.add(glass);
box(0.5, 0.8, 0.35, M({ color: '#4f4136' }), -2.9, 0.4, 1.55);   // commode
box(1.2, 0.02, 0.8, M({ color: '#6c5a6e', roughness: 1 }), -1.1, 0.01, 0.6, scene, false);   // tapis
// ---------- couloir (x 0..5.4, z -0.7..0.7) ----------
box(5.4, 0.1, 1.4, M({ map: planks, roughness: 0.7 }), 2.7, -0.05, 0);
CEIL.push(box(5.4, 0.1, 1.4, ceilM, 2.7, HH + 0.05, 0, scene, false));
box(5.4, HH, 0.1, wallM, 2.7, HH / 2, 0.75);
box(1.6, HH, 0.1, wallM, 0.8, HH / 2, -0.75); box(1.4, HH, 0.1, wallM, 4.7, HH / 2, -0.75);
box(0.06, 0.12, 5.4, M({ color: '#e1dbcf' }), 2.7, 0.06, 0.69, scene, false);
// mur ouest : porte de la chambre (z -0.42..0.42)
box(0.1, HH, 0.28, wallM, 0, HH / 2, -0.56); box(0.1, HH, 0.28, wallM, 0, HH / 2, 0.56); box(0.1, HH - 2.05, 0.84, wallM, 0, 2.05 + (HH - 2.05) / 2, 0);
const dHinge = new THREE.Group(); scene.add(dHinge); dHinge.position.set(0, 0, 0.42);
const doorM = M({ color: '#ece8df', roughness: 0.55 });
box(0.04, 2.04, 0.83, doorM, -0.02, 1.02, -0.42, dHinge);
for (const y of [0.55, 1.5]) box(0.012, 0.7, 0.6, M({ color: '#e2ddd2', roughness: 0.5 }), 0.005, y, -0.42, dHinge, false);
box(0.06, 0.02, 0.12, M({ color: '#9a9a96', metalness: 0.8, roughness: 0.3 }), 0.03, 1.02, -0.74, dHinge, false);
for (const s of [-1, 1]) box(0.12, 2.1, 0.05, M({ color: '#e6e2d8' }), 0.02, 1.05, s * 0.44);
// mur est : à gauche (z -0.62..-0.02) une porte ouverte sur le NOIR ; à droite l'étagère avec la caméra cachée
box(0.1, HH, 0.72, wallM, 5.45, HH / 2, 0.34); box(0.1, HH - 2.0, 0.62, wallM, 5.45, 2.0 + (HH - 2.0) / 2, -0.32); box(0.1, HH, 0.1, wallM, 5.45, HH / 2, -0.67);
const voidM = new THREE.MeshBasicMaterial({ color: '#000000' });
for (const [w, h, x, y, z, ry, rx] of [[1.2, 2.4, 6.9, 1.2, -0.3, -Math.PI / 2, 0], [1.4, 2.4, 6.2, 1.2, -0.9, 0, 0], [1.4, 2.4, 6.2, 1.2, 0.3, Math.PI, 0], [1.4, 1.2, 6.2, 0.0, -0.3, 0, -Math.PI / 2], [1.4, 1.2, 6.2, 2.4, -0.3, 0, Math.PI / 2]]) { const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), voidM); m.position.set(x, y, z); m.rotation.set(rx, ry, 0); scene.add(m); }
const ghostM = new THREE.MeshBasicMaterial({ color: '#0f1013', transparent: true, opacity: 0 });
const ghost = new THREE.Group(); scene.add(ghost); ghost.position.set(5.82, 0, -0.3);
{ const b = new THREE.Mesh(new THREE.CapsuleGeometry(0.15, 1.2, 4, 12), ghostM); b.position.y = 1.05; b.scale.set(1, 1, 0.7); ghost.add(b); const hd = new THREE.Mesh(new THREE.SphereGeometry(0.1, 16, 12), ghostM); hd.position.y = 1.83; hd.scale.set(0.9, 1.25, 0.9); ghost.add(hd); }
for (const s of [-0.63, -0.01]) box(0.12, 2.04, 0.04, M({ color: '#e6e2d8' }), 5.4, 1.02, s);
const eyeM = new THREE.MeshBasicMaterial({ color: '#d8dccf', transparent: true, opacity: 0 });
const EYES = [0.045, -0.045].map(dz => { const e = new THREE.Mesh(new THREE.SphereGeometry(0.0055, 10, 8), eyeM); e.position.set(5.74, 1.85, -0.3 + dz * 0.8); scene.add(e); return e; });
const shelf = box(0.24, 0.025, 0.6, M({ color: '#5e4a3a' }), 5.28, 1.72, 0.33);
for (let i = 0; i < 6; i++) { const b = box(0.17, 0.2 + rnd() * 0.06, 0.035, M({ color: ['#6b2f2a', '#2f4b5e', '#7a6a3a', '#3c3c44', '#5b3d5c', '#8a8070'][i] }), 5.3, 1.84, 0.6 - i * 0.04); b.position.y = 1.735 + b.geometry.parameters.height / 2; }
const pot = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.05, 0.11, 14), M({ color: '#b4683f' })); pot.position.set(5.3, 1.79, 0.08); scene.add(pot);
for (let i = 0; i < 7; i++) { const l = new THREE.Mesh(new THREE.SphereGeometry(0.05, 8, 6), M({ color: '#3d5a2c' })); l.scale.set(0.5, 1.4, 0.3); l.position.set(5.3 + (rnd() - 0.5) * 0.06, 1.92, 0.08 + (rnd() - 0.5) * 0.08); l.rotation.set(rnd() - 0.5, rnd() * 3, rnd() - 0.5); scene.add(l); }
// la petite caméra blanche (dôme), LED rouge
const cam2 = new THREE.Group(); scene.add(cam2); cam2.position.set(5.3, 1.735, 0.33);
{ const b = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.04, 0.03, 20), M({ color: '#ecebe7', roughness: 0.4 })); b.position.y = 0.015; cam2.add(b);
  const d = new THREE.Mesh(new THREE.SphereGeometry(0.034, 20, 12), M({ color: '#f2f1ee', roughness: 0.3 })); d.position.y = 0.06; cam2.add(d);
  const lens = new THREE.Mesh(new THREE.CircleGeometry(0.014, 16), M({ color: '#050608', roughness: 0.1, metalness: 0.5 })); lens.position.set(-0.033, 0.062, 0); lens.rotation.y = -Math.PI / 2; cam2.add(lens); }
const led = new THREE.Mesh(new THREE.SphereGeometry(0.004, 8, 6), new THREE.MeshBasicMaterial({ color: '#ff2a1a', toneMapped: false })); led.position.set(5.297, 1.775, 0.355); scene.add(led);
const ledL = new THREE.PointLight('#ff2a1a', 0.06, 0.4, 2); ledL.position.copy(led.position).add(V(-0.03, 0, 0)); scene.add(ledL);
// tableaux, patère, tapis de couloir
const photo = canvasTex(256, 192, (g, w, h) => { const gr = g.createLinearGradient(0, 0, w, h); gr.addColorStop(0, '#7f8c95'); gr.addColorStop(1, '#a89a7a'); g.fillStyle = gr; g.fillRect(0, 0, w, h); g.filter = 'blur(5px)'; g.fillStyle = '#d9c3a5'; g.beginPath(); g.arc(128, 80, 34, 0, 7); g.fill(); g.fillStyle = '#4a5560'; g.fillRect(84, 112, 88, 90); g.filter = 'none'; });
for (const [x, y, s] of [[1.0, 1.55, 1], [3.6, 1.6, 0.8]]) { box(0.44 * s, 0.34 * s, 0.03, M({ color: '#2a2622' }), x, y, 0.735, scene, false); const p = new THREE.Mesh(new THREE.PlaneGeometry(0.38 * s, 0.28 * s), M({ map: photo, roughness: 0.4 })); p.position.set(x, y, 0.718); p.rotation.y = Math.PI; scene.add(p); }
box(0.6, 0.04, 0.06, M({ color: '#3a2c22' }), 2.4, 1.7, 0.71, scene, false);
for (const [x, c] of [[2.25, '#3b4a5c'], [2.55, '#6e5040']]) { const jk = box(0.3, 0.75, 0.1, M({ color: c, roughness: 1 }), x, 1.32, 0.64); jk.rotation.z = (rnd() - 0.5) * 0.1; }
box(3.8, 0.012, 0.75, M({ color: '#6e3d36', roughness: 1 }), 2.6, 0.006, 0.05, scene, false);
// ---------- cuisine (x 1.6..4.0, z -2.7..-0.7) ----------
box(2.4, 0.1, 2.0, M({ map: tiles, roughness: 0.5 }), 2.8, -0.049, -1.7);
CEIL.push(box(2.4, 0.1, 2.0, ceilM, 2.8, HH + 0.05, -1.7, scene, false));
box(0.1, HH, 2.0, kitWallM, 1.55, HH / 2, -1.7); box(0.1, HH, 2.0, kitWallM, 4.05, HH / 2, -1.7);
// mur nord avec fenêtre au-dessus de l'évier (x 2.7..3.5, y 1.15..2.05)
box(1.1, HH, 0.1, kitWallM, 2.15, HH / 2, -2.75); box(0.5, HH, 0.1, kitWallM, 3.75, HH / 2, -2.75);
box(0.8, 1.15, 0.1, kitWallM, 3.1, 0.575, -2.75); box(0.8, 0.45, 0.1, kitWallM, 3.1, 2.275, -2.75);
const sky2 = new THREE.Mesh(new THREE.PlaneGeometry(0.8, 0.9), new THREE.MeshBasicMaterial({ color: '#13213d' })); sky2.position.set(3.1, 1.6, -2.82); scene.add(sky2);
box(0.04, 0.9, 0.06, M({ color: '#e6e3dc' }), 3.1, 1.6, -2.7);
// plan de travail, placards, évier, bouilloire, planche
const cabM = M({ color: '#d7d2c6', roughness: 0.6 }), topM = M({ color: '#3a3836', roughness: 0.4 });
box(1.7, 0.86, 0.6, cabM, 3.15, 0.43, -2.4); box(1.74, 0.04, 0.64, topM, 3.15, 0.88, -2.4);
for (let i = 0; i < 4; i++) box(0.4, 0.78, 0.01, M({ color: '#cbc5b8', roughness: 0.6 }), 2.5 + i * 0.43, 0.44, -2.095, scene, false);
box(0.5, 0.02, 0.38, M({ color: '#8f9396', metalness: 0.7, roughness: 0.3 }), 3.1, 0.905, -2.42);
const kettle = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.09, 0.2, 16), M({ color: '#2f2f33', roughness: 0.3, metalness: 0.4 })); kettle.position.set(3.7, 1.0, -2.45); scene.add(kettle);
box(0.3, 0.02, 0.2, M({ color: '#9b7a52' }), 2.7, 0.91, -2.45);
for (const x of [2.6, 3.7]) box(0.62, 0.7, 0.35, cabM, x, 1.95, -2.53);
// table + chaise contre le mur est de la cuisine, tasse
box(0.7, 0.04, 0.7, M({ color: '#7b5b3f', roughness: 0.6 }), 3.6, 0.74, -1.25); for (const [dx, dz] of [[-0.3, -0.3], [0.3, -0.3], [-0.3, 0.3], [0.3, 0.3]]) box(0.04, 0.72, 0.04, M({ color: '#5b4330' }), 3.6 + dx, 0.36, -1.25 + dz);
box(0.38, 0.04, 0.38, M({ color: '#5b4330' }), 3.15, 0.45, -1.25); box(0.04, 0.45, 0.38, M({ color: '#5b4330' }), 2.95, 0.7, -1.25);
const mug = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.035, 0.09, 14), M({ color: '#c8513c' })); mug.position.set(3.5, 0.81, -1.15); scene.add(mug);
// le frigo (contre le mur ouest, façade vers +x) : caisse creuse, étagères, porte à charnière au nord
const fridge = new THREE.Group(); scene.add(fridge); fridge.position.set(1.6, 0, -1.6);
const frM = M({ color: '#e4e6e5', roughness: 0.35 }), inM = M({ color: '#f4f6f6', roughness: 0.5, emissive: '#cfe3ff', emissiveIntensity: 0 });
box(0.05, 1.85, 0.7, frM, 0.025, 0.925, 0, fridge); box(0.65, 0.05, 0.7, frM, 0.325, 1.825, 0, fridge); box(0.65, 0.08, 0.7, frM, 0.325, 0.04, 0, fridge);
box(0.65, 1.85, 0.04, frM, 0.325, 0.925, -0.33, fridge); box(0.65, 1.85, 0.04, frM, 0.325, 0.925, 0.33, fridge);
box(0.02, 1.7, 0.62, inM, 0.06, 0.93, 0, fridge, false);
for (const y of [0.45, 0.85, 1.25]) box(0.56, 0.015, 0.6, M({ color: '#dfeaf2', roughness: 0.1, transparent: true, opacity: 0.7 }), 0.35, y, 0, fridge, false);
for (const [x, y, z, w, h, c] of [[0.3, 0.55, -0.15, 0.12, 0.2, '#e8e2c8'], [0.35, 0.52, 0.12, 0.18, 0.12, '#8c3b2e'], [0.28, 0.95, 0.05, 0.08, 0.2, '#f2f2ee'], [0.3, 1.33, -0.12, 0.2, 0.1, '#5f7f45'], [0.3, 0.94, -0.18, 0.14, 0.16, '#d8a23a']])
  box(w, h, w, M({ color: c, roughness: 0.6 }), x, y + h / 2 - 0.05, z, fridge, false);
const fHinge = new THREE.Group(); scene.add(fHinge); fHinge.position.set(2.27, 0, -1.95);
box(0.05, 1.83, 0.7, frM, 0, 0.925, 0.35, fHinge);
box(0.012, 1.75, 0.6, M({ color: '#e9ecec', roughness: 0.5 }), -0.03, 0.93, 0.35, fHinge, false);
for (const y of [0.5, 0.95, 1.4]) box(0.1, 0.08, 0.56, M({ color: '#dfe7ea', roughness: 0.2, transparent: true, opacity: 0.75 }), -0.08, y, 0.35, fHinge, false);
box(0.03, 0.5, 0.03, M({ color: '#a7aaaa', metalness: 0.6, roughness: 0.3 }), 0.04, 1.15, 0.64, fHinge, false);
const handle = new THREE.Object3D(); handle.position.set(0.06, 1.12, 0.64); fHinge.add(handle);
box(0.18, 0.12, 0.01, M({ color: '#f5d33b' }), 0.026, 1.5, 0.25, fHinge, false).rotation.y = Math.PI / 2;   // magnets / mot
box(0.12, 0.15, 0.01, M({ color: '#9fc0e0' }), 0.026, 1.25, 0.45, fHinge, false).rotation.y = Math.PI / 2;
const fridgeL = new THREE.PointLight('#dfeeff', 0, 3.2, 1.6); fridgeL.position.set(2.05, 1.15, -1.6); scene.add(fridgeL);
const fridgeS = new THREE.SpotLight('#d8e8ff', 0, 5, 0.75, 0.6, 1.4); fridgeS.position.set(2.0, 1.3, -1.6); fridgeS.target.position.set(3.4, 1.1, -1.4); fridgeS.castShadow = true; fridgeS.shadow.mapSize.set(1024, 1024); scene.add(fridgeS, fridgeS.target);
// caméra 1 (cuisine), dans le coin en haut
const cam1 = new THREE.Group(); scene.add(cam1); cam1.position.set(3.95, 2.3, -0.82);
{ const d = new THREE.Mesh(new THREE.SphereGeometry(0.04, 16, 10), M({ color: '#ecebe7', roughness: 0.3 })); cam1.add(d); }

// ---------- lumières ----------
const moon = new THREE.SpotLight('#7d98d6', 0, 9, 0.5, 0.7, 1); moon.position.set(-4.8, 2.7, 0.8); moon.target.position.set(-1.4, 0.2, -0.6); moon.castShadow = true; moon.shadow.mapSize.set(1024, 1024); scene.add(moon, moon.target);
const moon2 = new THREE.SpotLight('#7d98d6', 0, 8, 0.6, 0.8, 1); moon2.position.set(3.1, 2.4, -4.2); moon2.target.position.set(2.6, 0, -0.9); moon2.castShadow = true; scene.add(moon2, moon2.target);
const sun = new THREE.SpotLight('#ffe2b8', 0, 12, 0.7, 0.5, 1); sun.position.set(3.4, 3.2, -4.8); sun.target.position.set(2.6, 0, -0.6); sun.castShadow = true; sun.shadow.mapSize.set(1024, 1024); scene.add(sun, sun.target);
const hallLamp = new THREE.PointLight('#ffc98a', 0, 7, 1.4); hallLamp.position.set(3.4, 2.35, 0); hallLamp.castShadow = true; scene.add(hallLamp);
const kitLamp = new THREE.PointLight('#fff1dc', 0, 6, 1.4); kitLamp.position.set(2.8, 2.35, -1.7); scene.add(kitLamp);
const irL = new THREE.PointLight('#ffffff', 0, 9, 1.3); scene.add(irL);
const nightL = new THREE.PointLight('#5f78b8', 0, 5, 1.5); nightL.position.set(4.4, 0.35, 0.55); scene.add(nightL);   // petite veilleuse dans le couloir
const phoneL = new THREE.PointLight('#a9c4ff', 0, 1.2, 2); scene.add(phoneL);

// ---------- téléphone (écran dessiné : écran verrouillé, 03:17, notification) ----------
const scrTex = canvasTex(360, 760, () => {});
let scrState = '';
function drawScreen(on) {
  const st = on ? 'on' : 'off'; if (st === scrState) return; scrState = st; const { g, c } = scrTex.userData, w = c.width, h = c.height;
  if (!on) { g.fillStyle = '#030305'; g.fillRect(0, 0, w, h); scrTex.needsUpdate = true; return; }
  const gr = g.createLinearGradient(0, 0, w, h); gr.addColorStop(0, '#1d2c4f'); gr.addColorStop(1, '#3b2347'); g.fillStyle = gr; g.fillRect(0, 0, w, h);
  g.fillStyle = '#fff'; g.textAlign = 'center'; g.font = '300 118px Helvetica, Arial, sans-serif'; g.fillText('3:17', w / 2, 210);
  g.font = '500 26px Helvetica, Arial, sans-serif'; g.fillText('Sonntag, 15. November', w / 2, 92);
  const y0 = 300; g.fillStyle = 'rgba(235,238,245,0.9)'; g.beginPath(); g.roundRect(18, y0, w - 36, 132, 26); g.fill();
  g.fillStyle = '#2c6bd8'; g.beginPath(); g.roundRect(36, y0 + 26, 52, 52, 12); g.fill();
  g.fillStyle = '#fff'; g.beginPath(); g.roundRect(46, y0 + 40, 26, 22, 4); g.fill(); g.beginPath(); g.moveTo(72, y0 + 51); g.lineTo(82, y0 + 43); g.lineTo(82, y0 + 59); g.fill();
  g.textAlign = 'left'; g.fillStyle = '#111'; g.font = '700 25px Helvetica, Arial, sans-serif'; g.fillText('Küchenkamera', 104, y0 + 46);
  g.font = '400 25px Helvetica, Arial, sans-serif'; g.fillText('Bewegung erkannt', 104, y0 + 82); g.fillStyle = '#666'; g.font = '400 20px Helvetica, Arial, sans-serif'; g.fillText('Küche · 03:17', 104, y0 + 112);
  g.textAlign = 'right'; g.fillText('jetzt', w - 38, y0 + 46);
  scrTex.needsUpdate = true;
}
const phone = new THREE.Group(); scene.add(phone);
box(0.072, 0.152, 0.008, M({ color: '#111216', roughness: 0.3, metalness: 0.5 }), 0, 0, -0.004, phone, false);
const scr = new THREE.Mesh(new THREE.PlaneGeometry(0.066, 0.143), new THREE.MeshBasicMaterial({ map: scrTex, toneMapped: false })); scr.position.z = 0.0005; phone.add(scr);
drawScreen(false);

// ---------- Lena ----------
await RealHuman.loadClips(['idle', 'slowwalk'], './mocap/');
const ENV = await (await fetch('./mocap/voice_kam.json')).json();
const LENA = await RealHuman.create('./models/g_Female_Adult_05.glb', { heightM: 1.66, seed: 3 });
scene.add(LENA.root); LENA.root.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });

// ---------- outils ----------
const ss = (a, b, x) => { const u = Math.min(1, Math.max(0, (x - a) / (b - a))); return u * u * (3 - 2 * u); };
const lerp = (a, b, u) => a + (b - a) * u;
const inR = (T, a, b) => T >= a && T < b;
const FULL = { pelvis: 1, spineAbs: 1, legs: 1, arms: 1, root: 1, headAbs: 0.3 };
const dur = (c) => RealHuman.clips[c].frames / RealHuman.clips[c].fps;
const loopT = (c, x) => ((x % dur(c)) + dur(c)) % dur(c);
const IDLE = (t, arms = 1) => [{ clip: 'idle', mode: 'abs', t: loopT('idle', t), k: 1, w: { legs: 1, root: 1, pelvis: 0.5, spineAbs: 0.5, arms } }];
const WALK = (t, arms = 1) => [{ clip: 'slowwalk', mode: 'abs', t: loopT('slowwalk', t), k: 1, w: { ...FULL, arms } }];
const SLEEPY = { squint: 0.55, raw: { BrowInnerUp: 0.3, EyeSquintLeft: 0.4, EyeSquintRight: 0.4 } };
const READ = { squint: 0.3, raw: { BrowInnerUp: 0.5, BrowDownLeft: 0.2, BrowDownRight: 0.2 } };
const CONF = { maxM: 1.2, raw: { BrowInnerUp: 0.9, BrowDownLeft: 0.3, BrowDownRight: 0.3, MouthPressLeft: 0.4, MouthPressRight: 0.4, MouthFrownLeft: 0.2, MouthFrownRight: 0.2 } };
const FOCUS = { raw: { BrowDownLeft: 0.25, BrowDownRight: 0.25, MouthPressLeft: 0.35, MouthPressRight: 0.35 } };
const BLANK = { noBlink: true, maxM: 1.2, raw: { EyeWideLeft: 0.55, EyeWideRight: 0.55, MouthClose: 0.1, BrowDownLeft: 0.05, BrowDownRight: 0.05 } };
const env = (T) => { const i = Math.floor(T * 30); return ENV[Math.max(0, Math.min(ENV.length - 1, i))] || 0; };
const whisper = (T) => { const e = Math.min(1, env(T) * 1.4); return { ...BLANK, raw: { ...BLANK.raw, JawOpen: 0.04 + 0.22 * e, MouthLowerDownLeft: 0.2 * e, MouthLowerDownRight: 0.2 * e, MouthFunnel: 0.25 * e } }; };
const yawTo = (a, b) => Math.atan2(b.x - a.x, b.z - a.z);
const path = (pts, u) => {
  const L = []; let tot = 0; for (let i = 1; i < pts.length; i++) { const d = pts[i].distanceTo(pts[i - 1]); L.push(d); tot += d; }
  let s = Math.min(1, Math.max(0, u)) * tot; for (let i = 0; i < L.length; i++) { if (s <= L[i] || i === L.length - 1) { const p = pts[i].clone().lerp(pts[i + 1], Math.min(1, s / L[i])); return { p, yaw: yawTo(pts[i], pts[i + 1]), tot }; } s -= L[i]; }
};
const pathLen = (pts) => pts.slice(1).reduce((a, p, i) => a + p.distanceTo(pts[i]), 0);
const frameOf = (yaw) => ({ f: V(Math.sin(yaw), 0, Math.cos(yaw)), r: V(-Math.cos(yaw), 0, Math.sin(yaw)) });
const boneW = (H, k) => H.bones[H.B[k]].getWorldPosition(new THREE.Vector3());
const WALKV = RealHuman.clips.slowwalk.speed || 1.0;

// ---------- chronologie (voix : words.json, 42,5 s) ----------
const END = 42.6;
const NIGHT_A = [0, 10.1], MORNING = [10.1, 14.0], EVENING = [14.0, 18.85];
const SEAT = V(-1.08, 0, -0.62);                              // assise au bord du lit, vers +x
const FRIDGE_P = V(2.85, 0, -1.55);                           // devant le frigo (vers -x)
const DARK = V(5.45, 1.62, -0.32);                            // la porte noire à côté de la caméra
const SW = [V(-0.75, 0, -0.05), V(0.4, 0, 0.0), V(1.5, 0, -0.12), FRIDGE_P];   // somnambule : chambre -> frigo
const SW0 = 21.85, SWL = pathLen(SW), SWV = 0.8;              // départ, longueur, vitesse (m/s)
const SW1 = SW0 + SWL / SWV;
const MW = [V(0.7, 0, 0.15), V(2.0, 0, -0.25), V(2.95, 0, -0.95)];   // le matin : elle entre dans la cuisine
const EW = [V(5.0, 0, 0.33), V(3.6, 0, 0.1), V(0.9, 0, 0.0)];        // le soir : elle repart vers la chambre
const YAW_DARK = yawTo(FRIDGE_P, DARK);
function fridgeOpen(T) {
  if (inR(T, 9.7, 14.0)) return 1.25;                          // vidéo qui revient + le matin : la porte est ouverte
  if (T >= 26.75) return 1.35 * ss(26.75, 27.6, T);
  return 0;
}
function doorOpen(T) {
  if (inR(T, 10.1, 18.85)) return 1.45;                        // le jour la porte de la chambre est ouverte
  if (T >= 20.9) return 1.25 * ss(20.9, 22.3, T) + 0.02 * Math.sin(T * 0.7);
  return 0;
}
function lenaState(T) {
  const s = { pos: SEAT.clone(), yaw: Math.PI / 2, layers: IDLE(T * 0.7, 0.4), face: SLEEPY, look: 'phone', sit: 0, phone: null, vis: true, lHand: null, rHand: null, lookW: 0.85 };
  if (T < 10.1) { s.sit = 1; s.phone = T > 1.75 ? 'hand' : null; s.face = T < 4.7 ? SLEEPY : READ; s.vis = T >= 1.75 && T < 6.1; return s; }
  if (T < 14.0) {    // le matin
    const u = Math.min(1, (T - 10.2) * 0.95 / pathLen(MW)); const P = path(MW, u); s.pos = P.p; s.yaw = u < 1 ? P.yaw : lerp(P.yaw, yawTo(P.p, V(2.0, 1, -1.5)), ss(12.0, 12.8, T));
    s.layers = u > 0 && u < 1 ? WALK(T, 1) : IDLE(T * 0.8, 1); s.face = CONF; s.look = T < 12.6 ? 'fridge' : 'around'; return s;
  }
  if (T < 18.85) {   // le soir : elle cache la caméra puis repart
    s.pos = EW[0].clone(); s.yaw = Math.PI / 2; s.face = FOCUS; s.look = 'cam2'; s.layers = IDLE(T * 0.8, 1);
    if (T < 16.3) s.rHand = cam2.position.clone().add(V(-0.05, 0.04 + 0.01 * Math.sin(T * 3), -0.03));
    if (T > 16.45) { const u = Math.min(1, (T - 16.45) * 1.0 / pathLen(EW)); const P = path(EW, u); s.pos = P.p; s.yaw = lerp(Math.PI / 2, P.yaw + 2 * Math.PI, ss(16.45, 16.9, T)); s.layers = WALK(T, 1); s.look = null; }
    return s;
  }
  // la nuit : elle sort de la chambre, va au frigo, s'arrête, tourne la tête puis le corps vers le noir
  s.face = BLANK; s.lookW = 1;
  if (T < SW0) { s.pos = SW[0].clone(); s.yaw = Math.PI / 2; s.layers = IDLE(T * 0.5, 0.3); s.look = 'ahead'; return s; }
  if (T < SW1) { const P = path(SW, (T - SW0) * SWV / SWL); s.pos = P.p; s.yaw = P.yaw; s.layers = WALK((T - SW0) * SWV / WALKV, 0.35); s.look = 'ahead'; }
  else { s.pos = FRIDGE_P.clone(); s.yaw = -Math.PI / 2; s.layers = IDLE(T * 0.4, 0.3); s.look = 'fridgeIn'; }
  if (inR(T, 26.5, 27.7)) s.lHand = handle.getWorldPosition(new THREE.Vector3()).add(V(0.03, 0, 0));
  if (T >= 30.6) {   // la tête d'abord, puis le corps qui suit lentement
    s.look = 'turn'; s.yaw = lerp(-Math.PI / 2, YAW_DARK, ss(31.0, 33.0, T)); s.lookW = 1;
  }
  if (inR(T, 33.3, 34.1)) s.face = whisper(T);
  return s;
}

// ---------- vues des caméras de surveillance ----------
const CC = {
  k: { cam: new THREE.PerspectiveCamera(78, 9 / 16, 0.05, 20), pos: V(3.9, 2.27, -0.86), tgt: V(2.2, 0.8, -1.65), name: 'CAM 1 · KÜCHE' },
  f: { cam: new THREE.PerspectiveCamera(92, 9 / 16, 0.05, 20), pos: V(5.25, 1.81, 0.33), tgt: V(1.6, 0.95, -0.55), name: 'CAM 2 · FLUR' },
};
for (const k in CC) { const c = CC[k]; c.cam.position.copy(c.pos); c.cam.lookAt(c.tgt); c.cam.updateMatrixWorld(true); }
const RT = new THREE.WebGLRenderTarget(405, 720, { samples: 2 });
const ovTex = canvasTex(1080, 1920, () => {});
let ovKey = '';
function drawOverlay(name, time, extra) {
  const key = name + time + extra; if (key === ovKey) return; ovKey = key; const { g, c } = ovTex.userData; g.clearRect(0, 0, c.width, c.height);
  g.font = 'bold 46px "DejaVu Sans Mono", "Courier New", monospace'; g.textBaseline = 'middle'; g.shadowColor = 'rgba(0,0,0,0.9)'; g.shadowBlur = 6;
  g.fillStyle = '#f2f2ea'; g.textAlign = 'left'; g.fillText(name, 70, 380);
  g.fillStyle = '#ff3b2f'; g.beginPath(); g.arc(860, 380, 15, 0, 7); g.fill(); g.fillStyle = '#f2f2ea'; g.fillText('REC', 888, 380);
  g.textAlign = 'right'; g.fillText('15.11.2026  ' + time, 1010, 1300);
  if (extra) { g.textAlign = 'left'; g.fillText(extra, 70, 1300); }
  g.shadowBlur = 0; ovTex.needsUpdate = true;
}
const postM = new THREE.ShaderMaterial({
  uniforms: { tex: { value: RT.texture }, ovl: { value: ovTex }, time: { value: 0 }, zoom: { value: 1 }, zc: { value: new THREE.Vector2(0.5, 0.5) }, black: { value: 0 }, gain: { value: 1 }, pix: { value: 0 } },
  vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }',
  fragmentShader: `uniform sampler2D tex, ovl; uniform float time, zoom, black, gain, pix; uniform vec2 zc; varying vec2 vUv;
    float h(vec2 p){ return fract(sin(dot(p, vec2(12.9898, 78.233)) + time * 61.7) * 43758.5453); }
    vec3 aces(vec3 x){ return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0); }
    void main(){
      vec2 c = vUv - 0.5; vec2 a = c * vec2(0.5625, 1.0); float r2 = dot(a, a);
      vec2 d = c * (1.0 - 0.22 * r2);                      // grand angle (barillet)
      vec2 uv = zc + d / zoom;
      if (pix > 0.0) { vec2 res = vec2(405.0, 720.0) / pix; uv = (floor(uv * res) + 0.5) / res; }
      vec3 col = texture2D(tex, uv).rgb * gain;
      float l = dot(aces(col * 1.4), vec3(0.3, 0.59, 0.11)); l = pow(l, 1.0 / 2.0);
      l += (h(vUv * 731.0) - 0.5) * 0.09; l *= 0.95 + 0.05 * sin(vUv.y * 1100.0 + time * 40.0);
      l *= 1.0 - 0.75 * smoothstep(0.08, 0.32, r2);         // vignette
      vec3 o = vec3(l) * vec3(0.93, 1.0, 0.96) * (1.0 - black);
      vec4 ov = texture2D(ovl, vUv); o = mix(o, ov.rgb, ov.a);
      gl_FragColor = vec4(o, 1.0); }`,
  depthTest: false, depthWrite: false,
});
ovTex.colorSpace = THREE.NoColorSpace;
const postScene = new THREE.Scene(); postScene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), postM)); const postCam = new THREE.Camera();
const clock = (s) => { const h = Math.floor(s / 3600), m = Math.floor(s / 60) % 60, x = Math.floor(s) % 60; return [h, m, x].map(v => String(v).padStart(2, '0')).join(':'); };
const T317 = 3 * 3600 + 17 * 60;
// [t0, t1, caméra, horloge(T) en s, options]
const CCTV = [
  [6.1, 10.1, 'k', (T) => T < 7.3 ? T317 - 2 + (T - 6.1) * 1.6 : T < 9.72 ? T317 + Math.floor(180 * ss(7.4, 9.65, T)) : T317 + 181 + (T - 9.72), (T) => ({ black: inR(T, 7.3, 9.72) ? 1 : 0 })],
  [18.85, 23.95, 'f', (T) => T317 - 1.4 + (T - 20.3)],
  [29.45, 30.55, 'f', (T) => T317 + 30 + (T - 29.45) * 420, () => ({ extra: '▶▶ x32' })],
  [34.05, 36.35, 'f', (T) => T317 + 512 + (T - 34.05), (T) => ({ zoom: lerp(1.0, 4.2, ss(34.1, 35.0, T)), pix: ss(34.3, 35.0, T) * 1.6, focus: 'lena' })],
];
function cctvAt(T) { for (const c of CCTV) if (T >= c[0] && T < c[1]) return c; return null; }

// ---------- caméra du film ----------
const _hw = new THREE.Vector3();
const FOC = { lena: () => _hw.clone(), phone: () => phone.position.clone(), cam2: () => cam2.position.clone().add(V(0, 0.05, 0)), dark: () => DARK.clone(), fridge: () => V(2.1, 1.1, -1.6), door: () => V(0, 1.2, 0) };
const CAM = [
  // A — 3:17 : le téléphone s'allume sur la table de nuit (vue du dessus qui descend)
  { t: 0.0, p: () => V(-0.45, 1.25, -1.1), l: () => V(-0.74, 0.56, -1.45), fov: 40 },
  { t: 1.73, p: () => V(-0.58, 0.92, -1.28), l: () => V(-0.74, 0.56, -1.45), fov: 32 },
  // B — Lena assise au bord du lit, le visage éclairé par l'écran ; la caméra tourne lentement autour
  { t: 1.75, cut: 1, f: 'lena', az: 55, el: -6, d: 1.0, fov: 40 },
  { t: 3.2, f: 'lena', az: 85, el: -9, d: 0.8, fov: 36 },
  { t: 4.68, f: 'lena', az: 105, el: -8, d: 0.62, fov: 32 },
  // C — l'écran : « Bewegung erkannt »
  { t: 4.7, cut: 1, p: () => phone.position.clone().addScaledVector(V(0, 0, 1).applyQuaternion(phone.quaternion), 0.2).add(V(0, 0.02, 0)), l: () => phone.position.clone(), fov: 40 },
  { t: 6.08, p: () => phone.position.clone().addScaledVector(V(0, 0, 1).applyQuaternion(phone.quaternion), 0.15).add(V(0, 0.015, 0)), l: () => phone.position.clone(), fov: 38 },
  // (6.1-10.1 : vue de la caméra de la cuisine)
  // D — le matin : la porte du frigo ouverte, Lena arrive
  { t: 10.1, cut: 1, p: () => V(3.75, 1.55, -1.95), l: () => V(2.2, 1.0, -0.9), fov: 50 },
  { t: 11.4, p: () => V(3.7, 1.5, -1.95), l: () => FOC.lena(), fov: 42 },
  { t: 12.62, p: () => V(3.6, 1.5, -1.9), l: () => FOC.lena(), fov: 36 },
  // E — « Lena lebte allein. » : vue large depuis le coin du couloir
  { t: 12.65, cut: 1, p: () => V(5.2, 2.3, 0.6), l: () => V(2.6, 0.8, -1.2), fov: 50 },
  { t: 13.98, p: () => V(5.15, 2.25, 0.5), l: () => V(2.6, 0.85, -1.2), fov: 46 },
  // F — le soir : elle cache la caméra sur l'étagère
  { t: 14.0, cut: 1, p: () => V(4.72, 1.98, -0.25), l: () => FOC.cam2(), fov: 36 },
  { t: 15.2, p: () => V(4.8, 1.9, -0.15), l: () => FOC.cam2(), fov: 30 },
  { t: 16.4, p: () => V(4.85, 1.88, -0.05), l: () => FOC.cam2(), fov: 28 },
  // G — derrière la caméra : le couloir, la porte de la chambre en face ; elle s'en va
  { t: 16.42, cut: 1, p: () => V(5.36, 1.86, 0.36), l: () => V(0.0, 1.05, 0.0), fov: 46 },
  { t: 18.83, p: () => V(5.3, 1.84, 0.36), l: () => V(0.0, 1.05, 0.0), fov: 38 },
  // (18.85-23.95 : caméra du couloir, la porte s'ouvre, elle sort)
  // H — « Mit offenen Augen. » : son visage, la caméra recule devant elle
  { t: 23.95, cut: 1, f: 'lena', az: 90, el: 0, d: 0.6, fov: 30 },
  { t: 25.35, f: 'lena', az: 75, el: 2, d: 0.48, fov: 28 },
  // I — elle va dans la cuisine : de côté, puis on passe devant le frigo
  { t: 25.38, cut: 1, f: 'lena', az: 175, el: 8, d: 1.6, fov: 44 },
  { t: 26.6, f: 'lena', az: 130, el: 10, d: 1.25, fov: 42 },
  { t: 27.6, p: () => V(2.4, 1.42, -1.38), l: () => FOC.lena(), fov: 44 },
  { t: 29.43, p: () => V(2.38, 1.46, -1.56), l: () => FOC.lena(), fov: 34 },
  // (29.45-30.55 : caméra du couloir en accéléré : elle reste debout)
  // J — elle tourne lentement la tête… puis le corps
  { t: 30.55, cut: 1, f: 'lena', az: 105, el: 4, d: 0.7, fov: 34 },
  { t: 31.9, f: 'lena', az: 85, el: 3, d: 0.6, fov: 32 },
  { t: 33.2, f: 'lena', az: 66, el: 2, d: 0.52, fov: 30 },
  // K — « Sie schläft noch. » : très près
  { t: 33.25, cut: 1, f: 'lena', az: 72, el: 0, d: 0.5, fov: 26 },
  { t: 34.03, f: 'lena', az: 70, el: -1, d: 0.42, fov: 24 },
  // (34.05-36.35 : caméra du couloir, zoom numérique sur son visage)
  // L — « Sie sah knapp daneben. » : à côté de la caméra, on regarde elle puis le noir
  { t: 36.35, cut: 1, p: () => V(5.2, 1.85, 0.12), l: () => FOC.lena(), fov: 38 },
  { t: 37.25, p: () => V(5.1, 1.82, 0.15), l: () => FOC.lena(), fov: 38 },
  { t: 37.85, p: () => V(4.75, 1.75, 0.3), l: () => V(5.8, 1.6, -0.42), fov: 42 },
  // M — dans le noir… deux yeux
  { t: 37.87, cut: 1, p: () => V(4.2, 1.72, -0.15), l: () => V(5.75, 1.78, -0.3), fov: 40 },
  { t: 40.75, p: () => V(5.05, 1.78, -0.27), l: () => V(5.75, 1.8, -0.3), fov: 32 },
  // N — depuis le noir : Lena au loin, devant le frigo
  { t: 40.78, cut: 1, p: () => V(5.85, 1.82, -0.4), l: () => V(4.2, 1.55, 0.45), fov: 50 },
  { t: 42.6, p: () => V(5.55, 1.84, -0.3), l: () => V(4.2, 1.55, 0.45), fov: 48 },
];
const DEG = Math.PI / 180;
let _lyaw = 0;
function keyVec(k) {
  if (k.p) { const F = k.p(), L = k.l(); return [F.x, F.y, F.z, 0, 0, 0, L.x, L.y, L.z, k.fov]; }
  const F = FOC[k.f](), L = k.lk ? FOC[k.lk]() : F.clone();
  return [F.x, F.y, F.z, k.az + (k.dyaw ? _lyaw / DEG - 90 : 0), k.el, k.d, L.x, L.y, L.z, k.fov];
}
function camAt(T) {
  let i = 0; while (i < CAM.length - 1 && CAM[i + 1].t <= T) i++;
  let s0 = i; while (s0 > 0 && !CAM[s0].cut) s0--;
  let s1 = i; while (s1 < CAM.length - 1 && !CAM[s1 + 1].cut) s1++;
  const ids = [Math.max(s0, i - 1), i, Math.min(s1, i + 1), Math.min(s1, i + 2)];
  const Vs = ids.map(j => keyVec(CAM[j]));
  const ty = (k) => (k.p ? 'p' : 'o');
  if (ty(CAM[ids[0]]) !== ty(CAM[ids[1]])) Vs[0] = Vs[1];
  if (ty(CAM[ids[3]]) !== ty(CAM[ids[2]])) Vs[3] = Vs[2];
  if (ty(CAM[ids[1]]) !== ty(CAM[ids[2]])) Vs[2] = Vs[1];
  for (let j = 1; j < 4; j++) { while (Vs[j][3] - Vs[j - 1][3] > 180) Vs[j][3] -= 360; while (Vs[j][3] - Vs[j - 1][3] < -180) Vs[j][3] += 360; }
  const t0 = CAM[ids[1]].t, t1 = CAM[ids[2]].t; const u = ids[2] === ids[1] ? 0 : Math.min(1, Math.max(0, (T - t0) / (t1 - t0)));
  const cr = (a, b, c, d) => 0.5 * ((2 * b) + (-a + c) * u + (2 * a - 5 * b + 4 * c - d) * u * u + (-a + 3 * b - 3 * c + d) * u * u * u);
  const v = Vs[0].map((_, j) => cr(Vs[0][j], Vs[1][j], Vs[2][j], Vs[3][j]));
  const az = v[3] * DEG, el = v[4] * DEG, d = Math.max(0, v[5]);
  const pos = V(v[0] + Math.sin(az) * Math.cos(el) * d, v[1] + Math.sin(el) * d, v[2] + Math.cos(az) * Math.cos(el) * d);
  return { pos: clampRoom(pos), tgt: V(v[6], v[7], v[8]), fov: v[9] };
}
function clampRoom(p) {   // jamais dans les murs
  const q = p.clone(); q.y = Math.min(2.42, Math.max(0.15, q.y));
  if (q.x < 0) { q.x = Math.max(-3.32, Math.min(-0.07, q.x)); q.z = Math.max(-1.75, Math.min(1.75, q.z)); }
  else if (q.z < -0.68 && q.x > 1.63 && q.x < 3.97) { q.z = Math.max(-2.62, q.z); }
  else if (q.x < 5.4) { q.x = Math.max(0.07, q.x); q.z = Math.max(q.x > 1.63 && q.x < 3.97 ? -2.62 : -0.62, Math.min(0.66, q.z)); if (q.z < -0.62) q.x = Math.max(1.68, Math.min(3.92, q.x)); }
  return q;
}

// ---------- une image ----------
function setLights(T, cc) {
  const night = !(inR(T, MORNING[0], MORNING[1]) || inR(T, EVENING[0], EVENING[1]));
  moon.intensity = night ? 9 : 0; moon2.intensity = night ? 5 : 0; sun.intensity = inR(T, MORNING[0], MORNING[1]) ? 60 : 0;
  hemi.intensity = night ? 0.12 : inR(T, MORNING[0], MORNING[1]) ? 0.9 : 0.35; hemi.color.set(night ? '#5d75a8' : '#ffe9cf');
  hallLamp.intensity = inR(T, EVENING[0], EVENING[1]) ? 3.5 : 0; nightL.intensity = night ? 0.9 : 0; kitLamp.intensity = 0;
  sky.material.color.set(night ? '#0d1830' : inR(T, MORNING[0], MORNING[1]) ? '#c9dcef' : '#2c3550'); sky2.material.color.copy(sky.material.color);
  const fo = fridgeOpen(T) / 1.3; fridgeL.intensity = 4 * fo; fridgeS.intensity = 22 * fo; inM.emissiveIntensity = 0.9 * fo;
  irL.intensity = cc ? 7 : 0; if (cc) irL.position.copy(CC[cc[2]].pos);
  scene.background.set(night ? '#020306' : '#20242c');
  for (const l of [moon, moon2, sun, hallLamp, fridgeS]) l.castShadow = l.intensity > 0;
}
function frame(T) {
  const cc = cctvAt(T);
  dHinge.rotation.y = doorOpen(T); fHinge.rotation.y = fridgeOpen(T);
  const ph = T > 0.22 && T < 10.1; drawScreen(ph);
  setLights(T, cc);
  // Lena
  const h = lenaState(T); const hf = frameOf(h.yaw); _lyaw = h.yaw;
  LENA.root.position.copy(h.pos); LENA.root.rotation.y = h.yaw; LENA.root.updateMatrixWorld(true); LENA.headWorld(_hw);
  const lookP = (k) => k === 'phone' ? phone.position.clone() : k === 'fridge' ? V(2.1, 1.1, -1.65) : k === 'fridgeIn' ? V(2.0, 1.2, -1.6) : k === 'cam2' ? cam2.position.clone()
    : k === 'dark' ? DARK.clone().add(V(0, 0.15, 0)) : k === 'turn' ? V(2.0, 1.2, -1.6).lerp(DARK.clone().add(V(0, 0.15, 0)), ss(30.65, 32.2, T)) : k === 'around' ? V(4.5, 1.4, 0.2 + Math.sin(T * 1.4) * 0.6) : k === 'ahead' ? _hw.clone().addScaledVector(hf.f, 3).add(V(0, -0.05, 0)) : null;
  const pose = { mo: h.layers, lookW: h.lookW, sit: h.sit, sitH: 0.5 };
  if (h.sit) Object.assign(pose, { lHip: -1.52, rHip: -1.52, lKnee: 1.45, rKnee: 1.45, lHipZ: 0.06, rHipZ: -0.06, spineX: 0.18, headX: 0.25 });
  LENA.setPose(pose, h.face, lookP(h.look), T); LENA.headWorld(_hw);
  if (h.phone) {   // téléphone dans la main gauche, devant le visage, un peu bas
    const w = _hw.clone().addScaledVector(hf.f, 0.3).addScaledVector(hf.r, -0.04).add(V(0, -0.3 + 0.006 * Math.sin(T * 2.1), 0));
    Object.assign(pose, { lW: 1, lwx: w.x, lwy: w.y, lwz: w.z, lCurl: 0.75, lWrX: 0 });
  }
  if (h.lHand) Object.assign(pose, { lW: 1, lwx: h.lHand.x, lwy: h.lHand.y, lwz: h.lHand.z, lCurl: 0.85 });
  if (h.rHand) Object.assign(pose, { rW: 1, rwx: h.rHand.x, rwy: h.rHand.y, rwz: h.rHand.z, rCurl: 0.5 });
  LENA.setPose(pose, h.face, lookP(h.look), T); LENA.headWorld(_hw);
  // téléphone : sur la table de nuit, ou dans sa main, l'écran vers son visage
  if (h.phone && h.vis) {
    const lh = boneW(LENA, 'lHand'), lf = boneW(LENA, 'lFore'); const dir = lh.clone().sub(lf).normalize(); const p = lh.clone().addScaledVector(dir, 0.1);
    const zA = _hw.clone().sub(p).normalize(); const y2 = V(0, 1, 0).addScaledVector(zA, -zA.y).normalize(); const xA = new THREE.Vector3().crossVectors(y2, zA);
    phone.position.copy(p).addScaledVector(zA, 0.045); phone.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(xA, y2, zA));
  } else { phone.position.set(-0.74, 0.556, -1.45); phone.quaternion.setFromEuler(new THREE.Euler(-Math.PI / 2, 0, 0.4)); if (inR(T, 0.25, 1.7)) phone.position.x += 0.0015 * Math.sin(T * 90) * (Math.floor(T * 2.5) % 2); }
  phone.visible = T < 10.1; phoneL.position.copy(phone.position).add(V(0, 0.08, 0)); phoneL.intensity = ph && T < 6.1 ? (T < 1.75 ? 0.12 : 0.45) : 0;
  LENA.root.visible = h.vis;
  // yeux dans le noir (à peine)
  ghostM.opacity = ss(38.6, 40.0, T) * (T < 40.78 ? 1 : 0); eyeM.opacity = 0.42 * ss(39.5, 40.2, T) * (T < 40.78 ? 1 : 0) * (1 - 0.6 * (Math.floor(T * 7) % 9 === 0 ? 1 : 0));
  ledL.intensity = 0.06; led.visible = true;
  for (const c of CEIL) c.visible = true;
  if (cc) {   // vue de surveillance
    const C = CC[cc[2]]; const opt = cc[4] ? cc[4](T) : {};
    led.visible = false; LENA.root.visible = h.vis;
    let zc = new THREE.Vector2(0.5, 0.5);
    if (opt.focus === 'lena') { const p = _hw.clone().project(C.cam); zc.set(p.x * 0.5 + 0.5, p.y * 0.5 + 0.5 + 0.01); }
    renderer.setRenderTarget(RT); renderer.render(scene, C.cam); renderer.setRenderTarget(null);
    postM.uniforms.time.value = T; postM.uniforms.zoom.value = opt.zoom || 1; postM.uniforms.zc.value.copy(zc).lerp(V2(0.5, 0.5), 1 - Math.min(1, ((opt.zoom || 1) - 1) / 0.5));
    postM.uniforms.black.value = opt.black || 0; postM.uniforms.pix.value = opt.pix || 0; postM.uniforms.gain.value = 1;
    drawOverlay(C.name, clock(cc[3](T)), opt.extra || '');
    const w2 = innerWidth, h2 = innerHeight; if (canvas.width !== w2) renderer.setSize(w2, h2, false);
    renderer.render(postScene, postCam);
    return;
  }
  const c = camAt(T);
  const shake = 0.003;
  camera.position.copy(c.pos).add(V(Math.sin(T * 7.1) * shake, Math.sin(T * 9.3) * shake, Math.sin(T * 5.7) * shake));
  camera.up.set(0, 1, 0); camera.lookAt(c.tgt); camera.fov = c.fov;
  for (const cl of CEIL) cl.visible = camera.position.y < HH - 0.02;
  fillL.position.copy(camera.position).add(V(0, 0.15, 0)); fillL.target.position.copy(c.tgt);
  fillL.intensity = (inR(T, MORNING[0], MORNING[1]) ? 0.3 : 1.0) * Math.max(1, (camera.position.distanceTo(c.tgt) / 1.1) ** 2);
  fillL.color.set(inR(T, EVENING[0], EVENING[1]) ? '#ffd9b0' : '#9fb4dc');
  const w2 = innerWidth, h2 = innerHeight;
  if (canvas.width !== w2) renderer.setSize(w2, h2, false);
  camera.aspect = w2 / h2; camera.updateProjectionMatrix();
  renderer.render(scene, camera);
}
const V2 = (x, y) => new THREE.Vector2(x, y);
window.renderAt = (T) => frame(T);
window.dbg = (T) => { frame(T); const r = (v) => [v.x, v.y, v.z].map(x => +x.toFixed(2)); return { yaw: +_lyaw.toFixed(2), root: r(LENA.root.position), cam: r(camera.position), lena: r(_hw), phone: r(phone.position), walkv: WALKV, sw1: SW1 }; };
window.READY = true;
if (!MANUAL) { const c0 = performance.now(); const loop = () => { frame(((performance.now() - c0) / 1000) % END); requestAnimationFrame(loop); }; loop(); }
else frame(0);
