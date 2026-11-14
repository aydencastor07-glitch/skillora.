// « Der Mann in der Dinosaurier-Statue » (histoire vraie, compte allemand) – 3D avec nos personnages réalistes (Rocketbox).
// Place devant un magasin, statue géante de stégosaure CREUSE (construite ici : corps, pattes, plaques, queue).
// Le téléphone tombe dans une fente du dos, l'homme s'y glisse, tombe la tête la première dans la patte arrière,
// des jours passent (accéléré jour / nuit), des passants sentent l'odeur, la police arrive, fleurs au pied de la patte.
// Vues en coupe : plans de coupe (clipping) sur la statue pour voir l'intérieur.
// ?manual : rendu image par image (window.renderAt(T)).  ?cam=x,y,z,tx,ty,tz : caméra libre (réglages).
import * as THREE from 'three';
import { RealHuman } from './rig.js';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

const Q = new URLSearchParams(location.search);
const MANUAL = Q.has('manual');
const BLOCKY = Q.has('blocky');   // personnage « en blocs » (test de style)
const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1); renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.0; renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.localClippingEnabled = true;
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(40, 9 / 16, 0.03, 200);
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const rnd = (s => () => (s = (s * 16807) % 2147483647) / 2147483647)(11);
function canvasTex(w, h, draw) { const c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d'); draw(g, w, h); const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; t.userData = { c, g }; return t; }
const M = (o) => new THREE.MeshStandardMaterial({ roughness: 0.85, metalness: 0, ...o });
const box = (w, h, d, mat, x, y, z, parent = scene, shadow = true) => { const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); m.position.set(x, y, z); m.castShadow = shadow; m.receiveShadow = true; parent.add(m); return m; };
const cyl = (r, h, mat, x, y, z, parent = scene, seg = 20, r2 = r) => { const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r2, h, seg), mat); m.position.set(x, y, z); m.castShadow = true; m.receiveShadow = true; parent.add(m); return m; };
const ss = (a, b, x) => { const u = Math.min(1, Math.max(0, (x - a) / (b - a))); return u * u * (3 - 2 * u); };
const lerp = (a, b, u) => a + (b - a) * u;
const inR = (T, a, b) => T >= a && T < b;

// ---------- textures ----------
const paveT = canvasTex(512, 512, (g, w, h) => { g.fillStyle = '#8e8a82'; g.fillRect(0, 0, w, h); for (let y = 0; y < 8; y++) for (let x = 0; x < 4; x++) { const v = 150 + rnd() * 30 | 0; g.fillStyle = `rgb(${v},${v - 4},${v - 10})`; g.fillRect(x * 128 + (y % 2) * 64 + 2, y * 64 + 2, 124, 60); }
  for (let i = 0; i < 2500; i++) { g.fillStyle = `rgba(40,35,30,${rnd() * 0.08})`; g.fillRect(rnd() * w, rnd() * h, 2, 2); } });
paveT.wrapS = paveT.wrapT = THREE.RepeatWrapping; paveT.repeat.set(30, 30);
// peau de la statue : fibre de verre peinte, vert-gris taché, petites écailles en relief
function skin(g, w, h, bump) {
  g.fillStyle = bump ? '#808080' : '#6e7558'; g.fillRect(0, 0, w, h);
  for (let i = 0; i < 900; i++) { const x = rnd() * w, y = rnd() * h, r = 4 + rnd() * 26; const v = bump ? 100 + rnd() * 80 | 0 : 0;
    g.fillStyle = bump ? `rgba(${v},${v},${v},0.35)` : `rgba(${60 + rnd() * 50 | 0},${70 + rnd() * 40 | 0},${45 + rnd() * 30 | 0},0.18)`; g.beginPath(); g.arc(x, y, r, 0, 7); g.fill(); }
  for (let y = 0; y < h; y += 9) for (let x = (y / 9 % 2) * 5; x < w; x += 10) { g.fillStyle = bump ? 'rgba(220,220,220,0.5)' : 'rgba(30,35,20,0.10)'; g.beginPath(); g.arc(x, y, 3.2, 0, 7); g.fill(); }
  for (let i = 0; i < 160; i++) { g.strokeStyle = bump ? 'rgba(20,20,20,0.5)' : 'rgba(25,28,18,0.25)'; g.lineWidth = 1 + rnd() * 2; g.beginPath(); let x = rnd() * w, y = rnd() * h; g.moveTo(x, y); for (let k = 0; k < 5; k++) { x += (rnd() - 0.5) * 40; y += (rnd() - 0.5) * 40; g.lineTo(x, y); } g.stroke(); }
}
const skinT = canvasTex(1024, 1024, (g, w, h) => skin(g, w, h, false)); skinT.wrapS = skinT.wrapT = THREE.RepeatWrapping; skinT.repeat.set(6, 3);
const skinB = canvasTex(1024, 1024, (g, w, h) => skin(g, w, h, true)); skinB.colorSpace = THREE.NoColorSpace; skinB.wrapS = skinB.wrapT = THREE.RepeatWrapping; skinB.repeat.set(6, 3);
const CLIP = [];   // plans de coupe actifs (vues de l'intérieur)
const statueM = M({ map: skinT, bumpMap: skinB, bumpScale: 2.2, roughness: 0.62, clippingPlanes: CLIP, clipShadows: true });
const innerM = M({ color: '#17140f', roughness: 1, side: THREE.BackSide, clippingPlanes: CLIP });
const plateM = M({ map: skinT, bumpMap: skinB, bumpScale: 1.5, color: '#d2c79a', roughness: 0.6, clippingPlanes: CLIP, clipShadows: true });

// ---------- la place ----------
const SKY_DAY = new THREE.Color('#a9c4dd'), SKY_DUSK = new THREE.Color('#d98b5f'), SKY_NIGHT = new THREE.Color('#0d1424');
scene.background = SKY_DAY.clone(); scene.fog = new THREE.Fog(SKY_DAY.clone(), 30, 120);
box(160, 0.1, 160, M({ map: paveT, roughness: 0.9 }), 0, -0.05, 0);
// le magasin derrière (façade vitrée, enseigne générique)
const facadeM = M({ color: '#d7d3cb', roughness: 0.8 }), glassM = M({ color: '#2b3a46', roughness: 0.15, metalness: 0.6 });
box(44, 9, 10, facadeM, 0, 4.5, -17);
box(30, 3.0, 0.2, glassM, 0, 1.7, -11.95, scene, false);
for (let i = 0; i <= 10; i++) box(0.12, 3.0, 0.25, M({ color: '#55595e', metalness: 0.5, roughness: 0.4 }), -15 + i * 3, 1.7, -11.85, scene, false);
const signT = canvasTex(1024, 160, (g, w, h) => { g.fillStyle = '#c8202a'; g.fillRect(0, 0, w, h); g.fillStyle = '#fff'; g.font = 'bold 110px Arial'; g.textAlign = 'center'; g.fillText('BAUMARKT', w / 2, 118); });
const sign = new THREE.Mesh(new THREE.PlaneGeometry(12, 1.9), new THREE.MeshStandardMaterial({ map: signT, roughness: 0.5, emissive: '#ffffff', emissiveMap: signT, emissiveIntensity: 0.15 })); sign.position.set(0, 6.6, -11.94); scene.add(sign);
box(46, 0.5, 11, M({ color: '#9a978f' }), 0, 9.25, -17, scene, false);
// immeubles au loin
for (let i = 0; i < 9; i++) { const hgt = 10 + rnd() * 16; box(9 + rnd() * 6, hgt, 8, M({ color: ['#c9c0b2', '#b8b2a8', '#d8cfbf', '#a7a39b'][i % 4] }), -60 + i * 15, hgt / 2, -42 - rnd() * 8, scene, false); }
for (const s of [-1, 1]) for (let i = 0; i < 4; i++) { const hgt = 12 + rnd() * 10; box(10, hgt, 12, M({ color: ['#c4bcae', '#b0aaa0'][i % 2] }), s * (34 + rnd() * 4), hgt / 2, -4 + i * 14, scene, false); }
// arbres, lampadaires, bancs, bornes
const trunkM = M({ color: '#4d3b2c' }), leafM = M({ color: '#4f6b36', roughness: 0.9 });
function tree(x, z, s = 1) { cyl(0.16 * s, 3.2 * s, trunkM, x, 1.6 * s, z); for (let k = 0; k < 5; k++) { const m = new THREE.Mesh(new THREE.IcosahedronGeometry((1.2 + rnd() * 0.6) * s, 1), leafM); m.position.set(x + (rnd() - 0.5) * 1.4 * s, (3.6 + rnd() * 1.2) * s, z + (rnd() - 0.5) * 1.4 * s); m.castShadow = true; scene.add(m); } }
for (const [x, z] of [[-11, -6], [11, -6], [-15, 6], [15, 7], [-22, -2], [22, -1]]) tree(x, z, 1 + rnd() * 0.3);
const LAMPS = [];
function lamp(x, z) { cyl(0.07, 5, M({ color: '#2d3033', metalness: 0.6, roughness: 0.4 }), x, 2.5, z); const h = new THREE.Mesh(new THREE.SphereGeometry(0.22, 12, 8), new THREE.MeshStandardMaterial({ color: '#fff3d0', emissive: '#ffd890', emissiveIntensity: 0 })); h.position.set(x, 5.1, z); scene.add(h);
  const L = new THREE.PointLight('#ffc77a', 0, 16, 1.6); L.position.set(x, 4.8, z); scene.add(L); LAMPS.push({ h, L }); }
