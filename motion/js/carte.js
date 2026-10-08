// Motion design « carte 3D » : vue d'en haut, la caméra plonge vers un pays,
// une ligne lumineuse trace sa frontière, le pays se soulève, nom + capitale.
// ?pays=FRA  &manual (rendu image par image pour la vidéo)
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { Line2 } from 'three/addons/lines/Line2.js';
import { LineGeometry } from 'three/addons/lines/LineGeometry.js';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';

const Q = new URLSearchParams(location.search);
const ISO = Q.get('pays') || 'FRA';
const DUR = 14;
window.DUR = DUR;

// ---------- Rendu ----------
const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(1);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
const scene = new THREE.Scene();
scene.background = new THREE.Color('#04070d');
scene.fog = new THREE.Fog('#04070d', 60, 140);
const camera = new THREE.PerspectiveCamera(40, 9 / 16, 0.1, 200);

scene.add(new THREE.HemisphereLight('#9fb6ff', '#0a0f1c', 0.9));
const sun = new THREE.DirectionalLight('#ffffff', 2.2);
sun.position.set(-8, 20, 10);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
Object.assign(sun.shadow.camera, { left: -15, right: 15, top: 15, bottom: -15, near: 1, far: 60 });
scene.add(sun);

// ---------- Données ----------
await document.fonts.load('900 100px Montserrat');
const D = await (await fetch(`./data/${ISO}.json`)).json();
const [bx, by] = D.area_box;
const lon0 = (bx[0] + bx[1]) / 2, lat0 = (by[0] + by[1]) / 2;
const K = 10 / Math.max((bx[1] - bx[0]) * Math.cos((lat0 * Math.PI) / 180), by[1] - by[0]); // pays ≈ 10 unités
const P = ([lon, lat]) => new THREE.Vector2((lon - lon0) * Math.cos((lat0 * Math.PI) / 180) * K, (lat - lat0) * K);
const toShape = (ring) => new THREE.Shape(ring.map(P));

// Océan : grille de points discrète
{
  const g = new THREE.PlaneGeometry(260, 260);
  const m = new THREE.ShaderMaterial({
    uniforms: { uFog: { value: new THREE.Color('#04070d') } },
    vertexShader: 'varying vec3 vP; void main(){ vP = (modelMatrix*vec4(position,1.)).xyz; gl_Position = projectionMatrix*viewMatrix*vec4(vP,1.); }',
    fragmentShader: `varying vec3 vP; uniform vec3 uFog;
      void main(){ vec2 c = fract(vP.xz*1.25)-.5; float d = smoothstep(.07,.03,length(c));
        vec3 col = mix(vec3(.025,.045,.085), vec3(.12,.2,.36), d*.55);
        float f = smoothstep(40.,95.,length(vP.xz)); gl_FragColor = vec4(mix(col,uFog,f),1.); }`,
  });
  const o = new THREE.Mesh(g, m);
  o.rotation.x = -Math.PI / 2;
  o.position.y = -0.02;
  scene.add(o);
}
// Pays voisins : plats, sombres, frontières fines
const landMat = new THREE.MeshStandardMaterial({ color: '#1a2436', roughness: 0.9 });
const borderMat = new THREE.LineBasicMaterial({ color: '#3c5070', transparent: true, opacity: 0.8 });
const others = new THREE.Group();
for (const r of D.others) {
  const m = new THREE.Mesh(new THREE.ShapeGeometry(toShape(r)), landMat);
  m.rotation.x = -Math.PI / 2; m.receiveShadow = true;
  others.add(m);
  const pts = r.map((p) => { const v = P(p); return new THREE.Vector3(v.x, 0.01, -v.y); });
  others.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), borderMat));
}
scene.add(others);

