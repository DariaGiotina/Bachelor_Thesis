import { Tabs } from 'expo-router/js-tabs';

import { TabBar } from '@/components/tab-bar';
import { colors } from '@/lib/theme';

export default function TabsLayout() {
  return (
    <Tabs tabBar={(props) => <TabBar {...props} />} screenOptions={{ headerShown: false, sceneStyle: { backgroundColor: colors.canvas } }}>
      <Tabs.Screen name="today" />
      <Tabs.Screen name="skin" />
      <Tabs.Screen name="scan" />
      <Tabs.Screen name="routine" />
      <Tabs.Screen name="me" />
    </Tabs>
  );
}
