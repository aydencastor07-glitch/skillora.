import * as THREE from 'three';
import { Path, buildWorld, HOLE } from './world.js';
import { Story, SHOTS, T } from './story.js';
import { Hero } from './hero.js';
import { Wolf } from './wolf.js';
import { CineCam } from './camera.js';
import { Dust, Rain, DizzyStars, makeBam, makeOverlay } from './fx.js';
import { sstep, bump, lerp } from './util.js';

// Police BD pour le "BAM!" (on n'attend pas plus d'1,5 s)
try {
  await Promise.race([document.fonts.load('128px "Bangers"'), new Promise((r) => setTimeout(r, 1500))]);
} catch (e) { /* police de secours */ }

// ---------- Rendu ----------
const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(1);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.autoClear = false;

const scene = new THREE.Scene();
const SKY = new THREE.Color(0xdde4b8), SKY_RAIN = new THREE.Color(0x8e9a98);
scene.background = SKY.clone();
scene.fog = new THREE.Fog(SKY.clone(), 30, 120);

const hemi = new THREE.HemisphereLight(0xfaf6d8, 0x5d6e3f, 1.6);
scene.add(hemi);
const sun = new THREE.DirectionalLight(0xfff3d6, 2.4);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
Object.assign(sun.shadow.camera, { left: -22, right: 22, top: 22, bottom: -22, near: 1, far: 80 });
sun.shadow.bias = -0.0006;
sun.shadow.normalBias = 0.02;
scene.add(sun, sun.target);

const camera = new THREE.PerspectiveCamera(55, 9 / 16, 0.1, 400);

// ---------- Monde + acteurs ----------
const path = new Path();
const story = new Story(path);
buildWorld(scene, path, { C: story.C, Sc: story.Sc, Sh: story.Sh, hole: story.H });

const hero = new Hero();
scene.add(hero.root);
const wolves = [];
for (let i = 0; i < 5; i++) {
  const w = new Wolf(i);
  scene.add(w.root);
  wolves.push(w);
}

const dust = new Dust(scene);
const rain = new Rain(scene);
const stars = new DizzyStars(scene);
const bam = makeBam(scene);
const overlay = makeOverlay();

// Position du bâton au sol / en main
const stickGround = new THREE.Object3D();
stickGround.position.set(story.stickGround.x, 0.07, story.stickGround.z);
stickGround.rotation.set(0, story.stickGround.yaw, Math.PI / 2);
function placeStick(inHand) {
  const st = hero.stick;
  if (inHand) {
    if (st.parent !== hero.rArm.hand) hero.rArm.hand.add(st);
    st.position.set(0, 0.02, 0);
    st.rotation.set(-1.35, 0, 0);
  } else {
    if (st.parent !== scene) scene.add(st);
    st.position.copy(stickGround.position);
    st.rotation.copy(stickGround.rotation);
  }
}

// ---------- Cibles de la caméra ----------
const cur = { hero: {}, w: [{}, {}, {}, {}, {}], s: 0 };
const headV = new THREE.Vector3();
function focus(name) {
  const h = cur.hero, H = story.H;
  switch (name) {
    case 'hero': return { x: h.x, y: h.y + 1.3, z: h.z, yaw: h.yaw };
    case 'heroFall': return { x: h.x, y: h.y + 1.0, z: h.z, yaw: h.yaw };
    case 'heroHead': hero.headWorld(headV); return { x: headV.x, y: headV.y, z: headV.z, yaw: h.yaw };
    case 'lead': { const w = cur.w[1]; return { x: w.x, y: w.y + 0.9, z: w.z, yaw: w.yaw }; }
    case 'pack':
    case 'mid': {
      let x = 0, z = 0, n = 0;
      cur.w.forEach((w, i) => {
        if (i === 1 && cur.s > T.lunge) return;
        x += w.x; z += w.z; n++;
      });
      x /= n; z /= n;
      if (name === 'mid') return { x: (x + h.x) / 2, y: 1.0, z: (z + h.z) / 2, yaw: h.yaw };
      return { x, y: 0.9, z, yaw: h.yaw };
    }
    case 'C': return { x: story.C.x, y: 1.0, z: story.C.z, yaw: story.C.yaw };
    case 'impact': return story.impact;
    case 'hole': return { x: H.x, y: 0, z: H.z, yaw: H.yaw };
    case 'bottom': return { x: H.x, y: -4.4, z: H.z, yaw: H.yaw };
    case 'opening': return { x: H.x, y: 0.9, z: H.z, yaw: H.yaw };
  }
  return { x: 0, y: 0, z: 0, yaw: 0 };
}
const cine = new CineCam(story, SHOTS, focus);
const REAL_END = story.REAL_END;
const realHit = story.realOf(T.hit), realLand = story.realOf(T.bottom);