// Pays cible : relief extrudé avec le drapeau sur le dessus
const DEPTH = 0.7;
const flag = document.createElement('canvas');
flag.width = 512; flag.height = 512;
const FLAG = ISO === 'FRA' ? ['#1f3f9a', '#f4f1ea', '#d8282b'] : ['#3a7bff', '#f4f1ea', '#3a7bff'];
let flagFill = -1;
function drawFlag(u) {
  if (Math.abs(u - flagFill) < 0.002) return;
  flagFill = u;
  const g = flag.getContext('2d');
  g.fillStyle = '#26324a'; g.fillRect(0, 0, 512, 512);
  g.save(); g.beginPath(); g.rect(0, 0, 512 * u, 512); g.clip();
  FLAG.forEach((c, i) => { g.fillStyle = c; g.fillRect((i * 512) / 3, 0, 512 / 3 + 1, 512); });
  g.restore();
  if (u > 0 && u < 1) { g.fillStyle = 'rgba(255,230,160,0.9)'; g.fillRect(512 * u - 3, 0, 6, 512); }
  if (flagTex) flagTex.needsUpdate = true;
}
let flagTex = null;
drawFlag(0);
flagTex = new THREE.CanvasTexture(flag);
flagTex.colorSpace = THREE.SRGBColorSpace;
const target = new THREE.Group();
const tShapes = D.target.map(toShape);
const tgeo = new THREE.ExtrudeGeometry(tShapes, { depth: DEPTH, bevelEnabled: true, bevelThickness: 0.04, bevelSize: 0.04, bevelSegments: 2 });
// UV du dessus : position dans la boîte du pays -> drapeau
{
  tgeo.computeBoundingBox();
  const bb = tgeo.boundingBox, uv = tgeo.attributes.uv, p = tgeo.attributes.position;
  for (let i = 0; i < uv.count; i++) uv.setXY(i, (p.getX(i) - bb.min.x) / (bb.max.x - bb.min.x), (p.getY(i) - bb.min.y) / (bb.max.y - bb.min.y));
}
const topMat = new THREE.MeshStandardMaterial({ map: flagTex, roughness: 0.55, metalness: 0.05, emissive: '#ffffff', emissiveMap: flagTex, emissiveIntensity: 0.0 });
const sideMat = new THREE.MeshStandardMaterial({ color: '#0d1626', roughness: 0.6, metalness: 0.2, emissive: '#ffb02e', emissiveIntensity: 0.0 });
const tmesh = new THREE.Mesh(tgeo, [topMat, sideMat]);
tmesh.rotation.x = -Math.PI / 2;
tmesh.castShadow = true; tmesh.receiveShadow = true;
target.add(tmesh);
scene.add(target);

// Ligne lumineuse de frontière (le plus grand contour)
const main = D.target.reduce((a, b) => (b.length > a.length ? b : a));
const linePos = [];
for (const p of main) { const v = P(p); linePos.push(v.x, 0, -v.y); }
const lgeo = new LineGeometry();
lgeo.setPositions(linePos);
const lmat = new LineMaterial({ color: '#ffd04a', linewidth: 5, worldUnits: false, transparent: true, toneMapped: false });
const line = new Line2(lgeo, lmat);
line.computeLineDistances();
scene.add(line);
const NSEG = main.length - 1;
// tête lumineuse qui court le long de la frontière
const headDot = new THREE.Mesh(new THREE.SphereGeometry(0.09, 16, 12), new THREE.MeshBasicMaterial({ color: '#fff4c2', toneMapped: false }));
scene.add(headDot);
const ringPts = main.map((p) => { const v = P(p); return new THREE.Vector3(v.x, 0, -v.y); });

