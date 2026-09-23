// Le scénario : positions et poses de chaque acteur en fonction du temps.
// Tout est fonction du temps (aucun état) : on peut avancer / reculer librement.
import { clamp, lerp, sstep, bump, wrapPi, keys, DEG } from './util.js';

export const T_END = 66; // durée de l'histoire (secondes "histoire")
const DT = 1 / 60;
const PI = Math.PI;

// Moments clés (temps histoire)
export const T = {
  stop: 19.6, // les loups lui coupent la route
  pick: 27.0, // il ramasse le bâton
  grab: 27.65,
  lunge: 29.3, // le loup saute
  hit: 29.9, // BAM
  land: 31.1,
  run2: 32.15, // il s'enfuit
  hang: 45.45, // suspendu au-dessus du trou
  drop: 46.1, // il tombe
  bottom: 46.95, // touche le fond
  rain: 48.5,
  sit: 55.5,
};

// ---------- Actor baking ----------
class Track {
  constructor(n) {
    this.x = new Float32Array(n); this.y = new Float32Array(n); this.z = new Float32Array(n);
    this.yaw = new Float32Array(n); this.speed = new Float32Array(n); this.dist = new Float32Array(n);
    this.n = n;
  }
  sample(t, out = {}) {
    let f = clamp(t / DT, 0, this.n - 1.001);
    const i = Math.floor(f), u = f - i;
    const L = (a) => a[i] + (a[i + 1] - a[i]) * u;
    out.x = L(this.x); out.y = L(this.y); out.z = L(this.z);
    out.yaw = this.yaw[i] + wrapPi(this.yaw[i + 1] - this.yaw[i]) * u;
    out.speed = L(this.speed); out.dist = L(this.dist);
    return out;
  }
}

function bake(raw, faceFn) {
  const n = Math.ceil(T_END / DT) + 2;
  const tr = new Track(n);
  const ov = new Array(n);
  for (let i = 0; i < n; i++) {
    const r = raw(i * DT);
    tr.x[i] = r.x; tr.y[i] = r.y; tr.z[i] = r.z;
    ov[i] = r.yaw;
  }
  // vitesse, distance, orientation
  let prevYaw = ov[0] ?? 0, d = 0;
  for (let i = 0; i < n; i++) {
    const a = Math.max(0, i - 3), b = Math.min(n - 1, i + 3);
    const vx = (tr.x[b] - tr.x[a]) / ((b - a) * DT);
    const vz = (tr.z[b] - tr.z[a]) / ((b - a) * DT);
    const sp = Math.hypot(vx, vz);
    tr.speed[i] = sp;
    if (i > 0) d += Math.hypot(tr.x[i] - tr.x[i - 1], tr.z[i] - tr.z[i - 1]);
    tr.dist[i] = d;
    let yaw;
    if (ov[i] !== null && ov[i] !== undefined) yaw = ov[i];
    else {
      const vy = sp > 0.05 ? Math.atan2(vx, vz) : prevYaw;
      if (faceFn) {
        const fy = faceFn(i * DT, tr.x[i], tr.z[i]);
        const w = sstep(0.6, 2.2, sp);
        yaw = fy === null ? vy : fy + wrapPi(vy - fy) * w;
      } else yaw = sp > 0.4 ? vy : prevYaw;
    }
    tr.yaw[i] = prevYaw + wrapPi(yaw - prevYaw); // déroulé
    prevYaw = tr.yaw[i];
  }
  // lissage aller-retour de l'orientation
  const al = 1 - Math.exp(-DT / 0.07);
  for (let i = 1; i < n; i++) tr.yaw[i] = tr.yaw[i - 1] + (tr.yaw[i] - tr.yaw[i - 1]) * al;
  for (let i = n - 2; i >= 0; i--) tr.yaw[i] = tr.yaw[i + 1] + (tr.yaw[i] - tr.yaw[i + 1]) * al;
  return tr;
}

// ---------- Helpers de pose ----------
function mix(a, b, w) {
  if (w <= 0) return a;
  if (w >= 1) return { ...b };
  const o = { ...a };
  for (const k in b) o[k] = lerp(a[k] || 0, b[k], w);
  for (const k in a) if (!(k in b)) o[k] = lerp(a[k], 0, w);
  return o;
}
function add(a, b, w = 1) {
  const o = { ...a };
  for (const k in b) o[k] = (o[k] || 0) + b[k] * w;
  return o;
}

function heroRun(ph, amp) {
  const s = Math.sin(ph), c = Math.cos(ph);
  return {
    bodyY: amp * (0.11 * Math.abs(c) - 0.06),
    lHipX: -1.0 * amp * s, rHipX: 1.0 * amp * s,
    lKnee: amp * (0.25 + 1.35 * Math.max(0, c)), rKnee: amp * (0.25 + 1.35 * Math.max(0, -c)),
    lFoot: amp * 0.3 * Math.max(0, -c), rFoot: amp * 0.3 * Math.max(0, c),
    lShX: 0.95 * amp * s, rShX: -0.95 * amp * s,
    lElX: -1.7 * amp - 0.2, rElX: -1.7 * amp - 0.2,
    lShZ: 0.2, rShZ: -0.2,
    spineX: 0.3 * amp, spineY: 0.18 * amp * s,
    headX: -0.15 * amp,
  };
}

