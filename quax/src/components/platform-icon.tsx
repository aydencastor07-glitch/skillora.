import FontAwesome6 from '@expo/vector-icons/FontAwesome6';
import { View } from 'react-native';

import { PLATFORMS, type PlatformId } from '@/constants/platforms';

type Props = {
  platform: PlatformId;
  size?: number;
  /** Draws the logo inside a round badge filled with the brand color. */
  badge?: boolean;
  color?: string;
};

export function PlatformIcon({ platform, size = 18, badge = false, color }: Props) {
  const p = PLATFORMS[platform];
  const icon = <FontAwesome6 name={p.icon} brand size={size} color={color ?? (badge ? p.onColor : p.color)} />;
  if (!badge) return icon;
  const box = size * 1.9;
  return (
    <View
      style={{
        width: box,
        height: box,
        borderRadius: box / 2,
        backgroundColor: p.color,
        alignItems: 'center',
        justifyContent: 'center',
      }}>
      {icon}
    </View>
  );
}
