// « Le Procès » — le scénario calé sur le script (voix off ajoutée plus tard).
// Tout est fonction du temps : on peut avancer / reculer librement.
export const T_END = 75;

const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const lerp = (a, b, t) => a + (b - a) * t;
export const sstep = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
const bump = (a, b, c, d, x) => sstep(a, b, x) * (1 - sstep(c, d, x));
const PI = Math.PI;
const n1 = (t, s = 0) => Math.sin(t * 1.3 + s) * 0.6 + Math.sin(t * 2.9 + s * 2) * 0.4;

// ---------- Le script, phrase par phrase (pour la voix off / sous-titres) ----------
export const BEATS = [
  [0, 8.0, 'I was standing there in court facing a man who was accusing me of making him deaf and demanding millions of dollars in damages.'],
  [8.0, 9.5, 'He was crying.'],
  [9.5, 12.8, 'The judge was looking at me like I was a monster,'],
  [12.8, 17.0, 'and my son was playing Angry Birds at full volume in the courtroom.'],
  [17.0, 20.0, '"Don\'t worry, Dad, I got this." He\'s ten.'],
  [20.0, 23.6, 'I reached out to grab the phone from him; he dodged.'],
  [23.6, 27.8, 'The judge put on his glasses: "Silence! Cut that sound immediately!"'],
  [27.8, 32.1, 'My son pulled out a mini JBL speaker from his bag and connected it.'],
  [32.1, 33.6, 'I wanted to die.'],
  [33.6, 37.1, 'The sound blasted through the entire courthouse. People jumped.'],
  [37.1, 41.3, 'The supposedly deaf man didn\'t even flinch, didn\'t blink; he kept crying.'],
  [41.3, 43.9, 'Then my son screamed: "NO! I LOST!"'],
  [43.9, 47.3, 'And the deaf man slammed the table: "TURN THAT THING OFF!"'],
  [47.3, 48.9, 'The whole room froze.'],
  [48.9, 52.7, 'He turned bright red, trying to find words... too late.'],
  [52.7, 56.1, 'I stood up: "Your Honor, he can hear perfectly fine."'],
  [56.1, 58.3, 'The man walked out empty-handed.'],
  [58.3, 64.9, 'My son held up his phone: "Told you I had this, Dad. Can we sue him for making me lose my level?"'],
  [64.9, 66.6, 'He was ten years old.'],
  [66.6, 72.5, 'Would you have trusted a 10-year-old in a courtroom? Tell me in the comments.'],
];

// ---------- Mélange de poses ----------
function mix(a, b, w) {
  if (w <= 0) return a;
  const o = { ...a };
  for (const k in b) o[k] = lerp(a[k] === undefined ? DEF[k] || 0 : a[k], b[k], w);
  return o;
}
const DEF = { lX: 0.05, rX: 0.05, lZ: 0.1, rZ: -0.1, lEl: -0.18, rEl: -0.18, lookW: 0.75 };
// segments : [t0, t1, pose (objet ou fonction(t)), fondu]
function layer(t, base, segs) {
  let p = { ...base };
  for (const [a, b, pose, f = 0.35] of segs) {
    const w = bump(a - f, a, b, b + f, t);
    if (w > 0) p = mix(p, typeof pose === 'function' ? pose(t) : pose, w);
  }
  return p;
}
const talk = (t, spans, amp = 0.35) => {
  for (const [a, b, k = 1] of spans) if (t > a && t < b) {
    const e = bump(a, a + 0.08, b - 0.1, b, t);
    return e * k * clamp(0.12 + amp * Math.abs(Math.sin(t * 17.3) * 0.7 + Math.sin(t * 9.1) * 0.5), 0, 1);
  }
  return 0;
};

