import { Tabs } from 'expo-router/tabs';

import { QuaxTabBar } from '@/components/tab-bar';
import { Colors } from '@/constants/theme';

export default function TabsLayout() {
  return (
    <Tabs
      tabBar={(props) => <QuaxTabBar {...props} />}
      screenOptions={{ headerShown: false, sceneStyle: { backgroundColor: Colors.background } }}>
      <Tabs.Screen name="index" />
      <Tabs.Screen name="analytics" />
      <Tabs.Screen name="publish" />
      <Tabs.Screen name="calendar" />
      <Tabs.Screen name="ai" />
    </Tabs>
  );
}