for (const [x, z] of [[-7, 4.5], [7, 4.5], [-8, -8], [8, -8]]) lamp(x, z);
const benchM = M({ color: '#6b4f36' });
function bench(x, z, ry) { const b = new THREE.Group(); b.position.set(x, 0, z); b.rotation.y = ry; scene.add(b); box(1.8, 0.06, 0.45, benchM, 0, 0.45, 0, b); box(1.8, 0.4, 0.06, benchM, 0, 0.7, -0.22, b); for (const s of [-0.8, 0.8]) box(0.06, 0.45, 0.45, M({ color: '#333' }), s, 0.22, 0, b); }
bench(-5.5, 2.5, 0.4); bench(6, 2.8, -0.5);
for (let i = 0; i < 7; i++) cyl(0.09, 0.8, M({ color: '#3a3d40', metalness: 0.5, roughness: 0.5 }), -6 + i * 2, 0.4, 7.5, scene, 12);
// panneau devant la statue
box(0.08, 1.1, 0.08, M({ color: '#333' }), 3.2, 0.55, 3.0); box(0.9, 0.55, 0.05, M({ color: '#e9e2cf' }), 3.2, 1.15, 3.0);

// ---------- LA STATUE (stégosaure, ~8,5 m, creuse) : tête vers +x, côté caméra = +z ----------
const statue = new THREE.Group(); scene.add(statue);
// tube à section elliptique le long d'une courbe, rayon variable (corps + cou + tête + queue)
function sculptTube(pts, prof, seg = 140, rad = 40, noise = 0.03) {
  const curve = new THREE.CatmullRomCurve3(pts); const pos = [], uv = [], idx = [];
  const frames = curve.computeFrenetFrames(seg, false);
  for (let i = 0; i <= seg; i++) {
    const u = i / seg, c = curve.getPointAt(u); const [ry, rz, dy] = prof(u);
    const t = curve.getTangentAt(u); const side = V(0, 0, 1); const up = new THREE.Vector3().crossVectors(side, t).normalize();
    for (let j = 0; j <= rad; j++) {
      const a = j / rad * Math.PI * 2; const n = 1 + noise * (Math.sin(a * 5 + u * 31) * 0.5 + Math.sin(a * 11 - u * 57) * 0.3 + Math.sin(u * 90) * 0.2);
      const cy = Math.cos(a) * ry * n, cz = Math.sin(a) * rz * n;
      const p = c.clone().addScaledVector(up, cy + (dy || 0)).addScaledVector(side, cz);
      pos.push(p.x, p.y, p.z); uv.push(u * 4, j / rad);
    }
  }
  for (let i = 0; i < seg; i++) for (let j = 0; j < rad; j++) { const a = i * (rad + 1) + j, b = a + rad + 1; idx.push(a, a + 1, b, b, a + 1, b + 1); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2)); g.setIndex(idx); g.computeVertexNormals();
  return { g, curve };
}
const prof = (stops) => (u) => { let i = 0; while (i < stops.length - 2 && stops[i + 1][0] < u) i++; const [u0, a0, b0, d0] = stops[i], [u1, a1, b1, d1] = stops[i + 1]; const k = ss(u0, u1, u); return [lerp(a0, a1, k), lerp(b0, b1, k), lerp(d0 || 0, d1 || 0, k)]; };
const SPINE = [V(-4.9, 1.0, 0), V(-3.7, 1.75, 0), V(-2.3, 2.65, 0), V(-0.9, 3.05, 0), V(0.5, 2.8, 0), V(1.7, 2.25, 0), V(2.7, 1.65, 0), V(3.5, 1.32, 0), V(4.15, 1.12, 0)];
const BODY = sculptTube(SPINE, prof([[0, 0.05, 0.05], [0.12, 0.22, 0.2], [0.28, 0.62, 0.52], [0.43, 1.0, 0.9, -0.05], [0.56, 0.98, 0.92, -0.08], [0.7, 0.72, 0.66], [0.8, 0.38, 0.32], [0.88, 0.4, 0.33], [0.95, 0.3, 0.26], [1, 0.08, 0.08]]));
const bodyMesh = new THREE.Mesh(BODY.g, statueM); bodyMesh.castShadow = true; bodyMesh.receiveShadow = true; statue.add(bodyMesh);
statue.add(new THREE.Mesh(BODY.g, innerM));
// pattes : tubes coniques creux (la patte arrière droite, côté caméra, est celle du piège)
function leg(top, knee, foot, r0, r1, name) {
  const T = sculptTube([top, knee, foot], (u) => [lerp(r0, r1, u) * (1 + 0.12 * Math.sin(u * Math.PI)), lerp(r0, r1, u) * 0.95, 0], 40, 32, 0.02);
  const m = new THREE.Mesh(T.g, statueM); m.castShadow = true; m.receiveShadow = true; statue.add(m); statue.add(new THREE.Mesh(T.g, innerM));
  const f = new THREE.Mesh(new THREE.SphereGeometry(1, 28, 14), statueM); f.scale.set(r1 * 1.45, 0.24, r1 * 1.35); f.position.copy(foot).add(V(0.12, -foot.y + 0.17, 0)); f.castShadow = true; statue.add(f);
  for (let k = -1; k <= 1; k++) { const t = new THREE.Mesh(new THREE.SphereGeometry(0.11, 12, 8), statueM); t.scale.set(1.3, 0.8, 1); t.position.copy(foot).add(V(r1 * 1.35 + 0.05, -foot.y + 0.09, k * r1 * 0.6)); statue.add(t); }
  return { top, knee, foot, r0, r1, mesh: m, name };
}
const LEGS = {
  hindR: leg(V(-0.95, 2.35, 0.62), V(-0.75, 1.3, 0.72), V(-1.0, 0.3, 0.78), 0.56, 0.42, 'hindR'),
  hindL: leg(V(-0.95, 2.35, -0.62), V(-0.75, 1.3, -0.72), V(-1.0, 0.3, -0.78), 0.56, 0.42, 'hindL'),
  foreR: leg(V(1.75, 1.85, 0.5), V(1.85, 1.0, 0.58), V(1.75, 0.3, 0.62), 0.34, 0.3, 'foreR'),
  foreL: leg(V(1.75, 1.85, -0.5), V(1.85, 1.0, -0.58), V(1.75, 0.3, -0.62), 0.34, 0.3, 'foreL'),
};
// plaques dorsales (deux rangées alternées) et pointes de la queue
const plateShape = new THREE.Shape(); plateShape.moveTo(-0.5, 0); plateShape.quadraticCurveTo(-0.55, 0.55, 0, 1); plateShape.quadraticCurveTo(0.55, 0.55, 0.5, 0); plateShape.lineTo(-0.5, 0);
const plateG = new THREE.ExtrudeGeometry(plateShape, { depth: 0.07, bevelEnabled: true, bevelSize: 0.03, bevelThickness: 0.03, bevelSegments: 2, curveSegments: 10 }); plateG.translate(0, 0, -0.035);
const PLATES = [];
for (let i = 0; i < 17; i++) {
  const u = 0.13 + i * 0.042; if (u > 0.79) break; const c = BODY.curve.getPointAt(u), ry = prof([[0, 0.05], [0.12, 0.22], [0.28, 0.62], [0.43, 1.0], [0.56, 0.98], [0.7, 0.72], [0.8, 0.36], [1, 0.05]])(u)[0];
  const sz = 0.3 + 0.8 * Math.exp(-((u - 0.45) ** 2) / 0.035); const side = i % 2 ? 1 : -1;
  if (Math.abs(u - 0.31) < 0.065) continue;   // la fente : pas de plaque juste au-dessus
  const p = new THREE.Mesh(plateG, plateM); p.scale.set(sz * 0.9, sz, 1); p.position.set(c.x, c.y + ry - 0.08, side * 0.13); p.rotation.set(side * 0.12, 0, -(BODY.curve.getTangentAt(u).y) * 0.6); p.castShadow = true; statue.add(p); PLATES.push(p);
}
for (const [u, s] of [[0.04, 1], [0.04, -1], [0.075, 1], [0.075, -1]]) { const c = BODY.curve.getPointAt(u); const sp = cyl(0.0, 0.75, plateM, 0, 0, 0, statue, 12, 0.07); const d = V(-1, 0.45, s * 0.75).normalize(); sp.quaternion.setFromUnitVectors(V(0, 1, 0), d); sp.position.set(c.x, c.y + 0.12, s * 0.12).addScaledVector(d, 0.36); }
// yeux, narines, bouche
for (const s of [-1, 1]) { const e = new THREE.Mesh(new THREE.SphereGeometry(0.045, 12, 8), M({ color: '#1a1a14', roughness: 0.3 })); e.position.set(3.72, 1.4, s * 0.2); statue.add(e); }
// la FENTE dans le dos (entre les plaques, au-dessus des hanches) : là où tombe le téléphone
const RYP = prof([[0, 0.05], [0.12, 0.22], [0.28, 0.62], [0.43, 1.0, 0, -0.05], [0.56, 0.98, 0, -0.08], [0.7, 0.72], [0.8, 0.38]]);
const topExact = (u) => { const c = BODY.curve.getPointAt(u), t = BODY.curve.getTangentAt(u), up = new THREE.Vector3().crossVectors(V(0, 0, 1), t).normalize(); const [ry, , dy] = RYP(u); return c.addScaledVector(up, ry + dy); };
const SLOT_U = 0.31; const SLOT_TOP = topExact(SLOT_U);
const slotM = new THREE.Mesh(new THREE.SphereGeometry(1, 24, 10), new THREE.MeshBasicMaterial({ color: '#020201', clippingPlanes: CLIP }));
{ const t = BODY.curve.getTangentAt(SLOT_U); slotM.scale.set(0.34, 0.03, 0.19); slotM.position.copy(SLOT_TOP).add(V(0, 0.01, 0)); slotM.rotation.z = Math.atan2(t.y, t.x); } statue.add(slotM);
const slotRim = new THREE.Mesh(new THREE.TorusGeometry(1, 0.07, 8, 28), M({ map: skinT, color: '#5d6449', roughness: 0.7, clippingPlanes: CLIP })); slotRim.scale.set(0.33, 0.19, 0.25); slotRim.rotation.x = Math.PI / 2; slotRim.position.copy(slotM.position).add(V(0, 0.01, 0)); slotRim.rotateOnWorldAxis(V(0, 0, 1), slotM.rotation.z); statue.add(slotRim);
// socle d'herbe autour des pattes ? non : la statue est posée sur les pavés

