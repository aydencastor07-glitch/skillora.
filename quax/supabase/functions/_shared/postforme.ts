/**
 * Post for Me — publishing API + OAuth connection of the social accounts.
 * Secret: POSTFORME_API_KEY.
 *
 * ⚠️ Endpoints written from the public docs; double-check paths/fields against https://api.postforme.dev/docs
 * when the API key is available. Everything Post-for-Me-specific lives in this file.
 */
import { requireEnv } from './http.ts';
import type { PlatformId } from './types.ts';

const BASE = 'https://api.postforme.dev/v1';

export type PfmAccount = {
  id: string;
  platform: string;
  username?: string | null;
  status?: string;
};

async function pfm<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${requireEnv('POSTFORME_API_KEY')}`,
      'Content-Type': 'application/json',
      ...(init.headers ?? {}),
    },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(`Post for Me ${res.status}: ${JSON.stringify(data)}`);
  return data as T;
}

/** Quax platform id → Post for Me platform id. */
const PLATFORM: Partial<Record<PlatformId, string>> = {
  instagram: 'instagram',
  tiktok: 'tiktok',
  youtube: 'youtube',
  x: 'x',
  facebook: 'facebook',
  linkedin: 'linkedin',
  threads: 'threads',
  pinterest: 'pinterest',
};

export function toQuaxPlatform(p: string): PlatformId | null {
  const entry = Object.entries(PLATFORM).find(([, v]) => v === p);
  return (entry?.[0] as PlatformId) ?? null;
}

export async function authUrl(platform: PlatformId): Promise<string> {
  const pfmPlatform = PLATFORM[platform];
  if (!pfmPlatform) throw new Error(`La publication sur ${platform} n'est pas encore supportée.`);
  const { url } = await pfm<{ url: string }>('/social-accounts/auth-url', {
    method: 'POST',
    body: JSON.stringify({ platform: pfmPlatform }),
  });
  return url;
}

export async function listAccounts(): Promise<PfmAccount[]> {
  const { data } = await pfm<{ data: PfmAccount[] }>('/social-accounts');
  return data.filter((a) => a.status !== 'disconnected');
}

export async function disconnect(accountId: string): Promise<void> {
  await pfm(`/social-accounts/${encodeURIComponent(accountId)}/disconnect`, { method: 'POST' });
}

export async function createPost(input: {
  caption: string;
  accountIds: string[];
  mediaUrls?: string[];
  scheduledAt?: string;
}): Promise<{ id: string }> {
  return pfm<{ id: string }>('/social-posts', {
    method: 'POST',
    body: JSON.stringify({
      caption: input.caption,
      social_accounts: input.accountIds,
      media: (input.mediaUrls ?? []).map((url) => ({ url })),
      // Omitted = published right away.
      ...(input.scheduledAt ? { scheduled_at: input.scheduledAt } : {}),
    }),
  });
}
