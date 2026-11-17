// 06 · Privacy consent (asked before the first skin check)
import { Image } from 'expo-image';
import { router } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, Switch, Text, View } from 'react-native';

import { Icon, IconName } from '@/components/icon';
import { Button, Callout, Divider, Heading, IconTile, List, NavBar, Row, Screen, Section } from '@/components/ui';
import { POLICY_VERSION, useAuth } from '@/lib/auth';
import { colors, PastelName, radius, type } from '@/lib/theme';

const USES: [string, string, IconName, PastelName][] = [
  ['Face photos', 'Used to estimate likely skin concerns, then deleted. Photos are never saved by this version.', 'camera', 'rose'],
  ['Skin answers', 'Skin type, symptoms and age range. Used to personalise your result.', 'doc', 'lilac'],
  ['Where it’s kept', 'Results stay on this phone. The photo is analysed in memory and not stored.', 'lock', 'sky'],
];

function Toggle({ value, onChange, label }: { value: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <Switch
      accessibilityLabel={label}
      value={value}
      onValueChange={onChange}
      trackColor={{ true: colors.accent, false: colors.tintStrong }}
      thumbColor={colors.white}
      ios_backgroundColor={colors.tintStrong}
    />
  );
}

export default function Consent() {
  const { updateUser } = useAuth();
  const [photos, setPhotos] = useState(false);
  const [answers, setAnswers] = useState(false);
  const [busy, setBusy] = useState(false);

  async function agree() {
    setBusy(true);
    await updateUser({ consentVersion: POLICY_VERSION });
    setBusy(false);
    router.replace('/check/area');
  }

  return (
    <Screen
      nav={<NavBar />}
      contentStyle={{ gap: 24 }}
      footer={
        <>
          <Button label="Agree and continue" disabled={!photos || !answers} loading={busy} onPress={agree} />
          <Text style={[type.caption, { textAlign: 'center' }]}>Policy v{POLICY_VERSION} · You can withdraw consent any time in Me › Privacy and data.</Text>
        </>
      }>
      <View style={{ height: 140 }}>
        <Image source={require('@/assets/images/photos/applying-serum.jpg')} style={{ flex: 1, borderRadius: 22 }} contentFit="cover" />
        <View style={styles.tag}>
          <Icon name="shield" size={18} color={colors.accent} />
          <Text style={[type.label, { color: colors.ink }]}>Your data stays yours</Text>
        </View>
      </View>
      <Heading
        title="Before your first skin check"
        subtitle="Face photos and answers about your skin count as health data under GDPR. Here is what we use, why, and for how long."
      />
      <List>
        {USES.map(([title, sub, icon, tone], i) => (
          <View key={title}>
            {i > 0 ? <Divider inset={68} /> : null}
            <Row title={title} subtitle={sub} left={<IconTile name={icon} tone={tone} />} />
          </View>
        ))}
      </List>
      <Section title="Your choices">
        <List>
          <Row title="Photo analysis" subtitle="Required for a skin check" right={<Toggle label="Photo analysis" value={photos} onChange={setPhotos} />} />
          <Divider />
          <Row title="Skin and health answers" subtitle="Required for a personalised result" right={<Toggle label="Skin and health answers" value={answers} onChange={setAnswers} />} />
        </List>
      </Section>
      <Callout>
        Lumière gives general information and is not a medical device. It doesn’t diagnose or treat anything. For any worry about your skin, see a dermatologist.
      </Callout>
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