// ---------- lumières (jour / nuit) ----------
const hemi = new THREE.HemisphereLight('#dfe9f5', '#7d7466', 1.0); scene.add(hemi);
const sun = new THREE.DirectionalLight('#fff0dc', 3.0); sun.position.set(8, 14, 10); sun.target.position.set(0, 1, 0); sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048); Object.assign(sun.shadow.camera, { left: -12, right: 12, top: 12, bottom: -12, near: 1, far: 50 }); sun.shadow.bias = -0.0005; scene.add(sun, sun.target);
const fillL = new THREE.SpotLight('#f3f0ea', 0, 8, 0.7, 0.9, 1.6); scene.add(fillL, fillL.target);

// ---------- objets : téléphone, lampe torche, fleurs, bougies, brume ----------
const phone = new THREE.Group(); scene.add(phone);
box(0.074, 0.152, 0.009, M({ color: '#202327', roughness: 0.3, metalness: 0.7 }), 0, 0, 0, phone, false);
const scrT = canvasTex(256, 520, (g, w, h) => { const gr = g.createLinearGradient(0, 0, w, h); gr.addColorStop(0, '#5a7fd8'); gr.addColorStop(1, '#b65aa8'); g.fillStyle = gr; g.fillRect(0, 0, w, h); g.fillStyle = '#fff'; g.font = 'bold 54px Arial'; g.textAlign = 'center'; g.fillText('21:47', w / 2, 120); });
const scr = new THREE.Mesh(new THREE.PlaneGeometry(0.068, 0.14), new THREE.MeshBasicMaterial({ map: scrT, toneMapped: false })); scr.position.z = 0.0047; phone.add(scr);
const phoneL = new THREE.PointLight('#c9d6ff', 0, 1.6, 1.6); scene.add(phoneL);
const torch = new THREE.Group(); scene.add(torch); { const t = cyl(0.022, 0.2, M({ color: '#111', roughness: 0.4 }), 0, 0, 0, torch, 12); t.rotation.x = Math.PI / 2; const lens = new THREE.Mesh(new THREE.CircleGeometry(0.02, 12), new THREE.MeshBasicMaterial({ color: '#fffbe8', toneMapped: false })); lens.position.z = 0.101; torch.add(lens); }
const torchL = new THREE.SpotLight('#fff6e0', 0, 9, 0.32, 0.5, 1.2); scene.add(torchL, torchL.target);
const memorial = new THREE.Group(); scene.add(memorial);
{ const FOOT = LEGS.hindR.foot; const base = V(FOOT.x + 0.05, 0, FOOT.z + 0.62);
  const cols = ['#c8102e', '#f2f2f2', '#f6c344', '#e05a8a', '#ffffff', '#c8102e'];
  for (let b = 0; b < 7; b++) { const g = new THREE.Group(); g.position.copy(base).add(V(-0.65 + b * 0.21 + (rnd() - 0.5) * 0.08, 0.075, -0.15 + (rnd() - 0.5) * 0.2)); g.rotation.set(-(Math.PI / 2 - 0.12), 0, (rnd() - 0.5) * 0.9); memorial.add(g);
    const paper = new THREE.Mesh(new THREE.ConeGeometry(0.09, 0.36, 12, 1, true), M({ color: ['#e9e2d0', '#cfe0d6', '#e8d2dc', '#f3efe6'][b % 4], roughness: 0.6, side: THREE.DoubleSide })); g.add(paper);
    for (let k = 0; k < 9; k++) { const f = new THREE.Mesh(new THREE.SphereGeometry(0.04, 10, 8), M({ color: cols[(b + k) % cols.length], roughness: 0.7 })); f.scale.set(1, 0.8, 1); f.position.set((rnd() - 0.5) * 0.13, -0.2 - rnd() * 0.06, (rnd() - 0.5) * 0.13); g.add(f); }
    for (let k = 0; k < 4; k++) { const l = new THREE.Mesh(new THREE.SphereGeometry(0.03, 6, 4), M({ color: '#3f6b2e' })); l.scale.set(0.6, 1.6, 0.3); l.position.set((rnd() - 0.5) * 0.15, -0.19, (rnd() - 0.5) * 0.15); g.add(l); } }
  for (let c = 0; c < 7; c++) { const x = base.x - 0.6 + c * 0.2, z = base.z + 0.3 + (c % 2) * 0.12; cyl(0.03, 0.09, M({ color: '#b3202a', roughness: 0.4, transparent: true, opacity: 0.85 }), x, 0.045, z, memorial, 10);
    const fl = new THREE.Mesh(new THREE.SphereGeometry(0.012, 8, 6), new THREE.MeshBasicMaterial({ color: '#ffcf70', toneMapped: false })); fl.scale.y = 1.8; fl.position.set(x, 0.11, z); memorial.add(fl); }
}
const candleL = new THREE.PointLight('#ffb35a', 0, 3.5, 1.5); candleL.position.set(LEGS.hindR.foot.x, 0.3, LEGS.hindR.foot.z + 0.9); scene.add(candleL);
const hazeT = canvasTex(128, 128, (g, w, h) => { const r = g.createRadialGradient(64, 64, 4, 64, 64, 62); r.addColorStop(0, 'rgba(150,190,70,0.55)'); r.addColorStop(1, 'rgba(150,190,70,0)'); g.fillStyle = r; g.fillRect(0, 0, w, h); });
const HAZE = []; for (let i = 0; i < 26; i++) { const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: hazeT, transparent: true, depthWrite: false, opacity: 0 })); sp.userData = { ph: rnd(), x: (rnd() - 0.5) * 1.2, z: rnd() * 0.9, s: 0.6 + rnd() * 0.9 }; scene.add(sp); HAZE.push(sp); }

// ---------- personnages ----------
await RealHuman.loadClips(['idle', 'walk', 'slowwalk', 'facepalm', 'phone_talk', 'explain'], './mocap/');
const MK = async (u, h, seed) => { const H = await RealHuman.create(`./models/${u}.glb`, { heightM: h, seed }); scene.add(H.root); H.root.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } }); H.root.rotation.order = 'YXZ'; return H; };
const HERO = await MK('g_Male_Adult_04', 1.78, 5);
const WOMAN = await MK('g_Female_Adult_05', 1.66, 3), MAN2 = await MK('g_Male_Adult_09', 1.82, 8);
const COP1 = await MK('police', 1.84, 2), COP2 = await MK('police', 1.78, 6);
const EXTRA = [await MK('g_Female_Adult_02', 1.68, 4), await MK('g_Male_Adult_01', 1.8, 9), await MK('g_Female_Adult_08', 1.64, 12), await MK('dad', 1.8, 14)];

