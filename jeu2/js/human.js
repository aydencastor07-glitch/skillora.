// Personnages semi-réalistes construits en code : corps articulé, yeux 3D
// (regard, clignements), sourcils, bouche dessinée animée, larmes, rougeur.
import * as THREE from 'three';

// ---------- Géométrie de la tête ----------
// Déforme une sphère unité en crâne/visage humain.
function shapeHead(x, y, z) {
  if (y < 0) { const t = -y; x *= 1 - 0.28 * t * t; z *= 1 - 0.08 * t * t; }
  if (y < -0.55 && z > 0) z += 0.1 * (-y - 0.55) * z;
  if (z > 0) z *= 0.93 + 0.06 * (1 - Math.abs(x));
  if (z < 0) z *= 1.08;
  const brow = Math.exp(-(((y - 0.3) / 0.12) ** 2)) * Math.exp(-((x / 0.55) ** 2)) * Math.max(0, z);
  z += 0.045 * brow;
  const sock = Math.exp(-(((Math.abs(x) - 0.41) / 0.17) ** 2 + ((y - 0.1) / 0.13) ** 2)) * Math.max(0, z);
  z -= 0.055 * sock;
  const cheek = Math.exp(-(((y + 0.12) / 0.2) ** 2)) * Math.exp(-(((Math.abs(x) - 0.5) / 0.22) ** 2)) * Math.max(0, z);
  z += 0.04 * cheek;
  return [x * 0.079, y * 0.115, z * 0.1];
}
function headGeo(seg = 56) {
  const g = new THREE.SphereGeometry(1, seg, Math.round(seg * 0.75));
  const p = g.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const [x, y, z] = shapeHead(p.getX(i), p.getY(i), p.getZ(i));
    p.setXYZ(i, x, y, z);
  }
  g.computeVertexNormals();
  return g;
}
const HEAD_GEO = headGeo();

// Zone du visage (bouche, larmes, rougeurs) : même forme, un poil devant la peau.
const FACE = { p0: Math.PI / 2 - 0.95, pl: 1.9, t0: Math.PI * 0.36, tl: Math.PI * 0.55 };
const FACE_GEO = (() => {
  const g = new THREE.SphereGeometry(1.012, 40, 32, FACE.p0, FACE.pl, FACE.t0, FACE.tl);
  const p = g.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const [x, y, z] = shapeHead(p.getX(i) / 1.012, p.getY(i) / 1.012, p.getZ(i) / 1.012);
    p.setXYZ(i, x * 1.012, y * 1.012, z * 1.012 + 0.0008);
  }
  g.computeVertexNormals();
  return g;
})();
// coordonnées unité du visage -> pixels du canvas du visage
const FW = 512, FH = 512;
function facePx(x, y) {
  const th = Math.acos(Math.max(-1, Math.min(1, y)));
  const st = Math.sin(th) || 1e-3;
  const ph = Math.acos(Math.max(-1, Math.min(1, -x / st)));
  return [((ph - FACE.p0) / FACE.pl) * FW, ((th - FACE.t0) / FACE.tl) * FH];
}

// Cuir chevelu : calotte qui suit le crâne, ligne frontale découpée
function hairCapGeo(scale = 1.05, hairline = 0.5, sideDown = -0.05, back = 0.75) {
  const g = new THREE.SphereGeometry(1, 48, 36, 0, Math.PI * 2, 0, Math.PI * back);
  const p = g.attributes.position;
  for (let i = 0; i < p.count; i++) {
    let x = p.getX(i), y = p.getY(i), z = p.getZ(i);
    const ax = Math.abs(x);
    const hl = ax > 0.72 ? sideDown : hairline + 0.12 * ax;
    let k = scale;
    if (z > 0.15 && y < hl) k = 0.9; // cachée sous la peau -> ligne de cheveux
    if (z > -0.35 && y < sideDown) k = 0.9; // pas sur les joues
    if (y < -0.45) k = 0.9;
    const [a, b, c] = shapeHead(x, y, z);
    p.setXYZ(i, a * k, b * k, c * k);
  }
  g.computeVertexNormals();
  return g;
}

function strandTex(color, dark) {
  const c = document.createElement('canvas');
  c.width = 256; c.height = 256;
  const g = c.getContext('2d');
  g.fillStyle = color; g.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 900; i++) {
    const x = Math.random() * 256, y = Math.random() * 256;
    g.strokeStyle = Math.random() < 0.5 ? dark : 'rgba(255,255,255,0.18)';
    g.globalAlpha = 0.25 + Math.random() * 0.35;
    g.lineWidth = 0.6 + Math.random();
    g.beginPath(); g.moveTo(x, y); g.lineTo(x + (Math.random() - 0.5) * 6, y + 18 + Math.random() * 24); g.stroke();
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(4, 2);
  return t;
}

