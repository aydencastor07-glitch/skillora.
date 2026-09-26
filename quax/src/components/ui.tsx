import Ionicons from '@expo/vector-icons/Ionicons';
import { LinearGradient } from 'expo-linear-gradient';
import type { ComponentProps, ReactNode } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View, type StyleProp, type ViewStyle } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Colors, QuaxGradient, Radius, Spacing } from '@/constants/theme';
import { formatDelta } from '@/lib/format';

export type IconName = ComponentProps<typeof Ionicons>['name'];

export function Card({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

export function SectionTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <View style={styles.sectionRow}>
      <Text style={styles.sectionTitle}>{children}</Text>
      {action}
    </View>
  );
}

/** Large app-style header with safe-area padding. */
export function ScreenHeader({ title, subtitle, right }: { title: string; subtitle?: string; right?: ReactNode }) {
  const insets = useSafeAreaInsets();
  return (
    <View style={[styles.header, { paddingTop: insets.top + Spacing.three }]}>
      <View style={{ flex: 1 }}>
        {subtitle ? <Text style={styles.headerSubtitle}>{subtitle}</Text> : null}
        <Text style={styles.headerTitle}>{title}</Text>
      </View>
      {right}
    </View>
  );
}

export function Delta({ value, small, center }: { value: number; small?: boolean; center?: boolean }) {
  const up = value >= 0;
  const color = up ? Colors.success : Colors.danger;
  return (
    <View style={[styles.delta, center && { alignSelf: 'center' }, { backgroundColor: up ? 'rgba(46,229,157,0.12)' : 'rgba(255,77,109,0.12)' }]}>
      <Ionicons name={up ? 'arrow-up' : 'arrow-down'} size={small ? 10 : 12} color={color} />
      <Text style={[styles.deltaText, { color, fontSize: small ? 11 : 12 }]}>{formatDelta(value).replace(/^[+-]/, '')}</Text>
    </View>
  );
}

export function StatTile({
  label,
  value,
  delta,
  icon,
  tint = Colors.text,
}: {
  label: string;
  value: string;
  delta?: number;
  icon: IconName;
  tint?: string;
}) {
  return (
    <View style={styles.tile}>
      <View style={styles.tileTop}>
        <Ionicons name={icon} size={16} color={tint} />
        <Text style={styles.tileLabel} numberOfLines={1}>
          {label}
        </Text>
      </View>
      <Text style={styles.tileValue} numberOfLines={1} adjustsFontSizeToFit>
        {value}
      </Text>
      {delta !== undefined ? <Delta value={delta} small /> : null}
    </View>
  );
}

export function Chip({
  label,
  active,
  onPress,
  color = Colors.accent,
  left,
}: {
  label: string;
  active?: boolean;
  onPress?: () => void;
  color?: string;
  left?: ReactNode;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.chip,
        active && { backgroundColor: color, borderColor: color },
        pressed && { opacity: 0.7 },
      ]}>
      {left}
      <Text style={[styles.chipText, active && { color: color === '#FFFFFF' || color === '#E7E9EA' || color === '#FFFC00' ? '#000' : '#fff' }]}>
        {label}
      </Text>
    </Pressable>
  );
}

export function PrimaryButton({
  label,
  onPress,
  icon,
  loading,
  disabled,
  colors = QuaxGradient,
}: {
  label: string;
  onPress: () => void;
  icon?: IconName;
  loading?: boolean;
  disabled?: boolean;
  colors?: readonly [string, string, ...string[]];
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [{ opacity: disabled ? 0.4 : pressed ? 0.85 : 1 }]}>
      <LinearGradient colors={colors} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.primary}>
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <>
            {icon ? <Ionicons name={icon} size={18} color="#fff" /> : null}
            <Text style={styles.primaryText}>{label}</Text>
          </>
        )}
      </LinearGradient>
    </Pressable>
  );
}

export function IconButton({ icon, onPress, color = Colors.text }: { icon: IconName; onPress: () => void; color?: string }) {
  return (
    <Pressable onPress={onPress} hitSlop={8} style={({ pressed }) => [styles.iconButton, pressed && { opacity: 0.6 }]}>
      <Ionicons name={icon} size={20} color={color} />
    </Pressable>
  );
}

/** Tiny markdown renderer for the AI answers: **bold**, _italic_ and line breaks. */
export function RichText({ text, style }: { text: string; style?: StyleProp<import('react-native').TextStyle> }) {
  const parts = text.split(/(\*\*[^*]+\*\*|_[^_]+_)/g);
  return (
    <Text style={style}>
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return (
            <Text key={i} style={{ fontWeight: '800' }}>
              {part.slice(2, -2)}
            </Text>
          );
        }
        if (part.length > 2 && part.startsWith('_') && part.endsWith('_')) {
          return (
            <Text key={i} style={{ fontStyle: 'italic', opacity: 0.7 }}>
              {part.slice(1, -1)}
            </Text>
          );
        }
        return part;
      })}
    </Text>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.surface,
    borderRadius: Radius.lg,
    padding: Spacing.three,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.border,
  },
  sectionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.two + 2,
  },
  sectionTitle: { color: Colors.text, fontSize: 17, fontWeight: '800' },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    paddingHorizontal: Spacing.three + 4,
    paddingBottom: Spacing.three,
    gap: Spacing.two,
  },
  headerTitle: { color: Colors.text, fontSize: 32, fontWeight: '900', letterSpacing: -0.5 },
  headerSubtitle: { color: Colors.textSecondary, fontSize: 13, fontWeight: '600', marginBottom: 2 },
  delta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: Radius.pill,
    alignSelf: 'flex-start',
  },
  deltaText: { fontWeight: '700' },
  tile: {
    flex: 1,
    minWidth: 0,
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderRadius: Radius.md,
    padding: Spacing.three - 4,
    gap: 6,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: 'rgba(255,255,255,0.1)',
  },
  tileTop: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  tileLabel: { color: Colors.textSecondary, fontSize: 12, fontWeight: '600', flexShrink: 1 },
  tileValue: { color: Colors.text, fontSize: 22, fontWeight: '800' },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: Radius.pill,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  chipText: { color: Colors.text, fontSize: 13, fontWeight: '700' },
  primary: {
    height: 54,
    borderRadius: Radius.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.two,
  },
  primaryText: { color: '#fff', fontSize: 16, fontWeight: '800' },
  iconButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: Colors.surfaceRaised,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