// ---------- outils ----------
const FULL = { pelvis: 1, spineAbs: 1, legs: 1, arms: 1, root: 1, headAbs: 0.4 };
const dur = (c) => RealHuman.clips[c].frames / RealHuman.clips[c].fps;
const loopT = (c, x) => ((x % dur(c)) + dur(c)) % dur(c);
const IDLEM = (t, arms = 1) => [{ clip: 'idle', mode: 'abs', t: loopT('idle', t), k: 1, w: { legs: 1, root: 1, pelvis: 0.1, spineAbs: 0.1, arms } }];
const CLIPL = (c, t, k = 1) => [{ clip: c, mode: 'abs', t: loopT(c, t), k, w: FULL }];
const FEAR = { maxM: 1.5, raw: { EyeWideLeft: 1.3, EyeWideRight: 1.3, BrowInnerUp: 1.2, BrowOuterUpLeft: 1.0, BrowOuterUpRight: 1.0, JawOpen: 0.25, MouthStretchLeft: 0.6, MouthStretchRight: 0.6 } };
const SHOCK = { maxM: 1.6, raw: { EyeWideLeft: 1.6, EyeWideRight: 1.6, BrowInnerUp: 1.4, BrowOuterUpLeft: 1.3, BrowOuterUpRight: 1.3, JawOpen: 0.45, MouthLowerDownLeft: 0.5, MouthLowerDownRight: 0.5 } };
const STRAIN = { maxM: 1.6, raw: { BrowDownLeft: 1.0, BrowDownRight: 1.0, BrowInnerUp: 0.8, EyeSquintLeft: 0.8, EyeSquintRight: 0.8, JawOpen: 0.35, MouthStretchLeft: 0.9, MouthStretchRight: 0.9, NoseSneerLeft: 0.6, NoseSneerRight: 0.6 } };
const FOCUS = { maxM: 1.2, raw: { BrowDownLeft: 0.3, BrowDownRight: 0.3, EyeSquintLeft: 0.2, EyeSquintRight: 0.2 } };
const DISGUST = { maxM: 1.5, raw: { NoseSneerLeft: 1.2, NoseSneerRight: 1.2, BrowDownLeft: 0.8, BrowDownRight: 0.8, EyeSquintLeft: 0.9, EyeSquintRight: 0.9, MouthUpperUpLeft: 0.6, MouthUpperUpRight: 0.6, MouthFrownLeft: 0.6, MouthFrownRight: 0.6 } };
const DEAD = { maxM: 1, raw: { EyeBlinkLeft: 1, EyeBlinkRight: 1, JawOpen: 0.15 } };
const frameOf = (yaw) => ({ f: V(Math.sin(yaw), 0, Math.cos(yaw)), r: V(-Math.cos(yaw), 0, Math.sin(yaw)) });
const boneW = (H, k) => H.bones[H.B[k]].getWorldPosition(new THREE.Vector3());
const bn = (H, n) => H.bones[n].getWorldPosition(new THREE.Vector3());
function palm(H, s) { const h = bn(H, `Bip01_${s}_Hand`), f2 = bn(H, `Bip01_${s}_Finger2`), f1 = bn(H, `Bip01_${s}_Finger1`), f4 = bn(H, `Bip01_${s}_Finger4`);
  const fd = f2.clone().sub(h).normalize(), ac = f1.clone().sub(f4).normalize(); return { c: h.clone().lerp(f2, 0.55), fd, n: new THREE.Vector3().crossVectors(fd, ac).normalize(), h }; }
function palmIn(H, s) { const P = palm(H, s), th = bn(H, `Bip01_${s}_Finger0`); if (P.n.dot(th.clone().sub(P.c)) < 0) P.n.negate(); return P; }
const yawTo = (a, b) => Math.atan2(b.x - a.x, b.z - a.z);
const topAt = (u) => topExact(u).add(V(0, -0.02, 0));
function walkPath(a, b, t0, t1, T, clip = 'walk', speed = 1) {   // marche de a à b entre t0 et t1 ; avant / après : immobile
  const u = Math.min(1, Math.max(0, (T - t0) / (t1 - t0))); const pos = a.clone().lerp(b, u); const moving = u > 0 && u < 1;
  return { pos, yaw: yawTo(a, b), layers: moving ? CLIPL(clip, (T - t0) * speed) : IDLEM(T), moving };
}

// ---------- personnage « en blocs » (style jeu de construction, original) ----------
const BK = (() => {
  const S = 0.92, g = new THREE.Group(); g.rotation.order = 'YXZ'; scene.add(g);
  const plastic = (c) => new THREE.MeshStandardMaterial({ color: c, roughness: 0.45, metalness: 0.0 });
  const RB = (w, h, d, m, r = 0.05) => { const x = new THREE.Mesh(new RoundedBoxGeometry(w, h, d, 3, r), m); x.castShadow = true; x.receiveShadow = true; return x; };
  const skin = plastic('#f2c79a'), shirt = plastic('#8e9aa8'), pants = plastic('#2c2f36'), shoe = plastic('#e9e9e9'), hairM = plastic('#3a2a20');
  const hip = new THREE.Group(); hip.position.y = 0.8 * S; g.add(hip);
  const upper = new THREE.Group(); hip.add(upper);
  const torso = RB(0.76 * S, 0.76 * S, 0.38 * S, shirt); torso.position.y = 0.38 * S; upper.add(torso);
  const head = new THREE.Group(); head.position.y = 0.76 * S + 0.02; upper.add(head);
  const hd = new THREE.Mesh(new THREE.CylinderGeometry(0.235 * S, 0.235 * S, 0.42 * S, 32), skin); hd.position.y = 0.21 * S; hd.castShadow = true; head.add(hd);
  for (const y of [0, 0.42]) { const cap = new THREE.Mesh(new THREE.SphereGeometry(0.235 * S, 32, 8, 0, Math.PI * 2, y ? 0 : Math.PI / 2, Math.PI / 2), skin); cap.scale.y = 0.25; cap.position.y = y * S; head.add(cap); }
  const hair = RB(0.5 * S, 0.16 * S, 0.5 * S, hairM, 0.06); hair.position.set(0, 0.47 * S, -0.02); head.add(hair);
  const fringe = RB(0.46 * S, 0.1 * S, 0.12 * S, hairM, 0.04); fringe.position.set(0, 0.4 * S, 0.19 * S); head.add(fringe);
  const faces = {}; const faceC = document.createElement('canvas'); faceC.width = 256; faceC.height = 256; const fg = faceC.getContext('2d'); const faceT = new THREE.CanvasTexture(faceC); faceT.colorSpace = THREE.SRGBColorSpace;
  function drawFace(k) {
    fg.clearRect(0, 0, 256, 256); fg.fillStyle = '#1b1b1b'; fg.strokeStyle = '#1b1b1b'; fg.lineCap = 'round';
    const wide = k === 'shock' ? 1.35 : k === 'strain' ? 0.55 : 1;
    for (const x of [88, 168]) { fg.beginPath(); fg.ellipse(x, 112, 13, 19 * wide, 0, 0, 7); fg.fill(); fg.fillStyle = '#fff'; fg.beginPath(); fg.arc(x + 4, 104, 4.5, 0, 7); fg.fill(); fg.fillStyle = '#1b1b1b'; }
    fg.lineWidth = 7; fg.beginPath();
    if (k === 'shock') { fg.moveTo(68, 76); fg.lineTo(104, 70); fg.moveTo(188, 76); fg.lineTo(152, 70); } else if (k === 'strain') { fg.moveTo(68, 78); fg.lineTo(106, 90); fg.moveTo(188, 78); fg.lineTo(150, 90); } else { fg.moveTo(70, 82); fg.lineTo(104, 80); fg.moveTo(186, 82); fg.lineTo(152, 80); }
    fg.stroke(); fg.lineWidth = 7; fg.beginPath();
    if (k === 'shock') { fg.ellipse(128, 176, 18, 24, 0, 0, 7); fg.fill(); } else if (k === 'strain') { fg.fillStyle = '#fff'; fg.fillRect(100, 164, 56, 20); fg.strokeRect(100, 164, 56, 20); fg.moveTo(100, 174); fg.lineTo(156, 174); fg.stroke(); }
    else if (k === 'smile') { fg.arc(128, 150, 32, 0.25 * Math.PI, 0.75 * Math.PI); fg.stroke(); } else { fg.moveTo(108, 172); fg.lineTo(148, 172); fg.stroke(); }
    faceT.needsUpdate = true;
  }
  const face = new THREE.Mesh(new THREE.CylinderGeometry(0.237 * S, 0.237 * S, 0.42 * S, 32, 1, true, -Math.PI / 2, Math.PI), new THREE.MeshStandardMaterial({ map: faceT, transparent: true, roughness: 0.45 })); face.position.y = 0.21 * S; head.add(face);
  const limb = (m, hand) => { const pv = new THREE.Group(); const b = RB(0.37 * S, 0.76 * S, 0.37 * S, m); b.position.y = -0.38 * S; pv.add(b); if (hand) { const h = RB(0.36 * S, 0.14 * S, 0.36 * S, skin, 0.05); h.position.y = -0.7 * S; pv.add(h); } return pv; };
  const lArm = limb(shirt, true), rArm = limb(shirt, true); lArm.position.set(0.57 * S, 0.66 * S, 0); rArm.position.set(-0.57 * S, 0.66 * S, 0); upper.add(lArm, rArm);
  const lLeg = limb(pants), rLeg = limb(pants); lLeg.position.set(0.19 * S, 0, 0); rLeg.position.set(-0.19 * S, 0, 0); hip.add(lLeg, rLeg);
  for (const L of [lLeg, rLeg]) { const sh = RB(0.38 * S, 0.12 * S, 0.42 * S, shoe, 0.04); sh.position.set(0, -0.74 * S, 0.02); L.add(sh); }
  const handR = new THREE.Object3D(); handR.position.set(0, -0.76 * S, 0.12 * S); rArm.add(handR);
  let cur = ''; return { g, hip, upper, head, lArm, rArm, lLeg, rLeg, handR, setFace(k) { if (k !== cur) { cur = k; drawFace(k); } }, S };
})();
BK.g.visible = false;
function poseBlocky(T, h) {
  const B = BK; B.g.visible = h.vis && BLOCKY; B.g.position.copy(h.pos); B.g.rotation.set(h.pitch || 0, h.yaw, 0);
  const sit = h.sit || 0; B.hip.position.y = 0.8 * B.S - sit * 0.78 * B.S;
  const sway = Math.sin(T * 1.7) * 0.03;
  B.upper.rotation.set((h.lean || 0) * 0.9 + sway, 0, 0); B.head.rotation.set(h.look === 'slot' || h.look === 'phoneDown' ? 0.35 : h.look === 'phone' ? 0.15 : 0, 0, 0);
  // jambes
  for (const [L, sd] of [[B.lLeg, 1], [B.rLeg, -1]]) {
    if (h.legs === 'astride') L.rotation.set(-0.55, 0, sd * 1.05);
    else if (h.legs === 'kick') L.rotation.set(0.5 * Math.sin(T * 13 + (sd > 0 ? 0 : Math.PI)), 0, sd * 0.12);
    else if (h.legs === 'crawl') L.rotation.set(0.25 * Math.sin(T * 6 + (sd > 0 ? 0 : Math.PI)), 0, sd * 0.08);
    else L.rotation.set(0, 0, 0);
  }
  // bras
  const A = h.arms; const r = B.rArm.rotation, l = B.lArm.rotation; r.set(0.05 * Math.sin(T * 1.3), 0, 0.06); l.set(-0.05 * Math.sin(T * 1.3), 0, -0.06);
  if (A.phoneR) { r.set(-1.75, 0.35, -0.25); }
  if (A.grab > 0) { r.set(lerp(-1.75, -1.05, A.grab), lerp(0.35, 0, A.grab), -0.1); l.set(-0.4 * A.grab, 0, -0.2); }
  if (A.reach > 0) { r.set(lerp(-0.6, -1.2, A.reach) + 0.12 * Math.sin(T * 13) * A.reach, 0, -0.05); l.set(-0.9 * A.reach, 0, -0.35); }
  if (A.dive > 0) { r.set(lerp(r.x, -3.0, A.dive), 0, -0.1); l.set(lerp(l.x, -3.0, A.dive), 0, 0.1); }
  if (A.crawl) { r.set(-2.7 + 0.35 * Math.sin(T * 6), 0, -0.1); l.set(-2.7 - 0.35 * Math.sin(T * 6), 0, 0.1); }
  B.setFace(h.face === SHOCK ? 'shock' : h.face === STRAIN ? 'strain' : (h.face && h.face.raw && (h.face.raw.EyeWideLeft || 0) > 0.8) ? 'shock' : T < 2.3 ? 'smile' : 'neutral');
  B.g.updateMatrixWorld(true); B.head.getWorldPosition(_hw); _hw.add(V(0, 0.2, 0).applyQuaternion(B.g.quaternion));
}

