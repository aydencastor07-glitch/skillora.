import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { BokehPass } from 'three/addons/postprocessing/BokehPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { RealHuman } from './rig.js';
import { buildCourt } from './court.js';
import { cast, extras, SHOTS, BEATS, T_END, sstep, TABLE_SPK as TSPK } from './story.js';

// ---------- Rendu ----------
const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(1);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.95;
renderer.autoClear = false;

const scene = new THREE.Scene();
scene.background = new THREE.Color('#d8d2c6');
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
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
sun.shadow.radius = 4;
scene.add(sun, sun.target);
for (const [x, z] of [[-4, -7], [0, -7], [4, -7], [-4, -2.5], [0, -2.5], [4, -2.5], [0, 2], [0, 6.5]]) {
  const l = new THREE.PointLight('#ffe6c4', 5.5, 9, 2);
  l.position.set(x, 3.4, z);
  scene.add(l);
}
// lumière de face douce sur les visages (comme un éclairage de plateau)
const fill = new THREE.DirectionalLight('#fff1e0', 0.9);
fill.position.set(0, 4, -12);
fill.target.position.set(0, 1, -3);
scene.add(fill, fill.target);

const camera = new THREE.PerspectiveCamera(40, 9 / 16, 0.03, 80);

// ---------- Décor + personnages ----------
const court = buildCourt(scene);

const loadingEl = document.getElementById('loading');
const P = {};
const EX = [];
{
  const M = (n) => `./models/${n}.glb`;
  // Apparence calée sur la vidéo de référence (cheveux, vêtements)
  const LOOK = {
    dad: { hair: { sample: [0.2, 0.88], color: '#d4581c', loose: true }, clothes: [{ kind: 'hue', h: [185, 250], s: 0.25, color: '#c4c6c4' }], volume: { type: 'curls', color: '#e0621f', puff: 1.12 } },
    kid: { hair: { sample: [0.2, 0.88], color: '#c98a52' }, clothes: [{ kind: 'hue', h: [185, 250], s: 0.25, color: '#cfcfca' }] },
    plaintiff: { hair: { sample: [0.2, 0.88], color: '#d9b27c' }, clothes: [{ kind: 'hue', h: [185, 250], s: 0.1, pattern: 'wax' }], volume: { type: 'bun', color: '#d9b27c' } },
  };
  const main = [['dad', 'dad', { look: LOOK.dad }], ['kid', 'kid', { look: LOOK.kid }], ['plaintiff', 'plaintiff', { look: LOOK.plaintiff }], ['lawyer', 'lawyer', {}], ['judge', 'judge', { glasses: true }]];
  const gal = ['g_Female_Adult_02', 'g_Male_Adult_01', 'g_Female_Adult_05', 'g_Male_Adult_09', 'g_Female_Adult_08', 'g_Male_Adult_04', 'g_Male_Adult_01', 'g_Female_Adult_02', 'g_Male_Adult_09', 'g_Female_Adult_05'];
  let done = 0; const total = main.length + gal.length + 2;
  const tick = () => { done++; if (loadingEl) loadingEl.textContent = `Chargement des personnages… ${Math.round((done / total) * 100)} %`; };
  const jobs = main.map(([k, f, o], i) => RealHuman.create(M(f), { seed: i + 1, ...o }).then((h) => { P[k] = h; tick(); }));
  const galleryPos = [[-5.6, 0], [-3.0, 0], [3.1, 0], [5.4, 1], [-4.6, 1], [2.3, 2], [-2.4, 2], [4.9, 3], [-5.9, 3], [1.8, 4]];
  gal.forEach((f, i) => jobs.push(RealHuman.create(M(f), { seed: 10 + i }).then((h) => {
    const [x, row] = galleryPos[i];
    h.pos = [x, 0, -0.6 + row * 1.45 + 0.05]; h.yaw = Math.PI; h.kind = 'sit'; EX[i] = h; tick();
  })));
  [[5.6, -6.4, -1.15], [6.25, -5.9, -1.25]].forEach(([x, z, yaw], i) => jobs.push(RealHuman.create(M('police'), { seed: 30 + i }).then((h) => {
    h.pos = [x, 0, z]; h.yaw = yaw; h.kind = 'stand'; EX[gal.length + i] = h; tick();
  })));
  await Promise.all(jobs);
  for (const k in P) scene.add(P[k].root);
  for (const h of EX) { h.root.position.set(...h.pos); h.root.rotation.y = h.yaw; scene.add(h.root); }
}

