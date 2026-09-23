import * as THREE from 'three';
import { toon, part } from './util.js';

const GREY = toon(0x8d9194);
const DARK = toon(0x686d71);
const LIGHT = toon(0xb9bcb8);
const WHITE = toon(0xf4f1e6);
const NOSE = new THREE.MeshBasicMaterial({ color: 0x141414 });
const EYE = new THREE.MeshBasicMaterial({ color: 0xf2cf3a });
const MOUTH = new THREE.MeshBasicMaterial({ color: 0x3b1010 });
const TONGUE = toon(0xc9575a);

const SPH = new THREE.SphereGeometry(1, 20, 14);
const SPIKE = new THREE.ConeGeometry(1, 1, 5);
const TOOTH = new THREE.ConeGeometry(0.025, 0.08, 5);

function legGeo(len, r0, r1) {
  const g = new THREE.CylinderGeometry(r1, r0, len, 9);
  g.translate(0, -len / 2, 0);
  return g;
}
const UPPER = legGeo(0.46, 0.1, 0.12);
const LOWER = legGeo(0.44, 0.06, 0.075);

export class Wolf {
  constructor(seed = 0) {
    const root = (this.root = new THREE.Group());
    const tilt = (this.tilt = new THREE.Group());
    tilt.position.y = 0.92;
    root.add(tilt);
    const body = (this.body = new THREE.Group());
    tilt.add(body);
    const O = 0.028;

    part(SPH, GREY, body, { pos: [0, 0, -0.02], scale: [0.42, 0.4, 0.8], outline: O });
    part(SPH, GREY, body, { pos: [0, 0.06, 0.42], scale: [0.47, 0.5, 0.46], outline: O });
    part(SPH, GREY, body, { pos: [0, 0.02, -0.52], scale: [0.39, 0.39, 0.4], outline: O });
    part(SPH, LIGHT, body, { pos: [0, -0.16, 0.5], scale: [0.3, 0.3, 0.3], outline: O });
    // Poils hérissés sur le dos
    for (let i = 0; i < 5; i++) {
      part(SPIKE, DARK, body, {
        pos: [0, 0.42 - i * 0.04, 0.5 - i * 0.2],
        rot: [-1.9, 0, 0],
        scale: [0.09, 0.26, 0.09],
        outline: 0.02,
      });
    }

    // Cou + tête
    const neck = (this.neck = new THREE.Group());
    neck.position.set(0, 0.22, 0.66);
    body.add(neck);
    part(SPH, GREY, neck, { pos: [0, 0.08, 0.1], scale: [0.3, 0.34, 0.36], rot: [-0.5, 0, 0], outline: O });
    const head = (this.head = new THREE.Group());
    head.position.set(0, 0.22, 0.32);
    neck.add(head);
    part(SPH, GREY, head, { scale: [0.31, 0.28, 0.32], outline: O });
    for (const s of [-1, 1]) {
      // touffes des joues
      part(SPIKE, GREY, head, { pos: [s * 0.27, -0.08, -0.06], rot: [-1.3, 0, s * 0.9], scale: [0.09, 0.24, 0.09], outline: 0.02 });
      part(SPIKE, GREY, head, { pos: [s * 0.24, -0.16, 0.02], rot: [-1.5, 0, s * 1.3], scale: [0.07, 0.2, 0.07], outline: 0.02 });
    }
    // museau
    const snoutG = new THREE.CylinderGeometry(0.1, 0.17, 0.44, 12);
    snoutG.rotateX(Math.PI / 2);
    part(snoutG, GREY, head, { pos: [0, -0.05, 0.34], outline: O });
    part(SPH, NOSE, head, { pos: [0, 0.0, 0.56], scale: [0.075, 0.06, 0.06], outline: 0 });
    part(SPH, MOUTH, head, { pos: [0, -0.12, 0.3], scale: [0.11, 0.06, 0.2], outline: 0 });
    for (let i = 0; i < 4; i++) {
      const s = i % 2 ? 1 : -1;
      const t = part(TOOTH, WHITE, head, { pos: [s * 0.07, -0.14, 0.44 - Math.floor(i / 2) * 0.12], rot: [Math.PI, 0, 0], outline: 0.01 });
      t.castShadow = false;
    }
    // mâchoire
    const jaw = (this.jaw = new THREE.Group());
    jaw.position.set(0, -0.12, 0.14);
    head.add(jaw);
    const jawG = new THREE.CylinderGeometry(0.07, 0.12, 0.36, 10);
    jawG.rotateX(Math.PI / 2);
    part(jawG, GREY, jaw, { pos: [0, -0.02, 0.2], scale: [1, 0.55, 1], outline: 0.024 });
    part(SPH, TONGUE, jaw, { pos: [0, 0.02, 0.2], scale: [0.06, 0.02, 0.14], outline: 0 });
    for (let i = 0; i < 4; i++) {
      const s = i % 2 ? 1 : -1;
      part(TOOTH, WHITE, jaw, { pos: [s * 0.06, 0.04, 0.32 - Math.floor(i / 2) * 0.11], outline: 0.01, shadow: false });
    }
    // oreilles
    this.ears = [];
    for (const s of [-1, 1]) {
      const e = new THREE.Group();
      e.position.set(s * 0.15, 0.2, -0.08);
      head.add(e);
      part(SPIKE, DARK, e, { pos: [0, 0.12, 0], rot: [0, 0, -s * 0.25], scale: [0.11, 0.28, 0.08], outline: 0.022 });
      this.ears.push(e);
    }
    // yeux jaunes + sourcils méchants
    for (const s of [-1, 1]) {
      part(SPH, EYE, head, { pos: [s * 0.13, 0.05, 0.22], scale: [0.075, 0.06, 0.05], outline: 0.018 });
      part(SPH, NOSE, head, { pos: [s * 0.125, 0.045, 0.265], scale: [0.02, 0.035, 0.015], outline: 0 });
      part(new THREE.BoxGeometry(1, 1, 1), DARK, head, {
        pos: [s * 0.13, 0.13, 0.22],
        rot: [0.2, 0, s * 0.5],
        scale: [0.17, 0.045, 0.07],
        outline: 0.016,
      });
    }

    // Pattes
    const mkLeg = (x, y, z) => {
      const up = new THREE.Group();
      up.position.set(x, y, z);
      body.add(up);
      part(UPPER, GREY, up, { outline: 0.022 });
      const lo = new THREE.Group();
      lo.position.y = -0.44;
      up.add(lo);
      part(LOWER, GREY, lo, { outline: 0.02 });
      part(SPH, GREY, lo, { pos: [0, -0.45, 0.05], scale: [0.09, 0.055, 0.13], outline: 0.02 });
      return { up, lo };
    };
    this.fl = mkLeg(0.2, -0.05, 0.46);
    this.fr = mkLeg(-0.2, -0.05, 0.46);
    this.bl = mkLeg(0.19, 0, -0.52);
    this.br = mkLeg(-0.19, 0, -0.52);

    // Queue touffue
    const tail = (this.tail = new THREE.Group());
    tail.position.set(0, 0.14, -0.86);
    body.add(tail);
    part(SPH, GREY, tail, { pos: [0, 0, -0.35], scale: [0.14, 0.14, 0.42], outline: 0.024 });
    part(SPH, DARK, tail, { pos: [0, 0.02, -0.72], scale: [0.11, 0.11, 0.18], outline: 0.02 });
    part(SPIKE, DARK, tail, { pos: [0, 0.03, -0.88], rot: [-Math.PI / 2, 0, 0], scale: [0.09, 0.2, 0.09], outline: 0.018 });

    this.seed = seed;
  }

  setPose(p) {
    const g = (k) => p[k] || 0;
    this.tilt.position.y = 0.92 + g('bodyY');
    this.tilt.rotation.set(g('pitch'), 0, g('roll'), 'YXZ');
    this.neck.rotation.set(g('neckX'), g('neckY'), 0);
    this.head.rotation.set(g('headX'), g('headY'), g('headZ'));
    this.jaw.rotation.x = g('jaw');
    for (const e of this.ears) e.rotation.x = g('ears');
    this.tail.rotation.set(g('tailX'), g('tailY'), 0);
    for (const k of ['fl', 'fr', 'bl', 'br']) {
      this[k].up.rotation.x = g(k + 'U');
      this[k].up.rotation.z = g(k + 'Z');
      this[k].lo.rotation.x = g(k + 'L');
    }
  }
}