function eyeTex(iris) {
  const c = document.createElement('canvas');
  c.width = 256; c.height = 128;
  const g = c.getContext('2d');
  const grd = g.createLinearGradient(0, 0, 256, 0);
  grd.addColorStop(0, '#d9b8ad'); grd.addColorStop(0.1, '#f3eee8'); grd.addColorStop(0.4, '#f3eee8'); grd.addColorStop(0.5, '#e2cbc2'); grd.addColorStop(1, '#d9b8ad');
  g.fillStyle = grd; g.fillRect(0, 0, 256, 128);
  const cx = 64, cy = 64;
  const ig = g.createRadialGradient(cx, cy, 3, cx, cy, 21);
  ig.addColorStop(0, '#000'); ig.addColorStop(0.3, iris); ig.addColorStop(0.85, iris); ig.addColorStop(1, '#1a1410');
  g.fillStyle = ig;
  g.beginPath(); g.ellipse(cx, cy, 20, 20, 0, 0, Math.PI * 2); g.fill();
  g.strokeStyle = 'rgba(255,255,255,0.12)';
  for (let a = 0; a < Math.PI * 2; a += 0.2) {
    g.beginPath(); g.moveTo(cx + Math.cos(a) * 8, cy + Math.sin(a) * 8); g.lineTo(cx + Math.cos(a) * 18, cy + Math.sin(a) * 18); g.stroke();
  }
  g.fillStyle = '#050505';
  g.beginPath(); g.arc(cx, cy, 7.5, 0, Math.PI * 2); g.fill();
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

// Motif de chemise (wax / ethnique orange-bleu, comme la référence)
export function patternTex(kind, base) {
  const c = document.createElement('canvas');
  c.width = c.height = 256;
  const g = c.getContext('2d');
  g.fillStyle = base; g.fillRect(0, 0, 256, 256);
  if (kind === 'wax') {
    const cols = ['#e46b2a', '#2c6f86', '#f1d9b0', '#7a2b1c', '#1f3e52'];
    for (let y = 0; y < 256; y += 32) for (let x = 0; x < 256; x += 32) {
      const o = (y / 32) % 2 ? 16 : 0;
      g.fillStyle = cols[((x + y) / 32) % cols.length | 0];
      g.beginPath(); g.moveTo(x + o + 16, y); g.lineTo(x + o + 32, y + 16); g.lineTo(x + o + 16, y + 32); g.lineTo(x + o, y + 16); g.closePath(); g.fill();
      g.fillStyle = cols[(((x + y) / 32) + 2) % cols.length | 0];
      g.beginPath(); g.arc(x + o + 16, y + 16, 6, 0, Math.PI * 2); g.fill();
      g.strokeStyle = '#f5e6c8'; g.lineWidth = 1.5;
      g.beginPath(); g.arc(x + o + 16, y + 16, 10, 0, Math.PI * 2); g.stroke();
    }
  } else if (kind === 'knit') {
    g.globalAlpha = 0.08;
    for (let y = 0; y < 256; y += 3) { g.fillStyle = y % 6 ? '#000' : '#fff'; g.fillRect(0, y, 256, 1); }
  } else if (kind === 'denim') {
    g.globalAlpha = 0.12;
    for (let i = 0; i < 256; i += 2) { g.strokeStyle = i % 4 ? '#fff' : '#000'; g.beginPath(); g.moveTo(i, 0); g.lineTo(i + 40, 256); g.stroke(); }
  } else if (kind === 'fabric') {
    g.globalAlpha = 0.06;
    for (let i = 0; i < 2500; i++) { g.fillStyle = Math.random() < 0.5 ? '#000' : '#fff'; g.fillRect(Math.random() * 256, Math.random() * 256, 2, 2); }
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  return t;
}

function cloth(color, tex, rough = 0.85, rep = [3, 3]) {
  const m = new THREE.MeshStandardMaterial({ color, roughness: rough, metalness: 0 });
  if (tex) { const t = tex.clone(); t.needsUpdate = true; t.repeat.set(...rep); m.map = t; }
  return m;
}

// ---------- Helpers de construction ----------
function mesh(geo, mat, parent, pos, rot, scale) {
  const m = new THREE.Mesh(geo, mat);
  if (pos) m.position.set(...pos);
  if (rot) m.rotation.set(...rot);
  if (scale) m.scale.set(...scale);
  m.castShadow = true;
  m.receiveShadow = true;
  parent.add(m);
  return m;
}
const SPH = new THREE.SphereGeometry(1, 28, 20);
const SPH_LO = new THREE.SphereGeometry(1, 14, 10);
function cap(len, r) {
  const g = new THREE.CapsuleGeometry(r, len, 6, 14);
  g.translate(0, -len / 2, 0);
  return g;
}
function taper(len, r0, r1) {
  const g = new THREE.CylinderGeometry(r1, r0, len, 16, 1);
  g.translate(0, -len / 2, 0);
  return g;
}

// Buste : profil de révolution aplati
function torsoGeo(w = 1, chest = 1, belly = 0) {
  const pts = [
    [0.155, -0.02], [0.165 + belly * 0.3, 0.08], [0.158 + belly, 0.2], [0.168 * chest, 0.33],
    [0.182 * chest, 0.44], [0.175 * chest, 0.5], [0.14, 0.55], [0.07, 0.585], [0.0, 0.59],
  ].map(([r, y]) => new THREE.Vector2(r * w, y));
  const g = new THREE.LatheGeometry(pts, 32);
  g.scale(1, 1, 0.64);
  g.computeVertexNormals();
  return g;
}

// ---------- Le personnage ----------
export class Human {
  constructor(o) {
    this.o = o = {
      scale: 1, headScale: 1, skin: '#c98e67', eyes: '#5a3b22', hair: 'short', hairColor: '#2a1d14',
      shirt: '#ffffff', shirtTex: null, shirtRep: [3, 3], sleeves: 'long', pants: '#2c3444', pantsTex: null,
      shoes: '#2a1f18', collar: false, tie: null, jacket: null, width: 1, belly: 0, brows: null, glasses: false,
      lips: null, ...o,
    };
    const root = (this.root = new THREE.Group());
    const body = (this.body = new THREE.Group());
    body.scale.setScalar(o.scale);
    root.add(body);
    const hips = (this.hips = new THREE.Group());
    hips.position.y = 0.95;
    body.add(hips);

    this.skinMat = new THREE.MeshPhysicalMaterial({
      color: o.skin, roughness: 0.58, metalness: 0, sheen: 0.35, sheenRoughness: 0.7, sheenColor: new THREE.Color('#ffcfb8'),
    });
    this.baseSkin = new THREE.Color(o.skin);
    const shirtMat = cloth(o.shirt, o.shirtTex, 0.9, o.shirtRep);
    const topMat = o.jacket ? cloth(o.jacket, patternTex('fabric', '#777'), 0.75, [4, 4]) : shirtMat;
    const pantsMat = cloth(o.pants, o.pantsTex || patternTex('fabric', '#888'), 0.9, [2, 4]);
    const shoeMat = new THREE.MeshStandardMaterial({ color: o.shoes, roughness: 0.45 });

    // Bassin + jambes
    mesh(SPH, pantsMat, hips, [0, 0.0, 0], null, [0.15 * o.width, 0.1, 0.105]);
    const mkLeg = (side) => {
      const hip = new THREE.Group();
      hip.position.set(side * 0.092 * o.width, -0.02, 0);
      hips.add(hip);
      mesh(taper(0.45, 0.085, 0.062), pantsMat, hip);
      mesh(SPH, pantsMat, hip, [0, 0, 0], null, [0.085, 0.07, 0.085]);
      const knee = new THREE.Group();
      knee.position.y = -0.44;
      hip.add(knee);
      mesh(SPH, pantsMat, knee, [0, 0, 0], null, [0.06, 0.06, 0.06]);
      mesh(taper(0.43, 0.058, 0.045), pantsMat, knee);
      const ank = new THREE.Group();
      ank.position.y = -0.44;
      knee.add(ank);
      mesh(SPH, shoeMat, ank, [0, -0.035, 0.045], null, [0.048, 0.042, 0.12]);
      mesh(new THREE.BoxGeometry(0.1, 0.02, 0.26), shoeMat, ank, [0, -0.07, 0.045]);
      return { hip, knee, ank };
    };
    this.lLeg = mkLeg(1);
    this.rLeg = mkLeg(-1);

    // Buste
    const spine = (this.spine = new THREE.Group());
    hips.add(spine);
    spine.position.y = 0.03;
    this.torso = mesh(torsoGeo(o.width, 1, o.belly), topMat, spine);
    if (o.jacket) {
      // chemise visible dans l'encolure + cravate
      mesh(new THREE.PlaneGeometry(0.11, 0.2), cloth(o.shirt), spine, [0, 0.47, 0.105], [-0.25, 0, 0]);
    }
    if (o.tie) {
      const tie = mesh(new THREE.BoxGeometry(0.045, 0.26, 0.012), cloth(o.tie, patternTex('fabric', '#555'), 0.6), spine, [0, 0.42, 0.112], [-0.12, 0, 0]);
      tie.castShadow = false;
      mesh(SPH, cloth(o.tie), spine, [0, 0.545, 0.1], null, [0.02, 0.018, 0.012]);
    }
    if (o.collar) {
      const cg = new THREE.TorusGeometry(0.06, 0.018, 8, 24);
      mesh(cg, topMat, spine, [0, 0.565, 0.005], [Math.PI / 2 - 0.25, 0, 0], [1.1, 1, 0.9]);
    }
    if (o.badge) {
      mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.006, 6), new THREE.MeshStandardMaterial({ color: '#d4af37', metalness: 0.9, roughness: 0.3 }), spine, [0.09, 0.44, 0.108], [Math.PI / 2 - 0.2, 0, 0]);
    }
    if (o.belt) mesh(new THREE.TorusGeometry(0.16, 0.022, 6, 28), new THREE.MeshStandardMaterial({ color: '#1a1a1a', roughness: 0.5 }), spine, [0, 0.0, 0], [Math.PI / 2, 0, 0], [o.width, 0.66, 1]);

    // Cou + tête
    const neck = (this.neck = new THREE.Group());
    neck.position.y = 0.55;
    spine.add(neck);
    mesh(taper(0.12, 0.052, 0.048).translate(0, 0.12, 0), this.skinMat, neck, [0, 0, 0.005]);
    const head = (this.head = new THREE.Group());
    head.position.set(0, 0.1, 0.012);
    head.scale.setScalar(o.headScale);
    head.rotation.order = 'YXZ';
    neck.add(head);
    const hc = (this.headCenter = new THREE.Group());
    hc.position.y = 0.105;
    head.add(hc);
    this.headMesh = mesh(HEAD_GEO, this.skinMat, hc);

    // oreilles, nez
    for (const s of [-1, 1]) mesh(SPH, this.skinMat, hc, [s * 0.077, 0.0, -0.008], [0, s * 0.35, 0], [0.011, 0.028, 0.02]);
    mesh(SPH, this.skinMat, hc, [0, -0.008, 0.094], [-0.3, 0, 0], [0.0085, 0.026, 0.012]);
    mesh(SPH, this.skinMat, hc, [0, -0.033, 0.103], null, [0.0105, 0.0095, 0.0095]);
    for (const s of [-1, 1]) mesh(SPH, this.skinMat, hc, [s * 0.0105, -0.036, 0.097], null, [0.0065, 0.0055, 0.006]);

    // Yeux 3D + paupières + cils
    const eyeMat = new THREE.MeshPhysicalMaterial({ map: eyeTex(o.eyes), roughness: 0.15, clearcoat: 1, clearcoatRoughness: 0.05 });
    const lidMat = this.skinMat;
    const lashMat = new THREE.MeshStandardMaterial({ color: '#141010', roughness: 0.8 });
    this.eyes = [];
    for (const s of [-1, 1]) {
      const e = new THREE.Group();
      e.position.set(s * 0.0325, 0.0125, 0.0775);
      hc.add(e);
      const ball = mesh(new THREE.SphereGeometry(0.0128, 32, 20), eyeMat, e);
      ball.castShadow = false;
      const upper = new THREE.Group();
      e.add(upper);
      mesh(new THREE.SphereGeometry(0.0138, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2), lidMat, upper).castShadow = false;
      const lash = mesh(new THREE.TorusGeometry(0.0138, 0.0011, 4, 24, Math.PI), lashMat, upper, [0, 0, 0], [Math.PI / 2, 0, 0]);
      lash.castShadow = false;
      const lower = new THREE.Group();
      lower.rotation.x = 0.36;
      e.add(lower);
      mesh(new THREE.SphereGeometry(0.0136, 24, 12, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2), lidMat, lower).castShadow = false;
      this.eyes.push({ g: e, ball, upper });
    }
    // Sourcils
    const browMat = new THREE.MeshStandardMaterial({ color: o.brows || o.hairColor, roughness: 0.9 });
    this.brows = [];
    for (const s of [-1, 1]) {
      const b = new THREE.Group();
      b.position.set(s * 0.034, 0.036, 0.0905);
      hc.add(b);
      const bm = mesh(new THREE.CapsuleGeometry(0.0028, 0.027, 4, 8), browMat, b, [0, 0, 0], [0, s * 0.35, Math.PI / 2 + s * 0.06]);
      bm.castShadow = false;
      this.brows.push({ g: b, s });
    }
    // Zone du visage dessinée (bouche, larmes, rougeurs)
    this.faceCanvas = document.createElement('canvas');
    this.faceCanvas.width = FW; this.faceCanvas.height = FH;
    this.faceTex = new THREE.CanvasTexture(this.faceCanvas);
    this.faceTex.colorSpace = THREE.SRGBColorSpace;
    const fm = new THREE.MeshStandardMaterial({ map: this.faceTex, transparent: true, roughness: 0.5, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2 });
    const fmesh = mesh(FACE_GEO, fm, hc);
    fmesh.castShadow = false;
    fmesh.renderOrder = 2;
    this.lips = o.lips || new THREE.Color(o.skin).lerp(new THREE.Color('#9b3f3f'), 0.45).getStyle();
    this.faceKey = '';

    this.buildHair(hc);
    if (o.glasses) this.buildGlasses();

    // Bras
    const armMat = o.sleeves === 'long' ? topMat : this.skinMat;
    const mkArm = (side) => {
      const sh = new THREE.Group();
      sh.position.set(side * 0.17 * o.width, 0.475, -0.01);
      sh.rotation.order = 'ZXY';
      spine.add(sh);
      mesh(SPH, topMat, sh, [-Math.sign(side) * 0.01, -0.02, 0], null, [0.058, 0.06, 0.056]);
      mesh(taper(0.29, 0.052, 0.042), armMat, sh);
      if (o.sleeves === 'short') mesh(taper(0.15, 0.064, 0.058), topMat, sh);
      const el = new THREE.Group();
      el.position.y = -0.29;
      sh.add(el);
      mesh(SPH, armMat, el, null, null, [0.043, 0.043, 0.043]);
      const foreMat = o.sleeves === 'long' ? topMat : this.skinMat;
      mesh(taper(0.25, 0.042, 0.032), foreMat, el);
      const hand = new THREE.Group();
      hand.position.y = -0.255;
      el.add(hand);
      if (o.sleeves === 'long') mesh(taper(0.03, 0.036, 0.034).translate(0, 0.02, 0), cloth(o.jacket ? o.shirt : o.shirt), hand);
      mesh(SPH, this.skinMat, hand, [0, -0.045, 0.004], null, [0.036, 0.048, 0.017]);
      mesh(SPH, this.skinMat, hand, [0, -0.095, 0.012], [0.35, 0, 0], [0.034, 0.038, 0.015]);
      mesh(new THREE.CapsuleGeometry(0.0105, 0.035, 4, 8), this.skinMat, hand, [side * 0.03, -0.045, 0.02], [0.5, 0, side * 0.5]);
      return { sh, el, hand };
    };
    this.lArm = mkArm(1);
    this.rArm = mkArm(-1);

    this.v = new THREE.Vector3();
    this.q = new THREE.Quaternion();
  }

  buildHair(hc) {
    const o = this.o;
    const col = new THREE.Color(o.hairColor);
    const dark = col.clone().multiplyScalar(0.6).getStyle();
    const hm = new THREE.MeshStandardMaterial({ color: o.hairColor, roughness: 0.62, map: strandTex('#ffffff', dark) });
    this.hairMat = hm;
    const h = new THREE.Group();
    hc.add(h);
    this.hair = h;
    const add = (g, pos, rot, sc) => mesh(g, hm, h, pos, rot, sc);
    switch (o.hair) {
      case 'bun': {
        add(hairCapGeo(1.035, 0.52, 0.0, 0.7));
        add(SPH, [0, 0.118, -0.03], null, [0.045, 0.04, 0.045]);
        add(SPH, [0.018, 0.14, -0.02], null, [0.028, 0.026, 0.028]);
        add(SPH, [-0.02, 0.135, -0.04], null, [0.026, 0.024, 0.026]);
        mesh(new THREE.TorusGeometry(0.03, 0.006, 6, 16), new THREE.MeshStandardMaterial({ color: '#1b1b1b' }), h, [0, 0.1, -0.03], [Math.PI / 2 - 0.3, 0, 0]);
        break;
      }
      case 'wavy': {
        add(hairCapGeo(1.08, 0.62, -0.1, 0.72));
        const rnd = mulberry(5);
        for (let i = 0; i < 70; i++) {
          const th = 0.08 + rnd() * 1.25, ph = rnd() * Math.PI * 2;
          let x = Math.sin(th) * Math.cos(ph), y = Math.cos(th), z = Math.sin(th) * Math.sin(ph);
          if (z > 0.3 && y < 0.45) { y = 0.45 + rnd() * 0.25; }
          const [a, b, c] = shapeHead(x, y, z);
          const m = add(SPH, [a * 1.09, b * 1.07, c * 1.09], [rnd(), rnd() * 6, rnd()], [0.018 + rnd() * 0.008, 0.011, 0.03]);
          m.lookAt(0, 0, 0);
        }
        // mèches sur le front
        for (let i = 0; i < 5; i++) {
          const x = -0.5 + i * 0.25;
          const [a, b, c] = shapeHead(x, 0.5, Math.sqrt(Math.max(0, 1 - x * x - 0.25)));
          add(SPH, [a * 1.05, b * 1.02, c * 1.08], [0.6, x, 0.3 * x], [0.02, 0.012, 0.035]);
        }
        break;
      }
      case 'curly': {
        add(hairCapGeo(1.04, 0.58, 0.05, 0.72));
        const rnd = mulberry(9);
        const n = 2600;
        const im = new THREE.InstancedMesh(SPH_LO, hm, n);
        const m4 = new THREE.Matrix4();
        let k = 0;
        for (let i = 0; i < n * 3 && k < n; i++) {
          const th = rnd() * 1.45, ph = rnd() * Math.PI * 2;
          const x = Math.sin(th) * Math.cos(ph), y = Math.cos(th), z = Math.sin(th) * Math.sin(ph);
          const ax = Math.abs(x);
          if (z > 0.25 && y < (ax > 0.7 ? 0.05 : 0.55 + 0.1 * ax)) continue;
          if (z < -0.2 && y < -0.1) continue;
          const [a, b, c] = shapeHead(x, y, z);
          const r = 1.05 + rnd() * 0.12;
          const s = 0.0048 + rnd() * 0.0032;
          m4.compose(new THREE.Vector3(a * r, b * r + 0.004, c * r), new THREE.Quaternion(), new THREE.Vector3(s, s, s));
          im.setMatrixAt(k, m4);
          im.setColorAt(k, col.clone().multiplyScalar(0.8 + rnd() * 0.4));
          k++;
        }
        im.count = k;
        im.castShadow = true;
        h.add(im);
        break;
      }
      case 'grey': {
        add(hairCapGeo(1.03, 0.68, 0.0, 0.72));
        const rnd = mulberry(3);
        for (let i = 0; i < 22; i++) {
          const ph = rnd() * Math.PI * 2, th = 0.9 + rnd() * 0.5;
          const x = Math.sin(th) * Math.cos(ph), y = Math.cos(th), z = Math.sin(th) * Math.sin(ph);
          if (z > 0.1) continue;
          const [a, b, c] = shapeHead(x, y, z);
          add(SPH, [a * 1.06, b * 1.04, c * 1.06], [rnd(), rnd(), rnd()], [0.022, 0.014, 0.03]);
        }
        break;
      }
      case 'bald':
        break;
      default:
        add(hairCapGeo(1.04, 0.55, 0.0, 0.7));
    }
    if (o.hat) {
      const hatMat = new THREE.MeshStandardMaterial({ color: o.hat, roughness: 0.7 });
      mesh(new THREE.CylinderGeometry(0.1, 0.1, 0.075, 28), hatMat, h, [0, 0.105, -0.002], [-0.08, 0, 0]);
      mesh(new THREE.SphereGeometry(0.1, 28, 12, 0, Math.PI * 2, 0, Math.PI / 2), hatMat, h, [0, 0.14, -0.005], [-0.08, 0, 0], [1, 0.45, 1.05]);
      mesh(new THREE.CylinderGeometry(0.07, 0.07, 0.008, 20, 1, false, -Math.PI / 2, Math.PI), hatMat, h, [0, 0.07, 0.07], [-0.2, 0, 0], [1, 1, 0.9]);
      mesh(new THREE.CylinderGeometry(0.015, 0.015, 0.004, 6), new THREE.MeshStandardMaterial({ color: '#d4af37', metalness: 0.9, roughness: 0.3 }), h, [0, 0.12, 0.098], [Math.PI / 2 - 0.1, 0, 0]);
    }
  }

  buildGlasses() {
    const g = (this.glasses = new THREE.Group());
    const m = new THREE.MeshStandardMaterial({ color: '#b8a57a', metalness: 0.9, roughness: 0.25 });
    const lens = new THREE.MeshPhysicalMaterial({ color: '#ffffff', transparent: true, opacity: 0.12, roughness: 0.05, transmission: 0 });
    for (const s of [-1, 1]) {
      mesh(new THREE.TorusGeometry(0.019, 0.0017, 6, 28), m, g, [s * 0.033, 0, 0], null, [1.15, 0.9, 1]).castShadow = false;
      mesh(new THREE.CircleGeometry(0.019, 20), lens, g, [s * 0.033, 0, -0.001], null, [1.15, 0.9, 1]).castShadow = false;
      mesh(new THREE.CylinderGeometry(0.0012, 0.0012, 0.1), m, g, [s * 0.056, 0.004, -0.05], [Math.PI / 2, 0, 0]).castShadow = false;
    }
    mesh(new THREE.CylinderGeometry(0.0014, 0.0014, 0.02), m, g, [0, 0.006, 0], [0, 0, Math.PI / 2]).castShadow = false;
    this.headCenter.add(g);
    this.glassesOn = new THREE.Vector3(0, 0.012, 0.103);
    g.position.copy(this.glassesOn);
  }

  // ---------- Animation ----------
  // p : angles du squelette ; f : visage ; look : point regardé (monde)
  setPose(p = {}, f = {}, look = null, t = 0) {
    const g = (k, d = 0) => (p[k] === undefined ? d : p[k]); // p peut être enrichi par l'IK monde
    this.hips.position.y = 0.95 + g('hipY');
    this.hips.position.z = g('hipZ');
    this.hips.rotation.set(g('hipX'), g('hipYaw'), g('hipRoll'));
    const breath = Math.sin(t * 1.7 + this.o.scale * 10) * 0.012;
    this.spine.rotation.set(g('spineX') + breath, g('spineY'), g('spineZ'));
    this.neck.rotation.set(g('neckX'), g('neckY'), 0);
    const arm = (a, P) => {
      a.sh.rotation.set(g(P + 'X', 0.05), g(P + 'Y'), g(P + 'Z', P === 'l' ? 0.1 : -0.1));
      a.el.rotation.set(g(P + 'El', -0.18), g(P + 'ElY'), 0);
      a.hand.rotation.set(g(P + 'WrX'), g(P + 'WrY'), g(P + 'WrZ'));
    };
    arm(this.lArm, 'l'); arm(this.rArm, 'r');
    // Cinématique inverse : la main va au point demandé (repère du buste, ou monde)
    if (g('lW') > 0 || g('rW') > 0) {
      this.root.updateMatrixWorld(true);
      for (const [P, s] of [['l', 1], ['r', -1]]) {
        const w = g(P + 'W');
        if (w <= 0) continue;
        const v = this.spine.worldToLocal(new THREE.Vector3(g(P + 'wx'), g(P + 'wy'), g(P + 'wz')));
        const k = Math.min(1, w);
        p = { ...p, [P + 'IK']: Math.max(g(P + 'IK'), k), [P + 'hx']: g(P + 'hx') * (1 - k) + v.x * k, [P + 'hy']: g(P + 'hy') * (1 - k) + v.y * k, [P + 'hz']: g(P + 'hz') * (1 - k) + v.z * k };
      }
    }
    this.ik(this.lArm, 1, g('lIK'), g('lhx'), g('lhy'), g('lhz'), g('lPole', 0));
    this.ik(this.rArm, -1, g('rIK'), g('rhx'), g('rhy'), g('rhz'), g('rPole', 0));
    const leg = (l, P) => {
      l.hip.rotation.set(g(P + 'Hip'), g(P + 'HipY'), g(P + 'HipZ'));
      l.knee.rotation.x = g(P + 'Knee');
      l.ank.rotation.x = g(P + 'Ank');
    };
    leg(this.lLeg, 'l'); leg(this.rLeg, 'r');

    // Tête : pose + regard
    let hx = g('headX'), hy = g('headY'), hz = g('headZ');
    let ex = 0, ey = 0;
    if (look) {
      this.root.updateMatrixWorld(true);
      this.neck.getWorldPosition(this.v);
      const nq = this.neck.getWorldQuaternion(this.q).invert();
      const d = new THREE.Vector3(look.x, look.y, look.z).sub(this.v).applyQuaternion(nq);
      const yaw = Math.atan2(d.x, d.z);
      const pitch = -Math.atan2(d.y - 0.12, Math.hypot(d.x, d.z));
      const w = g('lookW', 0.75);
      const cy = Math.max(-1.1, Math.min(1.1, yaw));
      hy += cy * w; hx += Math.max(-0.6, Math.min(0.6, pitch)) * w;
      ey = Math.max(-0.45, Math.min(0.45, yaw - cy * w));
      ex = Math.max(-0.3, Math.min(0.3, pitch - pitch * w));
    }
    this.head.rotation.set(hx, hy, hz);
    ey += (f.eyeY || 0); ex += (f.eyeX || 0);
    // clignement
    const blinkPh = (t + this.o.scale * 3.1 + (this.o.seed || 0)) % 3.7;
    const blink = blinkPh < 0.14 ? Math.sin((blinkPh / 0.14) * Math.PI) : 0;
    let lid = -0.45 + 0.3 * (f.squint || 0) - 0.3 * (f.wide || 0);
    lid = lid + (0.45 - lid) * Math.max(blink, f.closed || 0);
    for (const e of this.eyes) {
      e.ball.rotation.set(ex, ey, 0);
      e.upper.rotation.x = lid;
    }
    for (const b of this.brows) {
      b.g.position.y = 0.036 + 0.006 * (f.browUp || 0);
      b.g.rotation.z = b.s * -0.35 * (f.angry || 0) + b.s * 0.3 * (f.sad || 0);
    }
    if (this.glasses) {
      const gp = f.glasses === undefined ? 1 : f.glasses;
      this.glasses.visible = gp > 0.001;
      this.glasses.position.set(this.glassesOn.x, this.glassesOn.y - (1 - gp) * 0.05, this.glassesOn.z + (1 - gp) * 0.09);
      this.glasses.rotation.set((1 - gp) * 0.5, 0, 0);
    }
    // Rougeur de tout le visage
    const red = f.red || 0;
    this.skinMat.color.copy(this.baseSkin).lerp(new THREE.Color('#d8332a'), red * 0.55);
    this.drawFace(f, t);
  }

  drawFace(f, t) {
    const open = Math.round((f.open || 0) * 20) / 20;
    const smile = Math.round((f.smile || 0) * 10) / 10;
    const wide = Math.round((f.mwide || 0) * 10) / 10;
    const tears = Math.round((f.tears || 0) * 20) / 20;
    const tearPh = tears > 0 ? Math.floor(t * 8) % 16 : 0;
    const blush = Math.round((f.red || 0) * 10) / 10;
    const key = [open, smile, wide, tears, tearPh, blush, f.teeth ? 1 : 0].join('|');
    if (key === this.faceKey) return;
    this.faceKey = key;
    const g = this.faceCanvas.getContext('2d');
    g.clearRect(0, 0, FW, FH);
    // rougeurs
    if (blush > 0) {
      for (const s of [-1, 1]) {
        const [x, y] = facePx(s * 0.45, -0.18);
        const rg = g.createRadialGradient(x, y, 5, x, y, 90);
        rg.addColorStop(0, `rgba(200,30,30,${0.55 * blush})`);
        rg.addColorStop(1, 'rgba(200,30,30,0)');
        g.fillStyle = rg; g.fillRect(0, 0, FW, FH);
      }
    }
    // pli naso-labial discret
    g.strokeStyle = 'rgba(80,40,30,0.05)'; g.lineWidth = 3;
    for (const s of [-1, 1]) {
      const [a, b] = facePx(s * 0.2, -0.28), [c, d] = facePx(s * 0.3, -0.52);
      g.beginPath(); g.moveTo(a, b); g.quadraticCurveTo(c + s * 6, (b + d) / 2, c, d); g.stroke();
    }
    // bouche
    const [mx, my] = facePx(0, -0.56);
    const w = 62 * (1 + 0.3 * wide + 0.12 * Math.max(0, smile));
    const h = 75 * open;
    const cy = -smile * 14;
    g.save();
    g.filter = 'blur(0.8px)';
    if (h > 1) {
      g.fillStyle = '#2a0b0b';
      g.beginPath();
      g.moveTo(mx - w, my + cy);
      g.quadraticCurveTo(mx, my - h * 0.45 - 4, mx + w, my + cy);
      g.quadraticCurveTo(mx, my + h + 6, mx - w, my + cy);
      g.fill();
      if (f.teeth !== false) {
        g.save(); g.clip();
        g.fillStyle = '#efeae0';
        g.fillRect(mx - w * 0.8, my - h * 0.5 - 8, w * 1.6, Math.min(24, h * 0.5) + 8);
        if (h > 18) { g.fillRect(mx - w * 0.6, my + h - 4, w * 1.2, 10); }
        g.fillStyle = '#b8484c';
        g.beginPath(); g.ellipse(mx, my + h * 0.8, w * 0.5, h * 0.3, 0, 0, Math.PI * 2); g.fill();
        g.restore();
      }
    }
    // lèvres
    g.fillStyle = this.lips;
    g.beginPath();
    g.moveTo(mx - w, my + cy);
    g.quadraticCurveTo(mx - w * 0.5, my - 17 - h * 0.45, mx, my - 11 - h * 0.45);
    g.quadraticCurveTo(mx + w * 0.5, my - 17 - h * 0.45, mx + w, my + cy);
    g.quadraticCurveTo(mx, my - h * 0.45 + 2, mx - w, my + cy);
    g.fill();
    g.beginPath();
    g.moveTo(mx - w, my + cy);
    g.quadraticCurveTo(mx, my + h + 5, mx + w, my + cy);
    g.quadraticCurveTo(mx, my + h + 26, mx - w, my + cy);
    g.fill();
    g.strokeStyle = 'rgba(60,15,15,0.7)'; g.lineWidth = 2.5;
    if (h <= 1) { g.beginPath(); g.moveTo(mx - w, my + cy); g.quadraticCurveTo(mx, my + 2, mx + w, my + cy); g.stroke(); }
    g.restore();
    // larmes
    if (tears > 0) {
      for (const s of [-1, 1]) {
        const [x0, y0] = facePx(s * 0.36, -0.02), [x1, y1] = facePx(s * 0.42, -0.45);
        g.strokeStyle = `rgba(210,235,255,${0.55 * tears})`; g.lineWidth = 5;
        g.beginPath(); g.moveTo(x0, y0); g.quadraticCurveTo(x0 + s * 6, (y0 + y1) / 2, x1, y1); g.stroke();
        g.strokeStyle = `rgba(255,255,255,${0.7 * tears})`; g.lineWidth = 1.5;
        g.beginPath(); g.moveTo(x0 - 1, y0); g.quadraticCurveTo(x0 + s * 6 - 1, (y0 + y1) / 2, x1 - 1, y1); g.stroke();
        const k = ((tearPh + (s > 0 ? 8 : 0)) % 16) / 16;
        const dx = x0 + (x1 - x0) * k + s * 3 * Math.sin(k * 3), dy = y0 + (y1 - y0) * k;
        g.fillStyle = `rgba(230,245,255,${0.9 * tears})`;
        g.beginPath(); g.ellipse(dx, dy, 5, 7, 0, 0, Math.PI * 2); g.fill();
        g.fillStyle = `rgba(255,255,255,${tears})`;
        g.beginPath(); g.arc(dx - 1.5, dy - 2, 1.6, 0, Math.PI * 2); g.fill();
      }
      // yeux rougis
      for (const s of [-1, 1]) {
        const [x, y] = facePx(s * 0.41, 0.02);
        const rg = g.createRadialGradient(x, y, 10, x, y, 40);
        rg.addColorStop(0, `rgba(190,60,60,${0.25 * tears})`); rg.addColorStop(1, 'rgba(190,60,60,0)');
        g.fillStyle = rg; g.fillRect(x - 40, y - 40, 80, 80);
      }
    }
    this.faceTex.needsUpdate = true;
  }

  ik(arm, side, w, x, y, z, pole) {
    if (w <= 0.001) return;
    const A = 0.29, B = 0.315;
    const S = arm.sh.position;
    const d = new THREE.Vector3(x - S.x, y - S.y, z - S.z);
    let L = d.length();
    L = Math.min(A + B - 0.002, Math.max(Math.abs(A - B) + 0.01, L));
    const dn = d.normalize();
    const alpha = Math.acos(Math.min(1, Math.max(-1, (A * A + L * L - B * B) / (2 * A * L))));
    const bend = Math.acos(Math.min(1, Math.max(-1, (A * A + B * B - L * L) / (2 * A * B))));
    // coude orienté vers le bas / l'extérieur / l'arrière (+ réglage 'pole')
    const pv = new THREE.Vector3(side * (0.45 + pole), -1, -0.5 + pole * 0.5).normalize();
    const axis = new THREE.Vector3().crossVectors(dn, pv);
    if (axis.lengthSq() < 1e-6) axis.set(1, 0, 0);
    axis.normalize();
    const u = dn.clone().applyAxisAngle(axis, alpha); // direction du bras
    const wv = dn.clone().sub(u.clone().multiplyScalar(dn.dot(u))).normalize(); // vers la main
    const Y = u.clone().negate(), Zv = wv, X = new THREE.Vector3().crossVectors(Y, Zv).normalize();
    const m = new THREE.Matrix4().makeBasis(X, Y, Zv);
    const q = new THREE.Quaternion().setFromRotationMatrix(m);
    arm.sh.quaternion.slerp(q, Math.min(1, w));
    arm.el.rotation.x = arm.el.rotation.x + (-(Math.PI - bend) - arm.el.rotation.x) * Math.min(1, w);
  }

  headWorld(out = new THREE.Vector3()) {
    return this.headCenter.getWorldPosition(out);
  }
}

export function mulberry(a) {
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
