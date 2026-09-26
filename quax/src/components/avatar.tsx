import { Image } from 'expo-image';
import { LinearGradient } from 'expo-linear-gradient';
import { StyleSheet, Text, View } from 'react-native';

import { PlatformIcon } from '@/components/platform-icon';
import { PLATFORMS } from '@/constants/platforms';
import { Colors } from '@/constants/theme';
import type { Account } from '@/lib/types';

/** Profile picture ringed with the platform gradient, with the platform logo pinned on the corner. */
export function Avatar({ account, size = 88 }: { account: Account; size?: number }) {
  const p = PLATFORMS[account.platform];
  const ring = 3;
  const initials = account.displayName
    .split(/\s+/)
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return (
    <View style={{ width: size, height: size }}>
      <LinearGradient
        colors={p.gradient}
        start={{ x: 0, y: 1 }}
        end={{ x: 1, y: 0 }}
        style={[styles.ring, { borderRadius: size / 2, padding: ring }]}>
        <View style={[styles.inner, { borderRadius: size / 2, padding: ring }]}>
          {account.avatarUrl ? (
            <Image source={account.avatarUrl} style={{ flex: 1, borderRadius: size / 2 }} contentFit="cover" />
          ) : (
            <LinearGradient
              colors={['#2B2B3D', '#1A1A26']}
              style={[styles.fallback, { borderRadius: size / 2 }]}>
              <Text style={[styles.initials, { fontSize: size * 0.32 }]}>{initials}</Text>
            </LinearGradient>
          )}
        </View>
      </LinearGradient>
      <View style={[styles.corner, { right: -2, bottom: -2 }]}>
        <PlatformIcon platform={account.platform} badge size={size * 0.14} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  ring: { flex: 1 },
  inner: { flex: 1, backgroundColor: Colors.background },
  fallback: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  initials: { color: Colors.text, fontWeight: '800', letterSpacing: 1 },
  corner: {
    position: 'absolute',
    borderRadius: 999,
    borderWidth: 3,
    borderColor: Colors.background,
  },
});
