// Caméra "plan-séquence" : interpolation continue (Hermite) entre des positions
// orbitales autour de cibles mobiles. Aucune coupure.
import * as THREE from 'three';
import { DEG, wrapPi } from './util.js';

const NV = 11; // fx fy fz lx ly lz az el d fov sl

export class CineCam {
  constructor(story, shots, focus) {
    this.story = story;
    this.focus = focus; // (name) => {x,y,z,yaw}
    this.keys = shots.map((k) => ({ ...k, tr: story.realOf(k.t) }));
    this.pos = new THREE.Vector3();
    this.look = new THREE.Vector3();
    this.fov = 55;
    this.speedLines = 0;
  }

  vec(k) {
    const f = this.focus(k.f);
    const l = k.lk ? this.focus(k.lk) : f;
    return [f.x, f.y, f.z, l.x, l.y + (k.h || 0), l.z, f.yaw + k.az * DEG, k.el, k.d, k.fov || 55, k.sl || 0];
  }

  update(treal) {
    const K = this.keys;
    let i = 0;
    while (i < K.length - 2 && treal >= K[i + 1].tr) i++;
    const ids = [Math.max(0, i - 1), i, i + 1, Math.min(K.length - 1, i + 2)];
    const V = ids.map((j) => this.vec(K[j]));
    const Ts = ids.map((j) => K[j].tr);
    // déroule les angles d'azimut
    for (let j = 1; j < 4; j++) V[j][6] = V[j - 1][6] + wrapPi(V[j][6] - V[j - 1][6]);
    const t0 = Ts[1], t1 = Ts[2];
    const dt = Math.max(1e-4, t1 - t0);
    let u = Math.min(1, Math.max(0, (treal - t0) / dt));
    const u2 = u * u, u3 = u2 * u;
    const h00 = 2 * u3 - 3 * u2 + 1, h10 = u3 - 2 * u2 + u, h01 = -2 * u3 + 3 * u2, h11 = u3 - u2;
    const out = new Array(NV);
    for (let c = 0; c < NV; c++) {
      const p0 = V[0][c], p1 = V[1][c], p2 = V[2][c], p3 = V[3][c];
      const m1 = ids[0] === ids[1] ? (p2 - p1) / dt : (p2 - p0) / Math.max(1e-4, Ts[2] - Ts[0]);
      const m2 = ids[3] === ids[2] ? (p2 - p1) / dt : (p3 - p1) / Math.max(1e-4, Ts[3] - Ts[1]);
      out[c] = h00 * p1 + h10 * dt * m1 + h01 * p2 + h11 * dt * m2;
    }
    const az = out[6], el = out[7] * DEG, d = Math.max(0.6, out[8]);
    this.pos.set(
      out[0] + Math.sin(az) * Math.cos(el) * d,
      out[1] + Math.sin(el) * d,
      out[2] + Math.cos(az) * Math.cos(el) * d,
    );
    this.look.set(out[3], out[4], out[5]);
    this.fov = out[9];
    this.speedLines = Math.max(0, out[10]);
    return this;
  }
}
