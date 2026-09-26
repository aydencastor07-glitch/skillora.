import { useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { BarChart } from '@/components/bar-chart';
import { Heatmap } from '@/components/heatmap';
import { LineChart } from '@/components/line-chart';
import { PlatformIcon } from '@/components/platform-icon';
import { PostRow } from '@/components/post-row';
import { Card, Chip, ScreenHeader, SectionTitle, StatTile } from '@/components/ui';
import { PLATFORMS, type PlatformId } from '@/constants/platforms';
import { Colors, QuaxGradient, Radius, Spacing, TabBarSpace } from '@/constants/theme';
import { combinedHeatmap, mondayIndex, topSlots } from '@/lib/best-time';
import { formatCompact, formatPercent, formatShortDate, weekdayLong, weekdayShort } from '@/lib/format';
import { useQuax } from '@/store/quax-store';

type Period = 7 | 30;

export default function AnalyticsScreen() {
  const { accounts } = useQuax();
  const insets = useSafeAreaInsets();
  const [filter, setFilter] = useState<PlatformId | 'all'>('all');
  const [period, setPeriod] = useState<Period>(7);

  const selected = filter === 'all' ? accounts : accounts.filter((a) => a.platform === filter);
  const color = filter === 'all' ? QuaxGradient[0] : PLATFORMS[filter].color;
  const len = Math.min(period, selected[0]?.history.length ?? 0);

  const series = (key: 'followers' | 'views' | 'likes') =>
    Array.from({ length: len }, (_, i) =>
      selected.reduce((s, a) => s + (a.history[a.history.length - len + i]?.[key] ?? 0), 0),
    );
  const followers = series('followers');
  const views = series('views');
  const likes = series('likes');
  const sum = (arr: number[]) => arr.reduce((s, v) => s + v, 0);
  const gained = followers.length > 1 ? followers[followers.length - 1] - followers[0] : 0;
  const engagement = sum(views) === 0 ? 0 : (sum(likes) / sum(views)) * 100;

  const dates = selected[0]?.history.slice(-len).map((d) => d.date) ?? [];
  const barLabels =
    period === 7 ? dates.map((d) => weekdayShort(mondayIndex(new Date(d))).slice(0, 3)) : undefined;

  const heat = combinedHeatmap(selected);
  const slots = topSlots(heat, 3);
  const totalFollowers = accounts.reduce((s, a) => s + a.followers, 0);
  const posts = selected.flatMap((a) => a.topPosts).sort((a, b) => b.views - a.views).slice(0, 5);

  return (
    <View style={styles.root}>
      <ScrollView contentContainerStyle={{ paddingBottom: TabBarSpace + insets.bottom }} showsVerticalScrollIndicator={false}>
        <ScreenHeader title="Statistiques" subtitle="Performances de tes comptes" />

        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filters}>
          <Chip label="Tous" active={filter === 'all'} onPress={() => setFilter('all')} />
          {accounts.map((a) => (
            <Chip
              key={a.id}
              label={PLATFORMS[a.platform].name}
              active={filter === a.platform}
              color={PLATFORMS[a.platform].color}
              onPress={() => setFilter(a.platform)}
              left={
                <PlatformIcon
                  platform={a.platform}
                  size={13}
                  color={filter === a.platform ? PLATFORMS[a.platform].onColor : PLATFORMS[a.platform].color}
                />
              }
            />
          ))}
        </ScrollView>

        <View style={styles.content}>
          <View style={styles.segment}>
            {([7, 30] as Period[]).map((p) => (
              <Text
                key={p}
                onPress={() => setPeriod(p)}
                style={[styles.segmentItem, period === p && styles.segmentActive]}>
                {p} jours
              </Text>
            ))}
          </View>

          <View style={styles.tiles}>
            <StatTile label="Nouveaux abonnés" value={`${gained >= 0 ? '+' : ''}${formatCompact(gained)}`} icon="person-add" tint={color} />
            <StatTile label="Vues" value={formatCompact(sum(views))} icon="eye" tint={color} />
          </View>
          <View style={styles.tiles}>
            <StatTile label="Likes" value={formatCompact(sum(likes))} icon="heart" tint={color} />
            <StatTile label="Engagement" value={formatPercent(engagement)} icon="flash" tint={color} />
          </View>

          <Card>
            <SectionTitle>Abonnés</SectionTitle>
            <LineChart
              values={followers}
              color={color}
              height={160}
              detailed
              labels={dates.length ? [formatShortDate(dates[0]), formatShortDate(dates[dates.length - 1])] : undefined}
            />
          </Card>

          <Card>
            <SectionTitle>Vues par jour</SectionTitle>
            <BarChart values={views} labels={barLabels} color={color} />
          </Card>

          <Card>
            <SectionTitle>Quand ton audience est active</SectionTitle>
            <Heatmap matrix={heat} color={color} />
            <Text style={styles.hint}>
              Meilleurs créneaux : {slots.map((s) => `${weekdayLong(s.day)} ${s.hour}h`).join(', ')}
            </Text>
          </Card>

          {filter === 'all' && accounts.length > 1 && (
            <Card>
              <SectionTitle>Répartition de l&apos;audience</SectionTitle>
              {[...accounts]
                .sort((a, b) => b.followers - a.followers)
                .map((a) => {
                  const share = totalFollowers ? a.followers / totalFollowers : 0;
                  return (
                    <View key={a.id} style={styles.shareRow}>
                      <PlatformIcon platform={a.platform} size={15} />
                      <View style={styles.shareTrack}>
                        <View style={[styles.shareFill, { width: `${share * 100}%`, backgroundColor: PLATFORMS[a.platform].color }]} />
                      </View>
                      <Text style={styles.shareText}>{Math.round(share * 100)} %</Text>
                    </View>
                  );
                })}
            </Card>
          )}

          <Card>
            <SectionTitle>Top contenus</SectionTitle>
            {posts.map((p, i) => (
              <PostRow key={p.id} post={p} rank={i + 1} showPlatform={filter === 'all'} />
            ))}
          </Card>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.background },
  filters: { gap: 8, paddingHorizontal: Spacing.three, paddingBottom: Spacing.three },
  content: { paddingHorizontal: Spacing.three, gap: Spacing.three },
  segment: {
    flexDirection: 'row',
    backgroundColor: Colors.surface,
    borderRadius: Radius.pill,
    padding: 4,
    alignSelf: 'flex-start',
  },
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
  tiles: { flexDirection: 'row', gap: Spacing.three - 4 },
  hint: { color: Colors.textSecondary, fontSize: 13, marginTop: Spacing.two, lineHeight: 18 },
  shareRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6 },
  shareTrack: { flex: 1, height: 8, borderRadius: 4, backgroundColor: Colors.surfaceRaised, overflow: 'hidden' },
  shareFill: { height: '100%', borderRadius: 4 },
  shareText: { color: Colors.textSecondary, width: 42, textAlign: 'right', fontWeight: '700', fontSize: 13 },
});