// ---------- Post-traitement : profondeur de champ ----------
let composer, bokeh;
function buildComposer(w, h) {
  composer = new EffectComposer(renderer);
  composer.setPixelRatio(1);
  composer.setSize(w, h);
  composer.addPass(new RenderPass(scene, camera));
  bokeh = new BokehPass(scene, camera, { focus: 1.0, aperture: 0.006, maxblur: 0.012 });
  composer.addPass(bokeh);
  composer.addPass(new OutputPass());
}

// Calque plein écran : vignettage, grain, fondu + sous-titres optionnels
const hud = new THREE.Scene();
const hudCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
const hudMat = new THREE.ShaderMaterial({
  transparent: true, depthTest: false, depthWrite: false,
  uniforms: { uTime: { value: 0 }, uFade: { value: 0 }, uAspect: { value: 1 }, uFlash: { value: 0 } },
  vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }',
  fragmentShader: `varying vec2 vUv; uniform float uTime, uFade, uAspect, uFlash;
    float h2(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233)))*43758.5453); }
    void main(){ vec2 p = vUv*2.0-1.0; p.x *= uAspect; float r = length(p);
      float vig = smoothstep(0.65, 1.75, r) * 0.55;
      float g = (h2(vUv*vec2(1013.0,797.0) + fract(uTime*7.0)) - 0.5) * 0.06;
      float a = clamp(vig + max(g, 0.0) * 0.6, 0.0, 1.0); vec3 c = vec3(0.0);
      a = mix(a, 1.0, uFade); c = mix(c, vec3(0.0), uFade);
      c = mix(c, vec3(1.0), uFlash); a = max(a, uFlash * 0.6);
      gl_FragColor = vec4(c, a); }`,
});
const hudQuad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), hudMat);
hudQuad.frustumCulled = false;
hud.add(hudQuad);
const capCanvas = document.createElement('canvas');
const capTex = new THREE.CanvasTexture(capCanvas);
capTex.colorSpace = THREE.SRGBColorSpace;
const capQuad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.MeshBasicMaterial({ map: capTex, transparent: true, depthTest: false }));
capQuad.frustumCulled = false;
capQuad.renderOrder = 2;
hud.add(capQuad);
let captions = false, capKey = '';
function drawCaption(t) {
  const words = [];
  for (const [a, b, txt] of BEATS) {
    const ws = txt.split(/\s+/);
    ws.forEach((w, i) => words.push([a + ((b - a) * i) / ws.length, w]));
  }
  let cur = '';
  if (captions) for (let i = 0; i < words.length; i++) if (t >= words[i][0] && (i === words.length - 1 || t < words[i + 1][0])) cur = words[i][1];
  if (t > BEATS[BEATS.length - 1][1]) cur = '';
  if (cur === capKey) return;
  capKey = cur;
  const g = capCanvas.getContext('2d');
  g.clearRect(0, 0, capCanvas.width, capCanvas.height);
  if (cur) {
    const s = capCanvas.width / 720;
    g.font = `800 ${Math.round(46 * s)}px Inter, Arial, sans-serif`;
    g.textAlign = 'center'; g.textBaseline = 'middle';
    g.lineWidth = 9 * s; g.strokeStyle = '#000'; g.lineJoin = 'round';
    const y = capCanvas.height * 0.62;
    g.strokeText(cur.replace(/[",.;:]/g, ''), capCanvas.width / 2, y);
    g.fillStyle = '#fff'; g.fillText(cur.replace(/[",.;:]/g, ''), capCanvas.width / 2, y);
  }
  capTex.needsUpdate = true;
}

// ---------- Format ----------
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
  hudMat.uniforms.uAspect.value = W / H;
  capCanvas.width = W; capCanvas.height = H; capKey = '#';
  buildComposer(W, H);
  fit();
}
function fit() {
  const r = document.getElementById('stage').getBoundingClientRect();
  const sc = Math.min(r.width / W, r.height / H);
  canvas.style.width = `${Math.floor(W * sc)}px`;
  canvas.style.height = `${Math.floor(H * sc)}px`;
}
window.addEventListener('resize', fit);

// ---------- Une image ----------
const heads = {};
const tmp = new THREE.Vector3(), tmp2 = new THREE.Vector3(), tmp3 = new THREE.Vector3(), tmp4 = new THREE.Vector3(), tmp5 = new THREE.Vector3(), tmp6 = new THREE.Vector3();
const mat4 = new THREE.Matrix4();
const S = {
  head: (k) => heads[k] || P[k].headWorld(new THREE.Vector3()),
  phonePos: new THREE.Vector3(), speakerPos: new THREE.Vector3(),
};
const handPt = (h, side, out) => h.handPoint(side, out);
const TABLE_PHONE = new THREE.Vector3(-1.85, 0.8, -4.62);
const TABLE_SPK = new THREE.Vector3(TSPK[0], TSPK[1] - 0.025, TSPK[2]);

function frame(t) {
  // 1) placement + pose (2 passes : les regards dépendent des têtes)
  for (let pass = 0; pass < 2; pass++) {
    const C = cast(t, { dad: { headWorld: () => S.head('dad') }, kid: { headWorld: () => S.head('kid') }, plaintiff: { headWorld: () => S.head('plaintiff') }, judge: { headWorld: () => S.head('judge') }, lawyer: { headWorld: () => S.head('lawyer') } });
    for (const k in C) {
      const c = C[k], h = P[k];
      h.root.position.set(...c.pos);
      h.root.rotation.y = c.yaw;
      h.root.visible = c.visible !== false;
      h.setPose(c.p, c.f, c.look, t);
      h.root.updateMatrixWorld(true);
      heads[k] = h.headWorld(new THREE.Vector3());
    }
    if (pass === 1) S.C = C;
  }
  const C = S.C;
  // figurants
  EX.forEach((h, i) => {
    const e = extras(t, i);
    const base = h.kind === 'sit'
      ? { sit: 1, hipY: e.jump * 0.07, lHip: -1.52, rHip: -1.52, lKnee: 1.5, rKnee: 1.5, spineX: 0.05 - e.jump * 0.2, lX: -0.3 - e.jump * 1.2, rX: -0.3 - e.jump * 1.2, lEl: -1.3, rEl: -1.3, lZ: 0.15, rZ: -0.15 }
      : { hipY: e.jump * 0.06, spineX: -e.jump * 0.15, lX: -0.1 - e.jump * 1.0, rX: -0.1 - e.jump * 1.0, lEl: -0.5 - e.jump, rEl: -0.5 - e.jump, lZ: 0.15, rZ: -0.15 };
    h.setPose(base, e.f, S.head(e.lookAt), t + i * 1.7);
  });

  // 2) accessoires
  const kid = P.kid;
  const phone = court.phone;
  let lost = C.kid.lost;
  if ((t > 41.25 && t < 58.3) || (t > 27.85 && t < 30.55)) {
    phone.position.copy(TABLE_PHONE);
    phone.rotation.set(-Math.PI / 2, 0, 0.3);
    lost = t > 41.25 ? 1 : 0;
  } else if (t >= 58.3) {
    // tenu d'une main, écran tourné vers le père
    handPt(kid, 'r', phone.position);
    phone.position.y += 0.035;
    phone.lookAt(S.head('dad'));
    lost = 1;
  } else {
    // tenu à deux mains, en paysage, écran vers son visage
    handPt(kid, 'r', tmp); handPt(kid, 'l', tmp2);
    const mid = tmp3.copy(tmp).add(tmp2).multiplyScalar(0.5);
    const X = tmp4.copy(tmp).sub(tmp2).normalize();
    const Z = tmp5.copy(S.head('kid')).sub(mid);
    Z.addScaledVector(X, -Z.dot(X)).normalize();
    const Y = tmp6.crossVectors(Z, X).normalize();
    phone.quaternion.setFromRotationMatrix(mat4.makeBasis(X, Y, Z));
    phone.position.copy(mid).addScaledVector(Z, 0.012).addScaledVector(Y, 0.012);
  }
  court.screen.draw(t, lost);
  S.phonePos.copy(phone.position);

  const spk = court.speaker;
  spk.visible = t > 28.6;
  if (t < 29.95) { handPt(kid, 'r', spk.position); spk.position.y += 0.02; spk.rotation.set(0.15, 0.4, 0.1); }
  else { spk.position.copy(TABLE_SPK); spk.position.y -= 0.008; spk.rotation.set(0, Math.PI - 0.35, 0); }
  S.speakerPos.copy(spk.position);
  const ledOn = t > 30.9 ? (t < 31.8 ? (Math.floor(t * 6) % 2) : 1) : 0;
  court.led.material.emissiveIntensity = ledOn * 4;
  court.led.material.color.set(ledOn ? '#2a7bff' : '#111');

  const gv = court.gavel;
  if (C.judge.gavel > 0.5) {
    handPt(P.judge, 'r', gv.position);
    P.judge.handQuat('r', gv.quaternion);
    gv.rotateX(Math.PI / 2);
    gv.translateY(0.1);
  } else {
    gv.position.set(0.55, 1.67, -8.62);
    gv.rotation.set(0, 0.4, Math.PI / 2 - 0.05);
  }

  // 3) caméra : plan courant (coupes franches entre les plans)
  let i = 0;
  while (i < SHOTS.length - 1 && t >= SHOTS[i + 1].t) i++;
  const sh = SHOTS[i];
  const t1 = i < SHOTS.length - 1 ? SHOTS[i + 1].t : T_END;
  const u = Math.min(1, Math.max(0, (t - sh.t) / (t1 - sh.t)));
  const cm = sh.cam(u, S);
  const shakeA = (sh.shake || 0) * (0.012 + 0.05 * Math.exp(-(t - sh.t) * 2.2)) + 0.0025;
  camera.position.set(cm.pos.x + Math.sin(t * 13.1) * shakeA, cm.pos.y + Math.sin(t * 17.7 + 1) * shakeA, cm.pos.z + Math.sin(t * 11.3 + 2) * shakeA * 0.5);
  camera.lookAt(cm.look.x + Math.sin(t * 0.7) * 0.004, cm.look.y + Math.sin(t * 0.9) * 0.004, cm.look.z);
  const k = camera.aspect > 1.2 ? 0.78 : camera.aspect > 0.8 ? 0.9 : 1;
  camera.fov = sh.fov * k;
  camera.updateProjectionMatrix();
  const fd = camera.position.distanceTo(tmp.set(cm.look.x, cm.look.y, cm.look.z));
  bokeh.uniforms.focus.value = fd;
  bokeh.uniforms.aperture.value = 0.0065 * (sh.ap ?? 1);
  bokeh.uniforms.maxblur.value = 0.012;

  // 4) calques
  hudMat.uniforms.uTime.value = t;
  hudMat.uniforms.uFade.value = Math.max(1 - sstep(0, 0.8, t), sstep(T_END - 2.2, T_END - 0.2, t));
  hudMat.uniforms.uFlash.value = t > 33.6 ? 0.35 * Math.exp(-(t - 33.6) * 12) : 0;
  drawCaption(t);

  renderer.clear();
  composer.render();
  renderer.render(hud, hudCam);
}

// ---------- Lecture / interface ----------
let t = 0, playing = true, last = performance.now(), recorder = null;
const $ = (id) => document.getElementById(id);
const scrub = $('scrub');
scrub.max = T_END.toFixed(2);
const fmt = (x) => `${Math.floor(x / 60)}:${String(Math.floor(x % 60)).padStart(2, '0')}.${Math.floor((x % 1) * 10)}`;

const beats = $('beats');
BEATS.forEach(([a, , txt], j) => {
  const li = document.createElement('li');
  const lab = SHOTS.find((s) => Math.abs(s.t - a) < 0.01 && s.label);
  li.innerHTML = `<b>${fmt(a)}</b><span><em>${txt}</em>${lab ? `<small>${lab.label}</small>` : ''}</span>`;
  li.onclick = () => seek(a);
  li.dataset.t = a;
  beats.appendChild(li);
});

function setPlaying(p) { playing = p; $('play').textContent = p ? '❚❚' : '▶'; }
function seek(x) { t = Math.max(0, Math.min(T_END, x)); frame(t); updateUI(); }
function updateUI() {
  scrub.value = t;
  $('time').textContent = `${fmt(t)} / ${fmt(T_END)}`;
  let curLi = null;
  for (const li of beats.children) { const on = +li.dataset.t <= t + 0.01; li.classList.toggle('on', on); li.classList.remove('cur'); if (on) curLi = li; }
  if (curLi) curLi.classList.add('cur');
}
$('play').onclick = () => { if (t >= T_END) t = 0; setPlaying(!playing); };
$('restart').onclick = () => { seek(0); setPlaying(true); };
scrub.oninput = () => { if (!recorder) seek(+scrub.value); };
$('format').onchange = (e) => { format = e.target.value; applySize(); frame(t); };
$('quality').onchange = (e) => { quality = +e.target.value; applySize(); frame(t); };
$('subs').onchange = (e) => { captions = e.target.checked; capKey = '#'; frame(t); };
$('hide').onclick = () => document.body.classList.toggle('clean');
window.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'SELECT' || e.target.tagName === 'INPUT' && e.target.type !== 'range') return;
  if (e.code === 'Space') { e.preventDefault(); $('play').click(); }
  if (e.key === 'h' || e.key === 'H') document.body.classList.toggle('clean');
  if (e.key === 'ArrowRight' && !recorder) seek(t + 1);
  if (e.key === 'ArrowLeft' && !recorder) seek(t - 1);
});

function pickMime() {
  const c = ['video/mp4;codecs=avc1.640028', 'video/mp4', 'video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm'];
  return c.find((m) => window.MediaRecorder && MediaRecorder.isTypeSupported(m));
}
$('rec').onclick = () => {
  if (recorder) { recorder.stop(); return; }
  const mime = pickMime();
  if (!mime) { alert("Votre navigateur ne permet pas l'enregistrement vidéo. Essayez Chrome ou Edge."); return; }
  const chunks = [];
  recorder = new MediaRecorder(canvas.captureStream(60), { mimeType: mime, videoBitsPerSecond: quality >= 1080 ? 16e6 : 10e6 });
  recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  recorder.onstop = () => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob(chunks, { type: mime }));
    a.download = `le-proces-${format.replace(':', 'x')}.${mime.includes('mp4') ? 'mp4' : 'webm'}`;
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
    if (t >= T_END) { t = T_END; setPlaying(false); if (recorder) setTimeout(() => recorder && recorder.stop(), 300); }
    frame(t);
    updateUI();
  }
  requestAnimationFrame(loop);
}

const q = new URLSearchParams(location.search);
if (q.get('format') && FORMATS[q.get('format')]) { format = q.get('format'); $('format').value = format; }
if (q.get('quality')) { quality = +q.get('quality'); }
if (q.get('subs')) { captions = true; $('subs').checked = true; }
applySize();
if (q.get('pause')) setPlaying(false);
seek(q.get('t') ? +q.get('t') : 0);
window.seek = seek;
window.cine = { T_END };
document.body.classList.add('ready');
requestAnimationFrame((n) => { last = n; loop(n); });
