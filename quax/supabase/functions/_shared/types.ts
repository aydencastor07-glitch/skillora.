// Mirror of `src/lib/types.ts` (the app) — keep both in sync.

export type PlatformId =
  | 'instagram'
  | 'tiktok'
  | 'youtube'
  | 'x'
  | 'facebook'
  | 'linkedin'
  | 'threads'
  | 'snapchat'
  | 'pinterest';

export type DailyPoint = { date: string; followers: number; views: number; likes: number };

export type Post = {
  id: string;
  platform: PlatformId;
  caption: string;
  publishedAt: string;
  views: number;
  likes: number;
  comments: number;
  shares: number;
};

export type Account = {
  id: string;
  platform: PlatformId;
  handle: string;
  displayName: string;
  avatarUrl?: string;
  bio: string;
  verified: boolean;
  followers: number;
  following: number;
  likes: number;
  views: number;
  posts: number;
  engagementRate: number;
  followersDelta: number;
  viewsDelta: number;
  likesDelta: number;
  history: DailyPoint[];
  topPosts: Post[];
  engagementByHour: number[][];
};
