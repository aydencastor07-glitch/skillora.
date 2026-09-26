import Ionicons from '@expo/vector-icons/Ionicons';
import { LinearGradient } from 'expo-linear-gradient';
import { StyleSheet, Text, View } from 'react-native';

import { PlatformIcon } from '@/components/platform-icon';
import { PLATFORMS } from '@/constants/platforms';
import { Colors, Radius } from '@/constants/theme';
import { formatCompact, formatShortDate } from '@/lib/format';
import type { Post } from '@/lib/types';

export function PostRow({ post, rank, showPlatform }: { post: Post; rank?: number; showPlatform?: boolean }) {
  const p = PLATFORMS[post.platform];
  return (
    <View style={styles.row}>
      <LinearGradient colors={[`${p.gradient[0]}`, `${p.gradient[p.gradient.length - 1]}`]} style={styles.thumb}>
        <Ionicons name="play" size={18} color="rgba(255,255,255,0.9)" />
        {rank !== undefined && (
          <View style={styles.rank}>
            <Text style={styles.rankText}>#{rank}</Text>
          </View>
        )}
      </LinearGradient>
      <View style={styles.body}>
        <Text style={styles.caption} numberOfLines={2}>
          {post.caption}
        </Text>
        <View style={styles.meta}>
          {showPlatform && <PlatformIcon platform={post.platform} size={12} />}
          <Text style={styles.date}>{formatShortDate(post.publishedAt)}</Text>
        </View>
        <View style={styles.stats}>
          <Stat icon="eye-outline" value={post.views} />
          <Stat icon="heart-outline" value={post.likes} />
          <Stat icon="chatbubble-outline" value={post.comments} />
          <Stat icon="arrow-redo-outline" value={post.shares} />
        </View>
      </View>
    </View>
  );
}

function Stat({ icon, value }: { icon: 'eye-outline' | 'heart-outline' | 'chatbubble-outline' | 'arrow-redo-outline'; value: number }) {
  return (
    <View style={styles.stat}>
      <Ionicons name={icon} size={12} color={Colors.textSecondary} />
      <Text style={styles.statText}>{formatCompact(value)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', gap: 12, paddingVertical: 10 },
  thumb: {
    width: 64,
    height: 84,
    borderRadius: Radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rank: {
    position: 'absolute',
    top: 4,
    left: 4,
    backgroundColor: 'rgba(0,0,0,0.55)',
    borderRadius: 6,
    paddingHorizontal: 5,
    paddingVertical: 1,
  },
  rankText: { color: '#fff', fontSize: 10, fontWeight: '800' },
  body: { flex: 1, justifyContent: 'center', gap: 4 },
  caption: { color: Colors.text, fontSize: 14, fontWeight: '600', lineHeight: 19 },
  meta: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  date: { color: Colors.textMuted, fontSize: 12 },
  stats: { flexDirection: 'row', gap: 12 },
  stat: { flexDirection: 'row', alignItems: 'center', gap: 3 },
  statText: { color: Colors.textSecondary, fontSize: 12, fontWeight: '600' },
});