const LEGS_READY = { bodyY: -0.1, lHipZ: 0.28, rHipZ: -0.28, lHipX: -0.35, rHipX: 0.2, lKnee: 0.5, rKnee: 0.35, lFoot: -0.1 };
const P = {
  skid: { bodyY: -0.15, spineX: -0.35, lHipX: -0.9, lKnee: 0.1, lFoot: -0.3, rHipX: 0.35, rKnee: 1.0, lShX: -2.3, rShX: -2.0, lShZ: 0.8, rShZ: -0.8, lElX: -0.3, rElX: -0.4, headX: 0.15 },
  scared: { bodyY: -0.1, spineX: -0.1, lShX: -1.25, rShX: -1.25, lShZ: 0.35, rShZ: -0.35, lElX: -1.7, rElX: -1.7, lHipZ: 0.18, rHipZ: -0.18, lHipX: -0.3, rHipX: -0.3, lKnee: 0.55, rKnee: 0.55, lFoot: -0.25, rFoot: -0.25, headX: 0.08 },
  crouch: { bodyY: -0.52, spineX: 1.0, lHipX: -1.3, rHipX: -0.8, lKnee: 2.1, rKnee: 1.6, lFoot: -0.8, rFoot: -0.8, lHipZ: 0.25, rHipZ: -0.2, rShX: -0.9, rShZ: -0.05, rElX: -0.25, lShX: -0.7, lShZ: 0.3, lElX: -1.3, headX: -0.4 },
  ready: { ...LEGS_READY, spineX: 0.05, rShX: -1.4, rShZ: 0.45, lShX: -1.35, lShZ: -0.45, rElX: -1.1, lElX: -1.1, headX: 0.1 },
  windup: { ...LEGS_READY, spineY: -0.8, spineX: -0.1, rShX: -2.9, rShZ: -0.35, lShX: -2.6, lShZ: -0.7, rElX: -0.9, lElX: -1.2, headX: 0.05, headY: 0.4 },
  swing: { ...LEGS_READY, lHipX: -0.6, lKnee: 0.7, spineY: 0.75, spineX: 0.3, rShX: -1.45, rShZ: 0.95, lShX: -1.3, lShZ: 0.2, rElX: -0.15, lElX: -0.6, headY: -0.3 },
  follow: { ...LEGS_READY, lHipX: -0.6, lKnee: 0.7, spineY: 1.05, spineX: 0.35, rShX: -0.9, rShZ: 1.3, lShX: -0.6, lShZ: 0.3, rElX: -0.2, lElX: -0.8, headY: -0.5 },
  triumph: { ...LEGS_READY, spineX: -0.1, rShX: -2.9, rShZ: -0.3, rElX: -0.3, lShX: -0.6, lShZ: 0.9, lElX: -2.0, headX: -0.15 },
  hang: { bodyY: 0, lHipX: -1.1, rHipX: 0.7, lKnee: 0.5, rKnee: 1.2, lShX: -0.4, rShX: -0.4, lShZ: 1.1, rShZ: -1.1, lElX: -0.5, rElX: -0.5, headX: 0.55 },
  fall: { lShX: -2.9, rShX: -2.9, lShZ: 0.5, rShZ: -0.5, lElX: -0.2, rElX: -0.2, lHipX: -0.6, rHipX: -0.2, lKnee: 1.2, rKnee: 0.6, headX: -0.3 },
  lie: { lShX: 0.1, rShX: 0.1, lShZ: 1.45, rShZ: -1.45, lElX: -0.3, rElX: -0.3, lHipZ: 0.45, rHipZ: -0.45, lKnee: 0.25, rKnee: 0.4, lFoot: 0.6, rFoot: 0.6, headY: 0.25 },
  sit: { bodyY: -0.86, spineX: -0.15, lHipX: -1.5, rHipX: -1.4, lHipZ: 0.15, rHipZ: -0.15, lKnee: 0.25, rKnee: 0.5, lShX: 0.4, rShX: 0.4, lShZ: 0.35, rShZ: -0.35, lElX: -0.15, rElX: -0.15, headX: -0.5 },
};

