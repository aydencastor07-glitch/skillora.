/**
 * Demo data, used while no backend / API key is configured (see `services/config.ts`).
 * Deterministic (seeded) so the app looks the same on every launch.
 */
import type { PlatformId } from '@/constants/platforms';
import type { Account, DailyPoint, Post } from '@/lib/types';

function seeded(seed: number) {
  let s = seed % 2147483647;
  if (s <= 0) s += 2147483646;
  return () => (s = (s * 16807) % 2147483647) / 2147483647;
}

type Profile = {
  handle: string;
  displayName: string;
  bio: string;
  followers: number;
  following: number;
  avgViews: number;
  posts: number;
  engagementRate: number;
  growth: number;
  /** Hours (0-23) where the audience is the most active, with a weight. */
  peaks: [number, number][];
  weekendBoost: number;
};

const PROFILES: Record<PlatformId, Profile> = {
  instagram: {
    handle: 'quax.studio',
    displayName: 'Quax Studio',
    bio: 'Créateur de contenu · Lifestyle & tech ✨',
    followers: 48_200,
    following: 612,
    avgViews: 21_000,
    posts: 214,
    engagementRate: 5.8,
    growth: 3.2,
    peaks: [[12, 0.8], [19, 1], [21, 0.9]],
    weekendBoost: 1.15,
  },
  tiktok: {
    handle: 'quax.studio',
    displayName: 'Quax Studio',
    bio: 'Des vidéos qui font du bruit 🔊',
    followers: 186_400,
    following: 98,
    avgViews: 94_000,
    posts: 342,
    engagementRate: 9.4,
    growth: 7.9,
    peaks: [[7, 0.5], [18, 0.8], [21, 1], [23, 0.7]],
    weekendBoost: 1.25,
  },
  youtube: {
    handle: 'QuaxStudio',
    displayName: 'Quax Studio',
    bio: 'Tutos, vlogs et coulisses. Nouvelle vidéo chaque mercredi.',
    followers: 23_900,
    following: 0,
    avgViews: 41_000,
    posts: 87,
    engagementRate: 4.1,
    growth: 1.8,
    peaks: [[17, 0.8], [20, 1]],
    weekendBoost: 1.35,
  },
  x: {
    handle: 'quaxstudio',
    displayName: 'Quax',
    bio: 'Threads, idées, coulisses de la création.',
    followers: 9_800,
    following: 431,
    avgViews: 12_000,
    posts: 1_904,
    engagementRate: 2.3,
    growth: 0.9,
    peaks: [[8, 0.9], [12, 1], [18, 0.7]],
    weekendBoost: 0.8,
  },
  facebook: {
    handle: 'quaxstudio',
    displayName: 'Quax Studio',
    bio: 'La page officielle de Quax Studio.',
    followers: 15_300,
    following: 0,
    avgViews: 6_500,
    posts: 402,
    engagementRate: 1.9,
    growth: -0.4,
    peaks: [[9, 0.7], [13, 1], [20, 0.8]],
    weekendBoost: 1.05,
  },
  linkedin: {
    handle: 'quax-studio',
    displayName: 'Quax Studio',
    bio: 'Social media & création de contenu pour les marques.',
    followers: 4_200,
    following: 380,
    avgViews: 3_900,
    posts: 96,
    engagementRate: 3.6,
    growth: 2.4,
    peaks: [[8, 1], [12, 0.8], [17, 0.6]],
    weekendBoost: 0.35,
  },
  threads: {
    handle: 'quax.studio',
    displayName: 'Quax Studio',
    bio: 'Les pensées en vrac du studio.',
    followers: 6_700,
    following: 120,
    avgViews: 4_800,
    posts: 158,
    engagementRate: 4.4,
    growth: 4.1,
    peaks: [[9, 0.8], [21, 1]],
    weekendBoost: 1.1,
  },
  snapchat: {
    handle: 'quaxstudio',
    displayName: 'Quax Studio',
    bio: 'Coulisses en direct 👻',
    followers: 11_200,
    following: 0,
    avgViews: 7_300,
    posts: 530,
    engagementRate: 6.2,
    growth: 1.2,
    peaks: [[16, 0.7], [22, 1]],
    weekendBoost: 1.2,
  },
  pinterest: {
    handle: 'quaxstudio',
    displayName: 'Quax Studio',
    bio: 'Moodboards & inspirations.',
    followers: 3_100,
    following: 210,
    avgViews: 18_000,
    posts: 640,
    engagementRate: 1.4,
    growth: 0.6,
    peaks: [[14, 0.7], [21, 1]],
    weekendBoost: 1.3,
  },
};

