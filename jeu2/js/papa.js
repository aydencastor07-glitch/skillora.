// « Ich bin's. Mach auf. » : histoire d'horreur interactive au « tu ». Maison la nuit, couloir, porte d'entrée,
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
box(2 * HW + 0.4, 0.1, HL + 1, M({ color: '#bdb6aa', roughness: 1 }), 0, HH + 0.05, HL / 2, scene, false);   // plafond
box(0.1, HH, HL, wallM, -HW - 0.05, HH / 2, HL / 2);                                                     // mur gauche
box(0.1, HH, 2.9, wallM, HW + 0.05, HH / 2, 1.45);                                                       // mur droit (avant le salon)
box(0.1, 0.5, 1.2, wallM, HW + 0.05, HH - 0.25, 3.5);                                                    // linteau de la porte du salon
box(0.1, HH, HL - 4.1, wallM, HW + 0.05, HH / 2, 4.1 + (HL - 4.1) / 2);
for (const s of [-1, 1]) box(0.03, 0.12, HL, M({ color: '#d9d3c4' }), s * (HW - 0.01), 0.06, HL / 2, scene, false);   // plinthes
// mur de la porte d'entrée
box(HW - 0.48, HH, 0.12, wallM, -(0.48 + (HW - 0.48) / 2), HH / 2, -0.06); box(HW - 0.48, HH, 0.12, wallM, 0.48 + (HW - 0.48) / 2, HH / 2, -0.06);
box(0.96, HH - 2.12, 0.12, wallM, 0, 2.12 + (HH - 2.12) / 2, -0.06);
// la porte : panneaux, verre dépoli en haut (lumière froide de la rue), judas, poignée
const door = new THREE.Group(); scene.add(door); door.position.set(0, 0, 0);
const doorM = M({ color: '#4a2f1d', roughness: 0.6 });
box(0.94, 1.32, 0.05, doorM, 0, 0.66, 0.0, door); box(0.94, 0.24, 0.05, doorM, 0, 2.0, 0.0, door);
box(0.2, 0.56, 0.05, doorM, -0.37, 1.6, 0.0, door); box(0.2, 0.56, 0.05, doorM, 0.37, 1.6, 0.0, door);
for (const y of [0.35, 0.95]) box(0.62, 0.42, 0.012, M({ color: '#3e2716', roughness: 0.65 }), 0, y, 0.03, door, false);
const glassTex = canvasTex(256, 384, () => {});
function drawGlass(sil) {
  const { g, c } = glassTex.userData, w = c.width, h = c.height;
  const gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, '#7f99c4'); gr.addColorStop(1, '#4b5f86'); g.fillStyle = gr; g.fillRect(0, 0, w, h);
  for (let i = 0; i < 900; i++) { g.fillStyle = `rgba(255,255,255,${Math.random() * 0.06})`; g.fillRect(Math.random() * w, Math.random() * h, 3, 3); }
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
box(2 * HW, HH, 0.1, wallM, 0, HH / 2, HL + 0.05);
// lumières
const moon = new THREE.DirectionalLight('#7f97c9', 0.35); moon.position.set(2, 4, -3); moon.target.position.set(0, 0, 3); scene.add(moon, moon.target);
const lamp = new THREE.PointLight('#ffb36b', 0.9, 3.2, 1.8); lamp.position.set(-HW + 0.3, 1.05, 1.9); lamp.castShadow = true; lamp.shadow.mapSize.set(512, 512); scene.add(lamp);
const underL = new THREE.SpotLight('#a9b8e0', 0, 3.2, 0.5, 0.6, 1.5); scene.add(underL, underL.target);   // lumière par en dessous sur le faux père

