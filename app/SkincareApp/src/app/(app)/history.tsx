// 22 · Past checks
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Alert, Platform, StyleSheet, Text, View } from 'react-native';

import { Button, Divider, IconTile, List, NavBar, Row, Screen } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { CheckResult, CLASS_INFO, loadHistory, pct, removeFromHistory, resultTitle, shortDate, useSkinCheck, zonesText } from '@/lib/skin-check';
import { startCheck } from '@/lib/start-check';
import { colors, pastel, PastelName, type } from '@/lib/theme';

function confirm(message: string, onYes: () => void) {
  if (Platform.OS === 'web') {
    if (window.confirm(message)) onYes();
    return;
  }
  Alert.alert('Remove result', message, [
    { text: 'Cancel', style: 'cancel' },
    { text: 'Remove', style: 'destructive', onPress: onYes },
  ]);
}

export default function History() {
  const { user } = useAuth();
  const check = useSkinCheck();
  const [items, setItems] = useState<CheckResult[]>([]);

  const reload = useCallback(() => {
    if (user) loadHistory(user.id).then(setItems);
  }, [user]);
  useFocusEffect(reload);

  const zones = new Set(items.flatMap((i) => i.zones)).size;
  const stats: [string, number, PastelName][] = [
    ['checks', items.length, 'rose'],
    ['zones', zones, 'sky'],
    ['photos kept', 0, 'mint'],
  ];

  return (
    <Screen nav={<NavBar />} footer={<Button label="New skin check" onPress={() => startCheck(user, check.reset)} />} contentStyle={{ gap: 24 }}>
      <Text style={type.display}>Past checks</Text>
      <View style={{ flexDirection: 'row', gap: 8 }}>
        {stats.map(([label, n, tone]) => (
          <View key={label} style={[styles.stat, { backgroundColor: pastel[tone].bg }]}>
            <Text style={[type.figure, { color: pastel[tone].ink }]}>{n}</Text>
            <Text style={type.label}>{label}</Text>
          </View>
        ))}
      </View>
      <List>
        {items.length === 0 ? <Row title="No checks yet" subtitle="Results you save show up here." /> : null}
        {items.map((r, i) => {
          const tone: PastelName = r.status === 'answered' && r.category ? CLASS_INFO[r.category].tone : 'butter';
          return (
            <View key={r.id}>
              {i > 0 ? <Divider inset={72} /> : null}
              <Row
                title={r.status === 'answered' && r.category ? CLASS_INFO[r.category].label : resultTitle(r)}
                subtitle={`${shortDate(r.date)} · ${zonesText(r.zones)}`}
                left={<IconTile name="face" tone={tone} size={44} />}
                right={<Text style={[type.bodyStrong, r.status !== 'answered' && { color: colors.ink3 }]}>{pct(r.confidence)}</Text>}
                onPress={() => confirm('Remove this result from your history?', () => user && removeFromHistory(user.id, r.id).then(reload))}
              />
            </View>
          );
        })}
      </List>
      <Text style={type.caption}>Photos are deleted after each check. Tap a result to remove it.</Text>
      {items.length > 0 ? null : <Button label="Back" variant="ghost" onPress={() => router.back()} />}
    </Screen>
  );
}

const styles = StyleSheet.create({
  stat: { flex: 1, borderRadius: 16, paddingVertical: 12, alignItems: 'center', gap: 2 },
});