const CAPTIONS = [
  'Ma routine du matin en 30 secondes ☀️',
  '3 astuces que personne ne te dit sur le montage',
  'POV : tu découvres enfin le bon réglage',
  'Coulisses du tournage de la semaine 🎬',
  'Le setup complet (budget mini)',
  'On a testé la tendance du moment…',
  'Réponse à vos questions en commentaire',
  'Avant / après : ça change tout',
];

function buildHeatmap(profile: Profile, rand: () => number): number[][] {
  return Array.from({ length: 7 }, (_, day) =>
    Array.from({ length: 24 }, (_, hour) => {
      const base = hour < 6 ? 0.05 : 0.2;
      const peak = profile.peaks.reduce(
        (sum, [h, w]) => sum + w * Math.exp(-((hour - h) ** 2) / 3.5),
        0,
      );
      const dayFactor = day >= 5 ? profile.weekendBoost : 1 + (day === 1 || day === 3 ? 0.08 : 0);
      return Math.max(0, (base + peak) * dayFactor * (0.85 + rand() * 0.3));
    }),
  );
}

function buildHistory(profile: Profile, rand: () => number, now: Date): DailyPoint[] {
  const days = 30;
  const dailyGrowth = profile.growth / 100 / 7;
  const points: DailyPoint[] = [];
  let followers = profile.followers / Math.pow(1 + dailyGrowth, days - 1);
  for (let i = days - 1; i >= 0; i--) {
    const date = new Date(now.getTime() - i * 86_400_000);
    const spike = rand() > 0.9 ? 2.4 : 1;
    const views = profile.avgViews * (0.6 + rand() * 0.8) * spike;
    points.push({
      date: date.toISOString().slice(0, 10),
      followers: Math.round(followers),
      views: Math.round(views),
      likes: Math.round(views * (profile.engagementRate / 100) * (0.7 + rand() * 0.5)),
    });
    followers *= 1 + dailyGrowth * (0.4 + rand() * 1.2) * (spike > 1 ? 2 : 1);
  }
  // Rescale so the last day matches the current follower count exactly.
  const scale = profile.followers / points[points.length - 1].followers;
  return points.map((pt) => ({ ...pt, followers: Math.round(pt.followers * scale) }));
}

function buildPosts(platform: PlatformId, profile: Profile, rand: () => number, now: Date): Post[] {
  return Array.from({ length: 6 }, (_, i) => {
    const views = Math.round(profile.avgViews * (0.5 + rand() * 3.5));
    const likes = Math.round(views * (profile.engagementRate / 100) * (0.8 + rand()));
    return {
      id: `${platform}-post-${i}`,
      platform,
      caption: CAPTIONS[Math.floor(rand() * CAPTIONS.length)],
      publishedAt: new Date(now.getTime() - (i * 3 + 1 + rand() * 2) * 86_400_000).toISOString(),
      views,
      likes,
      comments: Math.round(likes * (0.02 + rand() * 0.05)),
      shares: Math.round(likes * (0.01 + rand() * 0.08)),
    };
  }).sort((a, b) => b.views - a.views);
}

export function mockAccount(platform: PlatformId, now = new Date()): Account {
  const profile = PROFILES[platform];
  const rand = seeded(platform.split('').reduce((sum, c) => sum * 31 + c.charCodeAt(0), 7));
  const history = buildHistory(profile, rand, now);
  const sum = (from: number, to: number, key: 'views' | 'likes') =>
    history.slice(from, to).reduce((s, p) => s + p[key], 0);
  const pct = (a: number, b: number) => (b === 0 ? 0 : ((a - b) / b) * 100);
  const last = history.length;

  return {
    id: `demo-${platform}`,
    platform,
    handle: profile.handle,
    displayName: profile.displayName,
    bio: profile.bio,
    verified: profile.followers > 100_000,
    followers: profile.followers,
    following: profile.following,
    likes: Math.round(profile.avgViews * profile.posts * (profile.engagementRate / 100)),
    views: Math.round(profile.avgViews * profile.posts),
    posts: profile.posts,
    engagementRate: profile.engagementRate,
    followersDelta: pct(history[last - 1].followers, history[last - 8].followers),
    viewsDelta: pct(sum(last - 7, last, 'views'), sum(last - 14, last - 7, 'views')),
    likesDelta: pct(sum(last - 7, last, 'likes'), sum(last - 14, last - 7, 'likes')),
    history,
    topPosts: buildPosts(platform, profile, rand, now),
    engagementByHour: buildHeatmap(profile, rand),
  };
}

/** Accounts connected by default in demo mode. */
export const DEMO_CONNECTED: PlatformId[] = ['instagram', 'tiktok', 'youtube', 'x', 'facebook'];