// ---------- le téléphone ----------
const phone = new THREE.Group(); scene.add(phone);
box(0.074, 0.152, 0.009, M({ color: '#0d0d10', roughness: 0.3, metalness: 0.5 }), 0, 0, 0, phone, false);
const scrTex = canvasTex(540, 1110, () => {});
let scrState = '';
function drawScreen(state) {
  if (state === scrState) return; scrState = state; const { g, c } = scrTex.userData, w = c.width, h = c.height;
  g.fillStyle = '#0b0e14'; g.fillRect(0, 0, w, h);
  g.fillStyle = '#e9edf3'; g.font = '600 30px Arial'; g.textAlign = 'left'; g.fillText('01:58', 36, 52);
  g.fillStyle = '#161b25'; g.fillRect(0, 80, w, 120); g.fillStyle = '#3a6fd8'; g.beginPath(); g.arc(80, 140, 38, 0, 7); g.fill();
  g.fillStyle = '#fff'; g.font = 'bold 40px Arial'; g.textAlign = 'center'; g.fillText('P', 80, 154); g.textAlign = 'left'; g.font = 'bold 40px Arial'; g.fillText('Papa', 140, 135);
  g.fillStyle = '#8b95a7'; g.font = '28px Arial'; g.fillText(state === 'typing' ? 'schreibt …' : 'online', 140, 175);
  const bub = (y, txt, mine) => { g.font = '36px Arial'; const tw = g.measureText(txt).width + 50; const x = mine ? w - tw - 30 : 30;
    g.fillStyle = mine ? '#2f6fe0' : '#262d3a'; g.beginPath(); g.roundRect(x, y, tw, 74, 28); g.fill(); g.fillStyle = '#f2f4f8'; g.fillText(txt, x + 25, y + 49); };
  bub(300, 'Wo bist du?', true); bub(400, 'Bist du noch weg?', true);
  if (state === 'typing') { g.fillStyle = '#262d3a'; g.beginPath(); g.roundRect(30, 520, 130, 70, 28); g.fill(); g.fillStyle = '#9aa3b4'; for (let i = 0; i < 3; i++) { g.beginPath(); g.arc(65 + i * 30, 555, 9, 0, 7); g.fill(); } }
  if (state === 'msg') bub(520, 'Bin in 10 Minuten da.', false);
  scrTex.needsUpdate = true;
}
drawScreen('idle');
const scr = new THREE.Mesh(new THREE.PlaneGeometry(0.068, 0.14), new THREE.MeshBasicMaterial({ map: scrTex, toneMapped: false }));
scr.position.z = 0.0047; phone.add(scr);
const phoneL = new THREE.PointLight('#9fc0ff', 0, 0.9, 2); scene.add(phoneL);

// ---------- personnages ----------
await RealHuman.loadClips(['idle', 'slowwalk', 'walk2'], './mocap/');
const HERO = await RealHuman.create('./models/kid.glb', { heightM: 1.72, seed: 2 });
const PAPA = await RealHuman.create('./models/judge.glb', { heightM: 1.86, seed: 4 });
for (const H of [HERO, PAPA]) { scene.add(H.root); H.root.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } }); }

