/**
 * SociaVault — scraping of public profile stats and recent posts.
 * Secret: SOCIAVAULT_API_KEY.
 *
 * ⚠️ Endpoints and response fields vary per network; they are isolated in ENDPOINTS / normalize*() so
 * they can be adjusted against https://docs.sociavault.com once the API key is available.
 */
import { requireEnv } from './http.ts';
import type { Account, DailyPoint, PlatformId, Post } from './types.ts';

const BASE = 'https://api.sociavault.com/v1/scrape';

const ENDPOINTS: Partial<Record<PlatformId, { profile: string; posts: string }>> = {
  tiktok: { profile: '/tiktok/profile', posts: '/tiktok/videos' },
  instagram: { profile: '/instagram/profile', posts: '/instagram/posts' },
  youtube: { profile: '/youtube/channel', posts: '/youtube/channel-videos' },
  x: { profile: '/twitter/profile', posts: '/twitter/user-tweets' },
  facebook: { profile: '/facebook/profile', posts: '/facebook/profile/posts' },
  threads: { profile: '/threads/profile', posts: '/threads/user-posts' },
  linkedin: { profile: '/linkedin/profile', posts: '/linkedin/posts' },
};

async function sv(path: string, handle: string): Promise<Record<string, unknown>> {
  const res = await fetch(`${BASE}${path}?handle=${encodeURIComponent(handle)}`, {
    headers: { 'X-API-Key': requireEnv('SOCIAVAULT_API_KEY') },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(`SociaVault ${res.status}: ${JSON.stringify(data)}`);
  return (data?.data ?? data) as Record<string, unknown>;
}

/** Reads the first numeric/string value found among several possible (nested) keys. */
function pick(obj: unknown, ...paths: string[]): unknown {
  for (const path of paths) {
    let cur: unknown = obj;
    for (const key of path.split('.')) {
      cur = cur && typeof cur === 'object' ? (cur as Record<string, unknown>)[key] : undefined;
    }
    if (cur !== undefined && cur !== null && cur !== '') return cur;
  }
  return undefined;
}
const num = (obj: unknown, ...paths: string[]) => Number(pick(obj, ...paths) ?? 0) || 0;
const str = (obj: unknown, ...paths: string[]) => String(pick(obj, ...paths) ?? '');

function normalizePost(platform: PlatformId, raw: unknown, i: number): Post {
  const ts = pick(raw, 'createTime', 'create_time', 'timestamp', 'taken_at', 'publishedAt', 'created_at');
  const date = typeof ts === 'number' ? new Date(ts < 1e12 ? ts * 1000 : ts) : new Date(String(ts ?? Date.now()));
  return {
    id: str(raw, 'id', 'aweme_id', 'video_id', 'shortcode') || `${platform}-${i}`,
    platform,
    caption: str(raw, 'desc', 'caption', 'caption.text', 'title', 'text', 'full_text').slice(0, 200),
    publishedAt: (isNaN(date.getTime()) ? new Date() : date).toISOString(),
    views: num(raw, 'stats.playCount', 'statistics.play_count', 'play_count', 'view_count', 'views', 'video_view_count'),
    likes: num(raw, 'stats.diggCount', 'statistics.digg_count', 'like_count', 'likes', 'favorite_count'),
    comments: num(raw, 'stats.commentCount', 'statistics.comment_count', 'comment_count', 'comments', 'reply_count'),
    shares: num(raw, 'stats.shareCount', 'statistics.share_count', 'share_count', 'shares', 'retweet_count'),
  };
}

/**
 * Best-time engine input: average engagement of the posts published in each (weekday, hour) slot, then
 * smoothed over neighbouring hours so a handful of posts still give a usable heatmap.
 */
export function engagementHeatmap(posts: Post[], followers: number, timezoneOffset = 0): number[][] {
  const sum = Array.from({ length: 7 }, () => Array<number>(24).fill(0));
  const count = Array.from({ length: 7 }, () => Array<number>(24).fill(0));
  for (const p of posts) {
    // Shift to the user's local time (`timezoneOffset` = Date#getTimezoneOffset() on the phone).
    const d = new Date(new Date(p.publishedAt).getTime() - timezoneOffset * 60_000);
    const day = (d.getUTCDay() + 6) % 7;
    const hour = d.getUTCHours();
    const reach = Math.max(p.views, followers * 0.05, 1);
    sum[day][hour] += (p.likes + p.comments * 2 + p.shares * 3) / reach;
    count[day][hour] += 1;
  }
  const avg = sum.map((row, d) => row.map((v, h) => (count[d][h] ? v / count[d][h] : 0)));
  return avg.map((row, d) =>
    row.map((_, h) => {
      let total = 0;
      let weight = 0;
      for (let dh = -2; dh <= 2; dh++) {
        const hh = (h + dh + 24) % 24;
        const w = 1 / (1 + Math.abs(dh));
        total += avg[d][hh] * w;
        weight += w;
      }
      return total / weight;
    }),
  );
}

function dailyHistory(posts: Post[], followers: number): DailyPoint[] {
  const byDay = new Map<string, DailyPoint>();
  for (let i = 29; i >= 0; i--) {
    const date = new Date(Date.now() - i * 86_400_000).toISOString().slice(0, 10);
    byDay.set(date, { date, followers, views: 0, likes: 0 });
  }
  for (const p of posts) {
    const point = byDay.get(p.publishedAt.slice(0, 10));
    if (point) {
      point.views += p.views;
      point.likes += p.likes;
    }
  }
  return [...byDay.values()];
}

/**
 * Fetches and normalizes a profile. Follower history needs daily snapshots (see README → "Historique");
 * until then, the follower curve is flat and the deltas come from the posts of the last 14 days.
 */
export async function fetchAccount(
  platform: PlatformId,
  handle: string,
  id: string,
  timezoneOffset = 0,
): Promise<Account> {
  const endpoints = ENDPOINTS[platform];
  if (!endpoints) throw new Error(`Stats ${platform} pas encore disponibles.`);
  const [profile, postsRaw] = await Promise.all([sv(endpoints.profile, handle), sv(endpoints.posts, handle)]);

  const list = (pick(postsRaw, 'videos', 'posts', 'items', 'tweets', 'aweme_list') ?? postsRaw) as unknown;
  const posts = (Array.isArray(list) ? list : []).slice(0, 50).map((raw, i) => normalizePost(platform, raw, i));

  const followers = num(profile, 'stats.followerCount', 'follower_count', 'followers', 'edge_followed_by.count', 'subscriberCount', 'followers_count');
  const views = posts.reduce((s, p) => s + p.views, 0);
  const likes = num(profile, 'stats.heartCount', 'total_favorited', 'likes') || posts.reduce((s, p) => s + p.likes, 0);
  const engagement = views ? (posts.reduce((s, p) => s + p.likes + p.comments + p.shares, 0) / views) * 100 : 0;

  const history = dailyHistory(posts, followers);
  const week = (from: number, key: 'views' | 'likes') => history.slice(from, from + 7).reduce((s, p) => s + p[key], 0);
  const pct = (a: number, b: number) => (b ? ((a - b) / b) * 100 : 0);

  return {
    id,
    platform,
    handle,
    displayName: str(profile, 'user.nickname', 'nickname', 'full_name', 'name', 'title') || handle,
    avatarUrl: str(profile, 'user.avatarLarger', 'avatar', 'profile_pic_url_hd', 'profile_pic_url', 'thumbnail') || undefined,
    bio: str(profile, 'user.signature', 'signature', 'biography', 'description', 'bio'),
    verified: Boolean(pick(profile, 'user.verified', 'verified', 'is_verified')),
    followers,
    following: num(profile, 'stats.followingCount', 'following_count', 'following', 'edge_follow.count'),
    likes,
    views: num(profile, 'viewCount', 'view_count') || views,
    posts: num(profile, 'stats.videoCount', 'media_count', 'videoCount', 'statuses_count') || posts.length,
    engagementRate: Math.round(engagement * 10) / 10,
    followersDelta: 0,
    viewsDelta: pct(week(23, 'views'), week(16, 'views')),
    likesDelta: pct(week(23, 'likes'), week(16, 'likes')),
    history,
    topPosts: [...posts].sort((a, b) => b.views - a.views).slice(0, 6),
    engagementByHour: engagementHeatmap(posts, followers, timezoneOffset),
  };
}
