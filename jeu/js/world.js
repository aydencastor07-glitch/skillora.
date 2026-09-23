import * as THREE from 'three';
import { toon, outlineGeo, INK, rng } from './util.js';

// ---------- Chemin sinueux dans la forêt ----------
export class Path {
  constructor() {
    const pts = [];
    for (let i = 0; i <= 18; i++) {
      const z = -70 + i * 24;
      const x = Math.sin(i * 0.8) * 6 + Math.sin(i * 0.33 + 1) * 9;
      pts.push(new THREE.Vector3(x, 0, z));
    }
    const curve = new THREE.CatmullRomCurve3(pts, false, 'centripetal');
    curve.arcLengthDivisions = 4000;
    this.L = curve.getLength();
    this.S0 = 45; // s = 0 : départ de la poursuite
    this.step = 0.25;
    const n = Math.floor(this.L / this.step);
    this.px = new Float32Array(n + 1);
    this.pz = new Float32Array(n + 1);
    this.tx = new Float32Array(n + 1);
    this.tz = new Float32Array(n + 1);
    const p = new THREE.Vector3(), t = new THREE.Vector3();
    for (let i = 0; i <= n; i++) {
      const u = Math.min(1, (i * this.step) / this.L);
      curve.getPointAt(u, p);
      curve.getTangentAt(u, t);
      const l = Math.hypot(t.x, t.z);
      this.px[i] = p.x; this.pz[i] = p.z;
      this.tx[i] = t.x / l; this.tz[i] = t.z / l;
    }
    this.n = n;
    this.sMin = -this.S0;
    this.sMax = this.L - this.S0;
  }
  // position + tangente sur le chemin à l'abscisse s
  at(s) {
    let f = (s + this.S0) / this.step;
    f = Math.max(0, Math.min(this.n - 1.0001, f));
    const i = Math.floor(f), u = f - i;
    const x = this.px[i] + (this.px[i + 1] - this.px[i]) * u;
    const z = this.pz[i] + (this.pz[i + 1] - this.pz[i]) * u;
    let fx = this.tx[i] + (this.tx[i + 1] - this.tx[i]) * u;
    let fz = this.tz[i] + (this.tz[i + 1] - this.tz[i]) * u;
    const l = Math.hypot(fx, fz);
    fx /= l; fz /= l;
    // droite = F x Y
    return { x, z, fx, fz, rx: -fz, rz: fx, yaw: Math.atan2(fx, fz) };
  }
  // point à l'abscisse s décalé latéralement
  point(s, lat = 0) {
    const a = this.at(s);
    return { x: a.x + a.rx * lat, z: a.z + a.rz * lat, a };
  }
  // distance d'un point au chemin (approx.)
  dist(x, z, sFrom = this.sMin, sTo = this.sMax) {
    let best = 1e9;
    const i0 = Math.max(0, Math.floor((sFrom + this.S0) / this.step));
    const i1 = Math.min(this.n, Math.ceil((sTo + this.S0) / this.step));
    for (let i = i0; i <= i1; i += 4) {
      const d = (this.px[i] - x) ** 2 + (this.pz[i] - z) ** 2;
      if (d < best) best = d;
    }
    return Math.sqrt(best);
  }
}

// ---------- Textures dessinées ----------
function canvasTex(w, h, draw, repeat) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  draw(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  if (repeat) t.repeat.set(repeat, repeat);
  t.anisotropy = 8;
  return t;
}

function grassTexture() {
  return canvasTex(512, 512, (g, w, h) => {
    const r = rng(7);
    g.fillStyle = '#8aa262';
    g.fillRect(0, 0, w, h);
    for (let i = 0; i < 60; i++) {
      g.fillStyle = r() < 0.5 ? '#7c9656' : '#97ae6b';
      g.beginPath();
      g.ellipse(r() * w, r() * h, 20 + r() * 50, 10 + r() * 30, r() * 3, 0, Math.PI * 2);
      g.fill();
    }
    g.strokeStyle = '#4d6433';
    g.lineWidth = 1.6;
    g.lineCap = 'round';
    for (let i = 0; i < 260; i++) {
      const x = r() * w, y = r() * h, s = 5 + r() * 7;
      g.beginPath();
      g.moveTo(x - s * 0.6, y - s); g.lineTo(x, y); g.lineTo(x + s * 0.5, y - s * 1.1);
      g.stroke();
    }
  }, 230);
}

