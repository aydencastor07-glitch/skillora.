import { StyleSheet, Text, View } from 'react-native';

import { Colors } from '@/constants/theme';
import { weekdayShort } from '@/lib/format';

const HOURS = Array.from({ length: 18 }, (_, i) => i + 6); // 6h → 23h

/** Engagement by day × hour. Darker = quieter, brighter = more active audience. */
export function Heatmap({ matrix, color }: { matrix: number[][]; color: string }) {
  const max = Math.max(...matrix.flat(), 0.0001);
  return (
    <View>
      {matrix.map((row, day) => (
        <View key={day} style={styles.row}>
          <Text style={styles.day}>{weekdayShort(day)}</Text>
          {HOURS.map((h) => {
            const v = row[h] / max;
            return (
              <View
                key={h}
                style={[styles.cell, { backgroundColor: color, opacity: 0.08 + v * v * 0.92 }]}
              />
            );
          })}
        </View>
      ))}
      <View style={styles.row}>
        <Text style={styles.day} />
        {HOURS.map((h) => (
          <Text key={h} style={styles.hour}>
            {h % 3 === 0 ? `${h}h` : ''}
          </Text>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 3, marginBottom: 3 },
  day: { width: 34, color: Colors.textSecondary, fontSize: 11, fontWeight: '600' },
  cell: { flex: 1, aspectRatio: 1, borderRadius: 4 },
  hour: { flex: 1, color: Colors.textMuted, fontSize: 9, textAlign: 'left' },
});