// Assis : hanches à 0.56 m du sol, quelle que soit la taille
// Mains : cible dans le repère du buste (x = gauche du perso, y = haut, z = devant)
const HL = (x, y, z, pole = 0, w = 1) => ({ lIK: w, lhx: x, lhy: y, lhz: z, lPole: pole });
const HR = (x, y, z, pole = 0, w = 1) => ({ rIK: w, rhx: x, rhy: y, rhz: z, rPole: pole });
const WR = (x, y, z, w = 1) => ({ rW: w, rwx: x, rwy: y, rwz: z });
const WL = (x, y, z, w = 1) => ({ lW: w, lwx: x, lwy: y, lwz: z });
const LEGS_SIT = (s) => ({ sit: 1, lHip: -1.52, rHip: -1.52, lKnee: 1.5, rKnee: 1.5, lHipZ: 0.06, rHipZ: -0.06, spineX: 0.06 });
const SIT = (s, ty = 0.2, tz = 0.42) => ({ ...LEGS_SIT(s), ...HL(0.16, ty, tz), ...HR(-0.16, ty, tz), lWrX: 0.3, rWrX: 0.3 });
const STAND = { sit: 0, hipY: 0, lHip: 0, rHip: 0, lKnee: 0, rKnee: 0, spineX: 0, lHipZ: 0.04, rHipZ: -0.04, lIK: 0, rIK: 0, lWrX: 0, rWrX: 0 };

// Positions (monde)
export const SEAT = {
  dad: [-3.2, -4.0], kid: [-1.95, -4.0], plaintiff: [2.1, -4.0], lawyer: [3.35, -4.0],
};
export const JUDGE_ROOT = [0, 0.55, -9.3];
export const BAG_TOP = [-1.45, 0.42, -3.85];
export const TABLE_SPK = [-1.52, 0.86, -4.62];

