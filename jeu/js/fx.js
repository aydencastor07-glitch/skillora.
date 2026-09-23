// Effets : poussière, pluie, éclaboussures, étoiles, "BAM!", et calque BD plein écran.
import * as THREE from 'three';
import { toon, outlineGeo, INK, sstep } from './util.js';
import { HOLE } from './world.js';

const hash = (n) => {
  const s = Math.sin(n * 12.9898 + 78.233) * 43758.5453;
  return s - Math.floor(s);
};
const M = new THREE.Matrix4();
const Q = new THREE.Quaternion();
const E = new THREE.Euler();
const V = new THREE.Vector3();
const S = new THREE.Vector3();

export class Dust {
  constructor(scene) {
    const g = new THREE.IcosahedronGeometry(1, 1);
    this.mesh = new THREE.InstancedMesh(g, toon(0xd9c9a0), 200);
    this.ink = new THREE.InstancedMesh(outlineGeo(g, 0.09), INK, 200);
    this.mesh.frustumCulled = this.ink.frustumCulled = false;
    scene.add(this.mesh, this.ink);
  }
  update(s, tracks, visible) {
    let n = 0;
    const EVERY = 0.12, LIFE = 0.55;
    const o = {};
    tracks.forEach((tr, a) => {
      if (!visible[a]) return;
      const k0 = Math.floor((s - LIFE) / EVERY), k1 = Math.floor(s / EVERY);
      for (let k = Math.max(0, k0); k <= k1; k++) {
        const tk = k * EVERY;
        tr.sample(tk, o);
        if (o.speed < 3.5 || Math.abs(o.y) > 0.05) continue;
        if (Math.hypot(o.x - HOLE.x, o.z - HOLE.z) < HOLE.r + 0.3) continue;
        const age = s - tk;
        if (age < 0 || age > LIFE) continue;
        const fx = Math.sin(o.yaw), fz = Math.cos(o.yaw);
        const side = (hash(k * 7 + a * 131) - 0.5) * 0.7;
        const grow = (0.1 + 0.26 * Math.sqrt(age / LIFE)) * (1 - sstep(LIFE * 0.55, LIFE, age));
        for (let b = 0; b < 2; b++) {
          if (n >= 200) break;
          const j = hash(k * 13 + a * 71 + b * 5);
          V.set(o.x - fx * (0.3 + age * 0.5) - fz * side + (j - 0.5) * 0.3, 0.08 + age * 0.45 + b * 0.1, o.z - fz * (0.3 + age * 0.5) + fx * side + (j - 0.5) * 0.2);
          const sc = grow * (b ? 0.7 : 1);
          S.set(sc, sc * 0.85, sc);
          M.compose(V, Q.identity(), S);
          this.mesh.setMatrixAt(n, M);
          this.ink.setMatrixAt(n, M);
          n++;
        }
      }
    });
    this.mesh.count = this.ink.count = n;
    this.mesh.instanceMatrix.needsUpdate = this.ink.instanceMatrix.needsUpdate = true;
  }
}

export class Rain {
  constructor(scene) {
    this.N = 1800;
    const g = new THREE.CylinderGeometry(0.012, 0.012, 0.75, 4);
    this.mat = new THREE.MeshBasicMaterial({ color: 0xe6eef2, transparent: true, opacity: 0.8 });
    this.mesh = new THREE.InstancedMesh(g, this.mat, this.N);
    this.mesh.frustumCulled = false;
    scene.add(this.mesh);
    this.d = [];
    for (let i = 0; i < this.N; i++) {
      const inHole = hash(i * 3.1) < 0.14;
      const a = hash(i * 1.7) * Math.PI * 2;
      const r = inHole ? Math.sqrt(hash(i * 5.3)) * (HOLE.r - 0.1) : 1 + Math.sqrt(hash(i * 5.3)) * 26;
      this.d.push({ a, r, off: hash(i * 9.1), sp: 17 + hash(i * 2.3) * 5 });
    }
    // éclaboussures
    const rg = new THREE.RingGeometry(0.75, 1, 16);
    rg.rotateX(-Math.PI / 2);
    this.splash = new THREE.InstancedMesh(rg, new THREE.MeshBasicMaterial({ color: 0xeef4f7, transparent: true, opacity: 0.75 }), 260);
    this.splash.frustumCulled = false;
    scene.add(this.splash);
  }
  update(s, amt, cam) {
    const TOP = 22, H = 27;
    const n = Math.floor(this.N * amt);
    E.set(0.08, 0, 0.05);
    Q.setFromEuler(E);
    for (let i = 0; i < n; i++) {
      const d = this.d[i];
      const y = TOP - ((s * d.sp + d.off * H) % H);
      V.set(HOLE.x + Math.cos(d.a) * d.r + y * 0.04, y, HOLE.z + Math.sin(d.a) * d.r + y * 0.07);
      // pas de goutte collée à l'objectif
      const near = V.distanceToSquared(cam) < 2.5;
      M.compose(V, Q, near ? S.set(0.001, 0.001, 0.001) : S.set(1, 1, 1));
      this.mesh.setMatrixAt(i, M);
    }
    this.mesh.count = n;
    this.mesh.instanceMatrix.needsUpdate = true;
    const ns = Math.floor(140 * amt);
    for (let i = 0; i < ns; i++) {
      const per = 0.45 + hash(i * 4.7) * 0.5;
      const ph = ((s + hash(i * 8.3) * per) % per) / per;
      const cyc = Math.floor((s + hash(i * 8.3) * per) / per);
      const inHole = i % 7 === 0;
      const a = hash(i * 2.9 + cyc * 1.3) * Math.PI * 2;
      const r = inHole ? Math.sqrt(hash(i * 6.1 + cyc)) * (HOLE.r - 0.15) : HOLE.r + 0.3 + hash(i * 6.1 + cyc) * 14;
      const sc = 0.03 + ph * 0.14;
      V.set(HOLE.x + Math.cos(a) * r, inHole ? -4.97 : 0.05, HOLE.z + Math.sin(a) * r);
      M.compose(V, Q.identity(), S.set(sc, 1, sc * (1 - ph * 0.3)));
      if (ph > 0.8) M.scale(S.set(0.001, 1, 0.001));
      this.splash.setMatrixAt(i, M);
    }
    this.splash.count = ns;
    this.splash.instanceMatrix.needsUpdate = true;
  }
}