// ---------- chronologie (voix : horreur/de_ep06_dino/words.json, 34,5 s) ----------
const END = BLOCKY ? 10.85 : 34.62;
const SEAT = topAt(0.255), SLOTP = SLOT_TOP.clone();
const LEG = LEGS.hindR; const LEGTOP = V(LEG.top.x + 0.05, 2.2, LEG.top.z + 0.05), LEGBOT = V(LEG.foot.x + 0.05, 0.42, LEG.foot.z);
const PHONE_DOWN = V(LEG.foot.x + 0.27, 0.36, LEG.foot.z - 0.02);
const DAYS = [21.3, 24.75];
function heroState(T) {
  const s = { pos: SEAT.clone(), yaw: Math.PI / 2, pitch: 0, roll: 0, layers: [{ clip: 'idle', mode: 'abs', t: loopT('idle', T * 0.6), k: 1, w: { spineAbs: 0.1, arms: 0.3 } }], face: FOCUS, look: 'phone', vis: true, sit: 1, arms: {}, legs: 'astride', inside: false };
  if (T < 2.35) { s.face = FOCUS; s.arms.phoneR = 1; return s; }
  if (T < 3.4) { s.face = mix(FOCUS, SHOCK, ss(2.4, 2.75, T)); s.look = 'phoneF'; s.arms.grab = ss(2.35, 2.7, T); s.lean = 0.25 * ss(2.4, 2.9, T); return s; }
  if (T < 6.0) { s.face = SHOCK; s.look = 'slot'; s.lean = 0.25 + 0.35 * ss(3.4, 4.4, T); s.arms.grab = 0; return s; }
  if (T < 8.0) { s.face = mix(SHOCK, STRAIN, ss(6.2, 7.0, T)); s.look = 'slot'; s.lean = 0.6 + 0.25 * ss(6.0, 6.6, T); s.arms.reach = ss(6.0, 6.7, T) * (1 - ss(7.6, 8.0, T)); return s; }
  if (T < 10.05) {   // il plonge la tête la première dans la fente
    s.sit = 1 - ss(8.05, 8.4, T); s.legs = T < 8.4 ? 'astride' : 'kick'; s.face = STRAIN; s.look = 'slot'; s.lean = 0.8 * (1 - ss(8.6, 9.0, T));
    s.pitch = lerp(0, 1.2, ss(8.05, 8.6, T)) + lerp(0, 1.6, ss(8.6, 9.1, T));
    const top = SLOTP.clone().add(V(-0.35, 0.95, 0));   // hanches dans la fente, jambes en l'air
    s.pos = SEAT.clone().lerp(SEAT.clone().add(V(0.15, 0.1, 0)), ss(8.05, 8.6, T)).lerp(top, ss(8.6, 9.1, T)).add(V(0.12 * ss(9.1, 9.95, T), -1.15 * ss(9.1, 9.95, T) ** 1.3, 0)); s.arms.dive = ss(8.2, 8.7, T); return s;
  }
  s.inside = true; s.sit = 0; s.lean = 0; s.legs = 'kick';
  if (T < 13.0) {   // dans le ventre : il rampe vers l'arrière-train (la lumière du téléphone en bas)
    const u = ss(10.05, 12.95, T); s.pitch = 1.5; s.yaw = 1.15;
    s.pos = V(lerp(-3.2, -2.5, u), lerp(2.38, 2.45, u), lerp(-0.35, -0.08, u)); s.face = STRAIN; s.look = 'phoneDown'; s.arms.crawl = 1; s.legs = 'crawl'; return s;
  }
  if (T < 16.2) {   // il glisse… et tombe la tête la première dans la patte
    const f = ss(13.35, 14.05, T); s.pitch = lerp(1.5, Math.PI, ss(13.2, 13.9, T)); s.yaw = lerp(1.15, Math.PI, ss(13.2, 14.0, T));
    s.pos = V(lerp(-2.5, LEGTOP.x, f), lerp(2.45, LEGTOP.y - 0.13, f) + 0.05 * Math.sin(T * 30) * (inR(T, 14.05, 14.35) ? 1 : 0), lerp(-0.08, LEGTOP.z, f));
    s.face = f < 0.5 ? STRAIN : SHOCK; s.look = 'phoneDown'; s.arms.fall = f; s.legs = 'stuck'; return s;
  }
  // coincé la tête en bas
  s.pos = LEGTOP.clone().add(V(0, -0.13, 0)); s.pitch = Math.PI; s.yaw = Math.PI; s.legs = 'stuck';
  if (T < 21.3) { s.face = inR(T, 16.2, 18.3) ? FEAR : STRAIN; s.look = 'phoneDown'; s.arms.push = 1; s.struggle = 1; return s; }
  s.face = DEAD; s.look = null; s.arms.hang = 1; s.struggle = 0; return s;
}
// passants (accéléré « Tage vergingen »), le couple qui sent l'odeur, la police
const NEAR = V(LEG.foot.x - 1.45, 0, LEG.foot.z + 1.0);
function womanState(T) {
  if (T < 24.7 || T >= 33.0) return { vis: false };
  const w = walkPath(V(1.6, 0, 4.6), NEAR.clone().add(V(0.35, 0, 0.25)), 24.75, 26.3, T, 'slowwalk');
  const s = { vis: true, pos: w.pos, yaw: w.moving ? w.yaw : lerp(w.yaw, yawTo(NEAR, LEG.foot), ss(26.3, 26.8, T)), layers: w.layers, face: inR(T, 25.8, 33) ? DISGUST : { raw: {} }, look: T > 25.9 ? 'leg' : null, nose: 0, call: 0 };
  if (T > 26.2 && T < 28.6) s.nose = ss(26.25, 26.7, T) * (1 - ss(28.3, 28.65, T));
  if (T >= 28.6) { s.call = ss(28.6, 29.2, T); s.look = 'away'; s.face = mix(DISGUST, FEAR, 0.5); }
  if (T >= 30.0) { s.pos = s.pos.clone().lerp(NEAR.clone().add(V(1.6, 0, 1.0)), ss(30.0, 31.2, T)); s.call = 1 - ss(30.0, 30.4, T); s.look = 'cop'; s.layers = inR(T, 30.0, 31.2) ? CLIPL('slowwalk', T) : IDLEM(T); s.yaw = lerp(s.yaw, -2.4, ss(30.0, 30.6, T)); }
  return s;
}
function man2State(T) {
  if (T < 24.7 || T >= 33.0) return { vis: false };
  const w = walkPath(V(2.4, 0, 4.0), NEAR.clone().add(V(-0.45, 0, -0.1)), 24.9, 26.4, T, 'walk', 0.9);
  const s = { vis: true, pos: w.pos, yaw: w.moving ? w.yaw : lerp(w.yaw, yawTo(NEAR, LEG.foot) + 0.2, ss(26.4, 26.9, T)), layers: w.layers, face: T > 25.8 ? DISGUST : { raw: {} }, look: T > 25.9 ? 'leg' : null, nose: 0 };
  if (T > 26.0) s.nose = ss(26.05, 26.5, T);
  if (T >= 30.0) { s.pos = s.pos.clone().lerp(NEAR.clone().add(V(1.0, 0, 1.6)), ss(30.0, 31.0, T)); s.nose = 1 - ss(30.0, 30.4, T); s.layers = inR(T, 30.0, 31.0) ? CLIPL('walk', T) : IDLEM(T + 3); s.look = 'cop'; }
  return s;
}
function copState(T, i) {
  if (T < 29.85 || T >= 33.0) return { vis: false };
  const a = i ? V(-7, 0, 9) : V(-6.2, 0, 8.2), b = i ? V(LEG.foot.x - 0.75, 0, LEG.foot.z + 1.35) : V(LEG.foot.x + 0.15, 0, LEG.foot.z + 1.05);
  const w = walkPath(a, b, 29.9, 31.35, T, 'walk', 1.1);
  const s = { vis: true, pos: w.pos, yaw: w.moving ? w.yaw : yawTo(b, LEG.foot.clone().add(V(0, 0, 0))), layers: w.layers, face: T > 31.6 ? SHOCK : FOCUS, look: T > 31.3 ? 'legMid' : null, torch: i === 0 ? ss(31.3, 31.7, T) : 0 };
  return s;
}
const EXTRA_PATHS = [[V(-9, 0, 4.0), V(9, 0, 3.6), 21.4, 22.9], [V(9, 0, 2.8), V(-9, 0, 3.2), 21.9, 23.5], [V(-9, 0, 5.2), V(9, 0, 5.0), 22.9, 24.6], [V(9, 0, 6.0), V(-8, 0, 5.6), 21.5, 23.2]];

