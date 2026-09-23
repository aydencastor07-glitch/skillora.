import * as THREE from 'three';

export const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
export const lerp = (a, b, t) => a + (b - a) * t;
export const sstep = (a, b, x) => {
  const t = clamp((x - a) / (b - a), 0, 1);
  return t * t * (3 - 2 * t);
};
export const bump = (a, b, c, d, x) => sstep(a, b, x) * (1 - sstep(c, d, x));
export const wrapPi = (a) => {
  a = (a + Math.PI) % (Math.PI * 2);
  if (a < 0) a += Math.PI * 2;
  return a - Math.PI;
};
export const lerpAngle = (a, b, t) => a + wrapPi(b - a) * t;
export const DEG = Math.PI / 180;

// Générateur pseudo-aléatoire déterministe (même forêt à chaque lecture)
export function rng(seed) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Clés lissées : [[t, v], ...] avec transition smoothstep entre clés
export function keys(k, t) {
  if (t <= k[0][0]) return k[0][1];
  for (let i = 0; i < k.length - 1; i++) {
    if (t < k[i + 1][0]) {
      let u = (t - k[i][0]) / (k[i + 1][0] - k[i][0]);
      u = u * u * (3 - 2 * u);
      return lerp(k[i][1], k[i + 1][1], u);
    }
  }
  return k[k.length - 1][1];
}

// Clés linéaires
export function lin(k, t) {
  if (t <= k[0][0]) return k[0][1];
  for (let i = 0; i < k.length - 1; i++) {
    if (t < k[i + 1][0]) {
      const u = (t - k[i][0]) / (k[i + 1][0] - k[i][0]);
      return lerp(k[i][1], k[i + 1][1], u);
    }
  }
  return k[k.length - 1][1];
}

// ---------- Style BD : matériaux cartoon + contours encrés ----------

export const gradientMap = (() => {
  const d = new Uint8Array([95, 175, 255]);
  const tex = new THREE.DataTexture(d, 3, 1, THREE.RedFormat);
  tex.minFilter = tex.magFilter = THREE.NearestFilter;
  tex.needsUpdate = true;
  return tex;
})();

export function toon(color, extra = {}) {
  return new THREE.MeshToonMaterial({ color, gradientMap, ...extra });
}

export const INK = new THREE.MeshBasicMaterial({ color: 0x15130f, side: THREE.BackSide });
export const BLACK = new THREE.MeshBasicMaterial({ color: 0x111111 });

// Géométrie de contour : sommets poussés le long de la normale lissée
const outlineCache = new Map();
export function outlineGeo(geo, t) {
  const cacheKey = geo.uuid + ':' + t.toFixed(4);
  if (outlineCache.has(cacheKey)) return outlineCache.get(cacheKey);
  const g = geo.clone();
  const pos = g.attributes.position;
  const nor = g.attributes.normal;
  const acc = new Map();
  const key = (i) => `${pos.getX(i).toFixed(3)},${pos.getY(i).toFixed(3)},${pos.getZ(i).toFixed(3)}`;
  for (let i = 0; i < pos.count; i++) {
    const k = key(i);
    const a = acc.get(k) || [0, 0, 0];
    a[0] += nor.getX(i); a[1] += nor.getY(i); a[2] += nor.getZ(i);
    acc.set(k, a);
  }
  for (let i = 0; i < pos.count; i++) {
    const a = acc.get(key(i));
    const l = Math.hypot(a[0], a[1], a[2]) || 1;
    pos.setXYZ(i, pos.getX(i) + (a[0] / l) * t, pos.getY(i) + (a[1] / l) * t, pos.getZ(i) + (a[2] / l) * t);
  }
  g.deleteAttribute('uv');
  outlineCache.set(cacheKey, g);
  return g;
}

// Ajoute un contour noir à un mesh (épaisseur en unités monde approximatives)
export function ink(mesh, worldT = 0.03) {
  const s = mesh.scale;
  const avg = (Math.abs(s.x) + Math.abs(s.y) + Math.abs(s.z)) / 3 || 1;
  const o = new THREE.Mesh(outlineGeo(mesh.geometry, worldT / avg), INK);
  o.raycast = () => {};
  mesh.add(o);
  return mesh;
}

export function part(geo, mat, parent, { pos, rot, scale, outline = 0.03, shadow = true } = {}) {
  const m = new THREE.Mesh(geo, mat);
  if (pos) m.position.set(...pos);
  if (rot) m.rotation.set(...rot);
  if (scale) m.scale.set(...scale);
  if (outline) ink(m, outline);
  m.castShadow = shadow;
  parent.add(m);
  return m;
}
