// 10 · Today (skin-check parts; the routine and shelf blocks arrive with the routine module)
import { Image } from 'expo-image';
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Icon, IconName } from '@/components/icon';
import { Button, List, Row, Screen, Section } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { CheckResult, loadHistory, pct, resultTitle, shortDate, useSkinCheck, zonesText } from '@/lib/skin-check';
import { startCheck } from '@/lib/start-check';
import { colors, pastel, PastelName, radius, type } from '@/lib/theme';

function greeting(d = new Date()) {
  const h = d.getHours();
  return h < 12 ? 'Good morning,' : h < 18 ? 'Good afternoon,' : 'Good evening,';
}

const ACTIONS: { label: string; icon: IconName; tone: PastelName; route: '/skin' | '/scan' | '/routine' | '/history' }[] = [
  { label: 'Skin check', icon: 'face', tone: 'rose', route: '/skin' },
  { label: 'Scan', icon: 'scan', tone: 'peach', route: '/scan' },
  { label: 'Products', icon: 'bottle', tone: 'lilac', route: '/routine' },
  { label: 'History', icon: 'clock', tone: 'mint', route: '/history' },
];

export default function Today() {
  const { user } = useAuth();
  const check = useSkinCheck();
  const [latest, setLatest] = useState<CheckResult | null>(null);

  useFocusEffect(
    useCallback(() => {
      if (user) loadHistory(user.id).then((h) => setLatest(h[0] ?? null));
    }, [user]),
  );

  const firstName = user?.name.split(' ')[0] ?? '';
  const today = new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' });

  return (
    <Screen inTabs contentStyle={{ paddingTop: 12 }}>
      <View style={styles.header}>
        <View style={{ flexDirection: 'row', gap: 12, alignItems: 'center' }}>
          <View style={styles.avatar}>
            <Text style={[type.headline, { color: colors.accentDeep }]}>{firstName.charAt(0).toUpperCase()}</Text>
          </View>
          <View style={{ gap: 4 }}>
            <Text style={type.label}>{greeting()}</Text>
            <Text style={type.title}>{firstName}</Text>
          </View>
        </View>
        <View style={styles.bell}>
          <Icon name="bell" />
        </View>
      </View>

      <View style={styles.banner}>
        <Image source={require('@/assets/images/photos/flatlay.jpg')} style={StyleSheet.absoluteFill} contentFit="cover" />
        <View style={styles.fade} />
        <View style={{ gap: 4, maxWidth: 220 }}>
          <Text style={type.caption}>{today}</Text>
          <Text style={type.headline}>A calm minute for your skin</Text>
          <Text style={type.label}>A photo and five short questions.</Text>
        </View>
      </View>

      <View style={{ flexDirection: 'row', gap: 10 }}>
        {ACTIONS.map((a) => (
          <Pressable key={a.label} onPress={() => router.push(a.route)} style={[styles.action, { backgroundColor: pastel[a.tone].bg }]} accessibilityRole="button">
            <View style={styles.actionIcon}>
              <Icon name={a.icon} size={22} color={pastel[a.tone].ink} />
            </View>
            <Text style={[type.label, { color: pastel[a.tone].ink }]}>{a.label}</Text>
          </Pressable>
        ))}
      </View>

      <View style={styles.startCard}>
        <View style={{ flex: 1, gap: 12 }}>
          <Text style={type.headline}>Time for a new check?</Text>
          <Text style={[type.body, { color: colors.ink2 }]}>A photo and five short questions.</Text>
          <Button label="Start check" compact onPress={() => startCheck(user, check.reset)} />
        </View>
        <Image source={require('@/assets/images/photos/face-deep.jpg')} style={styles.startPhoto} contentFit="cover" />
      </View>

      <Section title="Latest skin check" action="History" onAction={() => router.push('/history')}>
        <List>
          {latest ? (
            <Row
              title={resultTitle(latest)}
              subtitle={`${shortDate(latest.date)} · ${zonesText(latest.zones)}${latest.status === 'answered' ? ` · ${pct(latest.confidence)} confidence` : ''}`}
              right={<Icon name="chevron-right" color={colors.ink3} />}
              onPress={() => router.push('/history')}
            />
          ) : (
            <Row title="No skin checks yet" subtitle="Your first result will show up here." />
          )}
        </List>
      </Section>
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  avatar: { width: 48, height: 48, borderRadius: 24, backgroundColor: colors.tint, alignItems: 'center', justifyContent: 'center' },
  bell: { width: 40, height: 40, borderRadius: 20, backgroundColor: colors.white, alignItems: 'center', justifyContent: 'center' },
  banner: { height: 160, borderRadius: 24, overflow: 'hidden', padding: 20, justifyContent: 'center' },
  fade: { ...StyleSheet.absoluteFill, backgroundColor: 'rgba(255,248,246,0.72)' },
  action: { flex: 1, borderRadius: radius.lg, paddingVertical: 14, paddingHorizontal: 4, alignItems: 'center', gap: 8 },
  actionIcon: { width: 40, height: 40, borderRadius: 20, backgroundColor: colors.white, alignItems: 'center', justifyContent: 'center' },
  startCard: { flexDirection: 'row', gap: 14, padding: 16, borderRadius: 22, backgroundColor: colors.tint, alignItems: 'center' },
  startPhoto: { width: 110, height: 150, borderRadius: 18 },
});