// ---------- Textes (plans face caméra) ----------
function textPlane(lines, w, h) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  const m = new THREE.Mesh(new THREE.PlaneGeometry(1, h / w), new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthTest: false, toneMapped: false }));
  m.renderOrder = 10;
  m.material.color.setScalar(0.8);
  m.userData.draw = (fn) => { const g = c.getContext('2d'); g.clearRect(0, 0, w, h); fn(g, w, h); tex.needsUpdate = true; };
  return m;
}
const title = textPlane(null, 1400, 360);
title.userData.draw((g, w, h) => {
  g.textAlign = 'center'; g.textBaseline = 'middle';
  g.font = '900 230px Montserrat';
  g.lineWidth = 18; g.strokeStyle = '#04070d'; g.strokeText(D.name.toUpperCase(), w / 2, h / 2);
  g.shadowColor = '#ffb02e'; g.shadowBlur = 40; g.fillStyle = '#ffffff'; g.fillText(D.name.toUpperCase(), w / 2, h / 2);
});
scene.add(title);
const sub = textPlane(null, 1400, 200);
scene.add(sub);
const capLabel = textPlane(null, 700, 180);
capLabel.userData.draw((g, w, h) => {
  g.textAlign = 'center'; g.textBaseline = 'middle'; g.font = '800 110px Montserrat';
  g.lineWidth = 14; g.strokeStyle = '#04070d'; g.strokeText(D.capital.name, w / 2, h / 2);
  g.fillStyle = '#ffffff'; g.fillText(D.capital.name, w / 2, h / 2);
});
scene.add(capLabel);
// épingle de la capitale : faisceau + anneau qui pulse
const capV = P(D.capital.lonlat);
const pin = new THREE.Group();
pin.position.set(capV.x, 0, -capV.y);
const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 1, 12), new THREE.MeshBasicMaterial({ color: '#ffb02e', toneMapped: false, transparent: true }));
const ring = new THREE.Mesh(new THREE.RingGeometry(0.18, 0.24, 48), new THREE.MeshBasicMaterial({ color: '#ffd04a', toneMapped: false, transparent: true, side: THREE.DoubleSide }));
ring.rotation.x = -Math.PI / 2;
const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.16, 20, 14), new THREE.MeshBasicMaterial({ color: '#ffd04a', toneMapped: false }));
pin.add(beam, ring, bulb);
scene.add(pin);

// ---------- Post-traitement : halo lumineux ----------
let composer, bloom;
function setSize(w, h) {
  renderer.setSize(w, h, false);
  composer = new EffectComposer(renderer);
  composer.setPixelRatio(1);
  composer.setSize(w, h);
  composer.addPass(new RenderPass(scene, camera));
  bloom = new UnrealBloomPass(new THREE.Vector2(w, h), 0.9, 0.6, 0.82);
  composer.addPass(bloom);
  composer.addPass(new OutputPass());
  lmat.resolution.set(w, h);
}
document.body.classList.add('ready');