// ---------- Poses du loup ----------
function wolfGallop(ph, a) {
  const s = Math.sin(ph), c = Math.cos(ph), s2 = Math.sin(ph - 0.5), c2 = Math.cos(ph - 0.5);
  return {
    flU: -0.8 * a * s, frU: -0.8 * a * s2,
    blU: 0.85 * a * s, brU: 0.85 * a * s2,
    flL: a * (0.15 + 1.1 * Math.max(0, c)), frL: a * (0.15 + 1.1 * Math.max(0, c2)),
    blL: -a * (0.25 + 0.9 * Math.max(0, -c)), brL: -a * (0.25 + 0.9 * Math.max(0, -c2)),
    pitch: 0.1 * a * Math.sin(ph + 1.4), bodyY: a * (0.1 * Math.abs(s) - 0.04),
    neckX: -0.05 + 0.1 * a * Math.sin(ph + 2), headX: 0.1,
    tailX: 0.55 + 0.15 * Math.sin(ph), tailY: 0.15 * Math.sin(ph * 0.5),
    jaw: 0.3 + 0.12 * Math.sin(ph * 2), ears: -0.35 * a,
  };
}
function wolfWalk(ph, a) {
  const s = Math.sin(ph), c = Math.cos(ph);
  return {
    flU: -0.45 * a * s, brU: -0.45 * a * s, frU: 0.45 * a * s, blU: 0.45 * a * s,
    flL: 0.7 * a * Math.max(0, c), brL: -0.6 * a * Math.max(0, c),
    frL: 0.7 * a * Math.max(0, -c), blL: -0.6 * a * Math.max(0, -c),
    bodyY: 0.03 * a * Math.abs(c), tailY: 0.1 * s,
  };
}
const W = {
  crouch: { bodyY: -0.16, flU: -0.55, frU: -0.55, flL: 1.0, frL: 1.0, blU: 0.5, brU: 0.5, blL: -0.9, brL: -0.9, neckX: 0.45, headX: -0.3, jaw: 0.38, ears: -0.55, tailX: -0.05 },
  lunge: { pitch: -0.3, bodyY: 0.05, flU: -1.35, frU: -1.2, flL: 0.1, frL: 0.2, blU: 1.2, brU: 1.05, blL: -0.2, brL: -0.3, neckX: -0.25, headX: 0.15, jaw: 0.9, ears: -0.7, tailX: 0.3 },
  peek: { bodyY: -0.12, pitch: 0.2, flU: -0.5, frU: -0.3, flL: 0.8, frL: 0.6, blU: 0.35, brU: 0.35, blL: -0.6, brL: -0.6, neckX: 0.8, headX: 0.35, jaw: 0.35, ears: -0.2, tailX: 0.25 },
};

// ---------- L'histoire ----------
export class Story {
  constructor(path) {
    this.path = path;
    this.buildTimeMap();

    // --- Vitesse du héros ---
    const HV = [[0, 6.5], [17.9, 6.5], [T.stop, 0], [T.run2, 0], [32.9, 7.2], [45.2, 7.2], [T.hang, 0]];
    const res = 1 / 600, N = Math.ceil(T_END / res) + 2;
    this.sArr = new Float32Array(N);
    let s = 0;
    const v = (t) => {
      for (let i = 0; i < HV.length - 1; i++)
        if (t < HV[i + 1][0]) return lerp(HV[i][1], HV[i + 1][1], (t - HV[i][0]) / (HV[i + 1][0] - HV[i][0]));
      return HV[HV.length - 1][1];
    };
    for (let i = 0; i < N; i++) { this.sArr[i] = s; s += v(i * res) * res; }
    this.sRes = res;

    // lieux importants
    this.Sc = this.heroS(T.stop);
    const cA = path.at(this.Sc);
    this.C = { x: cA.x, z: cA.z, yaw: cA.yaw, fx: cA.fx, fz: cA.fz, rx: cA.rx, rz: cA.rz };
    this.Sh = this.heroS(T.hang);
    const hA = path.at(this.Sh);
    this.H = { x: hA.x, z: hA.z, yaw: hA.yaw, fx: hA.fx, fz: hA.fz, rx: hA.rx, rz: hA.rz };

    this.hero = bake((t) => this.heroRaw(t));
    // bâton au sol : devant lui au moment où il se baisse
    const hp = this.hero.sample(27.4);
    const fx = Math.sin(hp.yaw), fz = Math.cos(hp.yaw);
    this.stickGround = { x: hp.x + fx * 0.75 - fz * 0.2, z: hp.z + fz * 0.75 + fx * 0.2, yaw: hp.yaw + 1.2 };

    this.wolves = [];
    for (let i = 0; i < 5; i++) {
      const face = (t, x, z) => this.wolfFace(i, t, x, z);
      this.wolves.push(bake((t) => this.wolfRaw(i, t), face));
    }
    this.impact = this.impactPoint();
  }