// ---------- caméra ----------
const _hw = new THREE.Vector3();
const FOC = {
  hero: () => _hw.clone(), seat: () => SEAT.clone().add(V(0, 0.8, 0)), slot: () => SLOTP.clone(), statue: () => V(-0.2, 2.0, 0), phone: () => phone.position.clone(),
  leg: () => V(LEG.knee.x, 1.25, LEG.knee.z), legLow: () => V(LEG.foot.x, 0.55, LEG.foot.z), belly: () => V(-2.3, 2.45, 0.1),
  woman: () => WOMAN.headWorld(new THREE.Vector3()), couple: () => NEAR.clone().add(V(0.25, 1.3, 0.1)), cops: () => V(LEG.foot.x - 0.3, 1.3, LEG.foot.z + 1.2), flowers: () => V(LEG.foot.x, 0.25, LEG.foot.z + 0.65),
};
const CAM = [
  // A — l'accroche : l'homme sur le dos de la statue géante, le téléphone tombe dans la fente
  { t: 0.0, f: 'seat', az: -20, el: -12, d: 5.0, fov: 44 },
  { t: 2.2, f: 'seat', az: 10, el: 4, d: 2.6, fov: 40 },
  { t: 2.3, cut: 1, f: 'slot', az: 40, el: 55, d: 1.7, fov: 40 },
  { t: 3.35, f: 'slot', az: 25, el: 68, d: 1.3, fov: 36 },
  { t: 3.4, cut: 1, f: 'statue', az: -72, el: 20, d: 9.0, fov: 46 },
  { t: 5.95, f: 'statue', az: -55, el: 16, d: 8.0, fov: 44 },
  // B — il veut le récupérer : le bras dans la fente
  { t: 6.0, cut: 1, f: 'hero', az: 15, el: 18, d: 1.8, fov: 38 },
  { t: 7.95, f: 'hero', az: 35, el: 22, d: 1.5, fov: 36 },
  // C — il se glisse dedans, la tête la première
  { t: 8.0, cut: 1, f: 'slot', az: 5, el: 25, d: 3.4, fov: 42 },
  { t: 10.0, f: 'slot', az: 20, el: 30, d: 2.8, fov: 40 },
  // D — dans le ventre (vue en coupe), il rampe
  { t: 10.05, cut: 1, clip: 'body', f: 'hero', az: -10, el: 8, d: 1.9, fov: 42 },
  { t: 12.95, clip: 'body', f: 'hero', az: 15, el: 4, d: 1.5, fov: 38 },
  // E — la chute dans la patte
  { t: 13.0, cut: 1, clip: 'leg', f: 'leg', az: 15, el: 4, d: 3.2, fov: 44 },
  { t: 16.15, clip: 'leg', f: 'leg', az: 0, el: 0, d: 2.7, fov: 42 },
  // F — coincé la tête en bas : gros plan visage, puis on tourne autour de la patte coupée
  { t: 16.2, cut: 1, clip: 'leg', f: 'hero', az: 8, el: 4, d: 0.95, fov: 36 },
  { t: 18.3, clip: 'leg', f: 'hero', az: -6, el: 2, d: 0.8, fov: 34 },
  { t: 18.35, cut: 1, clip: 'leg', f: 'leg', az: 40, el: 10, d: 2.4, fov: 42 },
  { t: 21.25, clip: 'leg', f: 'leg', az: -25, el: 6, d: 2.2, fov: 42 },
  // G — des jours passent (plan large accéléré)
  { t: 21.3, cut: 1, f: 'statue', az: 15, el: 8, d: 12.5, fov: 48 },
  { t: 24.7, f: 'statue', az: 30, el: 10, d: 11.5, fov: 48 },
  // H — les passants sentent l'odeur, elle appelle la police
  { t: 24.75, cut: 1, f: 'couple', az: 45, el: 10, d: 6.5, fov: 46 },
  { t: 26.6, f: 'couple', az: 30, el: 4, d: 3.0, fov: 42 },
  { t: 28.55, cut: 1, f: 'woman', az: 200, el: 4, d: 1.5, fov: 38 },
  { t: 29.9, f: 'woman', az: 215, el: 2, d: 1.25, fov: 36 },
  // I — la police arrive, la lampe sur la patte… puis la vue en coupe
  { t: 29.95, cut: 1, p: () => V(LEG.foot.x + 0.2, 1.3, LEG.foot.z + 0.45), l: () => V(-3.5, 1.2, 6.5), fov: 46 },
  { t: 31.55, p: () => V(LEG.foot.x + 0.35, 1.2, LEG.foot.z + 0.5), l: () => V(-1.6, 1.3, 3.0), fov: 44 },
  { t: 31.6, cut: 1, clip: 'leg', f: 'leg', az: 60, el: 2, d: 2.4, fov: 44 },
  { t: 32.95, clip: 'leg', f: 'leg', az: 45, el: 0, d: 2.1, fov: 42 },
  // J — les fleurs au pied de la patte
  { t: 33.0, cut: 1, f: 'flowers', az: 8, el: 28, d: 2.3, fov: 44 },
  { t: END, f: 'flowers', az: 0, el: 22, d: 1.8, fov: 42 },
];
const DEG = Math.PI / 180;
function keyVec(k) { if (k.p) { const F = k.p(), L = k.l(); return [F.x, F.y, F.z, 0, 0, 0, L.x, L.y, L.z, k.fov]; } const F = FOC[k.f](), L = k.lk ? FOC[k.lk]() : F.clone(); return [F.x, F.y, F.z, k.az, k.el, k.d, L.x, L.y, L.z, k.fov]; }
function camAt(T) {
  let i = 0; while (i < CAM.length - 1 && CAM[i + 1].t <= T) i++;
  let s0 = i; while (s0 > 0 && !CAM[s0].cut) s0--; let s1 = i; while (s1 < CAM.length - 1 && !CAM[s1 + 1].cut) s1++;
  const ids = [Math.max(s0, i - 1), i, Math.min(s1, i + 1), Math.min(s1, i + 2)]; const Vs = ids.map(j => keyVec(CAM[j]));
  for (let j = 1; j < 4; j++) { while (Vs[j][3] - Vs[j - 1][3] > 180) Vs[j][3] -= 360; while (Vs[j][3] - Vs[j - 1][3] < -180) Vs[j][3] += 360; }
  const t0 = CAM[ids[1]].t, t1 = CAM[ids[2]].t; const u = ids[2] === ids[1] ? 0 : Math.min(1, Math.max(0, (T - t0) / (t1 - t0)));
  const cr = (a, b, c, d) => 0.5 * ((2 * b) + (-a + c) * u + (2 * a - 5 * b + 4 * c - d) * u * u + (-a + 3 * b - 3 * c + d) * u * u * u);
  const v = Vs[0].map((_, j) => cr(Vs[0][j], Vs[1][j], Vs[2][j], Vs[3][j])); const az = v[3] * DEG, el = v[4] * DEG, d = Math.max(0, v[5]);
  return { pos: V(v[0] + Math.sin(az) * Math.cos(el) * d, v[1] + Math.sin(el) * d, v[2] + Math.cos(az) * Math.cos(el) * d), tgt: V(v[6], v[7], v[8]), fov: v[9], clip: CAM[i].clip };
}

