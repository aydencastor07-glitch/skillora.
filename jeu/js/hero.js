import * as THREE from 'three';
import { toon, part, BLACK, ink } from './util.js';

// ---------- Visages dessinés (texture canvas sur la tête sphérique) ----------
// u = 0.25 correspond à l'avant (+Z) de la sphère ; 1 radian ≈ 163 px.
const FW = 1024, FH = 512, CX = 256, CY = 250;

function drawFace(expr) {
  const c = document.createElement('canvas');
  c.width = FW; c.height = FH;
  const g = c.getContext('2d');
  g.fillStyle = '#f6f5ef';
  g.fillRect(0, 0, FW, FH);
  g.lineCap = 'round';
  g.lineJoin = 'round';
  g.strokeStyle = '#111';

  const eye = (x, y, rx, ry, px, py, pr) => {
    g.fillStyle = '#fff';
    g.lineWidth = 7;
    g.beginPath(); g.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2); g.fill(); g.stroke();
    g.fillStyle = '#111';
    g.beginPath(); g.arc(x + px, y + py, pr, 0, Math.PI * 2); g.fill();
  };
  const line = (pts, w = 12) => {
    g.lineWidth = w;
    g.beginPath();
    g.moveTo(pts[0], pts[1]);
    for (let i = 2; i < pts.length; i += 2) g.lineTo(pts[i], pts[i + 1]);
    g.stroke();
  };
  const sweat = (x, y, s) => {
    g.fillStyle = '#9fd3f2';
    g.lineWidth = 4;
    g.beginPath();
    g.moveTo(x, y - 22 * s);
    g.quadraticCurveTo(x + 13 * s, y, x, y + 10 * s);
    g.quadraticCurveTo(x - 13 * s, y, x, y - 22 * s);
    g.fill(); g.stroke();
  };
  const teeth = (x0, y0, x1, y1) => {
    g.fillStyle = '#fff';
    g.lineWidth = 7;
    g.beginPath();
    g.moveTo(x0, y0 + 8);
    g.quadraticCurveTo((x0 + x1) / 2, y0 - 10, x1, y0 + 8);
    g.lineTo(x1 - 6, y1);
    g.quadraticCurveTo((x0 + x1) / 2, y1 + 10, x0 + 6, y1);
    g.closePath(); g.fill(); g.stroke();
    g.lineWidth = 4;
    const my = (y0 + y1) / 2 + 2;
    g.beginPath(); g.moveTo(x0 + 4, my); g.lineTo(x1 - 4, my); g.stroke();
    for (let x = x0 + 22; x < x1 - 8; x += 22) {
      g.beginPath(); g.moveTo(x, y0 + 2); g.lineTo(x, y1 + 2); g.stroke();
    }
  };
  const openMouth = (x, y, w, h, tongue = true) => {
    g.fillStyle = '#3a0d0d';
    g.lineWidth = 7;
    g.beginPath(); g.ellipse(x, y, w, h, 0, 0, Math.PI * 2); g.fill(); g.stroke();
    if (tongue) {
      g.save();
      g.beginPath(); g.ellipse(x, y, w - 4, h - 4, 0, 0, Math.PI * 2); g.clip();
      g.fillStyle = '#d9575b';
      g.beginPath(); g.ellipse(x, y + h * 0.75, w * 0.6, h * 0.45, 0, 0, Math.PI * 2); g.fill();
      g.fillStyle = '#fff';
      g.fillRect(x - w, y - h, w * 2, h * 0.32);
      g.restore();
      g.lineWidth = 7;
      g.beginPath(); g.ellipse(x, y, w, h, 0, 0, Math.PI * 2); g.stroke();
    }
  };
  const spiral = (x, y) => {
    g.lineWidth = 6;
    g.beginPath();
    for (let a = 0; a < Math.PI * 6; a += 0.2) {
      const r = 3 + a * 2.1;
      const px = x + Math.cos(a) * r, py = y + Math.sin(a) * r;
      a === 0 ? g.moveTo(px, py) : g.lineTo(px, py);
    }
    g.stroke();
  };

  const L = CX - 50, R = CX + 50, EY = CY - 12;
  switch (expr) {
    case 'angry':
      eye(L, EY, 40, 46, 6, 6, 11);
      eye(R, EY, 40, 46, -6, 6, 11);
      line([L - 52, EY - 78, L + 30, EY - 40], 15);
      line([R + 52, EY - 78, R - 30, EY - 40], 15);
      line([CX - 10, EY - 70, CX, EY - 52, CX + 10, EY - 70], 5);
      teeth(CX - 72, CY + 62, CX + 72, CY + 108);
      line([CX - 90, CY + 70, CX - 78, CY + 84], 5);
      line([CX + 90, CY + 70, CX + 78, CY + 84], 5);
      sweat(CX - 150, CY - 40, 1.2);
      sweat(CX + 148, CY - 70, 1);
      sweat(CX + 165, CY + 10, 0.7);
      break;
    case 'fierce':
      eye(L, EY, 38, 40, 4, 4, 12);
      eye(R, EY, 38, 40, -4, 4, 12);
      line([L - 50, EY - 70, L + 34, EY - 26], 18);
      line([R + 50, EY - 70, R - 34, EY - 26], 18);
      g.fillStyle = '#3a0d0d';
      g.lineWidth = 7;
      g.beginPath();
      g.moveTo(CX - 80, CY + 55); g.lineTo(CX + 80, CY + 55);
      g.quadraticCurveTo(CX + 60, CY + 135, CX, CY + 138);
      g.quadraticCurveTo(CX - 60, CY + 135, CX - 80, CY + 55);
      g.fill(); g.stroke();
      g.fillStyle = '#fff';
      g.fillRect(CX - 70, CY + 59, 140, 16);
      g.strokeRect(CX - 70, CY + 59, 140, 16);
      g.fillStyle = '#d9575b';
      g.beginPath(); g.ellipse(CX, CY + 118, 34, 14, 0, 0, Math.PI * 2); g.fill();
      sweat(CX + 150, CY - 60, 1);
      break;
    case 'scared':
      eye(L, EY, 44, 52, 0, -2, 7);
      eye(R, EY, 44, 52, 0, -2, 7);
      line([L - 48, EY - 70, L + 26, EY - 92], 12);
      line([R + 48, EY - 70, R - 26, EY - 92], 12);
      g.fillStyle = '#3a0d0d';
      g.lineWidth = 7;
      g.beginPath();
      g.moveTo(CX - 60, CY + 90);
      for (let i = 0; i <= 12; i++) g.lineTo(CX - 60 + i * 10, CY + 80 + (i % 2 ? -8 : 6));
      g.lineTo(CX + 50, CY + 115);
      g.quadraticCurveTo(CX, CY + 132, CX - 50, CY + 115);
      g.closePath(); g.fill(); g.stroke();
      sweat(CX - 150, CY - 50, 1.3);
      sweat(CX + 150, CY - 40, 1.3);
      sweat(CX - 165, CY + 20, 0.8);
      break;
    case 'surprised':
      eye(L, EY, 46, 56, 0, 4, 8);
      eye(R, EY, 46, 56, 0, 4, 8);
      line([L - 44, EY - 90, L, EY - 108, L + 36, EY - 92], 11);
      line([R + 44, EY - 90, R, EY - 108, R - 36, EY - 92], 11);
      openMouth(CX, CY + 95, 22, 28, false);
      sweat(CX + 150, CY - 60, 1.3);
      break;
    case 'dizzy':
      g.fillStyle = '#fff';
      g.lineWidth = 7;
      g.beginPath(); g.ellipse(L, EY, 40, 44, 0, 0, Math.PI * 2); g.fill(); g.stroke();
      g.beginPath(); g.ellipse(R, EY, 40, 44, 0, 0, Math.PI * 2); g.fill(); g.stroke();
      spiral(L, EY); spiral(R, EY);
      g.lineWidth = 8;
      g.beginPath();
      g.moveTo(CX - 60, CY + 90);
      g.bezierCurveTo(CX - 30, CY + 70, CX - 10, CY + 110, CX + 15, CY + 88);
      g.bezierCurveTo(CX + 35, CY + 72, CX + 50, CY + 100, CX + 62, CY + 86);
      g.stroke();
      g.fillStyle = '#d9575b';
      g.beginPath(); g.ellipse(CX + 20, CY + 104, 14, 18, 0.2, 0, Math.PI * 2); g.fill(); g.stroke();
      break;
    case 'grumpy':
    default: {
      eye(L, EY, 40, 44, 0, 14, 11);
      eye(R, EY, 40, 44, 0, 14, 11);
      // paupières mi-closes
      g.fillStyle = '#e9e8e0';
      g.lineWidth = 7;
      for (const x of [L, R]) {
        g.beginPath(); g.ellipse(x, EY, 40, 44, 0, Math.PI, Math.PI * 2); g.closePath(); g.fill(); g.stroke();
      }
      line([L - 46, EY - 58, L + 30, EY - 44], 12);
      line([R + 46, EY - 58, R - 30, EY - 44], 12);
      g.lineWidth = 9;
      g.beginPath(); g.arc(CX, CY + 128, 48, Math.PI * 1.2, Math.PI * 1.8); g.stroke();
      break;
    }
  }
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  return tex;
}