// ---------- chronologie (voix calée) ----------
const ss = (a, b, x) => { const u = Math.min(1, Math.max(0, (x - a) / (b - a))); return u * u * (3 - 2 * u); };
const lerp = (a, b, u) => a + (b - a) * u;
const FULL = { pelvis: 1, spineAbs: 1, legs: 1, arms: 1, root: 1, headAbs: 0.4 };
const IDLEW = { legs: 1, root: 1, pelvis: 0.5, spineAbs: 0.5, arms: 1 };
const dur = (c) => RealHuman.clips[c].frames / RealHuman.clips[c].fps;
const loopT = (c, x) => ((x % dur(c)) + dur(c)) % dur(c);
const K = { klopft: 0.81, aber: 2.26, steht: 3.25, hinter: 3.89, zwei: 4.94, du: 6.24, papa: 7.75, bin: 8.74, end: 10.45 };
const HIPK = 0.9;                                                // hauteur de hanche du fils (m)
const WALK_V = RealHuman.clips.slowwalk.speed * HIPK;
const STOP = 2.15, Z0 = 1.25 + WALK_V * STOP;                   // il marche vers la porte et s'arrête à 1,25 m
const PAPAP = V(0.15, 0, 5.55);
const IDLE = (t) => [{ clip: 'idle', mode: 'abs', t: loopT('idle', t), k: 1, w: IDLEW }];
const FEAR = { maxM: 1.5, raw: { EyeWideLeft: 1.4, EyeWideRight: 1.4, BrowInnerUp: 1.3, BrowOuterUpLeft: 1.1, BrowOuterUpRight: 1.1, JawOpen: 0.42, MouthStretchLeft: 0.8, MouthStretchRight: 0.8, MouthLowerDownLeft: 0.5, MouthLowerDownRight: 0.5 } };
const GRIN = { maxM: 2, raw: { MouthSmileLeft: 1.9, MouthSmileRight: 1.9, CheekSquintLeft: 0.6, CheekSquintRight: 0.6, MouthStretchLeft: 0.9, MouthStretchRight: 0.9, MouthUpperUpLeft: 0.5, MouthUpperUpRight: 0.5, EyeWideLeft: 1.2, EyeWideRight: 1.2, MouthLowerDownLeft: 0.4, MouthLowerDownRight: 0.4 } };
const mix = (a, b, u) => { const r = {}; for (const k of new Set([...Object.keys(a.raw || {}), ...Object.keys(b.raw || {})])) r[k] = lerp((a.raw || {})[k] || 0, (b.raw || {})[k] || 0, u); return { maxM: Math.max(a.maxM || 1, b.maxM || 1), raw: r }; };
const _hw = new THREE.Vector3(), _pw = new THREE.Vector3();

