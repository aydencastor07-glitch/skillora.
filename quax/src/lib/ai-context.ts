import { PLATFORMS } from '@/constants/platforms';
import { combinedHeatmap, topSlots } from '@/lib/best-time';
import { formatCompact, formatDelta, weekdayLong } from '@/lib/format';
import type { Account, ScheduledPost } from '@/lib/types';

/**
 * Compact, text-only snapshot of the user's accounts that is sent to the AI with each question, so it
 * can answer about *their* numbers without us sending the full 30-day history.
 */
export function buildAiContext(accounts: Account[], scheduled: ScheduledPost[]): string {
  if (accounts.length === 0) return 'Aucun compte connecté pour le moment.';
  const lines = accounts.map((a) => {
    const p = PLATFORMS[a.platform];
    const best = topSlots(a.engagementByHour, 2)
      .map((s) => `${weekdayLong(s.day)} ${s.hour}h`)
      .join(', ');
    const top = a.topPosts[0];
    return [
      `- ${p.name} @${a.handle}: ${formatCompact(a.followers)} abonnés (${formatDelta(a.followersDelta)} sur 7 j),`,
      `${formatCompact(a.views)} ${p.viewsLabel.toLowerCase()} au total (${formatDelta(a.viewsDelta)} sur 7 j),`,
      `engagement ${a.engagementRate} %, meilleurs créneaux: ${best}.`,
      top ? `Meilleur post récent: « ${top.caption} » (${formatCompact(top.views)} vues, ${formatCompact(top.likes)} likes).` : '',
    ].join(' ');
  });
  const global = topSlots(combinedHeatmap(accounts), 3)
    .map((s) => `${weekdayLong(s.day)} ${s.hour}h`)
    .join(', ');
  const upcoming = scheduled.filter((s) => s.status === 'scheduled').length;
  return [
    'Comptes connectés :',
    ...lines,
    `Meilleurs créneaux tous réseaux confondus : ${global}.`,
    `Publications programmées à venir : ${upcoming}.`,
  ].join('\n');
}