  // ----- ralenti : temps réel <-> temps histoire -----
  buildTimeMap() {
    const rate = (s) => 1 - 0.82 * bump(29.5, 29.8, 30.35, 30.75, s);
    const ds = 1 / 1000;
    const n = Math.ceil(T_END / ds) + 2;
    this.realAt = new Float32Array(n);
    let r = 0;
    for (let i = 0; i < n; i++) { this.realAt[i] = r; r += ds / rate(i * ds); }
    this.REAL_END = this.realAt[Math.round(T_END / ds)];
    const m = Math.ceil(this.REAL_END / ds) + 2;
    this.storyAt = new Float32Array(m);
    let j = 0;
    for (let k = 0; k < m; k++) {
      const rt = k * ds;
      while (j < n - 2 && this.realAt[j + 1] < rt) j++;
      const a = this.realAt[j], b = this.realAt[j + 1];
      this.storyAt[k] = (j + clamp((rt - a) / (b - a), 0, 1)) * ds;
    }
    this.ds = ds;
  }
  realOf(s) {
    const f = clamp(s / this.ds, 0, this.realAt.length - 1.001);
    const i = Math.floor(f);
    return lerp(this.realAt[i], this.realAt[i + 1], f - i);
  }
  storyOf(r) {
    const f = clamp(r / this.ds, 0, this.storyAt.length - 1.001);
    const i = Math.floor(f);
    return lerp(this.storyAt[i], this.storyAt[i + 1], f - i);
  }

  heroS(t) {
    const f = clamp(t / this.sRes, 0, this.sArr.length - 1.001);
    const i = Math.floor(f);
    return lerp(this.sArr[i], this.sArr[i + 1], f - i);
  }
  heroLat(t) {
    return 0.35 * Math.sin(1.3 * t) * (1 - sstep(16.5, 18.8, t)) +
      0.3 * Math.sin(1.1 * t + 1) * sstep(33, 35, t) * (1 - sstep(43.2, 44.6, t));
  }

  // ----- Héros : position brute -----
  heroRaw(t) {
    const p = this.path.point(this.heroS(t), this.heroLat(t));
    let x = p.x, z = p.z, y = 0, yaw = null;
    const C = this.C, H = this.H;
    if (t > 19.0 && t < 32.7) {
      // orientation scénarisée pendant l'encerclement
      const d1 = this.prowl(1, t);
      const off = keys([
        [19.0, 0], [19.8, 0], [20.3, -0.8], [20.9, 0.8], [21.4, 0.3], [22.4, PI], [23.3, PI + 0.55],
        [24.3, PI - 0.6], [25.3, PI + 0.45], [26.3, PI - 0.1],
      ], t);
      let o = off;
      if (t > 26.3) o = lerp(PI - 0.1, PI - d1, sstep(26.3, 27.0, t));
      if (t > 32.0) o = lerp(PI - d1, 2 * PI, sstep(32.0, 32.5, t));
      yaw = C.yaw + o;
      if (t < 19.8) yaw = lerp(p.a.yaw, C.yaw, sstep(19.0, 19.8, t)) + (t > 19.8 ? o : 0);
    }
    if (t >= T.hang - 0.2) yaw = H.yaw;
    if (t > T.drop) {
      const u = t - T.drop;
      y = Math.max(-5, -0.5 * 16 * u * u);
      // bascule en arrière : le corps se centre dans le trou
      const lie = sstep(T.drop + 0.1, T.bottom, t);
      const sit = sstep(T.sit, T.sit + 1.1, t);
      const off = lerp(lerp(0, 0.95, lie), 0.35, sit);
      x = H.x + H.fx * off; z = H.z + H.fz * off;
      if (t > T.bottom) y = -5 + 0.3 * lie * (1 - sit) + 0.09 * Math.max(0, Math.sin((t - T.bottom) * 14)) * Math.exp(-(t - T.bottom) * 6);
    }
    return { x, y, z, yaw };
  }

