// Lecture d'une animation faite dans Tripo3D (Animate) sur le personnage,
// dans le décor du tribunal, avec une caméra qui le suit puis finit en gros plan.
// ?m=<modèle>&a=<n° animation>&manual (rendu image par image pour la vidéo)
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { buildCourt } from './court.js';

const Q = new URLSearchParams(location.search);
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
for (const [x, z] of [[-4, -7], [0, -7], [4, -7], [-4, -2.5], [0, -2.5], [4, -2.5], [0, 2]]) {
  const l = new THREE.PointLight('#ffe6c4', 5.5, 9, 2);
  l.position.set(x, 3.4, z);
  scene.add(l);
}
// lumière de face douce sur le visage
const key = new THREE.SpotLight('#fff3e6', 16, 14, 0.6, 0.8, 1.5);
key.position.set(1.2, 2.8, 0.5); key.target.position.set(0, 1.4, -4);
scene.add(key, key.target);
buildCourt(scene);

const camera = new THREE.PerspectiveCamera(40, 9 / 16, 0.03, 80);
const ui = document.getElementById('ui');
ui.style.display = 'none';

const gltf = await new GLTFLoader().loadAsync(`./models/${Q.get('m') || 'acteur2'}.glb`);
const model = gltf.scene;
model.traverse((n) => {
  if (n.isMesh) { n.castShadow = true; n.receiveShadow = true; n.frustumCulled = false; if (n.material.map) n.material.map.anisotropy = 8; }
});
// taille réelle (garçon ~1,72 m) ; départ au fond de l'allée, il marche vers la caméra (+Z)
const size = new THREE.Box3().setFromObject(model).getSize(new THREE.Vector3());
const holder = new THREE.Group();
holder.scale.setScalar((+Q.get('h') || 1.72) / size.y);
holder.position.set(0, 0, -7.2);
holder.add(model);
scene.add(holder);
const mixer = new THREE.AnimationMixer(model);
const clip = gltf.animations[+(Q.get('a') ?? gltf.animations.length - 1)] || gltf.animations[0];
const action = mixer.clipAction(clip);
action.setLoop(THREE.LoopOnce); action.clampWhenFinished = true; action.play();
export const DUR = clip.duration + 2.5; // + gros plan final
window.DUR = DUR;
let head = null;
model.traverse((n) => { if (/Head$/.test(n.name)) head = n; });
// orientation de la tête au repos (face à +Z) pour savoir où il regarde
model.updateMatrixWorld(true);
const headRest = head.getWorldQuaternion(new THREE.Quaternion()).invert();
const face = new THREE.Vector3(), _q = new THREE.Quaternion();
document.body.classList.add('ready');

const ss = (a, b, x) => { const u = Math.min(1, Math.max(0, (x - a) / (b - a))); return u * u * (3 - 2 * u); };
const lerp = (a, b, u) => a + (b - a) * u;
const hv = new THREE.Vector3(), camPos = new THREE.Vector3(), camTgt = new THREE.Vector3();
const clock = new THREE.Clock();
const MANUAL = Q.has('manual');
function frame() {
  const T = window.T_OVERRIDE ?? clock.getElapsedTime() % DUR;
  mixer.setTime(Math.min(T, clip.duration - 0.001));
  model.updateMatrixWorld(true);
  head.getWorldPosition(hv);
  const D = clip.duration;
  // caméra « portée » devant lui : plan large qui se resserre, puis gros plan sur le visage
  const u = ss(0, D - 1.5, T), c = ss(D - 1.5, D + 1.2, T);
  const body = new THREE.Vector3(hv.x, lerp(hv.y - 0.55, hv.y - 0.25, u), hv.z);
  const dist = lerp(lerp(4.6, 2.0, u), 0.62, c);
  const tgt = body.lerp(hv.clone().add(new THREE.Vector3(0, 0.02, 0)), c);
  // direction du visage (à plat) : en gros plan la caméra se met en face de lui
  face.set(0, 0, 1).applyQuaternion(head.getWorldQuaternion(_q).multiply(headRest));
  face.y = 0; face.normalize();
  const az = Math.atan2(face.x, face.z) * c + (1 - c) * Math.atan2(0.45, dist);
  const pos = new THREE.Vector3(tgt.x + Math.sin(az) * dist, lerp(1.55, hv.y + 0.07, c), tgt.z + Math.cos(az) * dist);
  const k = T < 0.05 ? 1 : 0.22;
  camPos.lerp(pos, k); camTgt.lerp(tgt, k);
  camera.position.copy(camPos).add(new THREE.Vector3(Math.sin(T * 1.3) * 0.006, Math.sin(T * 1.7) * 0.005, 0));
  camera.lookAt(camTgt);
  const w = innerWidth, h = innerHeight;
  if (canvas.width !== Math.floor(w * renderer.getPixelRatio())) renderer.setSize(w, h, false);
  camera.aspect = w / h; camera.fov = w < h ? 40 : 30; camera.updateProjectionMatrix();
  renderer.render(scene, camera);
  if (!MANUAL) requestAnimationFrame(frame);
}
window.renderAt = (T) => { window.T_OVERRIDE = T; frame(); };
frame();
