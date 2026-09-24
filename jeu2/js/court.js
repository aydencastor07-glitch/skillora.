// La salle d'audience + les accessoires (téléphone, enceinte, marteau, sac…)
import * as THREE from 'three';
import { mulberry } from './human.js';

function tex(w, h, draw, rep = [1, 1]) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  draw(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(...rep);
  t.anisotropy = 8;
  return t;
}

function woodTex(base = '#8a5530', rep = [1, 1], panels = false) {
  return tex(512, 512, (g, w, h) => {
    const r = mulberry(4);
    g.fillStyle = base; g.fillRect(0, 0, w, h);
    for (let i = 0; i < 180; i++) {
      const x = r() * w;
      g.strokeStyle = r() < 0.5 ? 'rgba(40,20,5,0.18)' : 'rgba(255,220,170,0.1)';
      g.lineWidth = 1 + r() * 3;
      g.beginPath(); g.moveTo(x, 0);
      for (let y = 0; y <= h; y += 32) g.lineTo(x + Math.sin(y * 0.02 + i) * 4, y);
      g.stroke();
    }
    if (panels) {
      g.strokeStyle = 'rgba(30,15,5,0.55)'; g.lineWidth = 6;
      g.strokeRect(40, 40, w - 80, h - 80);
      g.strokeStyle = 'rgba(255,220,180,0.25)'; g.lineWidth = 3;
      g.strokeRect(47, 47, w - 94, h - 94);
    }
  }, rep);
}

function floorTex() {
  return tex(1024, 1024, (g, w, h) => {
    const r = mulberry(8);
    const n = 4, s = w / n;
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
      const v = 200 + r() * 18;
      g.fillStyle = `rgb(${v + 12},${v + 5},${v - 10})`;
      g.fillRect(i * s, j * s, s, s);
      for (let k = 0; k < 6; k++) {
        g.strokeStyle = `rgba(150,130,110,${0.08 + r() * 0.1})`;
        g.lineWidth = 1 + r() * 2;
        g.beginPath();
        let x = i * s + r() * s, y = j * s;
        g.moveTo(x, y);
        for (let q = 0; q < 8; q++) { x += (r() - 0.5) * 60; y += s / 8; g.lineTo(x, y); }
        g.stroke();
      }
    }
    g.strokeStyle = 'rgba(120,105,90,0.6)'; g.lineWidth = 3;
    for (let i = 0; i <= n; i++) { g.beginPath(); g.moveTo(i * s, 0); g.lineTo(i * s, h); g.stroke(); g.beginPath(); g.moveTo(0, i * s); g.lineTo(w, i * s); g.stroke(); }
  }, [8, 11]);
}

function flagTex(kind) {
  return tex(512, 320, (g, w, h) => {
    if (kind === 'us') {
      for (let i = 0; i < 13; i++) { g.fillStyle = i % 2 ? '#f5f5f0' : '#b22234'; g.fillRect(0, (i * h) / 13, w, h / 13 + 1); }
      g.fillStyle = '#3c3b6e'; g.fillRect(0, 0, w * 0.4, (h * 7) / 13);
      g.fillStyle = '#fff';
      for (let y = 0; y < 9; y++) for (let x = 0; x < (y % 2 ? 5 : 6); x++) {
        g.beginPath(); g.arc(12 + x * 34 + (y % 2 ? 17 : 0), 10 + y * 18, 3.5, 0, Math.PI * 2); g.fill();
      }
    } else {
      g.fillStyle = '#1f3b73'; g.fillRect(0, 0, w, h);
      g.strokeStyle = '#e8c35a'; g.lineWidth = 10;
      g.beginPath(); g.arc(w / 2, h / 2, 90, 0, Math.PI * 2); g.stroke();
      g.fillStyle = '#e8c35a';
      g.beginPath(); g.arc(w / 2, h / 2, 50, 0, Math.PI * 2); g.fill();
    }
  });
}