  heroPose(t) {
    const h = this.hero.sample(t);
    const ph = (h.dist / 2.1) * 2 * PI;
    const amp = sstep(0.4, 4, h.speed);
    let p = heroRun(ph, amp);
    p = mix(p, P.skid, bump(18.2, 18.9, 19.6, 20.2, t));
    p = mix(p, add(P.scared, { headZ: 0.06 * Math.sin(t * 38), lShX: 0.12 * Math.sin(t * 23), rShX: 0.12 * Math.sin(t * 27 + 1) }), bump(19.6, 20.2, 26.8, 27.2, t));
    p = mix(p, P.crouch, bump(26.9, 27.35, 27.75, 28.3, t));
    p = mix(p, add(P.ready, { rShX: 0.12 * Math.sin(t * 9), lShX: 0.12 * Math.sin(t * 9) }), bump(27.9, 28.4, T.lunge, T.lunge + 0.12, t));
    p = mix(p, P.windup, bump(T.lunge, T.lunge + 0.3, 29.7, 29.76, t));
    p = mix(p, P.swing, bump(29.72, 29.84, 29.94, 30.05, t));
    p = mix(p, P.follow, bump(29.95, 30.08, 30.8, 31.2, t));
    p = mix(p, add(P.triumph, { rShZ: 0.25 * Math.sin(t * 14), lElX: 0.3 * Math.sin(t * 14) }), bump(30.9, 31.3, 31.9, 32.3, t));
    // regarde derrière lui pendant la 2e poursuite
    const look = bump(40.8, 41.3, 43.9, 44.3, t);
    p.headY = (p.headY || 0) + 2.2 * look;
    p.spineY = (p.spineY || 0) + 0.45 * look;
    // suspendu dans le vide : les jambes pédalent, puis figé
    if (t > T.hang - 0.15) {
      const spin = heroRun(t * 26, 1);
      const freeze = sstep(45.6, 45.75, t);
      let q = mix(spin, P.hang, freeze);
      q.headX = lerp(q.headX, keys([[45.6, 0], [45.75, 0.6], [45.95, 0.6], [46.1, -0.1]], t), freeze);
      p = mix(p, q, sstep(T.hang - 0.15, T.hang, t));
    }
    if (t > T.drop) {
      const fl = add(P.fall, { lShZ: 0.35 * Math.sin(t * 30), rShZ: 0.35 * Math.sin(t * 33), lHipX: 0.5 * Math.sin(t * 25), rHipX: -0.5 * Math.sin(t * 25) });
      p = mix(p, fl, sstep(T.drop, T.drop + 0.15, t));
      p = mix(p, add(P.lie, { headY: 0.35 * Math.sin(t * 2.2), headZ: 0.15 * Math.sin(t * 1.7) }), sstep(T.bottom - 0.05, T.bottom + 0.1, t));
      p = mix(p, add(P.sit, { headZ: 0.05 * Math.sin(t * 1.3), headX: 0.08 * Math.sin(t * 0.9) }), sstep(T.sit, T.sit + 1.1, t));
      p.rootPitch = -PI / 2 * sstep(T.drop + 0.1, T.bottom, t) * (1 - sstep(T.sit, T.sit + 1.1, t));
      p.hatY = keys([[46.05, 0], [46.5, 0.7], [46.95, 1.2], [47.35, 0], [47.5, 0.14], [47.65, 0]], t);
      p.hatTilt = keys([[46.05, 0], [46.9, 0.9], [47.35, 0.35], [47.65, 0.25]], t);
    }
    return p;
  }

  heroFace(t) {
    const F = [[0, 'angry'], [17.9, 'surprised'], [19.7, 'scared'], [27.2, 'fierce'], [30.9, 'fierce'], [32.4, 'angry'],
      [40.8, 'scared'], [44.3, 'angry'], [45.5, 'surprised'], [46.05, 'scared'], [T.bottom, 'dizzy'], [55.6, 'grumpy']];
    let f = F[0][1];
    for (const [k, v] of F) if (t >= k) f = v;
    return f;
  }

  // ----- Loups -----
  // formation pendant les poursuites : [latéral, écart]
  static FORM = [[-1.7, 5.2], [0, 3.9], [1.7, 5.2], [-0.9, 7.4], [0.9, 7.6]];
  static CIRCLE = [-0.9, PI, 0.9, -2.2, 2.2];
  static RIM = [-2.45, 0, 2.45, -1.8, 1.8];

  prowl(i, t) {
    return 0.3 * Math.sin(0.55 * (t - 20) + i * 1.3) * sstep(20.3, 22, t);
  }
  chasePos(i, t, phaseB) {
    const [lat, base] = Story.FORM[i];
    let gap;
    if (!phaseB) gap = base + 6 * (1 - sstep(0, 12, t)) + 0.5 * Math.sin(0.9 * t + i * 1.9);
    else gap = (i === 3 || i === 4 ? base - 1.2 : base - 1) + 1.0 * (1 - sstep(33, 40, t)) + 0.4 * Math.sin(0.8 * t + i * 2.3);
    const s = this.heroS(t) - gap;
    return this.path.point(s, lat + 0.25 * Math.sin(1.1 * t + i));
  }
  circlePos(i, t) {
    const C = this.C;
    const a = Story.CIRCLE[i] + this.prowl(i, t);
    const r = 4.6 - 0.9 * sstep(21, 28.5, t) + 1.5 * sstep(T.hit + 0.05, 31, t) * (i === 1 ? 0 : 1);
    return { x: C.x + (C.fx * Math.cos(a) + C.rx * Math.sin(a)) * r, z: C.z + (C.fz * Math.cos(a) + C.rz * Math.sin(a)) * r, a, r };
  }
  // interpolation polaire autour d'un centre (contourne au lieu de traverser)
  polar(from, cx, cz, F, a1, r1, w) {
    const dx = from.x - cx, dz = from.z - cz;
    const a0 = Math.atan2(dx * F.rx + dz * F.rz, dx * F.fx + dz * F.fz);
    const r0 = Math.hypot(dx, dz);
    const a = a1 + wrapPi(a0 - a1) * (1 - w);
    const r = lerp(r0, r1, w);
    return { x: cx + (F.fx * Math.cos(a) + F.rx * Math.sin(a)) * r, z: cz + (F.fz * Math.cos(a) + F.rz * Math.sin(a)) * r };
  }