// ---------- Format de sortie ----------
const FORMATS = { '9:16': [9, 16], '16:9': [16, 9], '1:1': [1, 1] };
let format = '9:16', quality = 720, W = 720, H = 1280;
function applySize() {
  const [a, b] = FORMATS[format];
  if (a < b) { W = quality; H = Math.round((quality * b) / a); }
  else if (a > b) { H = quality; W = Math.round((quality * a) / b); }
  else { W = H = quality; }
  W -= W % 2; H -= H % 2;
  renderer.setSize(W, H, false);
  camera.aspect = W / H;
  overlay.mat.uniforms.uAspect.value = W / H;
  fit();
}
function fit() {
  const stage = document.getElementById('stage');
  const r = stage.getBoundingClientRect();
  const sc = Math.min(r.width / W, r.height / H);
  canvas.style.width = `${Math.floor(W * sc)}px`;
  canvas.style.height = `${Math.floor(H * sc)}px`;
}
window.addEventListener('resize', fit);

// ---------- Une image ----------
const tmpV = new THREE.Vector3();
function frame(treal) {
  const s = story.storyOf(treal);
  cur.s = s;

  // Héros
  const h = story.hero.sample(s, cur.hero);
  hero.root.position.set(h.x, h.y, h.z);
  hero.root.rotation.y = h.yaw;
  hero.setPose(story.heroPose(s));
  hero.setFace(story.heroFace(s));
  placeStick(s >= T.grab);

  // Loups
  const vis = [true];
  wolves.forEach((wolf, i) => {
    const w = story.wolves[i].sample(s, cur.w[i]);
    wolf.root.position.set(w.x, w.y, w.z);
    wolf.root.rotation.y = w.yaw;
    wolf.setPose(story.wolfPose(i, s).p);
    wolf.root.visible = story.wolfVisible(i, s);
    vis.push(wolf.root.visible);
  });
  scene.updateMatrixWorld();

  // Caméra
  cine.update(treal);
  const shake = 0.025 + 0.35 * (treal > realHit ? Math.exp(-(treal - realHit) * 3.5) : 0) +
    0.3 * (treal > realLand ? Math.exp(-(treal - realLand) * 5) : 0);
  const n1 = Math.sin(treal * 7.1) + Math.sin(treal * 13.7) * 0.5;
  const n2 = Math.sin(treal * 8.3 + 1) + Math.sin(treal * 17.9) * 0.5;
  camera.position.copy(cine.pos);
  camera.position.x += n1 * shake * 0.5;
  camera.position.y += n2 * shake * 0.5;
  const inHole = Math.hypot(camera.position.x - HOLE.x, camera.position.z - HOLE.z) < HOLE.r - 0.2;
  camera.position.y = Math.max(camera.position.y, inHole ? -4.75 : 0.35);
  tmpV.copy(cine.look);
  tmpV.x += n2 * shake * 0.2;
  tmpV.y += n1 * shake * 0.2;
  camera.lookAt(tmpV);
  const k = camera.aspect < 0.8 ? 1.4 : camera.aspect < 1.2 ? 1.15 : 1;
  camera.fov = (2 * Math.atan(Math.tan((cine.fov * Math.PI) / 360) * k) * 180) / Math.PI;
  camera.updateProjectionMatrix();

  // Météo
  const dark = story.dark(s);
  scene.background.copy(SKY).lerp(SKY_RAIN, dark);
  scene.fog.color.copy(scene.background);
  scene.fog.far = lerp(120, 70, dark);
  scene.fog.near = lerp(30, 12, dark);
  hemi.intensity = lerp(1.6, 1.15, dark);
  sun.intensity = lerp(2.4, 0.9, dark);
  sun.position.set(tmpV.x - 14, tmpV.y + 26, tmpV.z + 10);
  sun.target.position.copy(tmpV);

  // Effets
  dust.update(s, [story.hero, ...story.wolves], vis);
  rain.update(s, story.rain(s), camera.position);
  hero.headWorld(headV);
  stars.update(s, headV, bump(T.bottom + 0.1, T.bottom + 0.5, 54.8, 55.5, s), camera.position);
  const bs = sstep(T.hit, T.hit + 0.05, s) * (1 - sstep(30.55, 30.8, s));
  bam.visible = bs > 0.01;
  bam.position.set(story.impact.x, story.impact.y + 1.45, story.impact.z);
  bam.scale.setScalar(1.6 * bs * (1 + 0.06 * Math.sin(treal * 30)));

  const u = overlay.mat.uniforms;
  u.uTime.value = treal;
  u.uSpeed.value = cine.speedLines * sstep(3, 5, cur.hero.speed);
  u.uFlash.value = treal > realHit ? 0.85 * Math.exp(-(treal - realHit) * 10) : 0;
  u.uFade.value = Math.max(1 - sstep(0, 0.9, treal), sstep(REAL_END - 2.2, REAL_END - 0.3, treal));
  u.uDark.value = dark;

  renderer.clear();
  renderer.render(scene, camera);
  renderer.render(overlay.scene, overlay.cam);
}

