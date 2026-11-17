// 21 · Result uncertain: confidence below the threshold, so the app does not guess.
import { Image } from 'expo-image';
import { Redirect, router } from 'expo-router';
import { useEffect } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { Icon } from '@/components/icon';
import { Button, Callout, Divider, Heading, IconTile, List, NavBar, Row, Screen, Section } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { answeredCount, CLASS_INFO, pct, saveToHistory, useSkinCheck } from '@/lib/skin-check';
import { colors, radius, type } from '@/lib/theme';

export default function Uncertain() {
  const { user } = useAuth();
  const check = useSkinCheck();
  const r = check.result;

  useEffect(() => {
    // uncertain checks are kept in the history too, so a pattern of unclear results stays visible
    if (user && r && r.status === 'uncertain') saveToHistory(user.id, r);
  }, [user, r]);

  if (!r || r.status !== 'uncertain') return <Redirect href="/skin" />;
  const answers = answeredCount(r.answers);

  function retake() {
    check.setResult(null);
    check.setArea(check.wholeFace, check.zones);
    router.replace('/check/capture');
  }

  function done() {
    check.reset();
    router.dismissTo('/skin');
  }

  return (
    <Screen
      nav={<NavBar onBack={done} backIcon="close" />}
      footer={
        <>
          <Button label="Retake in daylight" onPress={retake} />
          {answers < 5 ? (
            <Button label="Answer the remaining questions" variant="secondary" onPress={() => router.replace('/check/q/1')} />
          ) : (
            <Button label="Back to Today" variant="secondary" onPress={() => { check.reset(); router.dismissTo('/today'); }} />
          )}
        </>
      }>
      {check.photos[0] ? (
        <View style={{ height: 150 }}>
          <Image source={{ uri: check.photos[0].uri }} style={{ flex: 1, borderRadius: 22 }} contentFit="cover" />
          <View style={styles.tag}>
            <Icon name="info" size={18} color={colors.accent} />
            <Text style={[type.label, { color: colors.ink }]}>Not clear enough to be sure</Text>
          </View>
        </View>
      ) : null}
      <Heading
        title="We can’t tell this time"
        subtitle={`Confidence was below our threshold, so we’d rather not guess. The closest match was ${CLASS_INFO[r.closest].label.toLowerCase()} at ${pct(r.confidence)}.`}
      />
      <Section title="What can make it hard">
        <List>
          <Row title="Light and focus" subtitle="Dark, warm-toned or blurry photos are harder to read." left={<IconTile name="sun" tone="butter" />} />
          <Divider inset={68} />
          <Row
            title={answers < 5 ? 'Few answers' : 'Unclear pattern'}
            subtitle={answers < 5 ? `${answers} of 5 questions answered.` : 'The photo matches more than one pattern.'}
            left={<IconTile name="doc" tone="lilac" />}
          />
        </List>
      </Section>
      <Callout>
        <Text style={type.bodyStrong}>Consider seeing a professional</Text>
        <Text style={[type.label, { color: colors.ink }]}>A dermatologist can take a proper look. Lumière gives general information and can’t diagnose.</Text>
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
