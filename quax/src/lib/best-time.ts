import type { Account } from '@/lib/types';

export type Slot = {
  /** 0 = lundi … 6 = dimanche. */
  day: number;
  hour: number;
  /** Relative score between 0 and 1. */
  score: number;
};

/** Normalizes a 7×24 matrix so that its best slot equals 1. */
function normalize(matrix: number[][]): number[][] {
  const max = Math.max(...matrix.flat(), 0);
  if (max === 0) return matrix.map((row) => row.map(() => 0));
  return matrix.map((row) => row.map((v) => v / max));
}

/**
 * Combines the engagement heatmaps of several accounts. Each account is normalized first so that a
 * huge account doesn't drown out the others, then weighted by its audience size (log scale).
 */
export function combinedHeatmap(accounts: Account[]): number[][] {
  const out = Array.from({ length: 7 }, () => Array<number>(24).fill(0));
  if (accounts.length === 0) return out;
  let totalWeight = 0;
  for (const account of accounts) {
    const weight = Math.log10(account.followers + 10);
    totalWeight += weight;
    normalize(account.engagementByHour).forEach((row, d) =>
      row.forEach((v, h) => {
        out[d][h] += v * weight;
      }),
    );
  }
  return out.map((row) => row.map((v) => v / totalWeight));
}

export function topSlots(matrix: number[][], count = 3): Slot[] {
  const norm = normalize(matrix);
  const slots: Slot[] = [];
  norm.forEach((row, day) => row.forEach((score, hour) => slots.push({ day, hour, score })));
  return slots.sort((a, b) => b.score - a.score).slice(0, count);
}

/** Monday-first weekday index of a date. */
export function mondayIndex(date: Date): number {
  return (date.getDay() + 6) % 7;
}

/**
 * Finds the next moment (at least `minLeadMinutes` from now, within the next 7 days) that has the best
 * expected engagement. Slightly favors sooner slots so a post isn't delayed a whole week for a 2% gain.
 */
export function nextBestTime(accounts: Account[], now = new Date(), minLeadMinutes = 15): { date: Date; score: number } {
  const norm = normalize(combinedHeatmap(accounts));
  const start = new Date(now.getTime() + minLeadMinutes * 60_000);
  start.setMinutes(0, 0, 0);
  start.setHours(start.getHours() + 1);

  let best = { date: start, score: -1 };
  for (let i = 0; i < 7 * 24; i++) {
    const candidate = new Date(start.getTime() + i * 3_600_000);
    const raw = norm[mondayIndex(candidate)][candidate.getHours()];
    const decay = 1 - (i / (7 * 24)) * 0.15;
    const score = raw * decay;
    if (score > best.score) best = { date: candidate, score: raw };
  }
  return best;
}