export const FACES = ['angry', 'fierce', 'scared', 'surprised', 'dizzy', 'grumpy'];

// ---------- Construction du personnage bâton ----------

function limb(len, r) {
  const g = new THREE.CapsuleGeometry(r, len, 4, 10);
  g.translate(0, -len / 2, 0);
  return g;
}

export class Hero {
  constructor() {
    this.faces = {};
    for (const f of FACES) this.faces[f] = drawFace(f);
    this.face = 'angry';

    const root = (this.root = new THREE.Group());
    const tilt = (this.tilt = new THREE.Group());
    root.add(tilt);
    const body = (this.body = new THREE.Group());
    tilt.add(body);
    const pelvis = (this.pelvis = new THREE.Group());
    pelvis.position.y = 1.0;
    body.add(pelvis);

    const LW = 0.05; // épaisseur du trait
    // Colonne
    const spine = (this.spine = new THREE.Group());
    pelvis.add(spine);
    const torso = new THREE.Mesh(limb(0.8, LW), BLACK);
    torso.rotation.x = Math.PI; // vers le haut
    torso.castShadow = true;
    spine.add(torso);

    // Noeud papillon
    const bow = new THREE.Group();
    bow.position.set(0, 0.74, 0.06);
    spine.add(bow);
    const cone = new THREE.ConeGeometry(0.1, 0.2, 12);
    const b1 = new THREE.Mesh(cone, BLACK); b1.rotation.z = Math.PI / 2; b1.position.x = 0.09;
    const b2 = new THREE.Mesh(cone, BLACK); b2.rotation.z = -Math.PI / 2; b2.position.x = -0.09;
    const knot = new THREE.Mesh(new THREE.SphereGeometry(0.05, 10, 8), BLACK);
    bow.add(b1, b2, knot);

    // Tête
    const headPivot = (this.headPivot = new THREE.Group());
    headPivot.position.y = 0.8;
    spine.add(headPivot);
    this.headMat = toon(0xffffff, { map: this.faces.angry });
    const head = (this.head = new THREE.Mesh(new THREE.SphereGeometry(0.42, 48, 32), this.headMat));
    head.position.y = 0.4;
    head.castShadow = true;
    ink(head, 0.032);
    headPivot.add(head);

    // Chapeau haut-de-forme
    const hatMat = toon(0x1c1c1f);
    const hat = (this.hat = new THREE.Group());
    head.add(hat);
    this.hatBase = new THREE.Vector3(0, 0.3, -0.02);
    hat.position.copy(this.hatBase);
    part(new THREE.CylinderGeometry(0.52, 0.52, 0.05, 40), hatMat, hat, { pos: [0, 0, 0], outline: 0.02 });
    part(new THREE.CylinderGeometry(0.33, 0.35, 0.66, 40), hatMat, hat, { pos: [0, 0.35, 0], outline: 0.02 });

    // Bras (les deux partent du même point, style bonhomme bâton)
    const mkArm = (side) => {
      const sh = new THREE.Group();
      sh.position.set(side * 0.04, 0.66, 0);
      spine.add(sh);
      const up = new THREE.Mesh(limb(0.42, LW), BLACK); up.castShadow = true; sh.add(up);
      const el = new THREE.Group(); el.position.y = -0.42; sh.add(el);
      const lo = new THREE.Mesh(limb(0.4, LW), BLACK); lo.castShadow = true; el.add(lo);
      const hand = new THREE.Group(); hand.position.y = -0.42; el.add(hand);
      const fist = new THREE.Mesh(new THREE.SphereGeometry(0.095, 14, 10), BLACK);
      fist.castShadow = true;
      hand.add(fist);
      return { sh, el, hand };
    };
    this.lArm = mkArm(1);
    this.rArm = mkArm(-1);

    const mkLeg = (side) => {
      const hip = new THREE.Group();
      hip.position.set(side * 0.08, 0, 0);
      pelvis.add(hip);
      const th = new THREE.Mesh(limb(0.5, LW), BLACK); th.castShadow = true; hip.add(th);
      const kn = new THREE.Group(); kn.position.y = -0.5; hip.add(kn);
      const sh = new THREE.Mesh(limb(0.46, LW), BLACK); sh.castShadow = true; kn.add(sh);
      const ft = new THREE.Group(); ft.position.y = -0.47; kn.add(ft);
      const foot = new THREE.Mesh(new THREE.SphereGeometry(1, 14, 10), BLACK);
      foot.scale.set(0.1, 0.065, 0.2);
      foot.position.set(0, -0.01, 0.08);
      foot.castShadow = true;
      ft.add(foot);
      return { hip, kn, ft };
    };
    this.lLeg = mkLeg(1);
    this.rLeg = mkLeg(-1);

    // Bâton (tenu dans la main droite quand il le ramasse)
    const stick = (this.stick = new THREE.Group());
    const stickMat = toon(0x80593a);
    const sg = new THREE.CylinderGeometry(0.045, 0.065, 1.35, 9);
    sg.translate(0, -0.55, 0);
    part(sg, stickMat, stick, { outline: 0.022 });
    const twig = new THREE.CylinderGeometry(0.018, 0.028, 0.3, 6);
    twig.translate(0, 0.15, 0);
    part(twig, stickMat, stick, { pos: [0, -0.8, 0], rot: [0, 0, 0.8], outline: 0.015 });
    this.stickInHand = false;

    this.tmp = new THREE.Vector3();
  }

