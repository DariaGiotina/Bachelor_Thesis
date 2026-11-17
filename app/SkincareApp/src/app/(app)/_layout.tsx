import { Stack } from 'expo-router';

import { colors } from '@/lib/theme';

export default function AppLayout() {
  return (
    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.canvas } }}>
      <Stack.Screen name="(tabs)" />
      <Stack.Screen name="check/capture" options={{ contentStyle: { backgroundColor: colors.night } }} />
      <Stack.Screen name="check/analysing" options={{ gestureEnabled: false }} />
    </Stack>
  );
}
