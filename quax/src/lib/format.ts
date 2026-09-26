const DAYS = ['dimanche', 'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi'];
const DAYS_SHORT = ['dim.', 'lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.'];
const MONTHS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];

/** 1234 → "1,2 k", 2500000 → "2,5 M" (French style). */
export function formatCompact(value: number): string {
  const abs = Math.abs(value);
  const units: [number, string][] = [
    [1e9, ' Md'],
    [1e6, ' M'],
    [1e3, ' k'],
  ];
  for (const [size, suffix] of units) {
    if (abs >= size) {
      const n = value / size;
      const digits = Math.abs(n) >= 100 ? 0 : 1;
      return n.toFixed(digits).replace(/\.0$/, '').replace('.', ',') + suffix;
    }
  }
  return String(Math.round(value));
}

export function formatDelta(pct: number): string {
  const sign = pct > 0 ? '+' : '';
  return `${sign}${pct.toFixed(1).replace('.', ',')} %`;
}

export function formatPercent(pct: number): string {
  return `${pct.toFixed(1).replace('.', ',')} %`;
}

const pad = (n: number) => String(n).padStart(2, '0');

export function formatTime(date: Date): string {
  return `${pad(date.getHours())}h${pad(date.getMinutes())}`;
}

export function formatDayLabel(date: Date, now = new Date()): string {
  const startOf = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const diff = Math.round((startOf(date) - startOf(now)) / 86_400_000);
  if (diff === 0) return "Aujourd'hui";
  if (diff === 1) return 'Demain';
  if (diff === -1) return 'Hier';
  const day = DAYS[date.getDay()];
  return `${day.charAt(0).toUpperCase()}${day.slice(1)} ${date.getDate()} ${MONTHS[date.getMonth()]}`;
}

export function formatDateTime(date: Date, now = new Date()): string {
  return `${formatDayLabel(date, now)} · ${formatTime(date)}`;
}

export function formatShortDate(iso: string): string {
  const d = new Date(iso);
  return `${d.getDate()} ${MONTHS[d.getMonth()]}`;
}

/** Monday-first index (0 = lundi) → short French day name. */
export function weekdayShort(mondayIndex: number): string {
  return DAYS_SHORT[(mondayIndex + 1) % 7];
}

export function weekdayLong(mondayIndex: number): string {
  return DAYS[(mondayIndex + 1) % 7];
}

export function relativeFromNow(iso: string, now = new Date()): string {
  const minutes = Math.round((new Date(iso).getTime() - now.getTime()) / 60_000);
  const abs = Math.abs(minutes);
  const text =
    abs < 60 ? `${abs} min` : abs < 60 * 24 ? `${Math.round(abs / 60)} h` : `${Math.round(abs / 1440)} j`;
  return minutes >= 0 ? `dans ${text}` : `il y a ${text}`;
}