// ---------- Personnages : placement + pose + visage + regard ----------
export function cast(t, H) {
  const out = {};
  const head = (k) => H[k].headWorld();
  const sc = { dad: 1, kid: 0.74, plaintiff: 1, lawyer: 1, judge: 1.02 };

  // ===== PÈRE =====
  {
    const s = sc.dad;
    const standing = t < 8.4 ? 1 - sstep(8.0, 8.4, t) : sstep(52.8, 53.6, t);
    const pos = [SEAT.dad[0], 0, lerp(SEAT.dad[1], -4.28, standing)];
    let yaw = PI;
    if (t < 8.4) yaw = lerp(PI / 2 + 0.25, PI, sstep(8.0, 8.4, t));
    const base = mix(SIT(s), { ...STAND, lX: 0.08, rX: 0.08, lEl: -0.25, rEl: -0.25 }, standing);
    const p = layer(t, base, [
      [0, 8.0, { lX: 0.1, rX: -0.25, rEl: -1.0, rZ: 0.12, lEl: -0.25 }],
      [20.3, 22.4, (u) => ({ ...HR(-0.66, 0.38 + 0.03 * Math.sin(u * 9), 0.3, 0.3), spineZ: 0.24, spineY: -0.3, rWrX: -0.2 }), 0.25],
      [32.2, 33.6, { ...HR(0.0, 0.7, 0.19, -0.2), spineX: 0.32, neckX: 0.3, lookW: 0.1, rWrX: 1.0 }, 0.2],
      [53.4, 56.0, { ...HR(-0.22, 0.44, 0.42, 0.2), rWrX: -0.6, rIK: 1 }, 0.3],
    ]);
    let look = head('plaintiff');
    if (t > 8.2) look = head('judge');
    if (t > 16.8 && t < 23.6) look = head('kid');
    if (t > 27.8 && t < 32.1) look = head('kid');
    if (t > 37 && t < 41.3) look = head('plaintiff');
    if (t > 41.3 && t < 44.1) look = head('kid');
    if (t > 44.1 && t < 53) look = head('plaintiff');
    if (t > 53 && t < 56) look = head('judge');
    if (t > 56 && t < 58.5) look = head('plaintiff');
    if (t > 58.5) look = head('kid');
    const f = {
      angry: bump(0, 0.3, 7.5, 8, t) * 0.4 + bump(20, 20.4, 23.3, 23.8, t) * 0.5,
      sad: bump(32, 32.4, 34, 35, t) * 0.8 + bump(9.5, 10, 17, 17.5, t) * 0.4,
      closed: bump(32.1, 32.3, 33.5, 33.7, t),
      wide: bump(33.6, 33.8, 35.5, 36.5, t) + bump(43.9, 44.1, 48, 49, t) * 0.7,
      browUp: bump(43.9, 44.1, 48, 49, t) + bump(64.9, 65.2, 70, 71, t) * 0.6,
      smile: bump(58.8, 59.5, 75, 76, t) * 0.55 + bump(52.8, 53.2, 56, 56.5, t) * 0.3,
      open: talk(t, [[53.4, 56.0]]) + bump(33.6, 33.8, 35, 36, t) * 0.25,
    };
    if (t > 64.9 && t < 66.6) p.headY = (p.headY || 0) + 0.18 * Math.sin((t - 64.9) * 9);
    out.dad = { pos, yaw, p, f, look };
  }

  // ===== ENFANT =====
  {
    const s = sc.kid;
    const pos = [SEAT.kid[0], 0, SEAT.kid[1]];
    const PLAY = (u, k = 1) => ({ ...HL(0.105, 0.34, 0.3, 0.2), ...HR(-0.105, 0.34 + 0.006 * Math.sin(u * 13) * k, 0.3, 0.2), neckX: 0.32, lookW: 0.9, lWrX: -0.35, rWrX: -0.35, lWrZ: -0.9, rWrZ: 0.9, lCurl: 0.8, rCurl: 0.8 });
    const p = layer(t, SIT(s, 0.28, 0.5), [
      [0, 17.2, (u) => PLAY(u)],
      [17.2, 20.2, (u) => ({ ...PLAY(u, 0), neckX: 0, ...HL(0.105, 0.28, 0.28, 0.2), ...HR(-0.105, 0.28, 0.28, 0.2) })],
      [20.2, 22.6, { ...PLAY(0, 0), spineZ: 0.36, spineY: 0.3, ...HL(-0.12, 0.34, 0.22), ...HR(-0.3, 0.36, 0.16, 0.3), neckX: 0.1 }, 0.2],
      [22.6, 27.9, (u) => PLAY(u)],
      [27.9, 29.45, { ...WR(...BAG_TOP), rCurl: 0.8, spineX: 0.5, spineZ: 0.3, neckX: 0.25, ...HL(0.16, 0.28, 0.5) }, 0.3],
      [29.45, 30.6, { ...WR(TABLE_SPK[0], TABLE_SPK[1] - 0.03, TABLE_SPK[2]), rCurl: 0.8, spineX: 0.25, ...HL(0.16, 0.28, 0.5) }, 0.25],
      [30.6, 41.2, (u) => ({ ...PLAY(u), spineX: 0.06 + 0.06 * Math.sin(u * 8), neckX: 0.25 + 0.08 * Math.sin(u * 8) })],
      [41.3, 43.8, { spineX: -0.25, ...HL(0.14, 0.8, 0.03, 0.9), ...HR(-0.14, 0.8, 0.03, 0.9), neckX: -0.3 }, 0.15],
      [43.9, 52.7, { spineX: -0.12, ...HL(0.14, 0.25, 0.4), ...HR(-0.14, 0.25, 0.4) }],
      [58.3, 72, (u) => ({ ...HR(0.1, 0.74 + 0.02 * Math.sin(u * 3), 0.3, 0.3), rWrX: 0.2, rCurl: 0.9, ...HL(0.16, 0.28, 0.5), spineY: 0.28, spineZ: -0.08 })],
    ]);
    let look = null;
    if (t > 17.2 && t < 20.1) look = head('dad');
    if (t > 20.2 && t < 22.5) look = head('dad');
    if (t > 43.9 && t < 53) look = head('plaintiff');
    if (t > 53 && t < 56.2) look = head('dad');
    if (t > 56.2 && t < 58.3) look = head('plaintiff');
    if (t > 58.3) look = head('dad');
    const lost = bump(41.2, 41.35, 43.8, 44.2, t);
    const f = {
      smile: bump(17.2, 17.5, 19.8, 20.3, t) * 0.8 + bump(58.3, 58.8, 75, 76, t) * 0.9 + bump(0, 0.1, 17, 17.2, t) * 0.15 + bump(30.6, 31, 41, 41.3, t) * 0.4,
      open: Math.max(talk(t, [[17.3, 18.9], [58.9, 60.9], [61.3, 64.3]]), lost * (0.9 + 0.1 * Math.sin(t * 20))),
      mwide: lost * 0.8,
      angry: lost * 0.5 - bump(58.3, 58.8, 75, 76, t) * 0.2,
      squint: lost * 1.2,
      wide: bump(43.9, 44.1, 47.5, 48.5, t) * 1.2,
      browUp: bump(43.9, 44.1, 47.5, 48.5, t) + bump(17.2, 17.5, 19.8, 20.3, t) * 0.4,
    };
    if (t < 17.2 || (t > 22.6 && t < 27.9) || (t > 30.6 && t < 41.2)) { f.eyeX = 0.25; }
    out.kid = { pos, yaw: PI, p, f, look, lost };
  }

  // ===== PLAIGNANT (le « sourd ») =====
  {
    const s = sc.plaintiff;
    const stand = sstep(44.4, 45.2, t);
    let pos = [SEAT.plaintiff[0], 0, lerp(SEAT.plaintiff[1], -4.3, stand)];
    let yaw = PI;
    let base = mix(SIT(s, 0.22, 0.38), { ...STAND, spineX: 0.1, lX: 0.05, rX: 0.05 }, stand);
    // il sort : marche dans l'allée jusqu'à la porte
    const W0 = 56.1;
    if (t > W0) {
      const path = [[2.1, -4.3], [0.8, -3.4], [0.0, -2.2], [0.0, 4], [0.0, 10.6]];
      const dist = Math.max(0, (t - W0 - 0.3) * 1.35);
      let d = dist, i = 0;
      let seg = Math.hypot(path[1][0] - path[0][0], path[1][1] - path[0][1]);
      while (i < path.length - 2 && d > seg) { d -= seg; i++; seg = Math.hypot(path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1]); }
      const u = Math.min(1, d / seg);
      pos = [lerp(path[i][0], path[i + 1][0], u), 0, lerp(path[i][1], path[i + 1][1], u)];
      yaw = lerp(PI, Math.atan2(path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1]), sstep(W0, W0 + 0.6, t));
      const ph = dist / 0.75 * PI;
      const a = sstep(W0 + 0.2, W0 + 0.7, t);
      base = mix(base, {
        lHip: -0.4 * Math.sin(ph) * a, rHip: 0.4 * Math.sin(ph) * a, lKnee: 0.5 * Math.max(0, Math.cos(ph)) * a + 0.05, rKnee: 0.5 * Math.max(0, -Math.cos(ph)) * a + 0.05,
        lX: 0.3 * Math.sin(ph) * a, rX: -0.3 * Math.sin(ph) * a, spineX: 0.12, neckX: 0.25, hipY: -0.02 * Math.abs(Math.cos(ph)), lIK: 0, rIK: 0,
      }, 1);
    }
    const sob = (u) => ({ spineX: 0.2 + 0.03 * Math.sin(u * 11), neckX: 0.25 + 0.02 * Math.sin(u * 11), lookW: 0.3, ...HL(0.1, 0.22, 0.38), ...HR(-0.1, 0.22, 0.38) });
    const wipe = { ...HR(-0.02, 0.72, 0.16, 0.1), rWrX: 0.8, neckX: 0.35 };
    const p = layer(t, base, [
      [0, 43.8, sob, 0.2],
      [9.0, 10.6, wipe, 0.25],
      [43.85, 44.35, { ...HL(0.15, 0.62, 0.33), ...HR(-0.15, 0.62, 0.33), spineX: 0.0 }, 0.1],
      [44.35, 44.6, { ...HL(0.15, 0.18, 0.42), ...HR(-0.15, 0.18, 0.42), spineX: 0.3 }, 0.06],
      [44.6, 47.3, { spineX: 0.15, ...WL(-1.9, 1.3, -4.3), lCurl: 0.9, rIK: 0, rX: 0.0, rEl: -0.3, lWrX: -0.2 }, 0.3],
      [47.3, 52.7, (u) => ({ spineX: 0.05, lIK: 0, rIK: 0, lX: -0.25, lEl: -0.7, rX: -0.25, rEl: -0.7, headY: 0.25 * Math.sin((u - 47.3) * 1.6) }), 0.3],
      [52.7, 56.2, { spineX: 0.25, neckX: 0.4, lIK: 0, rIK: 0, lX: 0.1, rX: 0.1 }, 0.4],
    ]);
    let look = null;
    if (t > 43.8 && t < 47.8) look = head('kid');
    if (t > 47.8 && t < 49) look = head('judge');
    if (t > 52.7) look = null;
    const shout = bump(44.5, 44.6, 47.1, 47.3, t);
    const f = {
      tears: 1 - sstep(44.3, 44.6, t),
      sad: (1 - sstep(43.8, 44, t)) * 0.9 + bump(52.7, 53, 58, 59, t) * 0.5,
      squint: (1 - sstep(43.8, 44, t)) * 0.5,
      angry: shout * 1.2,
      open: Math.max(shout * (0.75 + 0.25 * Math.abs(Math.sin(t * 13))), (1 - sstep(43.8, 44, t)) * (0.12 + 0.06 * Math.sin(t * 11)), talk(t, [[49.4, 52.3, 0.5]]), bump(47.3, 47.4, 48.9, 49.2, t) * 0.45),
      mwide: shout * 0.6,
      wide: bump(47.3, 47.4, 52, 53, t) * 1.1,
      browUp: bump(47.3, 47.4, 52.7, 53.5, t),
      red: sstep(48.9, 51, t),
      eyeY: bump(49, 49.3, 52, 52.5, t) * 0.3 * Math.sin(t * 2.2),
      eyeX: bump(52.7, 53.2, 60, 61, t) * 0.25,
    };
    out.plaintiff = { pos, yaw, p, f, look, visible: t < 68.5 };
  }

  // ===== AVOCAT du plaignant =====
  {
    const s = sc.lawyer;
    const p = layer(t, SIT(s), [
      [0, 47, { neckX: 0.3, ...HR(-0.12, 0.21, 0.4) }],
      [33.6, 34.4, { spineX: -0.2, ...HL(0.25, 0.55, 0.3), ...HR(-0.25, 0.55, 0.3) }, 0.1],
      [49.2, 58, { ...HR(0.0, 0.71, 0.17, -0.2), rWrX: 1.0, neckX: 0.35, spineX: 0.25, lookW: 0.2 }, 0.3],
    ]);
    let look = t < 33.5 ? head('judge') : head('kid');
    if (t > 44 && t < 49) look = head('plaintiff');
    const f = { wide: bump(33.6, 33.8, 35, 36, t) + bump(44, 44.3, 49, 49.3, t), sad: bump(49, 49.3, 60, 61, t) * 0.7, closed: bump(49.3, 49.6, 58, 58.5, t) * 0.8 };
    out.lawyer = { pos: [SEAT.lawyer[0], 0, SEAT.lawyer[1]], yaw: PI, p, f, look };
  }

  // ===== JUGE =====
  {
    const base = { sit: 1, sitH: 0.62, lHip: -1.5, rHip: -1.5, lKnee: 1.45, rKnee: 1.45, spineX: 0.12, ...HL(0.18, 0.3, 0.46), ...HR(-0.18, 0.3, 0.46), lWrX: 0.3, rWrX: 0.3 };
    // coups de marteau : lever puis frapper
    const strike = (u) => {
      let up = 0, hit = 0;
      for (const s of [26.0, 26.6, 27.2, 57.4, 57.9]) {
        up = Math.max(up, bump(s - 0.4, s - 0.2, s - 0.12, s - 0.03, u));
        hit = Math.max(hit, bump(s - 0.05, s, s + 0.1, s + 0.25, u));
      }
      return { ...HR(-0.3, 0.48 + 0.3 * up - 0.06 * hit, 0.42 - 0.08 * up, 0.3), rWrX: -0.5 * up + 0.3 * hit };
    };
    const p = layer(t, base, [
      [23.7, 25.0, { ...HL(0.085, 0.76, 0.14, 0.6), ...HR(-0.085, 0.76, 0.14, 0.6), spineX: 0.02 }, 0.25],
      [25.0, 27.7, (u) => ({ ...strike(u), spineX: 0.28, neckX: -0.05 }), 0.2],
      [33.6, 34.5, { hipY: 0.05, spineX: -0.25, ...HL(0.28, 0.6, 0.35), ...HR(-0.28, 0.6, 0.35) }, 0.1],
      [34.5, 37.1, { ...HL(0.105, 0.76, 0.0, 0.9), ...HR(-0.105, 0.76, 0.0, 0.9), spineX: 0.1 }, 0.3],
      [57.1, 58.4, (u) => ({ ...strike(u), spineX: 0.15 }), 0.2],
    ]);
    let look = head('dad');
    if (t > 12.8 && t < 23.6) look = head('kid');
    if (t > 25 && t < 27.8) look = head('kid');
    if (t > 37.1 && t < 43.9) look = head('kid');
    if (t > 43.9 && t < 52.7) look = head('plaintiff');
    if (t > 56.1 && t < 58) look = head('plaintiff');
    const f = {
      angry: 0.55 + bump(24.8, 25, 27.8, 28.5, t) * 0.6 - bump(47, 47.3, 53, 53.5, t) * 0.5 - bump(55, 55.5, 75, 76, t) * 0.4,
      open: Math.max(talk(t, [[25.0, 27.6, 1.4]]), bump(33.6, 33.7, 34.4, 35, t) * 0.4),
      mwide: bump(25, 25.1, 27.6, 27.8, t) * 0.5,
      wide: bump(33.6, 33.7, 35, 36, t) + bump(47.3, 47.5, 49, 50, t) * 0.5,
      squint: bump(49, 49.5, 52.5, 53, t) * 0.8 + bump(9.5, 10, 12.8, 13, t) * 0.4,
      browUp: bump(47.3, 47.5, 49, 50, t),
      glasses: sstep(24.0, 24.9, t),
      smile: bump(55.5, 56, 75, 76, t) * 0.25,
    };
    out.judge = { pos: JUDGE_ROOT, yaw: 0, p, f, look, gavel: bump(24.9, 25.1, 27.6, 27.9, t) + bump(56.9, 57.1, 58.2, 58.5, t) };
  }
  return out;
}