function sealTex() {
  return tex(512, 512, (g, w, h) => {
    const c = w / 2;
    g.fillStyle = '#c9a44c'; g.beginPath(); g.arc(c, c, 250, 0, Math.PI * 2); g.fill();
    g.fillStyle = '#1f3b73'; g.beginPath(); g.arc(c, c, 215, 0, Math.PI * 2); g.fill();
    g.fillStyle = '#e8d7a0'; g.beginPath(); g.arc(c, c, 140, 0, Math.PI * 2); g.fill();
    g.fillStyle = '#e8d7a0';
    g.font = 'bold 34px Georgia, serif'; g.textAlign = 'center'; g.textBaseline = 'middle';
    const txt = '• SUPERIOR COURT • COUNTY OF JUSTICE ';
    for (let i = 0; i < txt.length; i++) {
      const a = (i / txt.length) * Math.PI * 2 - Math.PI / 2;
      g.save(); g.translate(c + Math.cos(a) * 178, c + Math.sin(a) * 178); g.rotate(a + Math.PI / 2); g.fillText(txt[i], 0, 0); g.restore();
    }
    g.fillStyle = '#1f3b73';
    g.beginPath(); g.moveTo(c, c - 90); g.lineTo(c + 70, c + 60); g.lineTo(c - 70, c + 60); g.closePath(); g.fill();
    g.fillStyle = '#c9a44c'; g.fillRect(c - 80, c + 60, 160, 16);
  });
}

// Écran du jeu sur le téléphone (oiseaux + lance-pierre), redessiné en direct
export class PhoneScreen {
  constructor() {
    this.c = document.createElement('canvas');
    this.c.width = 256; this.c.height = 128;
    this.tex = new THREE.CanvasTexture(this.c);
    this.tex.colorSpace = THREE.SRGBColorSpace;
    this.last = -1;
  }
  draw(t, lost = 0) {
    const f = Math.floor(t * 20);
    if (f === this.last) return;
    this.last = f;
    const g = this.c.getContext('2d');
    const sky = g.createLinearGradient(0, 0, 0, 128);
    sky.addColorStop(0, '#7fd0f5'); sky.addColorStop(1, '#d6f1ff');
    g.fillStyle = sky; g.fillRect(0, 0, 256, 128);
    g.fillStyle = '#6cbf45'; g.fillRect(0, 104, 256, 24);
    g.fillStyle = '#fff';
    for (const [x, y] of [[40, 22], [150, 14], [210, 30]]) { g.beginPath(); g.ellipse((x + t * 6) % 280 - 12, y, 18, 7, 0, 0, Math.PI * 2); g.fill(); }
    // structure + cochons verts
    g.fillStyle = '#b07a3c';
    g.fillRect(180, 70, 8, 34); g.fillRect(214, 70, 8, 34); g.fillRect(176, 64, 50, 7);
    g.fillStyle = '#9bd35a';
    g.beginPath(); g.arc(201, 94, 9, 0, Math.PI * 2); g.fill();
    g.beginPath(); g.arc(201, 56, 7, 0, Math.PI * 2); g.fill();
    // lance-pierre
    g.fillStyle = '#6b3d1c'; g.fillRect(34, 76, 5, 28); g.fillRect(28, 70, 5, 10); g.fillRect(40, 70, 5, 10);
    // oiseau rouge en vol
    const ph = (t * 0.55) % 1;
    const bx = 38 + ph * 170, by = 70 - Math.sin(ph * Math.PI) * 55;
    g.fillStyle = '#e02b20'; g.beginPath(); g.arc(bx, by, 7, 0, Math.PI * 2); g.fill();
    g.fillStyle = '#fff'; g.beginPath(); g.arc(bx + 3, by - 2, 2.2, 0, Math.PI * 2); g.fill();
    g.fillStyle = '#f2a51d'; g.beginPath(); g.moveTo(bx + 6, by); g.lineTo(bx + 11, by + 2); g.lineTo(bx + 6, by + 3); g.fill();
    g.fillStyle = '#fff'; g.font = 'bold 12px sans-serif'; g.fillText('SCORE ' + (1200 + f * 7), 8, 16);
    if (lost > 0) {
      g.fillStyle = `rgba(0,0,0,${0.55 * lost})`; g.fillRect(0, 0, 256, 128);
      g.globalAlpha = lost;
      g.fillStyle = '#ff4a3a'; g.font = 'bold 28px sans-serif'; g.textAlign = 'center';
      g.fillText('LEVEL FAILED', 128, 72);
      g.textAlign = 'left'; g.globalAlpha = 1;
    }
    this.tex.needsUpdate = true;
  }
}