  wolfRaw(i, t) {
    const C = this.C, H = this.H;
    let pos, y = 0, yaw = null;
    if (t < 26) {
      const win = [[16.3, 19.8], [18.3, 20.4], [16.3, 19.8], [17.5, 20.9], [17.5, 20.9]][i];
      pos = this.chasePos(i, t, false);
      const w = sstep(win[0], win[1], t);
      if (w > 0) {
        const hs = this.heroS(Math.min(t, T.stop));
        const hp = this.path.point(hs, this.heroLat(t));
        const c = this.circlePos(i, t);
        pos = this.polar(pos, hp.x, hp.z, hp.a, c.a, c.r, w);
      }
    } else if (i === 1 && t >= T.lunge) {
      // le loup chef : saut, coup de bâton, vol plané, fuite
      const c0 = this.circlePos(1, T.lunge);
      const hp = this.hero.sample(T.lunge);
      const dx = c0.x - hp.x, dz = c0.z - hp.z, dl = Math.hypot(dx, dz);
      const ux = dx / dl, uz = dz / dl;
      yaw = Math.atan2(-ux, -uz);
      if (t < T.hit) {
        const u = sstep(T.lunge, T.hit, t) * 0.4 + 0.6 * ((t - T.lunge) / (T.hit - T.lunge));
        const r = lerp(dl, 1.35, u);
        pos = { x: hp.x + ux * r, z: hp.z + uz * r };
        y = 1.25 * Math.sin(u * PI * 0.75);
      } else if (t < T.land) {
        const u = (t - T.hit) / (T.land - T.hit);
        const r = lerp(1.35, 9, 1 - (1 - u) * (1 - u));
        pos = { x: hp.x + ux * r, z: hp.z + uz * r };
        y = 0.88 * (1 - u) + 3.2 * u * (1 - u);
      } else {
        const r = 9 + 1.2 * sstep(T.land, 31.6, t);
        const land = { x: hp.x + ux * r, z: hp.z + uz * r };
        const flee = this.path.point(this.Sc - 5 - 9 * Math.max(0, t - 32.2), -1.2);
        const w = sstep(31.9, 32.9, t);
        pos = { x: lerp(land.x, flee.x, w), z: lerp(land.z, flee.z, w) };
        if (t > 32.0) yaw = null;
      }
    } else if (t < 38) {
      pos = this.circlePos(i, t);
      const win = [[32.5, 34.4], null, [32.5, 34.4], [32.9, 35.3], [32.9, 35.3]][i];
      if (win) {
        const w = sstep(win[0], win[1], t);
        if (w > 0) {
          const b = this.chasePos(i, t, true);
          pos = { x: lerp(pos.x, b.x, w), z: lerp(pos.z, b.z, w) };
        }
      }
    } else {
      pos = this.chasePos(i, t, true);
      if (i === 1) pos = this.path.point(this.Sc - 60, -1.2);
      // arrivée au bord du trou
      const t0 = 45.15 + i * 0.08;
      const w = sstep(t0, t0 + 1.6, t);
      if (w > 0 && i !== 1) {
        let a = Story.RIM[i];
        if (i === 3) a = lerp(a, -0.35, sstep(51, 54.5, t));
        if (i === 2) a = lerp(a, 1.25, sstep(52, 55.5, t));
        let r = 2.85;
        // ils abandonnent et repartent
        const lv = sstep(57.6 + i * 0.35, 63 + i * 0.35, t);
        if (lv > 0) {
          r = lerp(2.85, 22, lv * lv);
          a = lerp(a, Math.sign(a) * PI * 0.97, sstep(57.6 + i * 0.35, 59.5 + i * 0.35, t));
        }
        pos = this.polar(pos, H.x, H.z, H, a, r, w);
      }
    }
    return { x: pos.x, y, z: pos.z, yaw };
  }

  // quand un loup ralentit, il regarde sa cible
  wolfFace(i, t, x, z) {
    let tx, tz;
    if (t > 45 && !(t > 57.6 + i * 0.35)) { tx = this.H.x; tz = this.H.z; }
    else if (t > 19 && t < 33) { const h = this.hero.sample(t); tx = h.x; tz = h.z; }
    else return null;
    return Math.atan2(tx - x, tz - z);
  }

  wolfState(i, t) {
    if (i === 1) {
      if (t >= T.lunge - 0.25 && t < T.hit) return 'lunge';
      if (t >= T.hit && t < T.land) return 'fly';
      if (t >= T.land && t < 32.1) return 'down';
      if (t >= 32.1) return 'flee';
    }
    if (t > 19.6 && t < 33.2) return 'prowl';
    if (t > 46.4 && t < 57.6 + i * 0.35) return 'peek';
    return 'run';
  }