function starShape(r1, r0, n = 5) {
  const sh = new THREE.Shape();
  for (let i = 0; i <= n * 2; i++) {
    const a = (i / (n * 2)) * Math.PI * 2 + Math.PI / 2;
    const r = i % 2 ? r0 : r1;
    i === 0 ? sh.moveTo(Math.cos(a) * r, Math.sin(a) * r) : sh.lineTo(Math.cos(a) * r, Math.sin(a) * r);
  }
  return sh;
}

export class DizzyStars {
  constructor(scene) {
    const g = new THREE.ExtrudeGeometry(starShape(0.13, 0.06), { depth: 0.04, bevelEnabled: false });
    g.center();
    g.computeVertexNormals();
    this.stars = [];
    for (let i = 0; i < 3; i++) {
      const m = new THREE.Mesh(g, toon(0xf7d23e));
      m.add(new THREE.Mesh(outlineGeo(g, 0.02), INK));
      scene.add(m);
      this.stars.push(m);
    }
  }
  update(s, head, on, camPos) {
    this.stars.forEach((m, i) => {
      m.visible = on > 0.01;
      if (!m.visible) return;
      const a = s * 3 + (i / 3) * Math.PI * 2;
      m.position.set(head.x + Math.cos(a) * 0.55, head.y + 0.5 + Math.sin(a * 2) * 0.06, head.z + Math.sin(a) * 0.55);
      m.lookAt(camPos);
      m.rotateZ(s * 4 + i);
      m.scale.setScalar(on);
    });
  }
}

export function makeBam(scene) {
  const c = document.createElement('canvas');
  c.width = c.height = 512;
  const g = c.getContext('2d');
  const burst = (r1, r0, n, fill) => {
    g.beginPath();
    for (let i = 0; i <= n * 2; i++) {
      const a = (i / (n * 2)) * Math.PI * 2;
      const r = (i % 2 ? r0 : r1) * (0.85 + 0.3 * ((i * 7919) % 13) / 13);
      const x = 256 + Math.cos(a) * r, y = 256 + Math.sin(a) * r;
      i === 0 ? g.moveTo(x, y) : g.lineTo(x, y);
    }
    g.closePath();
    g.fillStyle = fill;
    g.fill();
    g.lineWidth = 10;
    g.strokeStyle = '#111';
    g.stroke();
  };
  burst(245, 150, 14, '#f04a2e');
  burst(190, 120, 12, '#ffd83a');
  g.font = '900 128px "Bangers", "Impact", sans-serif';
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  g.lineWidth = 16;
  g.strokeStyle = '#111';
  g.save();
  g.translate(256, 262);
  g.rotate(-0.12);
  g.strokeText('BAM!', 0, 0);
  g.fillStyle = '#fff';
  g.fillText('BAM!', 0, 0);
  g.restore();
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true }));
  sp.renderOrder = 999;
  scene.add(sp);
  return sp;
}

// Calque plein écran : lignes de vitesse, vignette, grain papier, flash, fondu
export function makeOverlay() {
  const scene = new THREE.Scene();
  const cam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const mat = new THREE.ShaderMaterial({
    transparent: true,
    depthTest: false,
    depthWrite: false,
    uniforms: {
      uTime: { value: 0 }, uSpeed: { value: 0 }, uFade: { value: 0 }, uFlash: { value: 0 },
      uAspect: { value: 1 }, uDark: { value: 0 },
    },
    vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`,
    fragmentShader: `
      varying vec2 vUv;
      uniform float uTime, uSpeed, uFade, uFlash, uAspect, uDark;
      float h(float n){ return fract(sin(n*91.345+7.13)*43758.5453); }
      float h2(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233)))*43758.5453); }
      void main(){
        vec2 p = vUv*2.0-1.0; p.x *= uAspect;
        float r = length(p);
        float a = atan(p.y, p.x);
        float bins = 150.0;
        float k = floor((a+3.14159)/6.28318*bins);
        float f = fract((a+3.14159)/6.28318*bins);
        float st = floor(uTime*18.0);
        float on = step(0.62, h(k + st*17.0));
        float start = 0.55 + 0.45*h(k*3.1 + st);
        float w = 1.0 - smoothstep(0.0, 0.5 * (r - start + 0.1), abs(f-0.5));
        float lines = on * w * smoothstep(start, start+0.25, r) * uSpeed;
        float vig = smoothstep(0.75, 1.7, r) * (0.35 + 0.25*uDark);
        float grain = (h2(vUv*vec2(913.0,677.0) + floor(uTime*12.0)) - 0.5) * 0.05;
        vec3 col = vec3(0.07,0.06,0.05);
        float alpha = clamp(max(lines*0.85, vig) + grain, 0.0, 1.0);
        alpha = mix(alpha, 1.0, uFade);
        vec3 c = mix(col, vec3(1.0), uFlash);
        alpha = max(alpha, uFlash*0.75);
        gl_FragColor = vec4(c, alpha);
      }`,
  });
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat);
  quad.frustumCulled = false;
  scene.add(quad);
  return { scene, cam, mat };
}
