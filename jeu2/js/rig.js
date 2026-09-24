// Personnages réalistes (Microsoft Rocketbox, licence MIT) pilotés par le même
// système de poses que le reste du jeu : squelette, cinématique inverse des bras,
// regard, et 52 expressions faciales (clignement, sourire, sourcils, mâchoire…).
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { clone as skClone } from 'three/addons/utils/SkeletonUtils.js';

const B = {
  pelvis: 'Bip01_Pelvis', sp0: 'Bip01_Spine', sp1: 'Bip01_Spine1', sp2: 'Bip01_Spine2', neck: 'Bip01_Neck', head: 'Bip01_Head',
  lClav: 'Bip01_L_Clavicle', lUp: 'Bip01_L_UpperArm', lFore: 'Bip01_L_Forearm', lHand: 'Bip01_L_Hand',
  rClav: 'Bip01_R_Clavicle', rUp: 'Bip01_R_UpperArm', rFore: 'Bip01_R_Forearm', rHand: 'Bip01_R_Hand',
  lThigh: 'Bip01_L_Thigh', lCalf: 'Bip01_L_Calf', lFoot: 'Bip01_L_Foot', rThigh: 'Bip01_R_Thigh', rCalf: 'Bip01_R_Calf', rFoot: 'Bip01_R_Foot',
  lEye: 'Bip01_LEye', rEye: 'Bip01_REye',
};

const cache = new Map();
const loader = new GLTFLoader();
export function loadModel(url) {
  if (!cache.has(url)) cache.set(url, new Promise((res, rej) => loader.load(url, (g) => res(g.scene), undefined, rej)));
  return cache.get(url);
}

const _q = new THREE.Quaternion(), _q2 = new THREE.Quaternion(), _v = new THREE.Vector3(), _v2 = new THREE.Vector3(), _m = new THREE.Matrix4();
const _e = new THREE.Euler();
const _I = new THREE.Quaternion();
const MOPARENT = { sp0: 'pelvis', sp1: 'sp0', sp2: 'sp1', neck: 'sp2', head: 'neck', lClav: 'sp2', rClav: 'sp2', lUp: 'lClav', rUp: 'rClav', lFore: 'lUp', rFore: 'rUp', lHand: 'lFore', rHand: 'rFore', lThigh: 'pelvis', rThigh: 'pelvis', lCalf: 'lThigh', rCalf: 'rThigh', lFoot: 'lCalf', rFoot: 'rCalf' };
const eq = (x, y, z, order = 'XYZ', out = new THREE.Quaternion()) => out.setFromEuler(_e.set(x, y, z, order));

// Échantillon d'un clip (interpolé entre deux images)
function sampleClip(c, t) {
  let f = t * c.fps;
  if (c.loop) f = ((f % c.frames) + c.frames) % c.frames; else f = Math.max(0, Math.min(c.frames - 1.001, f));
  const i = Math.floor(f), j = c.loop ? (i + 1) % c.frames : Math.min(c.frames - 1, i + 1), u = f - i;
  const B = c.names.length, q = {};
  c.names.forEach((n, b) => {
    const a = (i * B + b) * 4, d = (j * B + b) * 4;
    const qa = new THREE.Quaternion(c.q[a], c.q[a + 1], c.q[a + 2], c.q[a + 3]);
    const qb = new THREE.Quaternion(c.q[d], c.q[d + 1], c.q[d + 2], c.q[d + 3]);
    q[n] = qa.slerp(qb, u);
  });
  const p = new THREE.Vector3(c.p[i * 3], c.p[i * 3 + 1], c.p[i * 3 + 2]).lerp(new THREE.Vector3(c.p[j * 3], c.p[j * 3 + 1], c.p[j * 3 + 2]), u);
  return { q, p };
}

export class RealHuman {
  static clips = {};
  static async loadClips(names, base) {
    await Promise.all(names.map(async (n) => { RealHuman.clips[n] = await (await fetch(`${base}${n}.json`)).json(); }));
  }

  static async create(url, o = {}) {
    const src = await loadModel(url);
    return new RealHuman(skClone(src), o);
  }