function heroState(T) {
  const s = { pos: V(0, 0, 1.25), yaw: Math.PI, layers: IDLE(T), face: {}, look: null, phone: 0 };
  if (T < K.zwei) {                                               // il avance vers la porte, s'arrête, puis se retourne
    const stop = ss(STOP - 0.35, STOP + 0.25, T);
    s.pos = V(0.05, 0, Math.max(1.25, Z0 - WALK_V * T));
    s.layers = [{ clip: 'slowwalk', mode: 'abs', t: loopT('slowwalk', T + 0.3), k: 1 - stop, w: FULL }, ...IDLE(T).map(l => ({ ...l, k: stop }))];
    s.look = T < K.hinter + 0.1 ? V(0, 1.55, 0) : PAPAP.clone().add(V(0, 1.7, 0));
    const u = ss(K.aber, K.steht, T); s.face = mix({ raw: { BrowInnerUp: 0.4 } }, { maxM: 1.2, raw: { EyeWideLeft: 0.7, EyeWideRight: 0.7, BrowInnerUp: 0.9, BrowOuterUpLeft: 0.4, BrowOuterUpRight: 0.4 } }, u);
    if (T > K.hinter) { s.face = mix(s.face, FEAR, ss(K.hinter, K.hinter + 0.35, T)); s.yaw = Math.PI - 0.5 * ss(K.hinter, K.hinter + 0.5, T); }
  } else {                                                        // 2 heures du matin : seul dans le couloir, téléphone en main
    s.pos = V(0.1, 0, 3.0); s.yaw = Math.PI * 0.62; s.layers = IDLE(T + 3); s.phone = 1;
    s.look = null; s.face = T > K.bin + 0.3 ? { raw: { MouthSmileLeft: 0.25, MouthSmileRight: 0.25, BrowInnerUp: 0.2 } } : { raw: { BrowInnerUp: 0.35 } };
  }
  return s;
}
function placePhone(h) {
  // téléphone tenu devant la poitrine, écran vers le visage
  const fwd = V(Math.sin(h.yaw), 0, Math.cos(h.yaw)), right = V(Math.cos(h.yaw), 0, -Math.sin(h.yaw));
  const p = h.pos.clone().addScaledVector(fwd, 0.3).addScaledVector(right, -0.06).add(V(0, 1.2, 0));
  phone.position.copy(p); phone.lookAt(h.pos.clone().add(V(0, 1.6, 0)).addScaledVector(fwd, 0.05));
  return p;
}
function shot(T) {
  const H = _hw;
  if (T < K.aber) {                                                // de dos, il avance vers la porte (épaule, caméra portée)
    const p = HERO.root.position; return [V(p.x + 0.38, 1.62, p.z + 0.95), V(0, 1.25, 0), 50];
  }
  if (T < K.steht) { const u = ss(K.aber, K.steht, T); return [H.clone().add(V(0.08, -0.03, lerp(-0.75, -0.5, u))), H.clone(), 34]; }   // visage, de face (côté porte)
  if (T < K.hinter) {                                              // le faux père au fond du couloir
    const u = ss(K.steht, K.hinter, T); return [V(0.25, 1.62, lerp(3.4, 3.9, u)), _pw.clone().add(V(0, -0.05, 0)), lerp(30, 24, u)];
  }
  if (T < K.zwei) { const d = _pw.clone().sub(H).setY(0).normalize(), sd = V(d.z, 0, -d.x); return [H.clone().addScaledVector(d, 0.55).addScaledVector(sd, 0.16).add(V(0, 0.02, 0)), H.clone().add(V(0, -0.03, 0)), 32]; }   // il se retourne : la peur, de face
  if (T < K.du) { const u = ss(K.zwei, K.du, T); const c = V(-HW + 0.3, 0.9, 1.4); return [c.clone().add(V(lerp(0.45, 0.75, u), lerp(0.05, 0.18, u), lerp(0.05, 0.3, u))), c, lerp(30, 40, u)]; }   // le réveil 02:00
  if (T < K.papa) { const u = ss(K.du, K.papa, T); const a = lerp(-0.3, 0.35, u); return [V(Math.sin(a) * 2.2, lerp(2.45, 2.2, u), 3.0 + Math.cos(a) * 2.2), V(0.1, 0.9, 3.0), 50]; }   // seul, plan large qui tourne
  if (T < K.bin + 0.85) { const n = V(0, 0, 1).applyQuaternion(phone.quaternion), up = V(0, 1, 0).applyQuaternion(phone.quaternion); const u = ss(K.papa, K.bin + 0.85, T);
    return [phone.position.clone().addScaledVector(n, lerp(0.24, 0.2, u)).addScaledVector(up, -0.015), phone.position.clone().addScaledVector(up, 0.012), 34, up]; }   // l'écran, vu par ses yeux
  return [phone.position.clone().lerp(H, 0.35).add(V(0.25, 0.02, -0.35)), H.clone(), 30];                          // son visage éclairé par l'écran
}
const SHOTS = [K.aber, K.steht, K.hinter, K.zwei, K.du, K.papa, K.bin + 0.85];
let camPos = V(0, 1.6, 3), camTgt = V(0, 1.2, 0), lastShot = -1;