// ---------- jour / nuit ----------
function sky(T) {
  // soir au début (il est sur la statue à 21h47), jours qui défilent pendant « Tage vergingen », jour gris ensuite, nuit pour les fleurs
  let night = 0.55;
  if (T >= DAYS[0] && T < DAYS[1]) { const u = (T - DAYS[0]) / (DAYS[1] - DAYS[0]); night = 0.5 - 0.5 * Math.cos(u * Math.PI * 2 * 2.5); }
  else if (T >= DAYS[1] && T < 33.0) night = 0.05;
  else if (T >= 33.0) night = 0.85;
  const dusk = Math.max(0, 1 - Math.abs(night - 0.45) / 0.25) * 0.8;
  const c = SKY_DAY.clone().lerp(SKY_NIGHT, night).lerp(SKY_DUSK, dusk * 0.5); scene.background.copy(c); scene.fog.color.copy(c);
  sun.intensity = 3.0 * (1 - night) ** 1.5 + 0.05; hemi.intensity = 0.25 + 0.85 * (1 - night); sun.color.set('#fff0dc').lerp(new THREE.Color('#ff9a5a'), dusk * 0.7);
  for (const { h, L } of LAMPS) { const on = ss(0.35, 0.55, night); h.material.emissiveIntensity = 2.2 * on; L.intensity = 14 * on; }
  sign.material.emissiveIntensity = 0.15 + 1.2 * ss(0.35, 0.6, night);
  return night;
}

