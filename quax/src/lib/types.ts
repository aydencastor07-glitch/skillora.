import type { PlatformId } from '@/constants/platforms';

export type DailyPoint = {
  /** ISO date (yyyy-mm-dd). */
  date: string;
  followers: number;
  views: number;
  likes: number;
};

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
  /** Average engagement rate in percent. */
  engagementRate: number;
  /** Change over the last 7 days, in percent. */
  followersDelta: number;
  viewsDelta: number;
  likesDelta: number;
  /** Last 30 days, oldest first. */
  history: DailyPoint[];
  topPosts: Post[];
  /**
   * Average engagement per publication slot: 7 rows (Monday → Sunday) × 24 hours.
   * Filled from the scraping API in production, used by the "best time" engine.
   */
  engagementByHour: number[][];
};

export type PublishMode = 'now' | 'scheduled' | 'best';

export type PostStatus = 'scheduled' | 'publishing' | 'published' | 'failed';

export type ScheduledPost = {
  id: string;
  caption: string;
  platforms: PlatformId[];
  mode: PublishMode;
  scheduledAt: string;
  status: PostStatus;
  mediaKind: 'video' | 'image' | 'text';
  error?: string;
};

export type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  pending?: boolean;
};