// Figurants : public + huissiers (sursaut, têtes qui se tournent)
export function extras(t, i) {
  const jumpT = 33.65 + (i % 4) * 0.06;
  const jump = bump(jumpT, jumpT + 0.1, jumpT + 0.35, jumpT + 0.8, t);
  return {
    jump,
    f: { wide: jump + bump(44, 44.3, 49, 50, t) * 0.8 + bump(41.3, 41.5, 43, 44, t) * 0.5, open: jump * 0.4 + bump(47.3, 47.5, 49, 50, t) * 0.25, browUp: jump + bump(44, 44.3, 49, 50, t) },
    lookAt: t < 33.6 ? 'judge' : t < 41.3 ? 'kid' : t < 44 ? 'kid' : t < 56 ? 'plaintiff' : t < 60 ? 'plaintiff' : 'kid',
  };
}

// ---------- Plans de caméra ----------
// f(u) avec u ∈ [0,1] sur la durée du plan ; retourne pos, look (monde) + fov.
// Les coupes franches entre plans comme dans la vidéo de référence ; chaque plan bouge.
const V = (x, y, z) => ({ x, y, z });
const ease = (u) => u * u * (3 - 2 * u);
function orbit(tgt, az0, az1, el0, el1, d0, d1, dy = 0) {
  return (u, S) => {
    const c = typeof tgt === 'function' ? tgt(S) : tgt;
    const e = ease(u);
    const az = lerp(az0, az1, e) * PI / 180, el = lerp(el0, el1, e) * PI / 180, d = lerp(d0, d1, e);
    return { pos: V(c.x + Math.sin(az) * Math.cos(el) * d, c.y + Math.sin(el) * d, c.z + Math.cos(az) * Math.cos(el) * d), look: V(c.x, c.y + dy, c.z) };
  };
}
function dolly(p0, p1, l0, l1) {
  return (u) => {
    const e = ease(u);
    return { pos: V(lerp(p0[0], p1[0], e), lerp(p0[1], p1[1], e), lerp(p0[2], p1[2], e)), look: V(lerp(l0[0], l1[0], e), lerp(l0[1], l1[1], e), lerp(l0[2], l1[2], e)) };
  };
}
const HD = (k, oy = 0) => (S) => { const h = S.head(k); return V(h.x, h.y + oy, h.z); };
const MID = (a, b, oy = 0) => (S) => { const h = S.head(a), g = S.head(b); return V((h.x + g.x) / 2, (h.y + g.y) / 2 + oy, (h.z + g.z) / 2); };

