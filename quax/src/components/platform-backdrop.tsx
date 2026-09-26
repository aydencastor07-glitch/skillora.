import { LinearGradient } from 'expo-linear-gradient';
import { StyleSheet, View } from 'react-native';

import { Colors } from '@/constants/theme';

/** Brand gradient that melts into the dark app background — gives each network page its own color. */
export function PlatformBackdrop({ gradient, height = 520 }: { gradient: readonly string[]; height?: number }) {
  const colors = gradient.map((c) => `${c}B3`) as [string, string, ...string[]];
  return (
    <View style={[styles.wrap, { height }]} pointerEvents="none">
      <LinearGradient colors={colors} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0.6 }} style={StyleSheet.absoluteFill} />
      <LinearGradient
        colors={['rgba(11,11,18,0.1)', 'rgba(11,11,18,0.65)', Colors.background]}
        locations={[0, 0.55, 1]}
        style={StyleSheet.absoluteFill}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { position: 'absolute', top: 0, left: 0, right: 0 },
});