export function buildCourt(scene) {
  const out = {};
  const std = (color, rough = 0.6, extra = {}) => new THREE.MeshStandardMaterial({ color, roughness: rough, ...extra });
  const add = (geo, mat, pos, rot, parent = scene, shadow = true) => {
    const m = new THREE.Mesh(geo, mat);
    m.position.set(...pos);
    if (rot) m.rotation.set(...rot);
    m.castShadow = shadow; m.receiveShadow = true;
    parent.add(m);
    return m;
  };
  const box = (w, h, d, mat, x, y, z, parent) => add(new THREE.BoxGeometry(w, h, d), mat, [x, y + h / 2, z], null, parent);

  const W = 16, D = 22, H = 4.6;
  const wood = std('#ffffff', 0.55, { map: woodTex('#8b5a33', [2, 1]) });
  const woodPanel = std('#ffffff', 0.5, { map: woodTex('#8b5a33', [1, 1], true) });
  const woodDark = std('#ffffff', 0.5, { map: woodTex('#6e4424', [1, 1]) });
  const wallMat = std('#e7e1d6', 0.9);

  // Sol, plafond, murs
  add(new THREE.PlaneGeometry(W, D), std('#c9bfae', 0.42, { map: floorTex() }), [0, 0, 0], [-Math.PI / 2, 0, 0]).castShadow = false;
  add(new THREE.PlaneGeometry(W, D), std('#f3f1ec', 0.95), [0, H, 0], [Math.PI / 2, 0, 0]).castShadow = false;
  const wall = (w, x, z, ry) => {
    const g = new THREE.Group(); g.position.set(x, 0, z); g.rotation.y = ry; scene.add(g);
    add(new THREE.PlaneGeometry(w, H), wallMat, [0, H / 2, 0], null, g).castShadow = false;
    // lambris bas en panneaux
    const n = Math.round(w / 1.1);
    for (let i = 0; i < n; i++) add(new THREE.BoxGeometry(w / n - 0.02, 1.25, 0.05), woodPanel, [-w / 2 + (i + 0.5) * (w / n), 0.625, 0.025], null, g);
    add(new THREE.BoxGeometry(w, 0.07, 0.09), woodDark, [0, 1.28, 0.045], null, g);
    add(new THREE.BoxGeometry(w, 0.12, 0.03), woodDark, [0, 0.06, 0.06], null, g);
    add(new THREE.BoxGeometry(w, 0.1, 0.06), std('#ffffff', 0.9), [0, H - 0.05, 0.03], null, g);
    return g;
  };
  const back = wall(W, 0, -D / 2, 0); // mur du juge
  wall(W, 0, D / 2, Math.PI);
  const left = wall(D, -W / 2, 0, Math.PI / 2);
  const right = wall(D, W / 2, 0, -Math.PI / 2);

  // Fenêtres (mur droit) : lumière du jour
  const glass = std('#ffffff', 0.2, { emissive: '#e8f2ff', emissiveIntensity: 1.6 });
  for (const z of [-6, -1, 4]) {
    add(new THREE.PlaneGeometry(1.5, 2.1), glass, [z, 2.6, 0.03], null, right).castShadow = false;
    for (const dx of [-0.78, 0.78]) add(new THREE.BoxGeometry(0.08, 2.3, 0.1), woodDark, [z + dx, 2.6, 0.05], null, right);
    for (const dy of [1.5, 2.6, 3.7]) add(new THREE.BoxGeometry(1.6, 0.07, 0.1), woodDark, [z, dy, 0.05], null, right);
  }

  // Mur du juge : grand panneau bois + sceau + drapeaux
  for (let i = 0; i < 7; i++) add(new THREE.BoxGeometry(0.98, 2.4, 0.06), woodPanel, [-3.3 + i * 1.1, 1.9, 0.08], null, back);
  add(new THREE.BoxGeometry(8, 0.14, 0.14), woodDark, [0, 3.15, 0.1], null, back);
  add(new THREE.CircleGeometry(0.62, 48), std('#ffffff', 0.4, { map: sealTex(), metalness: 0.2 }), [0, 3.72, 0.06], null, back);
  const flag = (x, kind) => {
    add(new THREE.CylinderGeometry(0.025, 0.025, 2.9, 10), std('#d4af37', 0.3, { metalness: 0.9 }), [x, 1.45 + 0.55, -D / 2 + 0.7]);
    add(new THREE.SphereGeometry(0.06, 12, 8), std('#d4af37', 0.3, { metalness: 0.9 }), [x, 3.5, -D / 2 + 0.7]);
    add(new THREE.CylinderGeometry(0.25, 0.3, 0.1, 16), std('#2a2a2a', 0.5), [x, 0.6, -D / 2 + 0.7]);
    const fg = new THREE.PlaneGeometry(0.9, 1.25, 16, 16);
    const p = fg.attributes.position;
    for (let i = 0; i < p.count; i++) {
      const y = p.getY(i), xx = p.getX(i);
      p.setZ(i, Math.sin(y * 7 + xx * 2) * 0.05 * (0.6 - y * 0.3));
      p.setX(i, xx * 0.55 + Math.sin(y * 5) * 0.02);
    }
    fg.computeVertexNormals();
    add(fg, std('#ffffff', 0.8, { map: flagTex(kind), side: THREE.DoubleSide }), [x + (x < 0 ? 0.26 : -0.26), 2.75, -D / 2 + 0.7]);
  };
  flag(-2.7, 'us');
  flag(2.7, 'state');

  // Estrade + bureau du juge
  box(7, 0.55, 3, wood, 0, 0, -D / 2 + 1.5);
  box(4.4, 1.5, 0.12, woodPanel, 0, 0, -8.35);
  box(4.6, 0.08, 0.95, woodDark, 0, 1.5, -8.8);
  for (const x of [-2.25, 2.25]) box(0.12, 1.5, 0.9, woodDark, x, 0, -8.8);
  // fauteuil du juge (dossier haut en cuir)
  const leather = std('#3a2418', 0.45);
  box(0.7, 0.12, 0.6, leather, 0, 1.0, -9.35);
  box(0.72, 1.2, 0.14, leather, 0, 1.1, -9.72);
  // marteau + socle
  out.gavelBlock = add(new THREE.CylinderGeometry(0.09, 0.1, 0.04, 24), woodDark, [0.55, 1.6, -8.65]);
  const gavel = (out.gavel = new THREE.Group());
  const gw = std('#5b3418', 0.4);
  add(new THREE.CylinderGeometry(0.045, 0.045, 0.16, 16), gw, [0, 0, 0], [0, 0, Math.PI / 2], gavel);
  add(new THREE.CylinderGeometry(0.012, 0.015, 0.26, 10), gw, [0, -0.13, 0], null, gavel);
  add(new THREE.TorusGeometry(0.046, 0.006, 6, 16), std('#d4af37', 0.3, { metalness: 0.9 }), [0.05, 0, 0], [0, Math.PI / 2, 0], gavel);
  add(new THREE.TorusGeometry(0.046, 0.006, 6, 16), std('#d4af37', 0.3, { metalness: 0.9 }), [-0.05, 0, 0], [0, Math.PI / 2, 0], gavel);
  scene.add(gavel);
  // plaque, micro, papiers sur le bureau du juge
  add(new THREE.BoxGeometry(0.5, 0.1, 0.03), std('#d4af37', 0.3, { metalness: 0.8 }), [-0.9, 1.63, -8.4]);
  box(0.4, 0.02, 0.3, std('#f4f1e8', 0.9), -0.5, 1.58, -8.7);
  const mic = (x, y, z, ry = 0) => {
    const g = new THREE.Group(); g.position.set(x, y, z); g.rotation.y = ry; scene.add(g);
    add(new THREE.CylinderGeometry(0.05, 0.06, 0.03, 16), std('#1d1d1d', 0.4), [0, 0.015, 0], null, g);
    add(new THREE.CylinderGeometry(0.006, 0.006, 0.34, 8), std('#1d1d1d', 0.4), [0, 0.17, 0.05], [0.35, 0, 0], g);
    add(new THREE.CylinderGeometry(0.014, 0.012, 0.07, 12), std('#111', 0.5), [0, 0.34, 0.11], [0.9, 0, 0], g);
  };
  mic(1.15, 1.58, -8.55, -0.5);

  // Barre des témoins + greffier
  box(1.6, 1.0, 0.1, woodPanel, 4.2, 0, -7.6);
  box(0.1, 1.0, 1.4, woodPanel, 3.45, 0, -8.3);
  box(1.7, 0.06, 0.2, woodDark, 4.2, 1.0, -7.6);
  box(1.8, 0.9, 0.1, woodPanel, -4.3, 0, -7.4);
  box(1.9, 0.05, 0.7, woodDark, -4.3, 0.9, -7.7);

  // Tables des parties
  const table = (x, z) => {
    box(2.3, 0.05, 0.95, wood, x, 0.74, z);
    box(2.2, 0.62, 0.04, woodPanel, x, 0.12, z - 0.44);
    for (const dx of [-1.08, 1.08]) box(0.06, 0.74, 0.9, woodDark, x + dx, 0, z);
  };
  table(-2.55, -4.9);
  table(2.55, -4.9);
  mic(-2.55, 0.79, -5.15, Math.PI);
  mic(2.55, 0.79, -5.15, Math.PI);
  box(0.3, 0.015, 0.22, std('#f4f1e8', 0.9), -3.3, 0.79, -4.8);
  box(0.3, 0.015, 0.22, std('#f4f1e8', 0.9), 3.3, 0.79, -4.75);
  box(0.25, 0.04, 0.33, std('#1f4f7a', 0.6), 3.1, 0.79, -5.0);
  // boîte de mouchoirs devant le plaignant
  box(0.22, 0.1, 0.12, std('#f0e7d8', 0.8), 1.8, 0.79, -4.85);
  add(new THREE.SphereGeometry(0.05, 10, 8), std('#ffffff', 0.9), [1.8, 0.9, -4.85]);
  // verres d'eau
  const glassMat = new THREE.MeshPhysicalMaterial({ color: '#ffffff', roughness: 0.05, transmission: 0.9, thickness: 0.02, transparent: true, opacity: 0.35 });
  for (const x of [-3.5, 3.5]) add(new THREE.CylinderGeometry(0.035, 0.03, 0.11, 16), glassMat, [x, 0.845, -4.7]);

  // Fauteuils de bureau beiges
  const chairMat = std('#c8b79c', 0.5);
  const chair = (x, z, ry = Math.PI) => {
    const g = new THREE.Group(); g.position.set(x, 0, z); g.rotation.y = ry; scene.add(g);
    add(new THREE.BoxGeometry(0.52, 0.1, 0.5), chairMat, [0, 0.46, 0], null, g);
    add(new THREE.BoxGeometry(0.5, 0.62, 0.09), chairMat, [0, 0.84, -0.25], [-0.08, 0, 0], g);
    for (const s of [-1, 1]) add(new THREE.BoxGeometry(0.05, 0.05, 0.36), std('#2a2a2a', 0.4), [s * 0.28, 0.66, -0.02], null, g);
    add(new THREE.CylinderGeometry(0.03, 0.03, 0.36, 10), std('#2a2a2a', 0.3, { metalness: 0.6 }), [0, 0.22, 0], null, g);
    for (let i = 0; i < 5; i++) {
      const a = (i / 5) * Math.PI * 2;
      add(new THREE.BoxGeometry(0.04, 0.03, 0.3), std('#2a2a2a', 0.3, { metalness: 0.6 }), [Math.sin(a) * 0.14, 0.04, Math.cos(a) * 0.14], [0, a, 0], g);
    }
    return g;
  };
  out.chairs = { dad: chair(-3.2, -4.0), kid: chair(-1.95, -4.0), plaintiff: chair(2.1, -4.0), lawyer: chair(3.35, -4.0) };
  chair(0.2, -9.35, 0).visible = false;

  // Barre / balustrade
  const rail = (x0, x1) => {
    const L = x1 - x0, cx = (x0 + x1) / 2;
    box(L, 0.08, 0.12, woodDark, cx, 0.92, -2.2);
    box(L, 0.06, 0.08, woodDark, cx, 0.08, -2.2);
    for (let x = x0 + 0.08; x < x1; x += 0.22) add(new THREE.CylinderGeometry(0.025, 0.03, 0.84, 8), wood, [x, 0.5, -2.2]);
  };
  rail(-7.9, -0.9);
  rail(0.9, 7.9);

  // Bancs du public
  const bench = (x, z, w) => {
    box(w, 0.06, 0.45, wood, x, 0.44, z);
    box(w, 0.5, 0.06, woodPanel, x, 0.5, z + 0.24);
    box(w, 0.44, 0.04, woodDark, x, 0, z - 0.18);
    for (const dx of [-w / 2, w / 2]) box(0.07, 1.0, 0.55, woodDark, x + dx, 0, z + 0.03);
  };
  out.benchRows = [];
  for (let i = 0; i < 6; i++) {
    const z = -0.6 + i * 1.45;
    bench(-4.4, z, 6.4);
    bench(4.4, z, 6.4);
    out.benchRows.push(z);
  }

  // Portes d'entrée
  for (const s of [-1, 1]) {
    add(new THREE.BoxGeometry(0.95, 2.5, 0.08), woodPanel, [s * 0.5, 1.25, D / 2 - 0.05]);
    add(new THREE.SphereGeometry(0.035, 12, 8), std('#d4af37', 0.3, { metalness: 0.9 }), [s * 0.12, 1.15, D / 2 - 0.12]);
  }
  add(new THREE.BoxGeometry(2.3, 0.14, 0.14), woodDark, [0, 2.57, D / 2 - 0.07]);

  // Horloge
  const clock = new THREE.Group(); clock.position.set(-5.2, 3.3, -D / 2 + 0.06); scene.add(clock);
  add(new THREE.CylinderGeometry(0.28, 0.28, 0.05, 32), std('#ffffff', 0.6), [0, 0, 0], [Math.PI / 2, 0, 0], clock);
  add(new THREE.TorusGeometry(0.28, 0.025, 8, 32), std('#2a2a2a', 0.4), [0, 0, 0.02], null, clock);
  add(new THREE.BoxGeometry(0.02, 0.18, 0.01), std('#111'), [0.04, 0.06, 0.035], [0, 0, -0.6], clock);
  add(new THREE.BoxGeometry(0.015, 0.23, 0.01), std('#111'), [-0.03, 0.1, 0.04], [0, 0, 0.3], clock);

  // Suspensions rondes (comme la référence)
  const lampMat = std('#1b1b1b', 0.5);
  const lampGlow = new THREE.MeshStandardMaterial({ color: '#ffffff', emissive: '#fff4de', emissiveIntensity: 2.5 });
  out.lamps = [];
  for (const x of [-4, 0, 4]) for (const z of [-7, -2.5, 2, 6.5]) {
    add(new THREE.CylinderGeometry(0.004, 0.004, 1.0), lampMat, [x, H - 0.5, z], null, scene, false);
    add(new THREE.CylinderGeometry(0.42, 0.42, 0.07, 32), lampMat, [x, H - 1.0, z], null, scene, false);
    add(new THREE.CircleGeometry(0.39, 32), lampGlow, [x, H - 1.036, z], [Math.PI / 2, 0, 0], scene, false);
    out.lamps.push([x, H - 1.1, z]);
  }

  // ---------- Accessoires ----------
  // Téléphone (coque orange)
  const phone = (out.phone = new THREE.Group());
  add(new THREE.BoxGeometry(0.16, 0.078, 0.011), std('#e2682c', 0.45), [0, 0, 0], null, phone);
  out.screen = new PhoneScreen();
  const scr = add(new THREE.PlaneGeometry(0.146, 0.068), new THREE.MeshBasicMaterial({ map: out.screen.tex }), [0, 0, 0.0058], null, phone, false);
  scr.material.toneMapped = false;
  add(new THREE.BoxGeometry(0.03, 0.03, 0.004), std('#222', 0.3), [0.05, 0.02, -0.0065], null, phone);
  scene.add(phone);

  // Mini enceinte
  const spk = (out.speaker = new THREE.Group());
  const fab = std('#ffffff', 0.9, { map: tex(128, 128, (g) => { g.fillStyle = '#1b1c1e'; g.fillRect(0, 0, 128, 128); g.fillStyle = '#2d2f33'; for (let y = 0; y < 128; y += 4) for (let x = (y / 4) % 2 ? 2 : 0; x < 128; x += 4) g.fillRect(x, y, 2, 2); }, [3, 2]) });
  add(new THREE.CylinderGeometry(0.036, 0.036, 0.1, 28), fab, [0, 0, 0], null, spk);
  add(new THREE.SphereGeometry(0.036, 20, 10, 0, Math.PI * 2, 0, Math.PI / 2), std('#141414', 0.5), [0, 0.05, 0], null, spk);
  add(new THREE.SphereGeometry(0.036, 20, 10, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2), std('#141414', 0.5), [0, -0.05, 0], null, spk);
  add(new THREE.TorusGeometry(0.018, 0.005, 6, 16), std('#141414', 0.5), [0, 0.1, 0], null, spk);
  out.led = add(new THREE.SphereGeometry(0.005, 8, 6), new THREE.MeshStandardMaterial({ color: '#111', emissive: '#2a7bff', emissiveIntensity: 0 }), [0, 0.02, 0.036], null, spk, false);
  scene.add(spk);

  // Sac à dos de l'enfant (au pied de sa chaise)
  const bag = (out.bag = new THREE.Group());
  bag.position.set(-1.45, 0, -3.85);
  bag.rotation.y = -0.4;
  const bagMat = std('#b8342a', 0.75);
  add(new THREE.BoxGeometry(0.32, 0.4, 0.16), bagMat, [0, 0.21, 0], null, bag);
  add(new THREE.SphereGeometry(0.16, 16, 8, 0, Math.PI * 2, 0, Math.PI / 2), bagMat, [0, 0.4, 0], null, bag).scale.set(1, 0.35, 0.5);
  add(new THREE.BoxGeometry(0.24, 0.18, 0.05), std('#1d2a44', 0.7), [0, 0.15, 0.1], null, bag);
  scene.add(bag);

  out.bounds = { W, D, H };
  return out;
}