function frame(T) {
  // coups à la porte : la porte tremble, la silhouette derrière le verre
  const knocks = [K.klopft, K.klopft + 0.24, K.klopft + 0.48];
  let shake = 0; for (const k of knocks) if (T > k && T < k + 0.12) shake = 1 - (T - k) / 0.12;
  door.position.z = -0.006 * shake; door.rotation.y = 0.004 * shake;
  drawGlass(T < K.zwei ? 1 : 0);
  // le téléphone
  const h = heroState(T);
  HERO.root.position.copy(h.pos); HERO.root.rotation.y = h.yaw;
  phone.visible = h.phone > 0; phoneL.intensity = 0;
  const pose = { mo: h.layers, lookW: 0.8 };
  if (h.phone) {
    const p = placePhone(h); drawScreen(T < K.papa + 0.15 ? 'idle' : T < K.bin ? 'typing' : 'msg');
    const back = V(Math.sin(h.yaw), 0, Math.cos(h.yaw)).multiplyScalar(0.045);
    Object.assign(pose, { rW: 1, rwx: p.x + back.x, rwy: p.y - 0.115, rwz: p.z + back.z, rCurl: 0.55, rWrX: -0.4 });
    phoneL.position.copy(p).add(V(0, 0.1, 0)).addScaledVector(V(Math.sin(h.yaw), 0, Math.cos(h.yaw)), -0.12); phoneL.intensity = 0.9;
    h.look = p;
  }
  HERO.setPose(pose, h.face, h.look, T);
  HERO.root.visible = !(T >= K.papa && T < K.bin + 0.85);   // plan « écran » vu par ses yeux : le corps ne gêne pas
  HERO.headWorld(_hw);
  // le faux père : seulement quand on le révèle
  PAPA.root.visible = T > K.steht - 0.05 && T < K.zwei;
  PAPA.root.position.copy(PAPAP); PAPA.root.rotation.y = Math.PI;
  PAPA.setPose({ mo: [{ clip: 'idle', mode: 'abs', t: 4, k: 1, w: { legs: 1, root: 1, pelvis: 0.2, spineAbs: 0.2, arms: 1 } }], lookW: 1, headZ: 0.12 * ss(K.steht, K.hinter, T) }, mix({ raw: { MouthSmileLeft: 0.6, MouthSmileRight: 0.6 } }, GRIN, ss(K.steht + 0.1, K.hinter - 0.1, T)), camera.position, T);
  PAPA.headWorld(_pw);
  underL.intensity = PAPA.root.visible ? 9 : 0; underL.position.copy(_pw).add(V(0, -0.8, -0.35)); underL.target.position.copy(_pw);
  // lumières : télé qui vacille, lampe
  tvL.intensity = 2.2 + 1.2 * Math.sin(T * 13) * Math.sin(T * 5.3); tvL.color.setHSL(0.6 + 0.04 * Math.sin(T * 3), 0.6, 0.6);
  lamp.intensity = T < K.zwei ? 0.25 : 0.6; streetL.intensity = T < K.zwei ? 7 : 3;
  // caméra
  const [p, tgt, fov, up] = shot(T); camera.up.copy(up || V(0, 1, 0));
  const sid = SHOTS.filter(x => x <= T).length;
  if (sid !== lastShot) { camPos.copy(p); camTgt.copy(tgt); lastShot = sid; } else { camPos.lerp(p, 0.35); camTgt.lerp(tgt, 0.35); }
  const hand = T < K.aber ? 0.012 : T > K.hinter && T < K.zwei ? 0.008 : 0.004;   // caméra portée
  camera.position.copy(camPos).add(V(Math.sin(T * 7.1) * hand + Math.sin(T * 17) * hand * 0.3, Math.sin(T * 9.3) * hand + Math.cos(T * 4.2) * hand * 0.5, Math.sin(T * 5.7) * hand));
  camera.lookAt(camTgt); camera.fov = fov;
  fillL.position.copy(camera.position).add(V(0, 0.2, 0)); fillL.target.position.copy(camTgt); fillL.intensity = T > K.steht && T < K.hinter ? 0.4 : 2.0;
  const w2 = innerWidth, h2 = innerHeight;
  if (canvas.width !== w2) renderer.setSize(w2, h2, false);
  camera.aspect = w2 / h2; camera.updateProjectionMatrix();
  renderer.render(scene, camera);
}
window.renderAt = (T) => frame(T);
window.READY = true;
if (!MANUAL) { const c0 = performance.now(); const loop = () => { frame(((performance.now() - c0) / 1000) % K.end); requestAnimationFrame(loop); }; loop(); }
else frame(0);
