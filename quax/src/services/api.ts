/**
 * Single entry point between the app and the outside world.
 *
 * - Demo mode (no backend configured): everything is simulated locally.
 * - Live mode: calls the Quax backend (Supabase Edge Functions), which holds the API keys and talks to
 *   Post for Me (publishing + account connection), SociaVault (stats scraping) and Claude (AI).
 */
import { fetch as expoFetch } from 'expo/fetch';

import type { PlatformId } from '@/constants/platforms';
import { mockAccount } from '@/lib/mock-data';
import type { Account, ChatMessage, ScheduledPost } from '@/lib/types';
import { API_ANON_KEY, API_URL, DEMO_MODE } from '@/services/config';
import { demoAnswer } from '@/services/demo-ai';

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

function headers(): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    ...(API_ANON_KEY ? { Authorization: `Bearer ${API_ANON_KEY}`, apikey: API_ANON_KEY } : {}),
  };
}

async function call<T>(fn: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_URL}/${fn}`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data?.error ?? `Erreur serveur (${res.status})`);
  return data as T;
}

/* ------------------------------------------------------------------ accounts */

export async function fetchAccounts(platforms: PlatformId[]): Promise<Account[]> {
  if (DEMO_MODE) {
    await wait(300);
    return platforms.map((p) => mockAccount(p));
  }
  const { accounts } = await call<{ accounts: Account[] }>('quax-social', {
    action: 'accounts',
    timezoneOffset: new Date().getTimezoneOffset(),
  });
  return accounts;
}

export type ConnectResult =
  | { kind: 'connected'; account: Account }
  /** The user must finish the OAuth flow of the network in the browser. */
  | { kind: 'oauth'; url: string };

export async function connectAccount(platform: PlatformId): Promise<ConnectResult> {
  if (DEMO_MODE) {
    await wait(900);
    return { kind: 'connected', account: mockAccount(platform) };
  }
  const { url } = await call<{ url: string }>('quax-publish', { action: 'connect', platform });
  return { kind: 'oauth', url };
}

export async function disconnectAccount(account: Account): Promise<void> {
  if (DEMO_MODE) return;
  await call('quax-publish', { action: 'disconnect', accountId: account.id });
}

/* ---------------------------------------------------------------- publishing */

export type PublishInput = Pick<ScheduledPost, 'caption' | 'platforms' | 'mediaKind'> & {
  /** Omitted = publish right now. */
  scheduledAt?: string;
  mediaUrls?: string[];
  accountIds: string[];
};

export async function publishPost(input: PublishInput): Promise<{ id: string }> {
  if (DEMO_MODE) {
    await wait(input.scheduledAt ? 500 : 1600);
    return { id: `demo-${Date.now()}` };
  }
  return call<{ id: string }>('quax-publish', { action: 'post', ...input });
}

/* ------------------------------------------------------------------------ AI */

/**
 * Streams the AI answer. `onDelta` receives the text accumulated so far.
 * `context` is the text snapshot of the user's stats (see `lib/ai-context.ts`).
 */
export async function streamChat(
  history: ChatMessage[],
  context: string,
  accounts: Account[],
  onDelta: (text: string) => void,
): Promise<string> {
  if (DEMO_MODE) {
    const question = history[history.length - 1]?.content ?? '';
    const answer = demoAnswer(question, accounts);
    await wait(450);
    let shown = '';
    for (const word of answer.split(/(\s+)/)) {
      shown += word;
      onDelta(shown);
      await wait(14);
    }
    return answer;
  }

  const res = await expoFetch(`${API_URL}/quax-ai`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({
      context,
      messages: history.map(({ role, content }) => ({ role, content })),
    }),
  });
  if (!res.ok || !res.body) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `Erreur IA (${res.status})`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let full = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    full += decoder.decode(value, { stream: true });
    onDelta(full);
  }
  return full;
}

/** Writes a caption for a post, adapted to the selected networks. */
export async function generateCaption(idea: string, platforms: PlatformId[]): Promise<string> {
  if (DEMO_MODE) {
    await wait(700);
    const base = idea.trim() || 'mon nouveau contenu';
    const hooks = [
      `Personne ne parle de ça… ${base} 👀`,
      `${base.charAt(0).toUpperCase()}${base.slice(1)} — et le résultat m'a surpris 🔥`,
      `Sauvegarde ce post : ${base} 📌`,
    ];
    const tags = platforms.includes('linkedin') ? '#contenu #créateur' : '#pourtoi #astuce #creator';
    return `${hooks[Math.floor(Math.random() * hooks.length)]}\n\nDis-moi en commentaire ce que tu en penses ⬇️\n\n${tags}`;
  }
  const prompt =
    `Écris une seule légende prête à publier pour ${platforms.join(', ') || 'les réseaux sociaux'}. ` +
    `Sujet : ${idea || 'libre'}. Réponds uniquement avec la légende, hashtags inclus.`;
  return streamChat([{ id: 'caption', role: 'user', content: prompt }], '', [], () => {});
}
