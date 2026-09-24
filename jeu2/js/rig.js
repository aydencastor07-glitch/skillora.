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
const eq = (x, y, z, order = 'XYZ', out = new THREE.Quaternion()) => out.setFromEuler(_e.set(x, y, z, order));

export class RealHuman {
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

    const Ep = eq(g('hipX'), g('hipYaw'), g('hipRoll'));
    this.setBone(B.pelvis, Ep);
    const breath = Math.sin(t * 1.7 + (this.o.seed || 0) * 3) * 0.01;
    const Es = eq((g('spineX') + breath) / 3, g('spineY') / 3, g('spineZ') / 3);
    for (const n of [B.sp0, B.sp1, B.sp2]) this.setBone(n, Es);
    const As2 = Ep.clone().multiply(Es).multiply(Es).multiply(Es);
    const En = eq(g('neckX'), g('neckY'), 0);
    this.setBone(B.neck, En);
    for (const n of [B.lClav, B.rClav]) this.setBone(n, _q2.identity());

    // Jambes
    for (const s of ['l', 'r']) {
      this.setBone(B[s + 'Thigh'], eq(g(s + 'Hip'), g(s + 'HipY'), g(s + 'HipZ')));
      this.setBone(B[s + 'Calf'], eq(g(s + 'Knee'), 0, 0));
      this.setBone(B[s + 'Foot'], eq(g(s + 'Ank'), 0, 0));
    }

    // Bras : cinématique directe puis inverse
    this.root.updateMatrixWorld(true);
    const spineBase = this.charPos(B.sp0, new THREE.Vector3());
    // cibles monde -> repère du buste
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
      let Eu = eq(g(P + 'X', 0.05), g(P + 'Y'), g(P + 'Z', side * 0.1), 'ZXY');
      let el = g(P + 'El', -0.18);
      const w = Math.min(1, g(P + 'IK'));
      if (w > 0.001) {
        const S = this.charPos(B[s + 'Up'], new THREE.Vector3());
        const T = new THREE.Vector3(g(P + 'hx'), g(P + 'hy'), g(P + 'hz')).multiplyScalar(k).applyQuaternion(As2).add(spineBase);
        const [A, Bl] = this.len[s];
        const d = T.clone().sub(S);
        let L = Math.min(A + Bl - 0.002, Math.max(Math.abs(A - Bl) + 0.01, d.length()));
        const dn = d.normalize();
        const alpha = Math.acos(THREE.MathUtils.clamp((A * A + L * L - Bl * Bl) / (2 * A * L), -1, 1));
        const bend = Math.acos(THREE.MathUtils.clamp((A * A + Bl * Bl - L * L) / (2 * A * Bl), -1, 1));
        const pole = g(P + 'Pole', 0);
        const pv = new THREE.Vector3(side * (0.45 + pole), -1, -0.5 + pole * 0.5).normalize().applyQuaternion(As2);
        const axis = new THREE.Vector3().crossVectors(dn, pv);
        if (axis.lengthSq() < 1e-6) axis.set(1, 0, 0);
        axis.normalize();
        const u = dn.clone().applyAxisAngle(axis, alpha);
        const wv = dn.clone().sub(u.clone().multiplyScalar(dn.dot(u))).normalize();
        const Y = u.clone().negate(), X = new THREE.Vector3().crossVectors(Y, wv).normalize();
        const Wh = new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(X, Y, wv));
        const Eik = As2.clone().invert().multiply(Wh);
        Eu = Eu.slerp(Eik, w);
        el = el + (-(Math.PI - bend) - el) * w;
      }
      const adj = this.adj[s], adjI = adj.clone().invert();
      this.setBone(B[s + 'Up'], Eu.clone().multiply(adj));
      this.setBone(B[s + 'Fore'], adjI.clone().multiply(eq(el, g(P + 'ElY'), 0)).multiply(adj));
      this.setBone(B[s + 'Hand'], adjI.clone().multiply(eq(g(P + 'WrX'), g(P + 'WrY'), g(P + 'WrZ'))).multiply(adj));
      // doigts : légèrement repliés (poing / tenir un objet)
      const curl = g(P + 'Curl', 0.35);
      const Ec = adjI.clone().multiply(eq(0, 0, -side * curl)).multiply(adj);
      for (const fn of this.fingers[s]) this.setBone(fn, Ec);
    }

    // Tête + regard
    let hx = g('headX'), hy = g('headY'), hz = g('headZ');
    let ex = 0, ey = 0;
    if (look) {
      this.root.updateMatrixWorld(true);
      const np = this.charPos(B.neck, new THREE.Vector3());
      const An = As2.clone().multiply(En);
      const lp = this.root.worldToLocal(new THREE.Vector3(look.x, look.y, look.z));
      const d = lp.sub(np).applyQuaternion(An.invert());
      const yaw = Math.atan2(d.x, d.z);
      const pitch = -Math.atan2(d.y - 0.12, Math.hypot(d.x, d.z));
      const w = g('lookW', 0.75);
      const cy = THREE.MathUtils.clamp(yaw, -1.1, 1.1);
      hy += cy * w; hx += THREE.MathUtils.clamp(pitch, -0.6, 0.6) * w;
      ey = THREE.MathUtils.clamp(yaw - cy * w, -0.45, 0.45);
      ex = THREE.MathUtils.clamp(pitch - pitch * w, -0.3, 0.3);
    }
    this.setBone(B.head, eq(hx, hy, hz, 'YXZ'));
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
    const Ah = As2.clone().multiply(En).multiply(eq(hx, hy, hz, 'YXZ'));
    this.tears.forEach((tr, i) => {
      tr.visible = tears > 0.05;
      if (!tr.visible) return;
      const eye = this.charPos(i % 2 ? B.lEye : B.rEye, new THREE.Vector3());
      const ph = ((t * 0.45 + i * 0.37) % 1);
      const off = new THREE.Vector3((i % 2 ? 1 : -1) * 0.004, -0.012 - ph * 0.045, 0.012 + ph * 0.006).multiplyScalar(this.k).applyQuaternion(Ah);
      tr.position.copy(eye).add(off);
      tr.quaternion.copy(Ah);
    });
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