  wolfPose(i, t) {
    const w = this.wolves[i].sample(t);
    const st = this.wolfState(i, t);
    const gal = sstep(3.2, 5.5, w.speed);
    const walkA = sstep(0.2, 1.5, w.speed) * (1 - gal);
    let p = wolfGallop((w.dist / 2.7) * 2 * PI + i, gal);
    p = add(p, wolfWalk((w.dist / 1.3) * 2 * PI + i, walkA));
    const prowlW = bump(19.4, 20.4, 32.8, 33.6, t) * (i === 1 ? 1 - sstep(T.lunge - 0.3, T.lunge, t) : 1);
    if (prowlW > 0) {
      let c = add(W.crouch, { jaw: 0.08 * Math.sin(t * 17 + i) });
      c = add(c, wolfWalk((w.dist / 1.3) * 2 * PI + i, sstep(0.1, 1.2, w.speed)));
      // sursaut de recul au moment du coup
      c = add(c, { neckX: -0.5, ears: -0.4, pitch: -0.1 }, bump(T.hit, T.hit + 0.15, 30.7, 31.4, t));
      p = mix(p, c, prowlW);
    }
    if (st === 'lunge') p = mix(p, W.lunge, sstep(T.lunge - 0.25, T.lunge + 0.05, t));
    if (st === 'fly') {
      const u = (t - T.hit) / (T.land - T.hit);
      p = {
        flU: -0.9 + 0.7 * Math.sin(t * 24), frU: -0.3 + 0.7 * Math.sin(t * 21), blU: 0.9 + 0.6 * Math.sin(t * 19), brU: 0.2 + 0.6 * Math.sin(t * 26),
        flL: 0.5, frL: 0.9, blL: -0.4, brL: -0.8, jaw: 0.75, ears: 0.4, tailX: -0.3 + 0.5 * Math.sin(t * 15), neckX: -0.3,
        roll: u * PI * 2.5, pitch: 0.3 * Math.sin(u * PI),
      };
    }
    if (st === 'down') {
      const g = sstep(31.55, 32.1, t);
      p = { ...W.crouch, roll: lerp(PI / 2 + 2 * PI, 2 * PI, g), bodyY: lerp(-0.48, -0.16, g), jaw: 0.25, ears: 0.3, tailX: -0.4, neckX: 0.2, headZ: 0.3 * Math.sin(t * 9) * (1 - g) };
    }
    if (st === 'flee') p = add(p, { tailX: -0.95, ears: 0.6, neckX: 0.25, jaw: 0.35 });
    if (st === 'peek') {
      const pk = add(W.peek, { headY: 0.35 * Math.sin(t * 0.8 + i * 2), jaw: 0.06 * Math.sin(t * 13 + i), tailY: 0.2 * Math.sin(t * 3 + i) });
      p = mix(p, pk, bump(46.4, 47.1, 57.4 + i * 0.35, 58 + i * 0.35, t) * (1 - walkA * 0.8));
    }
    // tête tournée vers le héros quand il est proche
    if (t > 19 && t < 33 && st !== 'fly' && st !== 'down') {
      const h = this.hero.sample(t);
      const a = wrapPi(Math.atan2(h.x - w.x, h.z - w.z) - w.yaw);
      p.headY = (p.headY || 0) + clamp(a, -0.7, 0.7) * 0.8;
    }
    return { p, st };
  }

  impactPoint() {
    const h = this.hero.sample(T.hit), w = this.wolves[1].sample(T.hit);
    return { x: (h.x * 0.45 + w.x * 0.55), y: 1.45, z: (h.z * 0.45 + w.z * 0.55), yaw: h.yaw };
  }

  wolfVisible(i, t) {
    return !(i === 1 && t > 39);
  }

  // ----- Météo -----
  rain(t) {
    return 0.05 * sstep(T.rain, T.rain + 0.6, t) + 0.95 * sstep(51, 60, t);
  }
  dark(t) {
    return sstep(47.5, 57, t);
  }
}

