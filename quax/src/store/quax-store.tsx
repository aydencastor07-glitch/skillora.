import * as WebBrowser from 'expo-web-browser';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import { PLATFORM_ORDER, type PlatformId } from '@/constants/platforms';
import { buildAiContext } from '@/lib/ai-context';
import { DEMO_CONNECTED } from '@/lib/mock-data';
import type { Account, ChatMessage, PublishMode, ScheduledPost } from '@/lib/types';
import * as api from '@/services/api';
import { DEMO_MODE } from '@/services/config';

type NewPost = {
  caption: string;
  platforms: PlatformId[];
  mode: PublishMode;
  scheduledAt: Date;
  mediaKind: ScheduledPost['mediaKind'];
};

type QuaxState = {
  loading: boolean;
  accounts: Account[];
  connecting: PlatformId | null;
  posts: ScheduledPost[];
  chat: ChatMessage[];
  aiBusy: boolean;
  refresh: () => Promise<void>;
  connect: (platform: PlatformId) => Promise<void>;
  disconnect: (platform: PlatformId) => Promise<void>;
  createPost: (post: NewPost) => Promise<ScheduledPost>;
  cancelPost: (id: string) => void;
  ask: (question: string) => Promise<void>;
  resetChat: () => void;
};

const QuaxContext = createContext<QuaxState | null>(null);

const uid = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

const WELCOME: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  content:
    "Salut, je suis **Quax AI** 👋\nJe connais les stats de tous tes comptes. Demande-moi quand publier, ce qui a le mieux marché, ou de t'écrire une légende.",
};

function sortAccounts(list: Account[]) {
  return [...list].sort((a, b) => PLATFORM_ORDER.indexOf(a.platform) - PLATFORM_ORDER.indexOf(b.platform));
}

export function QuaxProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [connecting, setConnecting] = useState<PlatformId | null>(null);
  const [posts, setPosts] = useState<ScheduledPost[]>([]);
  const [chat, setChat] = useState<ChatMessage[]>([WELCOME]);
  const [aiBusy, setAiBusy] = useState(false);
  const accountsRef = useRef(accounts);
  const postsRef = useRef(posts);
  const chatRef = useRef(chat);
  useEffect(() => {
    accountsRef.current = accounts;
    postsRef.current = posts;
    chatRef.current = chat;
  }, [accounts, posts, chat]);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const platforms = DEMO_MODE ? accountsRef.current.map((a) => a.platform) : [];
      setAccounts(sortAccounts(await api.fetchAccounts(platforms)));
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load. In demo mode, a few networks are pre-connected so the app isn't empty.
  useEffect(() => {
    let cancelled = false;
    api
      .fetchAccounts(DEMO_MODE ? DEMO_CONNECTED : [])
      .then((list) => !cancelled && setAccounts(sortAccounts(list)))
      .catch(() => {})
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const connect = useCallback(
    async (platform: PlatformId) => {
      setConnecting(platform);
      try {
        const result = await api.connectAccount(platform);
        if (result.kind === 'connected') {
          setAccounts((list) => sortAccounts([...list.filter((a) => a.platform !== platform), result.account]));
        } else {
          await WebBrowser.openAuthSessionAsync(result.url);
          await refresh();
        }
      } finally {
        setConnecting(null);
      }
    },
    [refresh],
  );

  const disconnect = useCallback(async (platform: PlatformId) => {
    const account = accountsRef.current.find((a) => a.platform === platform);
    if (!account) return;
    await api.disconnectAccount(account);
    setAccounts((list) => list.filter((a) => a.platform !== platform));
  }, []);

  const updatePost = (id: string, patch: Partial<ScheduledPost>) =>
    setPosts((list) => list.map((p) => (p.id === id ? { ...p, ...patch } : p)));

  const createPost = useCallback(async (input: NewPost) => {
    const post: ScheduledPost = {
      id: uid(),
      caption: input.caption,
      platforms: input.platforms,
      mode: input.mode,
      mediaKind: input.mediaKind,
      scheduledAt: (input.mode === 'now' ? new Date() : input.scheduledAt).toISOString(),
      status: input.mode === 'now' ? 'publishing' : 'scheduled',
    };
    setPosts((list) => [post, ...list]);
    try {
      await api.publishPost({
        caption: post.caption,
        platforms: post.platforms,
        mediaKind: post.mediaKind,
        scheduledAt: input.mode === 'now' ? undefined : post.scheduledAt,
        accountIds: accountsRef.current.filter((a) => post.platforms.includes(a.platform)).map((a) => a.id),
      });
      if (input.mode === 'now') updatePost(post.id, { status: 'published' });
    } catch (e) {
      updatePost(post.id, { status: 'failed', error: e instanceof Error ? e.message : String(e) });
    }
    return post;
  }, []);

  const cancelPost = useCallback((id: string) => setPosts((list) => list.filter((p) => p.id !== id)), []);

  // In demo mode, flip scheduled posts to "published" once their time has come.
  useEffect(() => {
    if (!DEMO_MODE) return;
    const timer = setInterval(() => {
      const now = Date.now();
      setPosts((list) =>
        list.some((p) => p.status === 'scheduled' && new Date(p.scheduledAt).getTime() <= now)
          ? list.map((p) =>
              p.status === 'scheduled' && new Date(p.scheduledAt).getTime() <= now ? { ...p, status: 'published' } : p,
            )
          : list,
      );
    }, 15_000);
    return () => clearInterval(timer);
  }, []);

  const ask = useCallback(async (question: string) => {
    const text = question.trim();
    if (!text) return;
    const userMsg: ChatMessage = { id: uid(), role: 'user', content: text };
    const replyId = uid();
    const history = [...chatRef.current.filter((m) => m.id !== WELCOME.id && !m.pending), userMsg];
    setChat((list) => [...list, userMsg, { id: replyId, role: 'assistant', content: '', pending: true }]);
    setAiBusy(true);
    const setReply = (content: string, pending: boolean) =>
      setChat((list) => list.map((m) => (m.id === replyId ? { ...m, content, pending } : m)));
    try {
      const context = buildAiContext(accountsRef.current, postsRef.current);
      const answer = await api.streamChat(history, context, accountsRef.current, (t) => setReply(t, true));
      setReply(answer, false);
    } catch (e) {
      setReply(`⚠️ ${e instanceof Error ? e.message : "L'IA est indisponible pour le moment."}`, false);
    } finally {
      setAiBusy(false);
    }
  }, []);

  const resetChat = useCallback(() => setChat([WELCOME]), []);

  const value = useMemo<QuaxState>(
    () => ({
      loading,
      accounts,
      connecting,
      posts,
      chat,
      aiBusy,
      refresh,
      connect,
      disconnect,
      createPost,
      cancelPost,
      ask,
      resetChat,
    }),
    [loading, accounts, connecting, posts, chat, aiBusy, refresh, connect, disconnect, createPost, cancelPost, ask, resetChat],
  );

  return <QuaxContext.Provider value={value}>{children}</QuaxContext.Provider>;
}

export function useQuax(): QuaxState {
  const ctx = useContext(QuaxContext);
  if (!ctx) throw new Error('useQuax must be used inside <QuaxProvider>');
  return ctx;
}