  constructor(model, o) {
    this.o = { seed: 0, ...o };
    this.root = new THREE.Group();
    this.holder = new THREE.Group();
    this.holder.scale.setScalar(0.01);
    this.root.add(this.holder);
    this.holder.add(model);
    this.meshes = [];
    this.bones = {};
    model.traverse((n) => {
      if (n.isMesh) {
        n.castShadow = true; n.receiveShadow = true; n.frustumCulled = false;
        const ms = Array.isArray(n.material) ? n.material : [n.material];
        const nm = ms.map((m) => {
          const c = m.clone();
          c.roughness = /head/.test(c.name) ? 0.55 : 0.8;
          c.envMapIntensity = 0.6;
          if (c.map) c.map.anisotropy = 8;
          if (/pistol/.test(c.name)) c.visible = false;
          return c;
        });
        n.material = Array.isArray(n.material) ? nm : nm[0];
        this.meshes.push(n);
        for (const m of nm) if (/head/.test(m.name)) { this.headMat = m; this.baseHead = m.color.clone(); }
      }
      if (n.isBone || n.type === 'Bone' || /^Bip01/.test(n.name)) this.bones[n.name] = n;
    });
    // Repos : rotations "monde" de chaque os dans le repère du personnage
    this.root.updateMatrixWorld(true);
    const inv = new THREE.Matrix4().copy(this.holder.matrixWorld).invert();
    this.R = {}; this.L0 = {}; this.P0 = {};
    for (const [name, b] of Object.entries(this.bones)) {
      _m.multiplyMatrices(inv, b.matrixWorld);
      const p = new THREE.Vector3(), q = new THREE.Quaternion(), s = new THREE.Vector3();
      _m.decompose(p, q, s);
      this.R[name] = q; this.L0[name] = b.quaternion.clone();
      this.P0[name] = p.multiplyScalar(0.01);
    }
    const P0 = this.P0;
    this.height = P0[B.head].y + 0.12;
    this.k = this.height / 1.78;
    this.pelvisY = P0[B.pelvis].y;
    // Bras en T -> bras le long du corps
    this.adj = {};
    this.len = {};
    for (const s of ['l', 'r']) {
      const up = P0[B[s + 'Up']], fo = P0[B[s + 'Fore']], ha = P0[B[s + 'Hand']];
      const d = fo.clone().sub(up).normalize();
      this.adj[s] = new THREE.Quaternion().setFromUnitVectors(d, new THREE.Vector3(0, -1, 0));
      this.len[s] = [fo.distanceTo(up), ha.distanceTo(fo) + 0.075 * this.k];
    }
    this.fingers = { l: [], r: [] };
    for (const [name, b] of Object.entries(this.bones)) {
      const m = /^Bip01_([LR])_Finger([1-4])\d?$/.exec(name);
      if (m) this.fingers[m[1].toLowerCase()].push(name);
    }
    // Morphs du visage
    this.face = [];
    for (const m of this.meshes) if (m.morphTargetDictionary) this.face.push(m);
    // Larmes
    this.tears = [];
    const tm = new THREE.MeshPhysicalMaterial({ color: '#dff2ff', roughness: 0.05, transmission: 0.6, transparent: true, opacity: 0.8, clearcoat: 1 });
    for (let i = 0; i < 4; i++) {
      const t = new THREE.Mesh(new THREE.SphereGeometry(0.0032, 10, 8), tm);
      t.scale.set(1, 1.5, 0.7);
      t.visible = false;
      this.root.add(t);
      this.tears.push(t);
    }
    if (this.o.glasses) this.buildGlasses();
    // Apparence : recoloration des textures + volume de cheveux
    if (this.o.look) this.applyLook(this.o.look);
  }

  buildGlasses() {
    const g = (this.glasses = new THREE.Group());
    const m = new THREE.MeshStandardMaterial({ color: '#8c7a55', metalness: 0.9, roughness: 0.25 });
    const lens = new THREE.MeshPhysicalMaterial({ color: '#ffffff', transparent: true, opacity: 0.12, roughness: 0.05 });
    const add = (geo, mat, p, r, s) => { const x = new THREE.Mesh(geo, mat); x.position.set(...p); if (r) x.rotation.set(...r); if (s) x.scale.set(...s); g.add(x); return x; };
    for (const s of [-1, 1]) {
      add(new THREE.TorusGeometry(0.02, 0.0016, 6, 28), m, [s * 0.033, 0, 0], null, [1.15, 0.85, 1]);
      add(new THREE.CircleGeometry(0.02, 20), lens, [s * 0.033, 0, -0.001], null, [1.15, 0.85, 1]);
      add(new THREE.CylinderGeometry(0.0012, 0.0012, 0.1), m, [s * 0.058, 0.004, -0.05], [Math.PI / 2, 0, 0]);
    }
    add(new THREE.CylinderGeometry(0.0014, 0.0014, 0.02), m, [0, 0.006, 0], [0, 0, Math.PI / 2]);
    this.root.add(g);
  }