// ---------- image ----------
function poseHuman(H, st, T, extra = {}) {
  H.root.visible = st.vis !== false; if (!H.root.visible) return;
  H.root.position.copy(st.pos); H.root.rotation.set(st.pitch || 0, st.yaw, st.roll || 0);
  const pose = { mo: st.layers, lookW: 0.8, ...extra }; H.root.updateMatrixWorld(true); H.setPose(pose, st.face, st.lookP || null, T); return pose;
}
function frame(T) {
  const night = sky(T); const c = camAt(T);
  // plans de coupe : on ouvre la statue du côté de la caméra
  CLIP.length = 0;
  if (c.clip === 'body') CLIP.push(new THREE.Plane(V(0, 0, -1), 0.18));
  if (c.clip === 'leg') CLIP.push(new THREE.Plane(V(0, 0, -1), LEG.top.z + 0.02));
  camera.position.copy(c.pos); camera.up.set(0, 1, 0); camera.lookAt(c.tgt); camera.fov = c.fov;
  const inside = !!c.clip;
  hemi.intensity *= inside ? 0.35 : 1; sun.intensity *= inside ? 0.25 : 1;
  // --- l'homme
  const h = heroState(T); const hf = frameOf(h.yaw);
  const lookP = { phone: () => phone.position.clone(), phoneF: () => phone.position.clone(), slot: () => SLOTP.clone(), phoneDown: () => PHONE_DOWN.clone() }[h.look];
  h.lookP = lookP ? lookP() : null;
  const extra = { sit: h.sit, sitH: 0, spineX: (h.lean || 0) * 0.9, headX: (h.lean || 0) * 0.3 };
  if (h.legs === 'astride') Object.assign(extra, { lHip: +(Q.get('hx') || -1.0), rHip: +(Q.get('hx') || -1.0), lHipZ: -(Q.get('hz') || 1.2), rHipZ: +(Q.get('hz') || 1.2), lKnee: +(Q.get('kn') || 1.2), rKnee: +(Q.get('kn') || 1.2) });
  if (h.legs === 'kick') Object.assign(extra, { lHip: -0.3 + 0.35 * Math.sin(T * 11), rHip: -0.3 - 0.35 * Math.sin(T * 11), lKnee: 0.6 + 0.4 * Math.sin(T * 11 + 1), rKnee: 0.6 - 0.4 * Math.sin(T * 11 + 1) });
  if (h.legs === 'crawl') Object.assign(extra, { lHip: -0.2 + 0.25 * Math.sin(T * 5), rHip: -0.2 - 0.25 * Math.sin(T * 5), lKnee: 0.9, rKnee: 0.9 });
  if (h.legs === 'stuck') { const k = h.struggle ? 0.25 * Math.sin(T * 9) : 0; Object.assign(extra, { lHip: -0.55 + k, rHip: -0.45 - k, lKnee: 1.2 - k, rKnee: 1.0 + k, lHipZ: -0.15, rHipZ: 0.15 }); }
  let pose = poseHuman(HERO, { ...h, layers: h.inside || h.sit < 0.5 ? null : h.layers }, T, extra); HERO.headWorld(_hw);
  // bras
  const sh = boneW(HERO, 'sp2'), up = V(0, 1, 0).applyQuaternion(HERO.root.quaternion), fw = hf.f.clone().applyAxisAngle(hf.r, 0).applyQuaternion(new THREE.Quaternion());
  const bodyF = V(0, 0, 1).applyQuaternion(HERO.root.quaternion), bodyR = V(-1, 0, 0).applyQuaternion(HERO.root.quaternion);
  const A = h.arms; const tgt = {};
  const faceP = _hw.clone().addScaledVector(bodyF, 0.32).addScaledVector(up, -0.16).addScaledVector(bodyR, 0.04);
  if (A.phoneR) tgt.r = faceP.clone();
  if (A.grab > 0) tgt.r = faceP.clone().lerp(SLOTP.clone().add(V(-0.05, 0.12, 0.1)), A.grab);
  if (A.reach > 0) { tgt.r = sh.clone().addScaledVector(bodyR, 0.2).addScaledVector(up, -0.3).lerp(SLOTP.clone().add(V(0, -0.35 + 0.05 * Math.sin(T * 13), 0.02)), A.reach); tgt.l = SLOTP.clone().add(V(-0.25, 0.02, -0.28)); }
  if (A.dive > 0) { tgt.r = _hw.clone().addScaledVector(up, 0.45).addScaledVector(bodyR, 0.12); tgt.l = _hw.clone().addScaledVector(up, 0.45).addScaledVector(bodyR, -0.12); }
  if (A.crawl) { const a = Math.sin(T * 5); tgt.r = _hw.clone().addScaledVector(up, 0.25 + 0.12 * a).addScaledVector(bodyR, 0.22).addScaledVector(bodyF, 0.18); tgt.l = _hw.clone().addScaledVector(up, 0.25 - 0.12 * a).addScaledVector(bodyR, -0.22).addScaledVector(bodyF, 0.18); }
  if (A.fall > 0) { tgt.r = _hw.clone().addScaledVector(up, 0.4).addScaledVector(bodyR, 0.2); tgt.l = _hw.clone().addScaledVector(up, 0.4).addScaledVector(bodyR, -0.2); }
  if (A.push) { const k = 0.07 * Math.sin(T * 8); tgt.r = _hw.clone().add(V(-0.3, 0.1 + k, -0.04)); tgt.l = _hw.clone().add(V(0.3, 0.1 - k, -0.04)); }
  if (A.hang) { tgt.r = _hw.clone().add(V(0.12, -0.3, 0.12)); tgt.l = _hw.clone().add(V(-0.08, -0.3, -0.1)); }
  for (const [s, w] of [['r', tgt.r], ['l', tgt.l]]) if (w) Object.assign(pose, { [s + 'W']: 1, [s + 'wx']: w.x, [s + 'wy']: w.y, [s + 'wz']: w.z, [s + 'Curl']: A.push ? 0.2 : 0.6 });
  if (tgt.r || tgt.l) { HERO.setPose(pose, h.face, h.lookP, T); for (const [s, w, b] of [['r', tgt.r, 'rHand'], ['l', tgt.l, 'lHand']]) if (w) { const e = w.clone().sub(boneW(HERO, b)); pose[s + 'wx'] += e.x; pose[s + 'wy'] += e.y; pose[s + 'wz'] += e.z; } HERO.setPose(pose, h.face, h.lookP, T); }
  HERO.headWorld(_hw); HERO.root.visible = h.vis && (!h.inside || inside) && camera.position.distanceTo(_hw) > 0.2;
  if (BLOCKY) { HERO.root.visible = false; poseBlocky(T, h); BK.g.visible = h.vis && (!h.inside || inside) && camera.position.distanceTo(_hw) > 0.25; }
  // téléphone : dans la main, puis il tombe dans la fente, puis il éclaire le fond de la patte
  if (BLOCKY && T < 2.45) { BK.handR.getWorldPosition(phone.position); const q = BK.rArm.getWorldQuaternion(new THREE.Quaternion()); phone.quaternion.copy(q).multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(Math.PI / 2, Math.PI, 0))); phone.visible = true; }
  else if (T < 2.45) { const P = palmIn(HERO, 'R'); const n = _hw.clone().sub(P.c).normalize(); const yv = V(0, 1, 0).addScaledVector(n, -n.y).normalize(); const xv = new THREE.Vector3().crossVectors(yv, n);
    phone.position.copy(P.c).addScaledVector(n, 0.02).addScaledVector(yv, 0.03); phone.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(xv, yv, n)); phone.visible = true; }
  else if (T < 3.0) { const u = ss(2.45, 2.95, T); const a = phone.userData.a || phone.position.clone(); phone.userData.a = a; phone.position.copy(a.clone().lerp(SLOTP.clone().add(V(0, -0.35, 0)), u)).add(V(0, 0.18 * Math.sin(u * Math.PI), 0)); phone.rotation.set(u * 4.5, u * 1.3, u * 2.1); phone.visible = true; }
  else { phone.position.copy(PHONE_DOWN); phone.rotation.set(-Math.PI / 2 + 0.25, 0.4, 0); phone.visible = inside; }
  phoneL.position.copy(phone.position).add(V(0, 0.25, 0.05)); phoneL.intensity = inside && T < 21.3 ? 3.0 : inside ? 0.8 : 0;
  // --- passants, couple, police
  EXTRA.forEach((E, i) => { const [a, b, t0, t1] = EXTRA_PATHS[i]; const vis = T >= DAYS[0] && T < DAYS[1] && T >= t0 && T <= t1; const w = walkPath(a, b, t0, t1, T, 'walk', 2.6); poseHuman(E, { vis, pos: w.pos, yaw: w.yaw, layers: w.layers, face: { raw: {} } }, T); });
  const legMid = V(LEG.knee.x, 1.2, LEG.knee.z);
  for (const [H, st] of [[WOMAN, womanState(T)], [MAN2, man2State(T)]]) {
    if (st.vis === false) { H.root.visible = false; continue; }
    st.lookP = st.look === 'leg' ? legMid : st.look === 'cop' ? V(LEG.foot.x - 0.3, 1.6, LEG.foot.z + 1.2) : st.look === 'away' ? st.pos.clone().add(V(2, 1.5, 2)) : null;
    let layers = st.layers; if (st.call > 0.5) layers = [...IDLEM(T, 0.2), { clip: 'phone_talk', mode: 'abs', t: 6 + (T - 28.6), k: 1, w: { arms: 1, spineAbs: 0.3 } }];
    const p2 = poseHuman(H, { ...st, layers }, T);
    if (st.nose > 0) { const hw = H.headWorld(new THREE.Vector3()); const f = frameOf(st.yaw).f; const n = hw.clone().addScaledVector(f, 0.1).add(V(0, -0.06, 0)); Object.assign(p2, { rW: st.nose, rwx: n.x, rwy: n.y, rwz: n.z, rCurl: 0.4 }); H.setPose(p2, st.face, st.lookP, T); }
    if (H === WOMAN) { H._phone = st.call; }
  }
  // téléphone de la femme (main droite, monte à l'oreille avec le mouvement réel)
  if (WOMAN.root.visible && WOMAN._phone > 0.3) { const P = palmIn(WOMAN, 'R'); wphone.visible = true; wphone.position.copy(P.c).addScaledVector(P.n, 0.02); wphone.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(new THREE.Vector3().crossVectors(P.fd, P.n), P.fd, P.n)); } else wphone.visible = false;
  for (const [H, i] of [[COP1, 0], [COP2, 1]]) {
    const st = copState(T, i); if (st.vis === false) { H.root.visible = false; continue; }
    st.lookP = st.look === 'legMid' ? legMid : null; const p3 = poseHuman(H, st, T);
    if (st.torch > 0) { const hw = H.headWorld(new THREE.Vector3()); const f = frameOf(st.yaw); const w = hw.clone().add(V(0, -0.35, 0)).addScaledVector(f.f, 0.45).addScaledVector(f.r, 0.12); Object.assign(p3, { rW: st.torch, rwx: w.x, rwy: w.y, rwz: w.z, rCurl: 0.9 }); H.setPose(p3, st.face, st.lookP, T); }
    if (i === 0) { torch.visible = st.torch > 0.1; if (torch.visible) { const P = palmIn(H, 'R'); torch.position.copy(P.c).addScaledVector(P.n, 0.02); torch.lookAt(legMid); torchL.position.copy(torch.position); torchL.target.position.copy(legMid); torchL.intensity = 40 * st.torch; } else torchL.intensity = 0; }
  }
  if (T < 29.85) { torch.visible = false; torchL.intensity = 0; }
  // brume verte (odeur) au pied de la patte
  const hz = ss(25.2, 26.2, T) * (T < 33 ? 1 : 0);
  HAZE.forEach((sp) => { const d = sp.userData; const ph = (T * 0.25 + d.ph) % 1; sp.position.set(LEG.foot.x + d.x, 0.2 + ph * 1.6, LEG.foot.z + 0.3 + d.z); sp.scale.setScalar(d.s * (0.6 + ph)); sp.material.opacity = hz * 0.22 * Math.sin(ph * Math.PI) * Math.min(1, Math.max(0, (camera.position.distanceTo(sp.position) - 0.6) / 1.6)); });
  // mémorial
  memorial.visible = T >= 33.0; candleL.intensity = T >= 33.0 ? 6 * (1 + 0.15 * Math.sin(T * 23)) : 0;
  // lumière d'appoint sur ce que regarde la caméra
  fillL.position.copy(camera.position).add(V(0, 0.3, 0)); fillL.target.position.copy(c.tgt); fillL.intensity = (inside ? 0.7 : 0.8) * Math.max(1, (camera.position.distanceTo(c.tgt) / 1.5) ** 2) * (night > 0.6 && !inside ? 0.4 : 1);
  // tremblement de caméra à la chute
  if (inR(T, 13.9, 14.5)) camera.position.add(V(Math.sin(T * 61) * 0.03, Math.sin(T * 47) * 0.03, 0));
  const w2 = innerWidth, h2 = innerHeight; if (canvas.width !== w2) renderer.setSize(w2, h2, false);
  camera.aspect = w2 / h2; camera.updateProjectionMatrix(); renderer.render(scene, camera);
}
const wphone = new THREE.Group(); scene.add(wphone); box(0.072, 0.15, 0.009, M({ color: '#d9d4cc', roughness: 0.3, metalness: 0.5 }), 0, 0, 0, wphone, false);
function mix(a, b, u) { const r = {}; for (const k of new Set([...Object.keys(a.raw || {}), ...Object.keys(b.raw || {})])) r[k] = lerp((a.raw || {})[k] || 0, (b.raw || {})[k] || 0, u); return { maxM: Math.max(a.maxM || 1, b.maxM || 1), raw: r }; }
window.renderAt = (T) => {
  if (Q.get('cam')) { frame(+Q.get('T') || T); const c = Q.get('cam').split(',').map(Number); camera.position.set(c[0], c[1], c[2]); camera.lookAt(c[3], c[4], c[5]); camera.fov = +(Q.get('fov') || 40); camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight, false); renderer.render(scene, camera); return; }
  frame(T);
};
window.dbg = (T) => { frame(T); const r = (v) => [v.x, v.y, v.z].map(x => +x.toFixed(2)); return { cam: r(camera.position), tgt: r(camera.getWorldDirection(new THREE.Vector3())), hero: r(_hw), woman: r(WOMAN.root.position), man2: r(MAN2.root.position), wv: WOMAN.root.visible, near: r(NEAR) }; };
window.READY = true;
if (!MANUAL) { const c0 = performance.now(); const loop = () => { frame(((performance.now() - c0) / 1000) % END); requestAnimationFrame(loop); }; loop(); } else frame(0);
