/**
 * Offline stand-in for the Quax AI, used in demo mode. It answers a handful of common questions from
 * the user's (mock) data so the chat experience can be designed before the Claude API is plugged in.
 */
import { PLATFORMS } from '@/constants/platforms';
import { combinedHeatmap, nextBestTime, topSlots } from '@/lib/best-time';
import { formatCompact, formatDateTime, formatDelta, weekdayLong } from '@/lib/format';
import type { Account } from '@/lib/types';

function has(text: string, ...words: string[]) {
  return words.some((w) => text.includes(w));
}

export function demoAnswer(question: string, accounts: Account[]): string {
  const q = question.toLowerCase();
  if (accounts.length === 0) {
    return "Connecte au moins un réseau social (onglet Accueil → « Connecter un compte ») et je pourrai analyser tes performances.";
  }

  const byFollowers = [...accounts].sort((a, b) => b.followers - a.followers);
  const byGrowth = [...accounts].sort((a, b) => b.followersDelta - a.followersDelta);

  if (has(q, 'moment', 'quand', 'heure', 'créneau', 'creneau', 'publier')) {
    const slots = topSlots(combinedHeatmap(accounts), 3);
    const next = nextBestTime(accounts);
    return [
      "D'après l'activité de ton audience, tes meilleurs créneaux sont :",
      ...slots.map((s, i) => `${i + 1}. ${weekdayLong(s.day)} vers ${s.hour}h`),
      '',
      `Le prochain meilleur moment est **${formatDateTime(next.date)}**. Choisis « Au meilleur moment » dans Publier et je m'en occupe.`,
    ].join('\n');
  }

  if (has(q, 'abonné', 'abonne', 'follower', 'croissance', 'grandi', 'monté', 'monte')) {
    return [
      'Évolution de tes abonnés sur 7 jours :',
      ...byGrowth.map(
        (a) => `• ${PLATFORMS[a.platform].name} : ${formatCompact(a.followers)} (${formatDelta(a.followersDelta)})`,
      ),
      '',
      `${PLATFORMS[byGrowth[0].platform].name} est ta plateforme qui grandit le plus vite. Continue d'y publier régulièrement.`,
    ].join('\n');
  }

  if (has(q, 'marché', 'marche', 'meilleur', 'top', 'performant', 'vues', 'viral')) {
    const posts = accounts.flatMap((a) => a.topPosts).sort((a, b) => b.views - a.views).slice(0, 3);
    return [
      'Tes contenus qui ont le mieux marché récemment :',
      ...posts.map(
        (p, i) =>
          `${i + 1}. « ${p.caption} » sur ${PLATFORMS[p.platform].name} — ${formatCompact(p.views)} vues, ${formatCompact(p.likes)} likes`,
      ),
      '',
      'Point commun : des formats courts avec une accroche dès la première seconde. Refais-en un dans le même style cette semaine.',
    ].join('\n');
  }

  if (has(q, 'légende', 'legende', 'caption', 'description', 'texte', 'idée', 'idee', 'hashtag')) {
    return [
      'Voici 3 idées de légendes :',
      '1. « Personne ne parle de ça… et pourtant ça change tout 👀 »',
      '2. « Sauvegarde ce post, tu vas en avoir besoin 📌 »',
      '3. « Dis-moi en commentaire si tu veux la partie 2 ⬇️ »',
      '',
      'Hashtags suggérés : #astuce #creator #tuto #pourtoi',
    ].join('\n');
  }

  const total = accounts.reduce((s, a) => s + a.followers, 0);
  return [
    `Tu as ${formatCompact(total)} abonnés au total sur ${accounts.length} réseaux.`,
    `Ton plus gros compte est ${PLATFORMS[byFollowers[0].platform].name} (${formatCompact(byFollowers[0].followers)}).`,
    '',
    'Je peux t\'aider à : trouver le meilleur moment pour publier, analyser tes abonnés, repérer tes meilleurs contenus ou écrire tes légendes. Qu\'est-ce que tu veux savoir ?',
    '',
    '_(Mode démo : branche l\'API IA pour des réponses complètes.)_',
  ].join('\n');
}