// ---------- Lecture / interface ----------
let t = 0, playing = true, last = performance.now(), recorder = null;
const $ = (id) => document.getElementById(id);
const scrub = $('scrub');
scrub.max = REAL_END.toFixed(2);
const fmt = (x) => `${Math.floor(x / 60)}:${String(Math.floor(x % 60)).padStart(2, '0')}.${Math.floor((x % 1) * 10)}`;

// Découpage (pour écrire la voix off)
const beats = $('beats');
SHOTS.filter((k) => k.label).forEach((k) => {
  const li = document.createElement('li');
  const rt = story.realOf(k.t);
  li.innerHTML = `<b>${fmt(rt)}</b><span>${k.label}</span>`;
  li.onclick = () => seek(rt);
  li.dataset.t = rt;
  beats.appendChild(li);
});

function setPlaying(p) {
  playing = p;
  $('play').textContent = p ? '❚❚' : '▶';
}
function seek(x) {
  t = Math.max(0, Math.min(REAL_END, x));
  frame(t);
  updateUI();
}
function updateUI() {
  scrub.value = t;
  $('time').textContent = `${fmt(t)} / ${fmt(REAL_END)}`;
  for (const li of beats.children) li.classList.toggle('on', +li.dataset.t <= t + 0.01);
  const on = [...beats.children].filter((li) => +li.dataset.t <= t + 0.01);
  for (const li of beats.children) li.classList.remove('cur');
  if (on.length) on[on.length - 1].classList.add('cur');
}

$('play').onclick = () => {
  if (t >= REAL_END) t = 0;
  setPlaying(!playing);
};
$('restart').onclick = () => { seek(0); setPlaying(true); };
scrub.oninput = () => { if (!recorder) seek(+scrub.value); };
$('format').onchange = (e) => { format = e.target.value; applySize(); frame(t); };
$('quality').onchange = (e) => { quality = +e.target.value; applySize(); frame(t); };
$('hide').onclick = () => document.body.classList.toggle('clean');
window.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'SELECT') return;
  if (e.code === 'Space') { e.preventDefault(); $('play').click(); }
  if (e.key === 'h' || e.key === 'H') document.body.classList.toggle('clean');
  if (e.key === 'ArrowRight' && !recorder) seek(t + 1);
  if (e.key === 'ArrowLeft' && !recorder) seek(t - 1);
});

// Enregistrement vidéo direct depuis le canvas
function pickMime() {
  const c = ['video/mp4;codecs=avc1.640028', 'video/mp4', 'video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm'];
  return c.find((m) => window.MediaRecorder && MediaRecorder.isTypeSupported(m));
}
$('rec').onclick = () => {
  if (recorder) { recorder.stop(); return; }
  const mime = pickMime();
  if (!mime) { alert("Votre navigateur ne permet pas l'enregistrement vidéo. Essayez Chrome ou Edge."); return; }
  const stream = canvas.captureStream(60);
  const chunks = [];
  recorder = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: quality >= 1080 ? 16e6 : 10e6 });
  recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  recorder.onstop = () => {
    const blob = new Blob(chunks, { type: mime });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `chasse-aux-loups-${format.replace(':', 'x')}.${mime.includes('mp4') ? 'mp4' : 'webm'}`;
    a.click();
    recorder = null;
    document.body.classList.remove('recording');
    $('rec').textContent = '● Enregistrer la vidéo';
  };
  seek(0);
  recorder.start(250);
  document.body.classList.add('recording');
  $('rec').textContent = '■ Arrêter';
  setPlaying(true);
};

function loop(now) {
  const dt = Math.min(0.1, (now - last) / 1000);
  last = now;
  if (playing) {
    t += dt;
    if (t >= REAL_END) {
      t = REAL_END;
      setPlaying(false);
      if (recorder) setTimeout(() => recorder && recorder.stop(), 300);
    }
    frame(t);
    updateUI();
  }
  requestAnimationFrame(loop);
}

// Paramètres d'URL : ?t=12.5&pause=1&format=16:9
const q = new URLSearchParams(location.search);
if (q.get('format') && FORMATS[q.get('format')]) { format = q.get('format'); $('format').value = format; }
if (q.get('quality')) { quality = +q.get('quality'); $('quality').value = String(quality); }
applySize();
if (q.get('pause')) setPlaying(false);
seek(q.get('t') ? +q.get('t') : 0);
window.seek = seek;
window.cine = { story, REAL_END };
document.body.classList.add('ready');
requestAnimationFrame((n) => { last = n; loop(n); });