// ---------- Chronologie ----------
const ss = (a, b, x) => { const u = Math.min(1, Math.max(0, (x - a) / (b - a))); return u * u * (3 - 2 * u); };
const lerp = (a, b, u) => a + (b - a) * u;
const easeOutBack = (u) => { const c = 1.70158; return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2; };
const fmt = (n) => Math.round(n).toLocaleString('fr-FR');
let lastSub = '';
function update(T) {
  const W = canvas.width, H = canvas.height, portrait = W < H;
  // trace de la frontière 2,5 → 6,5 s
  const tr = ss(2.3, 6.6, T);
  const n = Math.max(0, Math.floor(tr * NSEG));
  lgeo.instanceCount = n;
  headDot.visible = tr > 0 && tr < 1;
  // soulèvement 6,6 → 8 s
  const lift = ss(6.4, 8.0, T);
  target.scale.set(1, 0.04 + 0.96 * lift, 1);
  const topY = (DEPTH + 0.04) * (0.04 + 0.96 * lift) + 0.02;
  line.position.y = topY;
  const hp = ringPts[Math.min(NSEG, n)];
  headDot.position.set(hp.x, topY + 0.02, hp.z);
  drawFlag(ss(7.0, 8.4, T));
  topMat.emissiveIntensity = 0.08 * lift;
  sideMat.emissiveIntensity = 0.35 * lift;
  landMat.color.set('#1a2436').multiplyScalar(lerp(1, 0.6, lift));
  lmat.opacity = 1;
  // caméra : vue d'ensemble -> plongée -> orbite
  const dive = ss(0, 7.2, T), orb = ss(7.5, DUR, T);
  const dist = lerp(78, portrait ? 31 : 19, dive) - orb * 2.5;
  const tilt = lerp(1.45, 1.0, ss(4, 9.5, T));
  const az = lerp(-0.35, 0.0, dive) + orb * 0.3;
  const tgt = new THREE.Vector3(0, 0, lerp(-2, 0, dive));
  camera.position.set(tgt.x + Math.sin(az) * Math.cos(tilt) * dist, Math.sin(tilt) * dist, tgt.z + Math.cos(az) * Math.cos(tilt) * dist);
  camera.lookAt(tgt);
  // titre (8,2 s) qui rebondit, sous-titre compteur (9 s), capitale (10,5 s)
  const ta = ss(8.1, 8.6, T), tb = easeOutBack(Math.min(1, Math.max(0, (T - 8.1) / 0.6)));
    // titre fixé en haut de l'écran (devant la caméra)
  const vh = 2 * 10 * Math.tan((camera.fov * Math.PI) / 360), vw = vh * camera.aspect;
  title.scale.setScalar(Math.min(vw * 0.86, vh * 1.1) * Math.max(0.001, tb));
  title.position.copy(camera.position).add(new THREE.Vector3(0, vh * 0.34, -10).applyQuaternion(camera.quaternion));
  title.quaternion.copy(camera.quaternion);
  title.material.opacity = ta;
  const sa = ss(9.0, 9.4, T);
  sub.scale.setScalar(Math.min(vw * 0.8, vh));
  sub.position.copy(camera.position).add(new THREE.Vector3(0, vh * 0.34 - Math.min(vw * 0.86, vh * 1.1) * 0.2, -10).applyQuaternion(camera.quaternion));
  sub.quaternion.copy(camera.quaternion);
  sub.material.opacity = sa;
  const txt = `${fmt((D.pop || 0) * ss(9.0, 11.0, T))} habitants`;
  if (txt !== lastSub) { lastSub = txt; sub.userData.draw((g, w, h) => { g.textAlign = 'center'; g.textBaseline = 'middle'; g.font = '700 110px Montserrat'; g.lineWidth = 12; g.strokeStyle = '#04070d'; g.strokeText(txt, w / 2, h / 2); g.fillStyle = '#ffd04a'; g.fillText(txt, w / 2, h / 2); }); }
  const ca = ss(10.4, 10.9, T);
  const bh = 2.2 * easeOutBack(Math.min(1, Math.max(0, (T - 10.4) / 0.6)));
  pin.visible = ca > 0;
  pin.position.y = topY;
  beam.scale.y = Math.max(0.001, bh); beam.position.y = bh / 2;
  bulb.position.y = bh;
  const pulse = ((T - 10.4) % 1.2) / 1.2;
  ring.scale.setScalar(1 + pulse * 3); ring.material.opacity = (1 - pulse) * ca;
  capLabel.scale.setScalar(5.5 * ca);
  capLabel.position.set(pin.position.x, topY + bh + 0.9, pin.position.z);
  capLabel.quaternion.copy(camera.quaternion);
  capLabel.material.opacity = ca;
  // fondu d'entrée / sortie
  renderer.toneMappingExposure = ss(0, 0.8, T) * (1 - ss(DUR - 0.5, DUR, T));
}

const MANUAL = Q.has('manual');
const clock = new THREE.Clock();
let size = '';
function frame() {
  const T = window.T_OVERRIDE ?? clock.getElapsedTime() % DUR;
  const w = innerWidth, h = innerHeight;
  if (size !== `${w}x${h}`) { size = `${w}x${h}`; setSize(w, h); }
  camera.aspect = w / h; camera.updateProjectionMatrix();
  update(T);
  composer.render();
  if (!MANUAL) requestAnimationFrame(frame);
}
window.renderAt = (T) => { window.T_OVERRIDE = T; frame(); };
frame();
