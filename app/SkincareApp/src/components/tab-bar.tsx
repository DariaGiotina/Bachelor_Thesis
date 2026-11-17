// TabBar component of the design: five tabs with a raised round Scan button in the middle.
import type { BottomTabBarProps } from 'expo-router/js-tabs';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, type } from '@/lib/theme';
import { Icon, IconName } from './icon';

const TABS: Record<string, { label: string; icon: IconName }> = {
  today: { label: 'Today', icon: 'home' },
  skin: { label: 'Skin', icon: 'face' },
  scan: { label: 'Scan', icon: 'scan' },
  routine: { label: 'Routine', icon: 'bottle' },
  me: { label: 'Me', icon: 'user' },
};

export function TabBar({ state, emitter, navigateToTab }: BottomTabBarProps) {
  const insets = useSafeAreaInsets();
  return (
    <View style={[styles.bar, { paddingBottom: Math.max(insets.bottom, 8) }]}>
      {state.routes.map((route, i) => {
        const tab = TABS[route.name];
        if (!tab) return null;
        const focused = state.index === i;
        const color = focused ? colors.accent : colors.ink2;
        const onPress = () => {
          const event = emitter.emit({ type: 'tabPress', target: route.key, canPreventDefault: true });
          if (!focused && !event.defaultPrevented) navigateToTab(route.key);
        };
        if (route.name === 'scan') {
          return (
            <Pressable key={route.key} onPress={onPress} accessibilityRole="tab" accessibilityLabel="Scan" style={styles.tab}>
              <View style={styles.scanButton}>
                <Icon name="scan" color={colors.white} />
              </View>
              <Text style={[type.tab, { color }]}>{tab.label}</Text>
            </Pressable>
          );
        }
        return (
          <Pressable key={route.key} onPress={onPress} accessibilityRole="tab" accessibilityState={{ selected: focused }} style={styles.tab}>
            <Icon name={tab.icon} color={color} />
            <Text style={[type.tab, { color }]}>{tab.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: 'row',
    backgroundColor: colors.white,
    borderTopWidth: 1,
    borderTopColor: colors.line,
    paddingHorizontal: 8,
    paddingTop: 8,
  },
  tab: { flex: 1, alignItems: 'center', justifyContent: 'flex-end', gap: 3, minHeight: 39 },
  scanButton: {
    position: 'absolute',
    top: -38,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.accent,
    borderWidth: 4,
    borderColor: colors.white,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