  applyLook(L) {
    for (const m of this.meshes) {
      const ms = Array.isArray(m.material) ? m.material : [m.material];
      for (const mat of ms) {
        if (!mat.map) continue;
        const part = /head/.test(mat.name) ? 'head' : /body/.test(mat.name) ? 'body' : null;
        const rules = part === 'head' ? L.hair && [{ kind: 'hair', ...L.hair }] : part === 'body' ? L.clothes : null;
        if (rules && rules.length) mat.map = recolorTexture(mat.map, rules);
      }
    }
    if (L.volume) this.buildHairVolume(L.volume);
  }

  // Boucles / chignon ajoutés sur la tête (suivent la tête à chaque image)
  buildHairVolume(V) {
    const g = (this.hairVol = new THREE.Group());
    this.root.add(g);
    const k = this.k * (V.scale || 1);
    const col = new THREE.Color(V.color);
    const mat = new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: 0.75 });
    let seed = 7;
    const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
    if (V.type === 'curls') {
      const n = 3400;
      const im = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1, 1), mat, n);
      const m4 = new THREE.Matrix4(), q = new THREE.Quaternion();
      let c = 0;
      for (let i = 0; i < n * 4 && c < n; i++) {
        const th = rnd() * 1.75, ph = rnd() * Math.PI * 2;
        const x = Math.sin(th) * Math.cos(ph), y = Math.cos(th), z = Math.sin(th) * Math.sin(ph);
        if (z > 0.2 && y < 0.5 + 0.2 * Math.abs(x)) continue; // visage dégagé
        if (y < -0.15) continue;
        const r = (0.1 + rnd() * 0.028) * (V.puff || 1);
        const s = (0.0068 + rnd() * 0.0058) * k;
        m4.compose(new THREE.Vector3(x * r * 0.95, y * r * 1.05 - 0.005, z * r * 1.05 - 0.01).multiplyScalar(k), q.random(), new THREE.Vector3(s, s, s));
        im.setMatrixAt(c, m4);
        im.setColorAt(c, col.clone().multiplyScalar(0.7 + rnd() * 0.5));
        c++;
      }
      im.count = c;
      im.castShadow = true;
      g.add(im);
    }
    if (V.type === 'bun') {
      // chignon fait de petites mèches torsadées
      const n = 420;
      const im = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1, 1), mat, n);
      const m4 = new THREE.Matrix4(), q = new THREE.Quaternion();
      for (let i = 0; i < n; i++) {
        const th = rnd() * Math.PI, ph = rnd() * Math.PI * 2;
        const rr = 0.036 * Math.cbrt(0.55 + rnd() * 0.45);
        const p = new THREE.Vector3(Math.sin(th) * Math.cos(ph) * rr, Math.cos(th) * rr * 1.1 + 0.122, Math.sin(th) * Math.sin(ph) * rr - 0.022);
        const s = (0.006 + rnd() * 0.005) * k;
        m4.compose(p.multiplyScalar(k), q.random(), new THREE.Vector3(s, s * 1.6, s));
        im.setMatrixAt(i, m4);
        im.setColorAt(i, col.clone().multiplyScalar(0.75 + rnd() * 0.45));
      }
      im.castShadow = true;
      g.add(im);
      const tie = new THREE.Mesh(new THREE.TorusGeometry(0.03 * k, 0.006 * k, 6, 16), new THREE.MeshStandardMaterial({ color: '#1b1b1b' }));
      tie.position.set(0, 0.09 * k, -0.02 * k); tie.rotation.x = Math.PI / 2 - 0.2; g.add(tie);
    }
  }

  // Applique une rotation "alignée personnage" E à un os
  setBone(name, E) {
    const b = this.bones[name];
    if (!b) return;
    const pr = this.R[b.parent && this.R[b.parent.name] ? b.parent.name : name];
    // L = Rp^-1 * E * Ri
    _q.copy(pr).invert().multiply(E).multiply(this.R[name]);
    b.quaternion.copy(_q);
  }

  // Repère aligné (personnage) cumulé d'une chaîne de rotations
  setPose(p = {}, f = {}, look = null, t = 0) {
    const g = (k, d = 0) => (p[k] === undefined ? d : p[k]);
    const k = this.k;
    // assis / debout : hauteur du bassin
    const sit = g('sit');
    this.holder.position.set(0, sit * (g('sitH', 0.56) - this.pelvisY) + g('hipY'), g('hipZ'));

    // ---- Orientation « alignée » absolue de chaque os (repère du personnage) ----
    // Mouvements réels (motion capture) : couches absolues ou additives
    const MO = this.sampleMocap(p.mo);
    const W = MO.w;
    const addQ = (n, w) => (MO.add[n] && w > 0 ? _I.clone().slerp(MO.add[n], Math.min(1, w)) : _I);
    const blend = (q, n, w) => (MO.abs[n] && w > 0 ? q.slerp(MO.abs[n], Math.min(1, w)) : q);
    const A = {};
    const breath = Math.sin(t * 1.7 + (this.o.seed || 0) * 3) * 0.01;
    A.pelvis = blend(eq(g('hipX'), g('hipYaw'), g('hipRoll')).multiply(addQ('pelvis', W.spine)), 'pelvis', W.pelvis);
    const Es = eq((g('spineX') + breath) / 3, g('spineY') / 3, g('spineZ') / 3);
    A.sp0 = blend(A.pelvis.clone().multiply(Es).multiply(addQ('sp0', W.spine)), 'sp0', W.spineAbs);
    A.sp1 = blend(A.sp0.clone().multiply(Es).multiply(addQ('sp1', W.spine)), 'sp1', W.spineAbs);
    A.sp2 = blend(A.sp1.clone().multiply(Es).multiply(addQ('sp2', W.spine)), 'sp2', W.spineAbs);
    const En = eq(g('neckX'), g('neckY'), 0);
    A.neck = blend(A.sp2.clone().multiply(En).multiply(addQ('neck', W.head)), 'neck', W.headAbs);
    for (const s of ['l', 'r']) {
      A[s + 'Clav'] = blend(A.sp2.clone(), s + 'Clav', W.arms);
      A[s + 'Thigh'] = blend(A.pelvis.clone().multiply(eq(g(s + 'Hip'), g(s + 'HipY'), g(s + 'HipZ'))), s + 'Thigh', W.legs);
      A[s + 'Calf'] = blend(A[s + 'Thigh'].clone().multiply(eq(g(s + 'Knee'), 0, 0)), s + 'Calf', W.legs);
      A[s + 'Foot'] = blend(A[s + 'Calf'].clone().multiply(eq(g(s + 'Ank'), 0, 0)), s + 'Foot', W.legs);
    }
    const PARENT = { sp0: 'pelvis', sp1: 'sp0', sp2: 'sp1', neck: 'sp2', head: 'neck', lClav: 'neck', rClav: 'neck', lUp: 'lClav', rUp: 'rClav', lFore: 'lUp', rFore: 'rUp', lHand: 'lFore', rHand: 'rFore', lThigh: 'sp0', rThigh: 'sp0', lCalf: 'lThigh', rCalf: 'rThigh', lFoot: 'lCalf', rFoot: 'rCalf' };
    const apply = (n) => {
      const pa = PARENT[n];
      this.setBone(B[n], pa ? A[pa].clone().invert().multiply(A[n]) : A[n]);
    };
    for (const n of ['pelvis', 'sp0', 'sp1', 'sp2', 'neck', 'lClav', 'rClav', 'lThigh', 'lCalf', 'lFoot', 'rThigh', 'rCalf', 'rFoot']) apply(n);
    if (MO.hip && W.root > 0) this.holder.position.y += MO.hip.y * this.pelvisY * W.root;
    const As2 = A.sp2;

    // Bras : pose calculée / mouvement réel, puis cinématique inverse (mains sur un objet)
    this.root.updateMatrixWorld(true);
    const spineBase = this.charPos(B.sp0, new THREE.Vector3());
    for (const s of ['l', 'r']) {
      const w = g(s + 'W');
      if (w > 0) {
        const v = this.root.worldToLocal(new THREE.Vector3(g(s + 'wx'), g(s + 'wy'), g(s + 'wz')));
        v.sub(spineBase).applyQuaternion(As2.clone().invert()).divideScalar(k);
        const kk = Math.min(1, w);
        p = { ...p, [s + 'IK']: Math.max(g(s + 'IK'), kk), [s + 'hx']: g(s + 'hx') * (1 - kk) + v.x * kk, [s + 'hy']: g(s + 'hy') * (1 - kk) + v.y * kk, [s + 'hz']: g(s + 'hz') * (1 - kk) + v.z * kk };
      }
    }
    for (const s of ['l', 'r']) {
      const side = s === 'l' ? 1 : -1;
      const P = s;
      const adj = this.adj[s], adjI = adj.clone().invert();
      let Eu = eq(g(P + 'X', 0.05), g(P + 'Y'), g(P + 'Z', side * 0.1), 'ZXY');
      let el = g(P + 'El', -0.18);
      A[s + 'Up'] = As2.clone().multiply(Eu).multiply(adj);
      A[s + 'Fore'] = A[s + 'Up'].clone().multiply(adjI).multiply(eq(el, g(P + 'ElY'), 0)).multiply(adj);
      A[s + 'Hand'] = A[s + 'Fore'].clone().multiply(adjI).multiply(eq(g(P + 'WrX'), g(P + 'WrY'), g(P + 'WrZ'))).multiply(adj);
      const wa = Math.min(1, W.arms * (1 - Math.min(1, g(P + 'IK'))));
      for (const n of ['Up', 'Fore', 'Hand']) blend(A[s + n], s + n, wa);
      const w = Math.min(1, g(P + 'IK'));
      if (w > 0.001) {
        const S = this.charPos(B[s + 'Up'], new THREE.Vector3());
        const T = new THREE.Vector3(g(P + 'hx'), g(P + 'hy'), g(P + 'hz')).multiplyScalar(k).applyQuaternion(As2).add(spineBase);
        const [La, Bl] = this.len[s];
        const d = T.clone().sub(S);
        let L = Math.min(La + Bl - 0.002, Math.max(Math.abs(La - Bl) + 0.01, d.length()));
        const dn = d.normalize();
        const alpha = Math.acos(THREE.MathUtils.clamp((La * La + L * L - Bl * Bl) / (2 * La * L), -1, 1));
        const bend = Math.acos(THREE.MathUtils.clamp((La * La + Bl * Bl - L * L) / (2 * La * Bl), -1, 1));
        const pole = g(P + 'Pole', 0);
        const pv = new THREE.Vector3(side * (0.45 + pole), -1, -0.5 + pole * 0.5).normalize().applyQuaternion(As2);
        const axis = new THREE.Vector3().crossVectors(dn, pv);
        if (axis.lengthSq() < 1e-6) axis.set(1, 0, 0);
        axis.normalize();
        const u = dn.clone().applyAxisAngle(axis, alpha);
        const wv = dn.clone().sub(u.clone().multiplyScalar(dn.dot(u))).normalize();
        const Y = u.clone().negate(), X = new THREE.Vector3().crossVectors(Y, wv).normalize();
        const Wh = new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(X, Y, wv));
        const upIK = Wh.clone().multiply(adj);
        const foreIK = upIK.clone().multiply(adjI).multiply(eq(-(Math.PI - bend), 0, 0)).multiply(adj);
        const handIK = foreIK.clone().multiply(adjI).multiply(eq(g(P + 'WrX'), g(P + 'WrY'), g(P + 'WrZ'))).multiply(adj);
        A[s + 'Up'].slerp(upIK, w); A[s + 'Fore'].slerp(foreIK, w); A[s + 'Hand'].slerp(handIK, w);
      }
      for (const n of ['Up', 'Fore', 'Hand']) apply(s + n);
      // doigts : repliés (poing / tenir un objet)
      const curl = g(P + 'Curl', 0.35);
      const Ec = adjI.clone().multiply(eq(0, 0, -side * curl)).multiply(adj);
      for (const fn of this.fingers[s]) this.setBone(fn, Ec);
    }

    // Tête + regard (+ petits mouvements réels additifs)
    let hx = g('headX'), hy = g('headY'), hz = g('headZ');
    let ex = 0, ey = 0;
    if (look) {
      this.root.updateMatrixWorld(true);
      const np = this.charPos(B.neck, new THREE.Vector3());
      const lp = this.root.worldToLocal(new THREE.Vector3(look.x, look.y, look.z));
      const d = lp.sub(np).applyQuaternion(A.neck.clone().invert());
      const yaw = Math.atan2(d.x, d.z);
      const pitch = -Math.atan2(d.y - 0.12, Math.hypot(d.x, d.z));
      const w = g('lookW', 0.75);
      const cy = THREE.MathUtils.clamp(yaw, -1.1, 1.1);
      hy += cy * w; hx += THREE.MathUtils.clamp(pitch, -0.6, 0.6) * w;
      ey = THREE.MathUtils.clamp(yaw - cy * w, -0.45, 0.45);
      ex = THREE.MathUtils.clamp(pitch - pitch * w, -0.3, 0.3);
    }
    A.head = blend(A.neck.clone().multiply(eq(hx, hy, hz, 'YXZ')).multiply(addQ('head', W.head)), 'head', W.headAbs);
    apply('head');
    ey += f.eyeY || 0; ex += f.eyeX || 0;
    for (const n of [B.lEye, B.rEye]) this.setBone(n, eq(ex, ey, 0, 'YXZ'));
    this.root.updateMatrixWorld(true);

    // Visage
    const blinkPh = (t + (this.o.seed || 0) * 1.37) % 3.9;
    const blink = blinkPh < 0.15 ? Math.sin((blinkPh / 0.15) * Math.PI) : 0;
    const smile = f.smile || 0;
    const M = {
      EyeBlinkLeft: Math.max(blink, f.closed || 0), EyeBlinkRight: Math.max(blink, f.closed || 0),
      EyeSquintLeft: (f.squint || 0) * 0.6, EyeSquintRight: (f.squint || 0) * 0.6,
      EyeWideLeft: (f.wide || 0) * 0.8, EyeWideRight: (f.wide || 0) * 0.8,
      BrowDownLeft: (f.angry || 0), BrowDownRight: (f.angry || 0),
      BrowInnerUp: Math.min(1, (f.sad || 0) + (f.browUp || 0) * 0.7),
      BrowOuterUpLeft: (f.browUp || 0) * 0.8, BrowOuterUpRight: (f.browUp || 0) * 0.8,
      JawOpen: Math.min(1, (f.open || 0) * 0.85),
      MouthLowerDownLeft: (f.open || 0) * 0.4 + (f.mwide || 0) * 0.3, MouthLowerDownRight: (f.open || 0) * 0.4 + (f.mwide || 0) * 0.3,
      MouthUpperUpLeft: (f.mwide || 0) * 0.4, MouthUpperUpRight: (f.mwide || 0) * 0.4,
      MouthStretchLeft: (f.mwide || 0) * 0.6, MouthStretchRight: (f.mwide || 0) * 0.6,
      MouthSmileLeft: Math.max(0, smile), MouthSmileRight: Math.max(0, smile),
      CheekSquintLeft: Math.max(0, smile) * 0.5, CheekSquintRight: Math.max(0, smile) * 0.5,
      MouthFrownLeft: Math.max(0, -smile) + (f.sad || 0) * 0.6, MouthFrownRight: Math.max(0, -smile) + (f.sad || 0) * 0.6,
      NoseSneerLeft: (f.angry || 0) * 0.35, NoseSneerRight: (f.angry || 0) * 0.35,
      MouthShrugLower: (f.sad || 0) * 0.4,
    };
    for (const m of this.face) {
      const d = m.morphTargetDictionary, inf = m.morphTargetInfluences;
      for (const key in d) inf[d[key]] = Math.min(1, Math.max(0, M[key] || 0));
    }
    if (this.headMat) this.headMat.color.copy(this.baseHead).lerp(new THREE.Color('#ff2f22'), (f.red || 0) * 0.62);

    // Larmes qui coulent
    const tears = f.tears || 0;
    const Ah = A.head.clone();
    this.tears.forEach((tr, i) => {
      tr.visible = tears > 0.05;
      if (!tr.visible) return;
      const eye = this.charPos(i % 2 ? B.lEye : B.rEye, new THREE.Vector3());
      const ph = ((t * 0.45 + i * 0.37) % 1);
      const off = new THREE.Vector3((i % 2 ? 1 : -1) * 0.004, -0.012 - ph * 0.045, 0.012 + ph * 0.006).multiplyScalar(this.k).applyQuaternion(Ah);
      tr.position.copy(eye).add(off);
      tr.quaternion.copy(Ah);
    });
    if (this.hairVol) {
      const hb = this.charPos(B.head, new THREE.Vector3());
      this.hairVol.position.copy(hb).add(new THREE.Vector3(0, 0.1, 0.012).multiplyScalar(this.k).applyQuaternion(Ah));
      this.hairVol.quaternion.copy(Ah);
    }
    if (this.glasses) {
      const gp = f.glasses === undefined ? 1 : f.glasses;
      this.glasses.visible = gp > 0.001;
      const l = this.charPos(B.lEye, new THREE.Vector3()), r = this.charPos(B.rEye, new THREE.Vector3());
      const c = l.add(r).multiplyScalar(0.5);
      const off = new THREE.Vector3(0, -(1 - gp) * 0.06, 0.028 + (1 - gp) * 0.09).applyQuaternion(Ah);
      this.glasses.position.copy(c).add(off);
      this.glasses.quaternion.copy(Ah).multiply(eq((1 - gp) * 0.5, 0, 0));
    }
  }

  // Échantillonne les couches de motion capture demandées par le scénario.
  // layer = { clip, t (s), w: { spine, spineAbs, pelvis, arms, legs, head, headAbs, root }, mode: 'add' | 'abs' }
  sampleMocap(layers) {
    const out = { abs: {}, add: {}, w: { spine: 0, spineAbs: 0, pelvis: 0, arms: 0, legs: 0, head: 0, headAbs: 0, root: 0 }, hip: null };
    if (!layers) return out;
    for (const L of Array.isArray(layers) ? layers : [layers]) {
      const c = RealHuman.clips[L.clip];
      if (!c || !(L.k > 0)) continue;
      const fr = sampleClip(c, L.t);
      const ref = L.mode === 'add' ? sampleClip(c, L.ref ?? 0) : null;
      for (const [part, w] of Object.entries(L.w || {})) out.w[part] = Math.max(out.w[part], w * L.k);
      for (const n in fr.q) {
        if (L.mode === 'add') {
          // mouvement local relatif à la première image : s'ajoute à la pose calculée
          const pa = MOPARENT[n];
          const loc = pa ? fr.q[pa].clone().invert().multiply(fr.q[n]) : fr.q[n].clone();
          const loc0 = pa ? ref.q[pa].clone().invert().multiply(ref.q[n]) : ref.q[n].clone();
          const d = loc0.invert().multiply(loc);
          out.add[n] = out.add[n] ? out.add[n].multiply(d) : d;
        } else {
          out.abs[n] = out.abs[n] ? out.abs[n].slerp(fr.q[n], L.k) : fr.q[n];
        }
      }
      if (L.mode !== 'add') out.hip = fr.p;
    }
    return out;
  }

  // position d'un os dans le repère du personnage (mètres)
  charPos(name, out) {
    this.bones[name].getWorldPosition(out);
    return this.root.worldToLocal(out);
  }
  headWorld(out = new THREE.Vector3()) {
    const l = this.bones[B.lEye].getWorldPosition(new THREE.Vector3());
    const r = this.bones[B.rEye].getWorldPosition(out);
    return out.copy(l).add(r).multiplyScalar(0.5);
  }
  handPoint(s, out) {
    const hb = this.bones[B[s + 'Hand']], fb = this.bones[B[s + 'Fore']];
    const h = hb.getWorldPosition(out), f = fb.getWorldPosition(_v2);
    const dir = _v.copy(h).sub(f).normalize();
    return out.addScaledVector(dir, 0.075 * this.k);
  }
  handQuat(s, out) {
    // repère "aligné" de la main dans le monde
    const hb = this.bones[B[s + 'Hand']];
    hb.getWorldQuaternion(out);
    return out.multiply(_q.copy(this.R[B[s + 'Hand']]).invert()).multiply(this.adj[s].clone().invert());
  }
}

