import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { LineChart } from '@/components/line-chart';
import { PlatformBackdrop } from '@/components/platform-backdrop';
import { PlatformIcon } from '@/components/platform-icon';
import { Card, Delta, SectionTitle, StatTile } from '@/components/ui';
import { PLATFORMS } from '@/constants/platforms';
import { Colors, QuaxGradient, Spacing, TabBarSpace } from '@/constants/theme';
import { nextBestTime } from '@/lib/best-time';
import { formatCompact, formatDateTime, formatDelta } from '@/lib/format';
import type { Account, ScheduledPost } from '@/lib/types';

type Props = {
  accounts: Account[];
  posts: ScheduledPost[];
  width: number;
  topInset: number;
  onOpen: (index: number) => void;
};

/** First page of the home pager: all networks summed up. */
export function OverviewPage({ accounts, posts, width, topInset, onOpen }: Props) {
  const insets = useSafeAreaInsets();
  const sum = (key: 'followers' | 'views' | 'likes') => accounts.reduce((s, a) => s + a[key], 0);
  const weighted = (key: 'followersDelta' | 'viewsDelta' | 'likesDelta', base: 'followers' | 'views' | 'likes') => {
    const total = sum(base);
    return total === 0 ? 0 : accounts.reduce((s, a) => s + a[key] * a[base], 0) / total;
  };
  const combined =
    accounts[0]?.history.map((_, i) => accounts.reduce((s, a) => s + (a.history[i]?.followers ?? 0), 0)) ?? [];
  const upcoming = posts
    .filter((p) => p.status === 'scheduled')
    .sort((a, b) => a.scheduledAt.localeCompare(b.scheduledAt));
  const best = accounts.length ? nextBestTime(accounts) : null;

  return (
    <View style={{ width, flex: 1 }}>
      <ScrollView
        contentContainerStyle={{ paddingTop: topInset, paddingBottom: TabBarSpace + insets.bottom }}
        showsVerticalScrollIndicator={false}>
        <PlatformBackdrop gradient={QuaxGradient} height={420} />

        <View style={styles.hero}>
          <Text style={styles.heroLabel}>Audience totale</Text>
          <Text style={styles.heroValue}>{formatCompact(sum('followers'))}</Text>
          <View style={styles.heroDelta}>
            <Delta value={weighted('followersDelta', 'followers')} />
            <Text style={styles.heroHint}>cette semaine · {accounts.length} réseaux</Text>
          </View>
        </View>

        <View style={styles.content}>
          <View style={styles.tiles}>
            <StatTile label="Vues" value={formatCompact(sum('views'))} delta={weighted('viewsDelta', 'views')} icon="eye" />
            <StatTile label="Likes" value={formatCompact(sum('likes'))} delta={weighted('likesDelta', 'likes')} icon="heart" />
          </View>

          {combined.length > 1 && (
            <Card>
              <SectionTitle>Abonnés · 30 jours</SectionTitle>
              <LineChart values={combined} color={QuaxGradient[0]} height={120} detailed />
            </Card>
          )}

          {best && (
            <Pressable onPress={() => router.push({ pathname: '/publish', params: { mode: 'best' } })}>
              <Card style={styles.bestCard}>
                <Ionicons name="sparkles" size={20} color={QuaxGradient[1]} />
                <View style={{ flex: 1 }}>
                  <Text style={styles.bestLabel}>Prochain meilleur moment</Text>
                  <Text style={styles.bestValue}>{formatDateTime(best.date)}</Text>
                </View>
                <Ionicons name="chevron-forward" size={18} color={Colors.textSecondary} />
              </Card>
            </Pressable>
          )}

          <Card>
            <SectionTitle
              action={
                <Pressable onPress={() => router.push('/accounts')} hitSlop={8}>
                  <Text style={styles.link}>Gérer</Text>
                </Pressable>
              }>
              Mes réseaux
            </SectionTitle>
            {accounts.map((a, i) => (
              <Pressable
                key={a.id}
                onPress={() => onOpen(i + 1)}
                style={({ pressed }) => [styles.accountRow, pressed && { opacity: 0.6 }]}>
                <PlatformIcon platform={a.platform} badge size={15} />
                <View style={{ flex: 1 }}>
                  <Text style={styles.accountName}>{PLATFORMS[a.platform].name}</Text>
                  <Text style={styles.accountHandle}>@{a.handle}</Text>
                </View>
                <View style={{ width: 64 }}>
                  <LineChart values={a.history.slice(-14).map((d) => d.followers)} color={PLATFORMS[a.platform].color} height={30} />
                </View>
                <View style={{ alignItems: 'flex-end', width: 70 }}>
                  <Text style={styles.accountValue}>{formatCompact(a.followers)}</Text>
                  <Text style={[styles.accountDelta, { color: a.followersDelta >= 0 ? Colors.success : Colors.danger }]}>
                    {formatDelta(a.followersDelta)}
                  </Text>
                </View>
              </Pressable>
            ))}
            <Pressable onPress={() => router.push('/accounts')} style={styles.addRow}>
              <Ionicons name="add-circle" size={22} color={Colors.accent} />
              <Text style={styles.addText}>Connecter un compte</Text>
            </Pressable>
          </Card>

          {upcoming.length > 0 && (
            <Card>
              <SectionTitle
                action={
                  <Pressable onPress={() => router.push('/calendar')} hitSlop={8}>
                    <Text style={styles.link}>Tout voir</Text>
                  </Pressable>
                }>
                À venir
              </SectionTitle>
              {upcoming.slice(0, 3).map((post) => (
                <View key={post.id} style={styles.upcoming}>
                  <View style={styles.upcomingIcons}>
                    {post.platforms.map((pl) => (
                      <PlatformIcon key={pl} platform={pl} size={13} />
                    ))}
                  </View>
                  <Text style={styles.upcomingCaption} numberOfLines={1}>
                    {post.caption || 'Sans légende'}
                  </Text>
                  <Text style={styles.upcomingDate}>{formatDateTime(new Date(post.scheduledAt))}</Text>
                </View>
              ))}
            </Card>
          )}

          <Text style={styles.swipeHint}>
            Swipe vers la gauche pour voir chaque réseau <Ionicons name="arrow-forward" size={12} />
          </Text>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  hero: { alignItems: 'center', paddingTop: Spacing.four, paddingBottom: Spacing.four },
  heroLabel: { color: 'rgba(255,255,255,0.8)', fontSize: 14, fontWeight: '700' },
  heroValue: { color: '#fff', fontSize: 56, fontWeight: '900', letterSpacing: -1.5 },
  heroDelta: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  heroHint: { color: 'rgba(255,255,255,0.75)', fontSize: 13, fontWeight: '600' },
  content: { paddingHorizontal: Spacing.three, gap: Spacing.three },
  tiles: { flexDirection: 'row', gap: Spacing.three - 4 },
  bestCard: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  bestLabel: { color: Colors.textSecondary, fontSize: 12, fontWeight: '600' },
  bestValue: { color: Colors.text, fontSize: 16, fontWeight: '800', marginTop: 2 },
  link: { color: Colors.accent, fontWeight: '700', fontSize: 14 },
  accountRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 9 },
  accountName: { color: Colors.text, fontSize: 15, fontWeight: '700' },
  accountHandle: { color: Colors.textMuted, fontSize: 12 },
  accountValue: { color: Colors.text, fontSize: 15, fontWeight: '800' },
  accountDelta: { fontSize: 12, fontWeight: '700' },
  addRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingTop: 12,
    marginTop: 4,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.border,
  },
  addText: { color: Colors.accent, fontWeight: '700', fontSize: 15 },
  upcoming: { paddingVertical: 8, gap: 3 },
  upcomingIcons: { flexDirection: 'row', gap: 6 },
  upcomingCaption: { color: Colors.text, fontSize: 14, fontWeight: '600' },
  upcomingDate: { color: Colors.textMuted, fontSize: 12 },
  swipeHint: { color: Colors.textMuted, fontSize: 12, textAlign: 'center', marginTop: Spacing.two },
});

