import Ionicons from '@expo/vector-icons/Ionicons';
import { LinearGradient } from 'expo-linear-gradient';
import type { BottomTabBarProps } from 'expo-router/tabs';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { IconName } from '@/components/ui';
import { Colors, QuaxGradient, Radius } from '@/constants/theme';

const TABS: Record<string, { label: string; icon: IconName; iconActive: IconName }> = {
  index: { label: 'Accueil', icon: 'home-outline', iconActive: 'home' },
  analytics: { label: 'Stats', icon: 'stats-chart-outline', iconActive: 'stats-chart' },
  publish: { label: 'Publier', icon: 'add', iconActive: 'add' },
  calendar: { label: 'Planning', icon: 'calendar-outline', iconActive: 'calendar' },
  ai: { label: 'Quax AI', icon: 'sparkles-outline', iconActive: 'sparkles' },
};

/** Floating pill tab bar with a big gradient "publish" button in the middle. */
export function QuaxTabBar({ state, navigation, insets }: BottomTabBarProps) {
  return (
    <View style={[styles.wrap, { paddingBottom: Math.max(insets.bottom, 12) }]} pointerEvents="box-none">
      <View style={styles.bar}>
        {state.routes.map((route, index) => {
          const tab = TABS[route.name];
          if (!tab) return null;
          const focused = state.index === index;
          const onPress = () => {
            const event = navigation.emit({ type: 'tabPress', target: route.key, canPreventDefault: true });
            if (!focused && !event.defaultPrevented) navigation.navigate(route.name, route.params);
          };

          if (route.name === 'publish') {
            return (
              <Pressable key={route.key} onPress={onPress} style={styles.item} accessibilityLabel={tab.label}>
                <LinearGradient colors={QuaxGradient} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.publish}>
                  <Ionicons name="add" size={30} color="#fff" />
                </LinearGradient>
              </Pressable>
            );
          }

          const color = focused ? Colors.text : Colors.textMuted;
          return (
            <Pressable key={route.key} onPress={onPress} style={styles.item} accessibilityLabel={tab.label}>
              <Ionicons name={focused ? tab.iconActive : tab.icon} size={22} color={color} />
              <Text style={[styles.label, { color }]}>{tab.label}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { position: 'absolute', left: 0, right: 0, bottom: 0, paddingHorizontal: 14 },
  bar: {
    flexDirection: 'row',
    alignItems: 'center',
    height: 68,
    borderRadius: Radius.lg + 10,
    backgroundColor: 'rgba(21,21,31,0.96)',
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: 'rgba(255,255,255,0.12)',
    shadowColor: '#000',
    shadowOpacity: 0.5,
    shadowRadius: 20,
    shadowOffset: { width: 0, height: 8 },
    elevation: 12,
  },
  item: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 3 },
  label: { fontSize: 10, fontWeight: '700' },
  publish: {
    width: 52,
    height: 52,
    borderRadius: 26,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: QuaxGradient[1],
    shadowOpacity: 0.6,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
  },
});