// ---------- Recoloration des textures (cheveux, vêtements) ----------
const hex = (h) => { const c = new THREE.Color(h); return [c.r, c.g, c.b].map((v) => Math.pow(v, 1 / 2.2)); };
const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
const WAX = ['#e46b2a', '#2c6f86', '#f1d9b0', '#8a3b1c', '#1f3e52'].map(hex);
function waxAt(x, y) {
  const cell = ((Math.floor(x / 40) + Math.floor(y / 40)) % 5 + 5) % 5;
  const cx = (x % 40) - 20, cy = (y % 40) - 20, r = Math.hypot(cx, cy);
  if (Math.abs(cx) + Math.abs(cy) < 6) return WAX[(cell + 3) % 5];
  if (r < 9) return WAX[(cell + 2) % 5];
  if (r > 12 && r < 15) return hex('#f5e6c8');
  return WAX[cell];
}
function recolorTexture(tex, rules) {
  const img = tex.image, W = img.width, H = img.height;
  const cv = document.createElement('canvas');
  cv.width = W; cv.height = H;
  const g = cv.getContext('2d', { willReadFrequently: true });
  g.drawImage(img, 0, 0);
  const id = g.getImageData(0, 0, W, H), d = id.data;
  const L = (i) => (d[i] * 0.299 + d[i + 1] * 0.587 + d[i + 2] * 0.114) / 255;
  for (const r of rules) {
    const w = new Float32Array(W * H);
    let sumL = 0, n = 0;
    let ref = null, refL = 0;
    if (r.kind === 'hair') {
      const sx = Math.floor(r.sample[0] * W), sy = Math.floor(r.sample[1] * H);
      ref = [0, 0, 0]; let c = 0;
      for (let y = sy - 6; y <= sy + 6; y++) for (let x = sx - 6; x <= sx + 6; x++) { const i = (y * W + x) * 4; ref[0] += d[i] / 255; ref[1] += d[i + 1] / 255; ref[2] += d[i + 2] / 255; c++; }
      ref = ref.map((v) => v / c);
      refL = ref[0] * 0.299 + ref[1] * 0.587 + ref[2] * 0.114;
    }
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const p = y * W + x, i = p * 4, u = x / W, v = y / H;
      let m = 0;
      if (r.kind === 'hue') {
        const R = d[i] / 255, G = d[i + 1] / 255, Bc = d[i + 2] / 255;
        const mx = Math.max(R, G, Bc), mn = Math.min(R, G, Bc), dd = mx - mn + 1e-6;
        let h = mx === R ? ((G - Bc) / dd) % 6 : mx === G ? (Bc - R) / dd + 2 : (R - G) / dd + 4;
        h = (h * 60 + 360) % 360;
        const sat = dd / (mx + 1e-6);
        const inRegion = (u > 0.33 && u < 0.67) || v < (r.maxV || 0.6);
        if (inRegion) m = smooth(r.h[0] - 12, r.h[0], h) * (1 - smooth(r.h[1], r.h[1] + 12, h)) * smooth(r.s * 0.5, r.s, sat);
      } else {
        const l = L(i);
        const ch = Math.hypot(d[i] / 255 / (l + 0.08) - ref[0] / (refL + 0.08), d[i + 1] / 255 / (l + 0.08) - ref[1] / (refL + 0.08), d[i + 2] / 255 / (l + 0.08) - ref[2] / (refL + 0.08));
        const dist = ch * 0.35 + Math.abs(l - refL) * 1.2;
        m = 1 - smooth(r.t0 ?? 0.15, r.t1 ?? 0.35, dist);
        if (r.loose) m = Math.max(m, 0.9);
        // visage et oreilles protégés, cheveux seulement dans le bas de la texture
        const fe = ((u - 0.5) / 0.27) ** 2 + ((v - 0.64) / (r.faceRy || 0.21)) ** 2;
        m *= smooth(0.85, 1.15, fe) * smooth(0.5, 0.6, v);
        for (const ex of [0.25, 0.75]) m *= smooth(0.03, 0.06, Math.hypot(u - ex, v - 0.72));
      }
      w[p] = m;
      if (m > 0.5) { sumL += L(i); n++; }
    }
    const baseL = r.kind === 'hair' ? Math.max(0.05, refL) : Math.max(0.05, (sumL / Math.max(1, n)) * 1.05);
    const tgt = r.color ? hex(r.color) : null;
    for (let p = 0; p < W * H; p++) {
      const m = w[p]; if (m <= 0.001) continue;
      const i = p * 4, k = Math.min(1.6, L(i) / baseL);
      const c = r.pattern === 'wax' ? waxAt(p % W, Math.floor(p / W)) : tgt;
      for (let j = 0; j < 3; j++) d[i + j] = d[i + j] * (1 - m) + Math.min(255, c[j] * k * 255) * m;
    }
  }
  g.putImageData(id, 0, 0);
  const t = new THREE.CanvasTexture(cv);
  t.flipY = tex.flipY; t.colorSpace = tex.colorSpace; t.wrapS = tex.wrapS; t.wrapT = tex.wrapT; t.anisotropy = 8;
  return t;
}