export const SHOTS = [
  { t: 0, fov: 48, ap: 0.4, cam: dolly([0.4, 3.3, 9.5], [0.1, 2.2, 2.8], [0, 1.2, -6], [-0.4, 1.3, -6]), label: 'Plan large : la salle d’audience' },
  { t: 4.5, fov: 32, ap: 1, cam: orbit(HD('dad'), 125, 112, 2, 0, 1.7, 1.25), label: 'Le père, debout face à l’homme qui l’accuse' },
  { t: 8.0, fov: 30, ap: 1, cam: orbit(HD('plaintiff'), 200, 193, 0, 0, 0.95, 0.75), label: 'Il pleure' },
  { t: 9.5, fov: 34, ap: 1, cam: orbit(HD('judge'), 12, 2, -12, -7, 1.7, 1.2), label: 'Le juge le regarde comme un monstre' },
  { t: 12.8, fov: 34, ap: 1.2, cam: (u, S) => { const h = S.head('kid'); const ph = S.phonePos; const e = ease(u); return { pos: V(h.x + 0.28 - 0.05 * e, h.y + 0.2 - 0.04 * e, h.z + 0.32 - 0.08 * e), look: V(ph.x, ph.y, ph.z) }; }, focus: 'phone', label: 'L’enfant joue sur son téléphone, son à fond' },
  { t: 15.3, fov: 32, ap: 1, cam: orbit(HD('kid', -0.05), 192, 184, -6, -3, 0.95, 0.8) },
  { t: 17.0, fov: 30, ap: 1.1, cam: (u, S) => { const d = S.head('dad'), k = S.head('kid'); const e = ease(u); return { pos: V(d.x - 0.25 + 0.05 * e, d.y + 0.12, d.z + 0.38 - 0.05 * e), look: V(k.x, k.y, k.z) }; }, focus: 'kid', label: '« Don’t worry, Dad, I got this. »' },
  { t: 20.0, fov: 40, ap: 0.5, cam: orbit(MID('dad', 'kid', -0.2), 186, 174, 5, 4, 3.8, 3.3), label: 'Il tend la main… l’enfant esquive' },
  { t: 23.6, fov: 30, ap: 1, cam: orbit(HD('judge'), 22, 10, 0, 1, 0.95, 0.75), label: 'Le juge met ses lunettes' },
  { t: 25.4, fov: 38, ap: 0.8, cam: orbit(HD('judge', -0.2), -28, -10, -8, -5, 1.9, 1.35), label: '« Silence ! Coupez ce son ! »' },
  { t: 27.8, fov: 40, ap: 1, cam: (u, S) => { const e = ease(u); const sp = S.speakerPos; return { pos: V(-0.45 - 0.2 * e, 0.95 + 0.1 * e, -3.05 - 0.35 * e), look: V(lerp(-1.6, sp.x, e), lerp(0.55, sp.y, e), lerp(-3.9, sp.z, e)) }; }, focus: 'speaker', label: 'Il sort une mini enceinte de son sac' },
  { t: 30.5, fov: 30, ap: 1.1, cam: (u, S) => { const sp = S.speakerPos; const e = ease(u); return { pos: V(sp.x + 0.2 - 0.08 * e, sp.y + 0.12, sp.z - 0.75 + 0.12 * e), look: V(sp.x - 0.05, sp.y + 0.05, sp.z) }; }, focus: 'speaker', label: '… et la connecte' },
  { t: 32.1, fov: 32, ap: 1, cam: orbit(HD('dad'), 205, 198, 4, 3, 0.9, 0.8), label: 'J’avais envie de mourir' },
  { t: 33.6, fov: 44, ap: 0.3, shake: 1, cam: dolly([3.2, 3.5, -8.4], [2.9, 3.1, -8.0], [-1.4, 0.8, -4.0], [-1.2, 0.9, -3.8]), label: 'Le son explose dans le tribunal. Tout le monde sursaute' },
  { t: 37.1, fov: 34, ap: 1, cam: orbit(HD('plaintiff'), 168, 178, 2, 1, 1.5, 0.72), label: 'Le « sourd » ne bronche pas. Il pleure toujours' },
  { t: 41.3, fov: 38, ap: 1, cam: orbit(HD('kid'), 172, 182, -16, -12, 0.95, 0.78), label: '« NO! I LOST! »' },
  { t: 43.9, fov: 40, ap: 0.8, shake: 0.6, cam: (u, S) => { const h = S.head('plaintiff'); const e = ease(u); return { pos: V(1.2 - 0.1 * e, 1.0 + 0.2 * e, -5.6 - 0.35 * e), look: V(h.x, h.y - 0.12, h.z) }; }, focus: 'plaintiff', label: 'Il frappe la table : « TURN THAT THING OFF! »' },
  { t: 47.3, fov: 46, ap: 0.5, cam: dolly([3.7, 1.75, -5.7], [3.45, 1.6, -5.35], [-1.6, 1.15, -4.1], [-1.4, 1.15, -4.1]), focus: 'kid', label: 'Toute la salle se fige' },
  { t: 48.9, fov: 30, ap: 1.1, cam: orbit(HD('plaintiff'), 202, 166, 3, 2, 0.85, 0.72), label: 'Il devient rouge… trop tard' },
  { t: 52.7, fov: 34, ap: 1, cam: orbit(HD('dad'), 160, 178, -10, -6, 1.35, 1.05), label: '« Your Honor, he can hear perfectly fine. »' },
  { t: 56.1, fov: 38, ap: 0.8, cam: (u, S) => { const h = S.head('plaintiff'); const e = ease(u); return { pos: V(0.55 - 0.2 * e, 1.6, 2.4 - 0.2 * e), look: V(h.x, h.y - 0.05, h.z) }; }, focus: 'plaintiff', label: 'Il repart les mains vides' },
  { t: 58.3, fov: 30, ap: 1.1, cam: (u, S) => { const d = S.head('dad'), k = S.head('kid'); const e = ease(u); return { pos: V(d.x - 0.3 + 0.05 * e, d.y + 0.08, d.z + 0.42 - 0.08 * e), look: V(k.x + 0.05, k.y + 0.02, k.z) }; }, focus: 'kid', label: '« Told you I had this, Dad. »' },
  { t: 62.0, fov: 30, ap: 1.1, cam: orbit(HD('kid'), 186, 178, 0, 1, 0.9, 0.78), label: '« Can we sue him for making me lose my level? »' },
  { t: 64.9, fov: 30, ap: 1, cam: orbit(HD('dad'), 158, 166, 2, 2, 0.85, 0.75), label: 'Il avait dix ans' },
  { t: 66.6, fov: 40, ap: 0.5, cam: (u, S) => { const m = MID('dad', 'kid')(S); const e = ease(u); return { pos: V(lerp(m.x + 0.2, 0.5, e), lerp(1.45, 4.1, e), lerp(m.z - 2.1, -9.6, e)), look: V(lerp(m.x, -0.5, e), lerp(m.y - 0.1, 0.9, e), lerp(m.z, -2.5, e)) }; }, label: 'Question au public — la caméra s’élève. FIN' },
];
