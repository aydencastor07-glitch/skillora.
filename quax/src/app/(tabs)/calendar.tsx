import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { PlatformIcon } from '@/components/platform-icon';
import { Card, PrimaryButton, ScreenHeader } from '@/components/ui';
import { Colors, Radius, Spacing, TabBarSpace } from '@/constants/theme';
import { mondayIndex } from '@/lib/best-time';
import { formatDayLabel, formatTime, relativeFromNow, weekdayShort } from '@/lib/format';
import type { PostStatus, ScheduledPost } from '@/lib/types';
import { useQuax } from '@/store/quax-store';

const STATUS: Record<PostStatus, { label: string; color: string }> = {
  scheduled: { label: 'Programmé', color: Colors.accent },
  publishing: { label: 'En cours…', color: Colors.warning },
  published: { label: 'Publié', color: Colors.success },
  failed: { label: 'Échec', color: Colors.danger },
};

const dayKey = (d: Date) => `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;

export default function CalendarScreen() {
  const { posts, cancelPost } = useQuax();
  const insets = useSafeAreaInsets();
  const [tab, setTab] = useState<'upcoming' | 'history'>('upcoming');

  const upcoming = posts
    .filter((p) => p.status === 'scheduled' || p.status === 'publishing')
    .sort((a, b) => a.scheduledAt.localeCompare(b.scheduledAt));
  const history = posts
    .filter((p) => p.status === 'published' || p.status === 'failed')
    .sort((a, b) => b.scheduledAt.localeCompare(a.scheduledAt));
  const list = tab === 'upcoming' ? upcoming : history;

  // Week strip: how many posts are planned each of the next 7 days.
  const week = Array.from({ length: 7 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() + i);
    return { date: d, count: upcoming.filter((p) => dayKey(new Date(p.scheduledAt)) === dayKey(d)).length };
  });

  const groups = list.reduce<{ label: string; items: ScheduledPost[] }[]>((acc, post) => {
    const label = formatDayLabel(new Date(post.scheduledAt));
    const last = acc[acc.length - 1];
    if (last?.label === label) last.items.push(post);
    else acc.push({ label, items: [post] });
    return acc;
  }, []);

  return (
    <View style={styles.root}>
      <ScrollView contentContainerStyle={{ paddingBottom: TabBarSpace + insets.bottom }} showsVerticalScrollIndicator={false}>
        <ScreenHeader title="Planning" subtitle={`${upcoming.length} publication${upcoming.length > 1 ? 's' : ''} à venir`} />

        <View style={styles.content}>
          <View style={styles.week}>
            {week.map(({ date, count }, i) => (
              <View key={i} style={[styles.day, i === 0 && styles.today]}>
                <Text style={[styles.dayName, i === 0 && { color: '#fff' }]}>{weekdayShort(mondayIndex(date))}</Text>
                <Text style={styles.dayNum}>{date.getDate()}</Text>
                <View style={[styles.dayDot, { opacity: count > 0 ? 1 : 0 }]} />
              </View>
            ))}
          </View>

          <View style={styles.segment}>
            <Text onPress={() => setTab('upcoming')} style={[styles.segmentItem, tab === 'upcoming' && styles.segmentActive]}>
              À venir
            </Text>
            <Text onPress={() => setTab('history')} style={[styles.segmentItem, tab === 'history' && styles.segmentActive]}>
              Historique
            </Text>
          </View>

          {groups.length === 0 && (
            <Card style={styles.empty}>
              <Ionicons name="calendar-clear-outline" size={36} color={Colors.textMuted} />
              <Text style={styles.emptyText}>
                {tab === 'upcoming' ? 'Rien de programmé pour le moment.' : 'Aucune publication pour le moment.'}
              </Text>
              {tab === 'upcoming' && (
                <View style={{ alignSelf: 'stretch' }}>
                  <PrimaryButton label="Programmer un post" icon="add" onPress={() => router.push('/publish')} />
                </View>
              )}
            </Card>
          )}

          {groups.map((g) => (
            <View key={g.label} style={{ gap: Spacing.two }}>
              <Text style={styles.groupLabel}>{g.label}</Text>
              {g.items.map((post) => {
                const status = STATUS[post.status];
                return (
                  <Card key={post.id} style={styles.post}>
                    <View style={styles.timeCol}>
                      <Text style={styles.time}>{formatTime(new Date(post.scheduledAt))}</Text>
                      {post.mode === 'best' && <Ionicons name="sparkles" size={12} color={Colors.accent} />}
                    </View>
                    <View style={{ flex: 1, gap: 6 }}>
                      <Text style={styles.caption} numberOfLines={2}>
                        {post.caption || (post.mediaKind === 'video' ? 'Vidéo' : 'Photo')}
                      </Text>
                      <View style={styles.meta}>
                        {post.platforms.map((p) => (
                          <PlatformIcon key={p} platform={p} size={13} />
                        ))}
                        <View style={[styles.badge, { backgroundColor: `${status.color}22` }]}>
                          <Text style={[styles.badgeText, { color: status.color }]}>{status.label}</Text>
                        </View>
                      </View>
                      {post.status === 'scheduled' && <Text style={styles.relative}>{relativeFromNow(post.scheduledAt)}</Text>}
                      {post.error && <Text style={styles.error}>{post.error}</Text>}
                    </View>
                    {post.status === 'scheduled' && (
                      <Pressable onPress={() => cancelPost(post.id)} hitSlop={10} accessibilityLabel="Annuler">
                        <Ionicons name="trash-outline" size={18} color={Colors.textMuted} />
                      </Pressable>
                    )}
                  </Card>
                );
              })}
            </View>
          ))}
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.background },
  content: { paddingHorizontal: Spacing.three, gap: Spacing.three },
  week: { flexDirection: 'row', gap: 6 },
  day: { flex: 1, alignItems: 'center', paddingVertical: 10, borderRadius: Radius.md, backgroundColor: Colors.surface, gap: 2 },
  today: { backgroundColor: Colors.accent },
  dayName: { color: Colors.textSecondary, fontSize: 11, fontWeight: '700' },
  dayNum: { color: Colors.text, fontSize: 17, fontWeight: '800' },
  dayDot: { width: 5, height: 5, borderRadius: 3, backgroundColor: '#fff', marginTop: 2 },
  segment: { flexDirection: 'row', backgroundColor: Colors.surface, borderRadius: Radius.pill, padding: 4, alignSelf: 'flex-start' },
  segmentItem: {
    color: Colors.textSecondary,
    fontWeight: '700',
    fontSize: 13,
    paddingHorizontal: 16,
    paddingVertical: 7,
    borderRadius: Radius.pill,
    overflow: 'hidden',
  },
  segmentActive: { backgroundColor: Colors.surfaceRaised, color: Colors.text },
  empty: { alignItems: 'center', gap: Spacing.three, paddingVertical: Spacing.five },
  emptyText: { color: Colors.textSecondary, fontSize: 15 },
  groupLabel: { color: Colors.textSecondary, fontSize: 13, fontWeight: '800', textTransform: 'uppercase', letterSpacing: 0.5 },
  post: { flexDirection: 'row', gap: 12, alignItems: 'flex-start' },
  timeCol: { alignItems: 'center', gap: 4, width: 50 },
  time: { color: Colors.text, fontSize: 15, fontWeight: '800' },
  caption: { color: Colors.text, fontSize: 14, fontWeight: '600', lineHeight: 19 },
  meta: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  badge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: Radius.pill },
  badgeText: { fontSize: 11, fontWeight: '800' },
  relative: { color: Colors.textMuted, fontSize: 12 },
  error: { color: Colors.danger, fontSize: 12 },
});
