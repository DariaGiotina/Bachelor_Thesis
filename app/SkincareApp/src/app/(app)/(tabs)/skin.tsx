// 11 · Skin check intro
import { Image } from 'expo-image';
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { Icon } from '@/components/icon';
import { Button, Callout, Heading, List, Row, Screen, StepNumber } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { loadHistory, useSkinCheck } from '@/lib/skin-check';
import { startCheck } from '@/lib/start-check';
import { colors, PastelName, radius, type } from '@/lib/theme';

const STEPS: [string, string, PastelName][] = [
  ['Choose an area', 'Your whole face, or zones like cheeks or chin.', 'rose'],
  ['Take a photo', 'Daylight, no filter and no make-up if you can.', 'peach'],
  ['Answer 5 questions', 'Skip any you’re not sure about.', 'lilac'],
  ['See what it may indicate', 'Possible concerns, how confident we are and a routine idea.', 'mint'],
];

export default function SkinIntro() {
  const { user } = useAuth();
  const check = useSkinCheck();
  const [count, setCount] = useState(0);

  useFocusEffect(
    useCallback(() => {
      if (user) loadHistory(user.id).then((h) => setCount(h.length));
    }, [user]),
  );

  return (
    <Screen inTabs contentStyle={{ paddingTop: 12 }} footer={<Button label="Start skin check" onPress={() => startCheck(user, check.reset)} />}>
      <Heading large title="Skin check" subtitle="A photo plus a few answers. It takes about two minutes." />
      <View style={{ height: 200 }}>
        <Image source={require('@/assets/images/photos/face-deep.jpg')} style={{ flex: 1, borderRadius: 24 }} contentFit="cover" contentPosition="top" />
        <View style={styles.tag}>
          <Icon name="clock" size={18} color={colors.accent} />
          <Text style={[type.label, { color: colors.ink }]}>About 2 minutes</Text>
        </View>
      </View>
      <View style={{ gap: 20 }}>
        {STEPS.map(([title, sub, tone], i) => (
          <View key={title} style={{ flexDirection: 'row', gap: 14 }}>
            <StepNumber n={i + 1} tone={tone} />
            <View style={{ flex: 1, gap: 2 }}>
              <Text style={type.bodyStrong}>{title}</Text>
              <Text style={[type.body, { color: colors.ink2 }]}>{sub}</Text>
            </View>
          </View>
        ))}
      </View>
      <Callout>This is information, not a diagnosis. Photos are deleted after the check unless you choose to save them.</Callout>
      <List>
        <Row
          title="Past checks"
          left={<Icon name="clock" color={colors.ink2} />}
          right={<Text style={type.bodyStrong}>{count}</Text>}
          onPress={() => router.push('/history')}
        />
      </List>
    </Screen>
  );
}

const styles = StyleSheet.create({
  tag: {
    position: 'absolute',
    left: 14,
    bottom: 16,
    flexDirection: 'row',
    gap: 6,
    alignItems: 'center',
    backgroundColor: colors.white,
    borderRadius: radius.pill,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
});
