// Test d'un acteur créé avec Tripo3D (squelette Mixamo) : vrais mouvements
// (motion capture CMU) dans le décor du tribunal, caméra qui tourne autour.
import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { RealHuman } from './rig.js';
import { buildCourt } from './court.js';

const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(2, devicePixelRatio));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.95;

const scene = new THREE.Scene();
scene.background = new THREE.Color('#d8d2c6');
scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = 0.45;
scene.add(new THREE.HemisphereLight('#fff6ea', '#7d6248', 0.55));
const sun = new THREE.DirectionalLight('#ffe8c8', 2.1);
sun.position.set(11, 8, 1.5);
sun.target.position.set(-1, 0, -4);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
Object.assign(sun.shadow.camera, { left: -12, right: 12, top: 12, bottom: -12, near: 1, far: 40 });
sun.shadow.bias = -0.0004;
sun.shadow.normalBias = 0.02;
scene.add(sun, sun.target);
for (const [x, z] of [[-4, -2.5], [0, -2.5], [4, -2.5], [0, 2]]) {
  const l = new THREE.PointLight('#ffe6c4', 5.5, 9, 2);
  l.position.set(x, 3.4, z);
  scene.add(l);
}
const fill = new THREE.DirectionalLight('#fff1e0', 1.1);
fill.position.set(0, 3, 6);
fill.target.position.set(0, 1, -2);
scene.add(fill, fill.target);
buildCourt(scene);

const camera = new THREE.PerspectiveCamera(32, 1, 0.03, 80);
const CLIP = { idle: 18, explain: 8, angry: 11, facepalm: 5.5, cry: 6.5, walk: 0.93 };
const loopT = (c, x) => ((x % CLIP[c]) + CLIP[c]) % CLIP[c];
const FULL = { pelvis: 1, spineAbs: 1, legs: 1, arms: 1, root: 1 };
const BODY = { pelvis: 1, spineAbs: 1, legs: 1, root: 1 };
const ACTS = [
  ['Debout', 'idle', BODY, {}],
  ['Explique', 'explain', FULL, { open: 0.3 }],
  ['En colère', 'angry', FULL, {}],
  ['Désespéré', 'facepalm', FULL, {}],
  ['Pleure', 'cry', FULL, {}],
  ['Marche', 'walk', FULL, {}],
];
let act = 0, t0 = 0;
const ui = document.getElementById('ui');
ACTS.forEach(([label], i) => {
  const b = document.createElement('button');
  b.textContent = label;
  b.onclick = () => { act = i; t0 = clock.getElapsedTime(); [...ui.children].forEach((x, j) => x.classList.toggle('on', j === i)); };
  if (!i) b.classList.add('on');
  ui.appendChild(b);
});

await RealHuman.loadClips(['idle', 'explain', 'angry', 'facepalm', 'cry', 'walk'], './mocap/');
const H = await RealHuman.create('./models/acteur1.glb', { heightM: 1.8 });
scene.add(H.root);
window.ACTEUR = H;
// pilotage externe (rendu vidéo image par image)
window.setAct = (i, at) => { act = i; t0 = at; [...ui.children].forEach((x, j) => x.classList.toggle('on', j === i)); };
document.body.classList.add('ready');

const clock = new THREE.Clock();
const C = new THREE.Vector3(0, 0, -1.6);
function frame() {
  const T = window.T_OVERRIDE ?? clock.getElapsedTime(), t = T - t0;
  const [, clip, w] = ACTS[act];
  let x = C.x, z = C.z, yaw = 0.25 * Math.sin(T * 0.2);
  if (clip === 'walk') {
    // tour en cercle à vitesse de marche réelle (0,78 m/s)
    const a = (t * 0.78) / 1.3;
    x = C.x + Math.sin(a) * 1.3; z = C.z + Math.cos(a) * 1.3 - 1.3;
    yaw = a + Math.PI / 2;
  }
  H.root.position.set(x, 0, z);
  H.root.rotation.y = yaw;
  H.setPose({ mo: [{ clip, mode: 'abs', t: loopT(clip, t), k: 1, w }] }, {}, null, T);
  // caméra : lent travelling autour de l'acteur
  const az = 0.5 * Math.sin(T * 0.15), d = clip === 'walk' ? 6 : 3.4;
  const tgt = new THREE.Vector3(clip === 'walk' ? C.x : x, 1.0, clip === 'walk' ? C.z - 1.3 : z);
  camera.position.set(tgt.x + Math.sin(az) * d, 1.45, tgt.z + Math.cos(az) * d);
  camera.lookAt(tgt);
  const w2 = innerWidth, h2 = innerHeight;
  if (canvas.width !== Math.floor(w2 * renderer.getPixelRatio())) renderer.setSize(w2, h2, false);
  camera.aspect = w2 / h2;
  camera.fov = w2 < h2 ? 46 : 32;
  camera.updateProjectionMatrix();
  renderer.render(scene, camera);
  if (!MANUAL) requestAnimationFrame(frame);
}
// ?manual : une image à la demande (rendu vidéo)
const MANUAL = new URLSearchParams(location.search).has('manual');
window.renderAt = (T) => { window.T_OVERRIDE = T; frame(); };
frame();
