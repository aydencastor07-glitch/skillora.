import { useState } from 'react';
import { type LayoutChangeEvent, StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Defs, Line, LinearGradient, Path, Stop } from 'react-native-svg';

import { Colors } from '@/constants/theme';
import { formatCompact } from '@/lib/format';

type Props = {
  values: number[];
  color: string;
  height?: number;
  /** Shows min/max labels and a dot on the last value. */
  detailed?: boolean;
  labels?: [string, string];
};

function buildPath(values: number[], width: number, height: number, pad: number) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const step = values.length > 1 ? width / (values.length - 1) : 0;
  const pts = values.map((v, i) => [i * step, pad + (1 - (v - min) / range) * (height - pad * 2)] as const);
  // Smooth curve (cardinal spline → cubic Bézier).
  let d = `M ${pts[0][0]} ${pts[0][1]}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] ?? p2;
    const t = 0.18;
    d += ` C ${p1[0] + (p2[0] - p0[0]) * t} ${p1[1] + (p2[1] - p0[1]) * t}, ${p2[0] - (p3[0] - p1[0]) * t} ${p2[1] - (p3[1] - p1[1]) * t}, ${p2[0]} ${p2[1]}`;
  }
  return { d, pts, min, max };
}

export function LineChart({ values, color, height = 140, detailed = false, labels }: Props) {
  const [width, setWidth] = useState(0);
  const onLayout = (e: LayoutChangeEvent) => setWidth(e.nativeEvent.layout.width);
  const gradientId = `fill-${color.replace('#', '')}`;

  return (
    <View onLayout={onLayout}>
      {width > 0 && values.length > 1 && (() => {
        const { d, pts, min, max } = buildPath(values, width, height, 10);
        const last = pts[pts.length - 1];
        return (
          <View style={{ height }}>
            <Svg width={width} height={height}>
              <Defs>
                <LinearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                  <Stop offset="0" stopColor={color} stopOpacity={0.35} />
                  <Stop offset="1" stopColor={color} stopOpacity={0} />
                </LinearGradient>
              </Defs>
              {detailed &&
                [0.25, 0.5, 0.75].map((f) => (
                  <Line key={f} x1={0} x2={width} y1={height * f} y2={height * f} stroke={Colors.border} strokeDasharray="4 6" />
                ))}
              <Path d={`${d} L ${width} ${height} L 0 ${height} Z`} fill={`url(#${gradientId})`} />
              <Path d={d} stroke={color} strokeWidth={2.5} fill="none" strokeLinecap="round" />
              {detailed && <Circle cx={last[0]} cy={last[1]} r={5} fill={color} stroke={Colors.background} strokeWidth={2} />}
            </Svg>
            {detailed && (
              <View style={styles.scale} pointerEvents="none">
                <Text style={styles.scaleText}>{formatCompact(max)}</Text>
                <Text style={styles.scaleText}>{formatCompact(min)}</Text>
              </View>
            )}
          </View>
        );
      })()}
      {labels && (
        <View style={styles.labels}>
          <Text style={styles.scaleText}>{labels[0]}</Text>
          <Text style={styles.scaleText}>{labels[1]}</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  scale: { position: 'absolute', left: 0, top: 0, bottom: 0, justifyContent: 'space-between', paddingVertical: 2 },
  scaleText: { color: Colors.textMuted, fontSize: 11, fontWeight: '600' },
  labels: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 6 },
});