// ---------- Plans de caméra (un seul plan-séquence, sans coupure) ----------
// t : temps histoire ; f : cible ; az : angle autour de la cible (0 = devant, 90 = à droite, 180 = derrière)
// el : hauteur (degrés) ; d : distance ; h : décalage vertical du regard ; lk : cible du regard ; sl : lignes de vitesse
export const SHOTS = [
  { t: 0, f: 'mid', az: 10, el: 80, d: 40, fov: 50, label: "Vue d'en haut : la forêt, la poursuite commence" },
  { t: 2.6, f: 'hero', az: -25, el: 38, d: 13, fov: 50 },
  { t: 4.8, f: 'hero', az: 0, el: 9, d: 5.8, fov: 55, sl: 0.5, label: 'Face caméra : il court, les loups derrière lui' },
  { t: 7.0, f: 'hero', az: 40, el: 5, d: 4.6, h: 0.1, fov: 55, sl: 0.4 },
  { t: 9.0, f: 'hero', az: 95, el: 10, d: 5.8, fov: 52, sl: 0.3, label: 'Travelling de côté' },
  { t: 11.0, f: 'hero', az: 168, el: 17, d: 4.6, fov: 55, label: 'La caméra passe derrière lui…' },
  { t: 12.6, f: 'pack', az: 35, el: 22, d: 5.2, fov: 60, label: '…et se retourne sur les loups' },
  { t: 15.2, f: 'pack', az: -25, el: 4, d: 6.2, h: 0.2, fov: 60, sl: 0.4, label: 'Contre-plongée sur les loups' },
  { t: 17.0, f: 'hero', az: -70, el: 12, d: 6.5, fov: 55, label: 'Deux loups le dépassent et lui coupent la route' },
  { t: 18.8, f: 'hero', az: -5, el: 10, d: 6.5, fov: 55 },
  { t: 20.4, f: 'C', az: 30, el: 45, d: 12, fov: 52, label: 'Encerclé ! La caméra monte et tourne' },
  { t: 22.6, f: 'C', az: 150, el: 76, d: 16, fov: 52 },
  { t: 24.8, f: 'C', az: 290, el: 70, d: 13, fov: 52 },
  { t: 26.8, f: 'hero', az: -35, el: 24, d: 4.2, h: -0.7, fov: 48, label: 'Il repère un bâton et le ramasse' },
  { t: 28.5, f: 'hero', az: 15, el: -2, d: 3.3, h: 0.3, fov: 55, label: 'Contre-plongée : il se prépare' },
  { t: 29.35, f: 'impact', az: 80, el: 30, d: 4.4, fov: 55, label: 'Le loup attaque — RALENTI' },
  { t: 29.8, f: 'impact', az: 135, el: 26, d: 4.0, fov: 55 },
  { t: 30.15, f: 'impact', az: 215, el: 22, d: 4.2, fov: 55, label: 'BAM !' },
  { t: 30.6, f: 'lead', az: 290, el: 18, d: 6.5, fov: 55 },
  { t: 31.7, f: 'hero', az: 250, el: 24, d: 7, fov: 55, label: 'Le loup frappé s’enfuit' },
  { t: 33.2, f: 'hero', az: 20, el: 7, d: 5.2, fov: 55, sl: 0.5, label: 'Il s’enfuit : nouvelle poursuite' },
  { t: 35.4, f: 'hero', az: 120, el: 30, d: 7, fov: 55, sl: 0.3 },
  { t: 37.6, f: 'mid', az: 175, el: 68, d: 15, fov: 55, label: "Vue d'en haut" },
  { t: 39.6, f: 'pack', az: 15, el: 7, d: 6.5, fov: 58, sl: 0.4 },
  { t: 41.6, f: 'hero', az: -20, el: 8, d: 3.6, h: 0.3, fov: 55, sl: 0.4, label: 'Il regarde derrière lui… et ne voit pas le trou' },
  { t: 43.8, f: 'hole', az: -12, el: 12, d: 5.5, fov: 55, lk: 'hero' },
  { t: 45.35, f: 'hero', az: 25, el: 4, d: 3.3, h: 0.25, fov: 52, label: 'Suspendu dans le vide…' },
  { t: 45.95, f: 'hero', az: 70, el: -14, d: 2.6, h: 0.3, fov: 55 },
  { t: 46.55, f: 'hole', az: 40, el: 82, d: 8.5, lk: 'heroFall', fov: 55, label: '…il tombe dans le trou !' },
  { t: 47.8, f: 'hole', az: 110, el: 84, d: 5.5, lk: 'bottom', fov: 55 },
  { t: 49.8, f: 'bottom', az: 150, el: 72, d: 3.4, lk: 'bottom', fov: 58, label: 'Au fond du trou, étourdi' },
  { t: 52.2, f: 'bottom', az: 210, el: 22, d: 1.3, lk: 'opening', fov: 65, label: "Vue d'en bas : les loups le regardent, il commence à pleuvoir" },
  { t: 55.0, f: 'bottom', az: 270, el: 22, d: 1.3, lk: 'opening', fov: 65 },
  { t: 57.3, f: 'bottom', az: 345, el: 28, d: 2.0, lk: 'heroHead', fov: 68, label: 'Il se relève sous la pluie' },
  { t: 59.8, f: 'bottom', az: 395, el: 66, d: 3.4, lk: 'bottom', fov: 60, label: 'Les loups abandonnent' },
  { t: 62.6, f: 'hole', az: 440, el: 84, d: 13, lk: 'bottom', fov: 55 },
  { t: 66, f: 'hole', az: 500, el: 86, d: 42, lk: 'hole', fov: 55, label: 'La caméra s’élève au-dessus de la forêt — FIN' },
];