function dirtTexture() {
  return canvasTex(256, 512, (g, w, h) => {
    const r = rng(11);
    g.fillStyle = '#a9865a';
    g.fillRect(0, 0, w, h);
    for (let i = 0; i < 40; i++) {
      g.fillStyle = r() < 0.5 ? '#9a774c' : '#b69366';
      g.beginPath();
      g.ellipse(r() * w, r() * h, 10 + r() * 30, 20 + r() * 50, 0, 0, Math.PI * 2);
      g.fill();
    }
    // bords plus sombres
    const grad = g.createLinearGradient(0, 0, w, 0);
    grad.addColorStop(0, 'rgba(90,65,35,0.75)');
    grad.addColorStop(0.12, 'rgba(90,65,35,0)');
    grad.addColorStop(0.88, 'rgba(90,65,35,0)');
    grad.addColorStop(1, 'rgba(90,65,35,0.75)');
    g.fillStyle = grad;
    g.fillRect(0, 0, w, h);
    g.strokeStyle = '#5d4128';
    g.lineCap = 'round';
    for (let i = 0; i < 70; i++) {
      const x = 20 + r() * (w - 40), y = r() * h;
      g.lineWidth = 2 + r() * 2.5;
      g.beginPath(); g.moveTo(x, y); g.lineTo(x + (r() - 0.5) * 8, y + 6 + r() * 14); g.stroke();
    }
    for (let i = 0; i < 25; i++) {
      g.fillStyle = '#c4a57a';
      g.strokeStyle = '#5d4128';
      g.lineWidth = 2;
      const x = 20 + r() * (w - 40), y = r() * h;
      g.beginPath(); g.ellipse(x, y, 4 + r() * 5, 3 + r() * 3, r() * 3, 0, Math.PI * 2); g.fill(); g.stroke();
    }
  });
}

// Découpe le sol à l'endroit du trou
export const HOLE = { x: 0, z: 0, r: 2.2, depth: 5 };
const holeUniform = { value: new THREE.Vector3(0, 0, HOLE.r) };
function holeCut(mat) {
  mat.onBeforeCompile = (sh) => {
    sh.uniforms.uHole = holeUniform;
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vWPos;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvWPos = (modelMatrix * vec4(transformed, 1.0)).xyz;');
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vWPos;\nuniform vec3 uHole;')
      .replace('void main() {', 'void main() {\n  if (length(vWPos.xz - uHole.xy) < uHole.z) discard;');
  };
  return mat;
}

// InstancedMesh + son contour instancié
function instanced(geo, mat, count, outlineT, { shadow = true, receive = true } = {}) {
  const m = new THREE.InstancedMesh(geo, mat, count);
  m.castShadow = shadow;
  m.receiveShadow = receive;
  const group = new THREE.Group();
  group.add(m);
  let o = null;
  if (outlineT) {
    o = new THREE.InstancedMesh(outlineGeo(geo, outlineT), INK, count);
    group.add(o);
  }
  let i = 0;
  const mtx = new THREE.Matrix4();
  const q = new THREE.Quaternion();
  const e = new THREE.Euler();
  const add = (x, y, z, sx, sy, sz, rx = 0, ry = 0, rz = 0, color) => {
    if (i >= count) return;
    q.setFromEuler(e.set(rx, ry, rz));
    mtx.compose(new THREE.Vector3(x, y, z), q, new THREE.Vector3(sx, sy, sz));
    m.setMatrixAt(i, mtx);
    if (o) o.setMatrixAt(i, mtx);
    if (color !== undefined) m.setColorAt(i, new THREE.Color(color));
    i++;
  };
  const done = () => {
    m.count = i;
    if (o) o.count = i;
    m.instanceMatrix.needsUpdate = true;
    if (m.instanceColor) m.instanceColor.needsUpdate = true;
    m.computeBoundingSphere();
    if (o) { o.instanceMatrix.needsUpdate = true; o.computeBoundingSphere(); }
  };
  return { group, add, done };
}

