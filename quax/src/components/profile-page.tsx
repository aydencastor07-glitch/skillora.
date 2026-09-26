import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Avatar } from '@/components/avatar';
import { LineChart } from '@/components/line-chart';
import { PlatformBackdrop } from '@/components/platform-backdrop';
import { PlatformIcon } from '@/components/platform-icon';
import { PostRow } from '@/components/post-row';
import { Card, Chip, Delta, SectionTitle, StatTile } from '@/components/ui';
import { PLATFORMS } from '@/constants/platforms';
import { Colors, Radius, Spacing, TabBarSpace } from '@/constants/theme';
import { nextBestTime, topSlots } from '@/lib/best-time';
import { formatCompact, formatDateTime, formatPercent, formatShortDate, weekdayLong } from '@/lib/format';
import type { Account } from '@/lib/types';

type Metric = 'followers' | 'views' | 'likes';

/** One page of the home pager: the "improved profile" of a single network, themed with its colors. */
export function ProfilePage({ account, width, topInset }: { account: Account; width: number; topInset: number }) {
  const p = PLATFORMS[account.platform];
  const insets = useSafeAreaInsets();
  const [metric, setMetric] = useState<Metric>('followers');
  const history = account.history.map((d) => d[metric]);
  const best = nextBestTime([account]);
  const slots = topSlots(account.engagementByHour, 3);
  const accent = p.color;

  return (
    <View style={{ width, flex: 1 }}>
      <ScrollView
        contentContainerStyle={{ paddingTop: topInset, paddingBottom: TabBarSpace + insets.bottom }}
        showsVerticalScrollIndicator={false}>
        <PlatformBackdrop gradient={p.gradient} />

        {/* Header: platform logo + name */}
        <View style={styles.platformRow}>
          <PlatformIcon platform={account.platform} size={16} color="#fff" />
          <Text style={styles.platformName}>{p.name}</Text>
        </View>

        {/* Identity */}
        <View style={styles.identity}>
          <Avatar account={account} size={96} />
          <View style={styles.nameRow}>
            <Text style={styles.displayName}>{account.displayName}</Text>
            {account.verified && <Ionicons name="checkmark-circle" size={18} color="#3BA3FF" />}
          </View>
          <Text style={styles.handle}>@{account.handle}</Text>
          <Text style={styles.bio}>{account.bio}</Text>
        </View>

        {/* Headline counters, like a profile but with the growth */}
        <View style={styles.counters}>
          <Counter label="Abonnés" value={account.followers} delta={account.followersDelta} />
          <View style={styles.divider} />
          <Counter label="Likes" value={account.likes} delta={account.likesDelta} />
          <View style={styles.divider} />
          <Counter label={p.viewsLabel} value={account.views} delta={account.viewsDelta} />
        </View>

        <View style={styles.content}>
          {/* Growth chart */}
          <Card>
            <SectionTitle action={<Text style={styles.period}>30 derniers jours</Text>}>Évolution</SectionTitle>
            <View style={styles.chips}>
              <Chip label="Abonnés" active={metric === 'followers'} color={accent} onPress={() => setMetric('followers')} />
              <Chip label={p.viewsLabel} active={metric === 'views'} color={accent} onPress={() => setMetric('views')} />
              <Chip label="Likes" active={metric === 'likes'} color={accent} onPress={() => setMetric('likes')} />
            </View>
            <LineChart
              values={history}
              color={accent}
              height={150}
              detailed
              labels={[formatShortDate(account.history[0].date), "Aujourd'hui"]}
            />
          </Card>

          {/* Performance tiles */}
          <View style={styles.tiles}>
            <StatTile label="Engagement" value={formatPercent(account.engagementRate)} icon="flash" tint={accent} />
            <StatTile label="Publications" value={formatCompact(account.posts)} icon="grid" tint={accent} />
          </View>
          <View style={styles.tiles}>
            <StatTile
              label={`${p.viewsLabel} / post`}
              value={formatCompact(account.views / Math.max(1, account.posts))}
              icon="eye"
              tint={accent}
            />
            <StatTile label="Abonnements" value={formatCompact(account.following)} icon="people" tint={accent} />
          </View>

          {/* Best time */}
          <Card>
            <SectionTitle>Meilleur moment pour publier</SectionTitle>
            <View style={styles.bestRow}>
              <View style={[styles.bestIcon, { backgroundColor: `${accent}26` }]}>
                <Ionicons name="time" size={22} color={accent} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.bestTitle}>{formatDateTime(best.date)}</Text>
                <Text style={styles.bestSub}>
                  Habituellement : {slots.map((s) => `${weekdayLong(s.day)} ${s.hour}h`).join(' · ')}
                </Text>
              </View>
            </View>
            <Pressable
              onPress={() => router.push({ pathname: '/publish', params: { platform: account.platform, mode: 'best' } })}
              style={({ pressed }) => [styles.bestButton, { backgroundColor: accent, opacity: pressed ? 0.8 : 1 }]}>
              <Ionicons name="sparkles" size={16} color={p.onColor} />
              <Text style={[styles.bestButtonText, { color: p.onColor }]}>Programmer sur {p.name}</Text>
            </Pressable>
          </Card>

          {/* Top posts */}
          <Card>
            <SectionTitle>Ce qui a le mieux marché</SectionTitle>
            {account.topPosts.slice(0, 4).map((post, i) => (
              <PostRow key={post.id} post={post} rank={i + 1} />
            ))}
          </Card>
        </View>
      </ScrollView>
    </View>
  );
}

