// 20 · Result
import { Image } from 'expo-image';
import { Redirect, router } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { ConfidenceRing } from '@/components/confidence-ring';
import { Bar, Button, Callout, Divider, List, NavBar, Pill, Row, Screen, Section } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { CLASSES } from '@/lib/ml-api';
import { meaningText, ROUTINE_IDEA } from '@/lib/result-text';
import { answeredCount, CLASS_INFO, pct, saveToHistory, shortDate, useSkinCheck, ZONE_LABEL, zonesText } from '@/lib/skin-check';
import { colors, pastel, radius, type } from '@/lib/theme';

export default function Result() {
  const { user } = useAuth();
  const check = useSkinCheck();
  const [saved, setSaved] = useState(false);
  const r = check.result;
  if (!r || r.status !== 'answered' || !r.category) return <Redirect href="/skin" />;

  const info = CLASS_INFO[r.category];
  const others = CLASSES.filter((c) => c !== r.category).sort((a, b) => r.probabilities[b] - r.probabilities[a]);
  const answers = answeredCount(r.answers);
  const symptoms = (r.answers.symptoms ?? []).filter((s) => s !== 'None of these').slice(0, 2);
  const routine = ROUTINE_IDEA[r.category];

  async function save() {
    if (!user || !r) return;
    await saveToHistory(user.id, r);
    setSaved(true);
  }

  function done() {
    check.reset();
    router.dismissTo('/skin');
  }

  return (
    <Screen nav={<NavBar title="Result" onBack={done} backIcon="close" />}>
      <Text style={type.label}>
        {shortDate(r.date, true)} · {zonesText(r.zones)}
      </Text>

      <View style={{ flexDirection: 'row', gap: 10, alignItems: 'center' }}>
        {check.photos.slice(0, 2).map((p) => (
          <Image key={p.zone} source={{ uri: p.uri }} style={styles.thumb} contentFit="cover" />
        ))}
        <View style={{ flex: 1, gap: 2 }}>
          <Text style={type.bodyStrong}>
            {check.photos.length} photo{check.photos.length === 1 ? '' : 's'} · {answers} of 5 answers
          </Text>
          <Text style={type.label}>Photos are deleted after this result</Text>
        </View>
      </View>

      {check.photos[0] ? (
        <View style={styles.photoCard}>
          <Image source={{ uri: check.photos[0].uri }} style={StyleSheet.absoluteFill} contentFit="cover" />
          <View style={styles.zoneChip}>
            <View style={{ width: 7, height: 7, borderRadius: 4, backgroundColor: colors.accent }} />
            <Text style={[type.caption, { color: colors.white }]}>{ZONE_LABEL[check.photos[0].zone]}</Text>
          </View>
        </View>
      ) : null}

      <View style={{ gap: 10 }}>
        <Text style={type.section}>May indicate</Text>
        <Text style={type.title}>{info.label}</Text>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
          <Pill label={zonesText(r.zones)} tone="rose" />
          {symptoms.map((s, i) => (
            <Pill key={s} label={s} tone={i === 0 ? 'peach' : 'lilac'} />
          ))}
        </View>
        <View style={{ flexDirection: 'row', gap: 14, alignItems: 'center', marginTop: 4 }}>
          <ConfidenceRing value={r.confidence} />
          <View style={{ flex: 1, gap: 2 }}>
            <Text style={type.bodyStrong}>Match confidence</Text>
            <Text style={type.caption}>How closely your photo matches this pattern. It is not certainty.</Text>
          </View>
        </View>
      </View>

      <Section title="Other possibilities">
        <List>
          {others.map((c, i) => (
            <View key={c}>
              {i > 0 ? <Divider inset={0} /> : null}
              <View style={styles.otherRow}>
                <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: pastel[CLASS_INFO[c].tone].ink }} />
                <View style={{ flex: 1, gap: 6 }}>
                  <Text style={type.body}>{CLASS_INFO[c].label}</Text>
                  <Bar value={r.probabilities[c]} color={pastel[CLASS_INFO[c].tone].ink} track={pastel[CLASS_INFO[c].tone].bg} />
                </View>
                <Text style={[type.bodyStrong, { width: 40, textAlign: 'right' }]}>{pct(r.probabilities[c])}</Text>
              </View>
            </View>
          ))}
        </List>
      </Section>

      {r.perPhoto.length > 1 ? (
        <Section title="Photo by photo">
          <List>
            {r.perPhoto.map((p, i) => (
              <View key={p.zone}>
                {i > 0 ? <Divider /> : null}
                <Row
                  title={ZONE_LABEL[p.zone]}
                  subtitle={
                    p.status === 'answered' && p.category
                      ? `${CLASS_INFO[p.category].label} · ${pct(p.confidence)}`
                      : p.status === 'uncertain'
                        ? 'Not sure for this photo'
                        : 'Photo not usable'
                  }
                />
              </View>
            ))}
          </List>
        </Section>
      ) : null}

      <Section title="What this may mean">
        <Text style={[type.bodyL, { color: colors.ink }]}>{meaningText(r.category, r.answers)}</Text>
        <Text style={type.caption}>
          Based on {r.perPhoto.length} photo{r.perPhoto.length === 1 ? '' : 's'} · {answers} of 5 answers
          {r.answers.skinTone ? ` · Skin tone ${r.answers.skinTone}` : ''} · Model 1.0
        </Text>
      </Section>

      <Section title={routine.title}>
        <List>
          {routine.steps.map(([name, step, tone], i) => (
            <View key={name}>
              {i > 0 ? <Divider /> : null}
              <Row title={name} right={<Pill label={step} tone={tone} />} />
            </View>
          ))}
        </List>
        <Button label={saved ? 'Saved to history' : 'Save to history'} icon={saved ? 'check' : undefined} disabled={saved} onPress={save} />
        <Button label="Done" variant="secondary" onPress={done} />
      </Section>

      <Callout icon="alert" tone="caution">
        This is not a diagnosis. If it lasts, gets worse, hurts or spreads, please see a dermatologist.
      </Callout>
    </Screen>
  );
}

const styles = StyleSheet.create({
  thumb: { width: 56, height: 56, borderRadius: 14 },
  photoCard: { height: 360, borderRadius: radius.xl, overflow: 'hidden', backgroundColor: colors.tint },
  zoneChip: {
    position: 'absolute',
    left: 12,
    top: 14,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: 'rgba(26,18,20,0.45)',
    borderRadius: radius.pill,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  otherRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 16, paddingVertical: 14 },
});