// ---------- Construction du monde ----------
export function buildWorld(scene, path, info) {
  const { C, Sc, Sh, hole, stick } = info;
  HOLE.x = hole.x; HOLE.z = hole.z;
  holeUniform.value.set(hole.x, hole.z, HOLE.r);
  const r = rng(1234);

  // Sol
  const groundMat = holeCut(toon(0xffffff, { map: grassTexture() }));
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(900, 900), groundMat);
  ground.rotation.x = -Math.PI / 2;
  ground.position.set(0, 0, 120);
  ground.receiveShadow = true;
  scene.add(ground);

  // Ruban du chemin (bords irréguliers, élargi dans la clairière)
  {
    const pos = [], uv = [], idx = [];
    let k = 0;
    for (let s = path.sMin + 1; s < path.sMax - 1; s += 0.5) {
      const a = path.at(s);
      let w = 2.1 + 0.35 * Math.sin(s * 0.37) + 0.22 * Math.sin(s * 1.31 + 2);
      const dc = Math.hypot(a.x - C.x, a.z - C.z);
      w += 3.2 * Math.max(0, 1 - dc / 9) ** 0.7;
      const wl = w + 0.15 * Math.sin(s * 2.1), wr = w + 0.15 * Math.sin(s * 1.7 + 1);
      pos.push(a.x - a.rx * wl, 0.03, a.z - a.rz * wl, a.x + a.rx * wr, 0.03, a.z + a.rz * wr);
      uv.push(0, s / 7, 1, s / 7);
      if (k > 0) {
        const b = (k - 1) * 2;
        idx.push(b, b + 1, b + 2, b + 1, b + 3, b + 2);
      }
      k++;
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
    g.setIndex(idx);
    g.computeVertexNormals();
    const tex = dirtTexture();
    tex.repeat.set(1, 1);
    const mat = holeCut(toon(0xffffff, { map: tex }));
    const m = new THREE.Mesh(g, mat);
    m.receiveShadow = true;
    scene.add(m);
    // flaque de terre de la clairière
    const cg = new THREE.CircleGeometry(5.8, 40);
    cg.rotateX(-Math.PI / 2);
    const cm = new THREE.Mesh(cg, holeCut(toon(0xa27f54)));
    cm.position.set(C.x, 0.025, C.z);
    cm.receiveShadow = true;
    scene.add(cm);
  }

  // Le trou
  {
    const R = HOLE.r, D = HOLE.depth;
    const wg = new THREE.CylinderGeometry(R + 0.02, R - 0.1, D, 36, 6, true);
    const col = [];
    const p = wg.attributes.position;
    for (let i = 0; i < p.count; i++) {
      const t = (p.getY(i) + D / 2) / D; // 1 en haut
      const c = new THREE.Color(0x5a4028).lerp(new THREE.Color(0x1d140c), 1 - t);
      col.push(c.r, c.g, c.b);
    }
    wg.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
    const walls = new THREE.Mesh(wg, toon(0xffffff, { vertexColors: true, side: THREE.BackSide }));
    walls.position.set(hole.x, -D / 2, hole.z);
    walls.receiveShadow = true;
    scene.add(walls);
    const bg = new THREE.CircleGeometry(R, 36);
    bg.rotateX(-Math.PI / 2);
    const bottom = new THREE.Mesh(bg, toon(0x3a2918));
    bottom.position.set(hole.x, -D + 0.01, hole.z);
    bottom.receiveShadow = true;
    scene.add(bottom);
    const ring = new THREE.Mesh(new THREE.RingGeometry(R - 0.03, R + 0.09, 48), new THREE.MeshBasicMaterial({ color: 0x15130f }));
    ring.rotation.x = -Math.PI / 2;
    ring.position.set(hole.x, 0.04, hole.z);
    scene.add(ring);
    // mottes de terre autour + racines dans les parois
    const clods = instanced(new THREE.IcosahedronGeometry(1, 1), toon(0xffffff), 40, 0.12);
    for (let i = 0; i < 26; i++) {
      const a = (i / 26) * Math.PI * 2 + r() * 0.2;
      const rr = R + 0.15 + r() * 0.35;
      const s = 0.12 + r() * 0.16;
      clods.add(hole.x + Math.cos(a) * rr, 0.02, hole.z + Math.sin(a) * rr, s * 1.4, s * 0.7, s * 1.2, 0, r() * 3, 0, r() < 0.5 ? 0x8d6a42 : 0x9d7a50);
    }
    for (let i = 0; i < 7; i++) {
      const a = r() * Math.PI * 2;
      clods.add(hole.x + Math.cos(a) * 0.9 * r(), -D + 0.05, hole.z + Math.sin(a) * 0.9 * r(), 0.15, 0.08, 0.12, 0, 0, 0, 0x6b5a4a);
    }
    clods.done();
    scene.add(clods.group);
    const roots = instanced(new THREE.CylinderGeometry(0.03, 0.05, 1, 6), toon(0x6d4c2f), 16, 0.02);
    for (let i = 0; i < 12; i++) {
      const a = r() * Math.PI * 2, y = -0.4 - r() * 3.6;
      roots.add(hole.x + Math.cos(a) * (R - 0.15), y, hole.z + Math.sin(a) * (R - 0.15), 1, 0.4 + r() * 0.5, 1, 1.2, -a + Math.PI / 2, 0.3, undefined);
    }
    roots.done();
    scene.add(roots.group);
  }

  // Bâton au sol (celui qu'il ramasse)
  // (le bâton "en main" est porté par le héros, voir story)

  // ---------- Végétation ----------
  const nearPath = (x, z, d) => path.dist(x, z) < d;
  const nearC = (x, z, d) => Math.hypot(x - C.x, z - C.z) < d;
  const nearHole = (x, z, d) => Math.hypot(x - hole.x, z - hole.z) < d;

  // Arbres
  const trunks = instanced(
    (() => { const g = new THREE.CylinderGeometry(0.62, 1, 1, 9, 1); g.translate(0, 0.5, 0); return g; })(),
    toon(0xffffff), 700, 0.1,
  );
  const canopy = instanced(new THREE.IcosahedronGeometry(1, 1), toon(0xffffff), 2600, 0.06);
  const trunkCols = [0x8c6c4b, 0x7b5d3f, 0x957453, 0x6f5238];
  const leafCols = [0x6f8c4c, 0x5f7c40, 0x7e9a57, 0x56733b, 0x87a25e];
  let nTrees = 0;
  for (let s = path.sMin + 2; s < path.sMax - 2 && nTrees < 690; s += 2.2) {
    const a = path.at(s);
    for (const side of [-1, 1]) {
      for (let j = 0; j < 3; j++) {
        if (r() > [0.85, 0.6, 0.4][j]) continue;
        const lat = side * ([6.2, 11, 18][j] + r() * [4, 6, 20][j]);
        const x = a.x + a.rx * lat + (r() - 0.5) * 2, z = a.z + a.rz * lat + (r() - 0.5) * 2;
        if (nearPath(x, z, 6) || nearC(x, z, 12.5) || nearHole(x, z, 6.5)) continue;
        const rad = 0.35 + r() * 0.35, h = 9 + r() * 5;
        trunks.add(x, -0.2, z, rad, h, rad, (r() - 0.5) * 0.08, r() * 6, (r() - 0.5) * 0.08, trunkCols[Math.floor(r() * 4)]);
        const nb = 3 + Math.floor(r() * 3);
        for (let b = 0; b < nb; b++) {
          const cr = 1.8 + r() * 1.6;
          canopy.add(
            x + (r() - 0.5) * 3.2, h - 1 + r() * 2.5, z + (r() - 0.5) * 3.2,
            cr, cr * 0.8, cr, r(), r() * 6, r(), leafCols[Math.floor(r() * leafCols.length)],
          );
        }
        nTrees++;
      }
    }
  }
  trunks.done(); canopy.done();
  scene.add(trunks.group, canopy.group);

  // Buissons au bord du chemin
  const bushes = instanced(new THREE.IcosahedronGeometry(1, 2), toon(0xffffff), 3000, 0.05);
  const bushCols = [0x6e8b4b, 0x7b9855, 0x5f7a41, 0x88a360, 0x668449];
  for (let s = path.sMin + 2; s < path.sMax - 2; s += 1.1) {
    const a = path.at(s);
    for (const side of [-1, 1]) {
      if (r() > 0.75) continue;
      const lat = side * (3.0 + r() * 4.5);
      const x = a.x + a.rx * lat, z = a.z + a.rz * lat;
      if (nearPath(x, z, 2.7) || nearC(x, z, 7.5) || nearHole(x, z, 3.2)) continue;
      const nb = 2 + Math.floor(r() * 3);
      const col = bushCols[Math.floor(r() * bushCols.length)];
      for (let b = 0; b < nb; b++) {
        const br = 0.5 + r() * 0.7;
        bushes.add(x + (r() - 0.5) * 1.4, br * 0.35, z + (r() - 0.5) * 1.4, br, br * 0.8, br, 0, r() * 6, 0, col);
      }
    }
  }
  // buissons autour de la clairière
  for (let i = 0; i < 40; i++) {
    const ang = r() * Math.PI * 2, d = 8 + r() * 4;
    const x = C.x + Math.cos(ang) * d, z = C.z + Math.sin(ang) * d;
    if (nearPath(x, z, 3)) continue;
    const br = 0.6 + r() * 0.8;
    bushes.add(x, br * 0.35, z, br, br * 0.8, br, 0, r() * 6, 0, bushCols[Math.floor(r() * bushCols.length)]);
  }
  bushes.done();
  scene.add(bushes.group);

  // Fougères (éventails de feuilles pointues)
  const leafG = new THREE.SphereGeometry(1, 8, 6);
  leafG.scale(0.16, 0.035, 0.75);
  leafG.translate(0, 0, 0.72);
  const ferns = instanced(leafG, toon(0xffffff), 6000, 0.022, { shadow: false });
  const fernCols = [0x7c9a56, 0x6c8a49, 0x8fab66];
  for (let s = path.sMin + 2; s < path.sMax - 2; s += 1.3) {
    const a = path.at(s);
    for (const side of [-1, 1]) {
      if (r() > 0.55) continue;
      const lat = side * (2.4 + r() * 3.5);
      const x = a.x + a.rx * lat, z = a.z + a.rz * lat;
      if (nearPath(x, z, 2.3) || nearC(x, z, 6.3) || nearHole(x, z, 2.6)) continue;
      const n = 6 + Math.floor(r() * 4), sc = 0.8 + r() * 0.8;
      const col = fernCols[Math.floor(r() * 3)];
      for (let l = 0; l < n; l++) {
        ferns.add(x, 0.05, z, sc, sc, sc, -0.5 - r() * 0.4, (l / n) * Math.PI * 2 + r() * 0.4, 0, col);
      }
    }
  }
  ferns.done();
  scene.add(ferns.group);

  // Cailloux
  const rocks = instanced(new THREE.DodecahedronGeometry(1, 0), toon(0xffffff), 200, 0.05);
  for (let s = path.sMin + 2; s < path.sMax - 2; s += 3) {
    if (r() > 0.4) continue;
    const a = path.at(s);
    const lat = (r() < 0.5 ? -1 : 1) * (2.2 + r() * 2);
    const x = a.x + a.rx * lat, z = a.z + a.rz * lat;
    if (nearHole(x, z, 3)) continue;
    const sc = 0.18 + r() * 0.3;
    rocks.add(x, sc * 0.3, z, sc * 1.3, sc, sc, r(), r() * 6, r(), r() < 0.5 ? 0x9a9a92 : 0x85857d);
  }
  rocks.done();
  scene.add(rocks.group);

  return { ground };
}