function Counter({ label, value, delta }: { label: string; value: number; delta: number }) {
  return (
    <View style={styles.counter}>
      <Text style={styles.counterValue}>{formatCompact(value)}</Text>
      <Text style={styles.counterLabel}>{label}</Text>
      <Delta value={delta} small center />
    </View>
  );
}

const styles = StyleSheet.create({
  platformRow: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'center',
    gap: 8,
    backgroundColor: 'rgba(0,0,0,0.3)',
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: Radius.pill,
    marginTop: Spacing.two,
  },
  platformName: { color: '#fff', fontWeight: '800', fontSize: 14 },
  identity: { alignItems: 'center', marginTop: Spacing.four, paddingHorizontal: Spacing.four },
  nameRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: Spacing.three },
  displayName: { color: '#fff', fontSize: 24, fontWeight: '900' },
  handle: { color: 'rgba(255,255,255,0.75)', fontSize: 15, fontWeight: '600', marginTop: 2 },
  bio: { color: 'rgba(255,255,255,0.85)', fontSize: 14, textAlign: 'center', marginTop: Spacing.two, lineHeight: 20 },
  counters: {
    flexDirection: 'row',
    marginHorizontal: Spacing.three,
    marginTop: Spacing.four,
    paddingVertical: Spacing.three,
    borderRadius: Radius.lg,
    backgroundColor: 'rgba(12,12,20,0.55)',
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: 'rgba(255,255,255,0.15)',
  },
  counter: { flex: 1, alignItems: 'center', gap: 4 },
  counterValue: { color: '#fff', fontSize: 22, fontWeight: '900' },
  counterLabel: { color: Colors.textSecondary, fontSize: 12, fontWeight: '600' },
  divider: { width: StyleSheet.hairlineWidth, backgroundColor: 'rgba(255,255,255,0.15)' },
  content: { paddingHorizontal: Spacing.three, gap: Spacing.three, marginTop: Spacing.three },
  period: { color: Colors.textMuted, fontSize: 12, fontWeight: '600' },
  chips: { flexDirection: 'row', gap: 8, marginBottom: Spacing.three, flexWrap: 'wrap' },
  tiles: { flexDirection: 'row', gap: Spacing.three - 4 },
  bestRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  bestIcon: { width: 46, height: 46, borderRadius: 23, alignItems: 'center', justifyContent: 'center' },
  bestTitle: { color: Colors.text, fontSize: 17, fontWeight: '800' },
  bestSub: { color: Colors.textSecondary, fontSize: 12, marginTop: 2, lineHeight: 17 },
  bestButton: {
    marginTop: Spacing.three,
    height: 46,
    borderRadius: Radius.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  bestButtonText: { fontWeight: '800', fontSize: 15 },
});
