import { StyleSheet, Text, View } from 'react-native';

import { Colors } from '@/constants/theme';

/** Simple vertical bars, e.g. views per day. */
export function BarChart({ values, labels, color, height = 120 }: { values: number[]; labels?: string[]; color: string; height?: number }) {
  const max = Math.max(...values, 1);
  return (
    <View>
      <View style={[styles.bars, { height }]}>
        {values.map((v, i) => (
          <View key={i} style={styles.col}>
            <View
              style={[
                styles.bar,
                { height: Math.max(3, (v / max) * height), backgroundColor: color, opacity: i === values.length - 1 ? 1 : 0.55 },
              ]}
            />
          </View>
        ))}
      </View>
      {labels && (
        <View style={styles.labels}>
          {labels.map((l, i) => (
            <Text key={i} style={styles.label}>
              {l}
            </Text>
          ))}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  bars: { flexDirection: 'row', alignItems: 'flex-end', gap: 4 },
  col: { flex: 1, justifyContent: 'flex-end' },
  bar: { borderRadius: 4 },
  labels: { flexDirection: 'row', gap: 4, marginTop: 6 },
  label: { flex: 1, textAlign: 'center', color: Colors.textMuted, fontSize: 10, fontWeight: '600' },
});