  setFace(name) {
    if (name !== this.face && this.faces[name]) {
      this.face = name;
      this.headMat.map = this.faces[name];
      this.headMat.needsUpdate = true;
    }
  }

  // p : dictionnaire d'angles (radians)
  setPose(p) {
    const g = (k) => p[k] || 0;
    this.tilt.rotation.set(g('rootPitch'), 0, g('rootRoll'));
    this.body.position.y = g('bodyY');
    this.spine.rotation.set(g('spineX'), g('spineY'), g('spineZ'));
    this.headPivot.rotation.set(g('headX'), g('headY'), g('headZ'));
    this.lArm.sh.rotation.set(g('lShX'), g('lShY'), g('lShZ'));
    this.rArm.sh.rotation.set(g('rShX'), g('rShY'), g('rShZ'));
    this.lArm.el.rotation.set(g('lElX'), 0, 0);
    this.rArm.el.rotation.set(g('rElX'), 0, 0);
    this.lLeg.hip.rotation.set(g('lHipX'), 0, g('lHipZ'));
    this.rLeg.hip.rotation.set(g('rHipX'), 0, g('rHipZ'));
    this.lLeg.kn.rotation.x = g('lKnee');
    this.rLeg.kn.rotation.x = g('rKnee');
    this.lLeg.ft.rotation.x = g('lFoot');
    this.rLeg.ft.rotation.x = g('rFoot');
    this.hat.position.set(this.hatBase.x + g('hatX'), this.hatBase.y + g('hatY'), this.hatBase.z);
    this.hat.rotation.set(-0.08 + g('hatTiltX'), 0, -0.12 + g('hatTilt'));
  }

  headWorld(out) {
    return this.head.getWorldPosition(out);
  }
}
