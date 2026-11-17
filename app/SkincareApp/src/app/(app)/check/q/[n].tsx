// 14-18 · The five questions. Every question can be skipped; the result says how many were answered.
import { router, useLocalSearchParams } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Icon, IconName } from '@/components/icon';
import { Button, Chip, ChipGroup, Divider, IconTile, List, Radio, Row, Section, Segmented } from '@/components/ui';
import { SkinToneScale } from '@/components/skin-tone';
import { useAuth } from '@/lib/auth';
import { Answers, useSkinCheck, zonesText } from '@/lib/skin-check';
import { colors, pastel, PastelName, type } from '@/lib/theme';

const SKIN_TYPES = [
  ['Oily', 'Shiny all over, visible pores'],
  ['Combination', 'Oily T-zone, drier cheeks'],
  ['Dry', 'Tight, sometimes flaky'],
  ['Normal', 'Balanced, rarely reactive'],
  ['Sensitive', 'Stings or reddens easily'],
];
const DURATIONS = [
  ['Days', 'Appeared in the last two weeks'],
  ['Weeks', 'About 2 to 6 weeks'],
  ['Months', 'More than 6 weeks'],
  ['Years', 'As long as I can remember'],
];
const SYMPTOMS = ['Itching', 'Burning', 'Flaking', 'Tightness', 'Stinging with products', 'Bumps', 'Dryness', 'None of these'];
const CHANGES = ['New product', 'Sun exposure', 'Change of season', 'Hormonal cycle', 'Stress', 'Travel or new climate', 'Not sure'];
const AGES = ['Under 18', '18–24', '25–34', '35–44', '45–54', '55+'];

const META: { icon: IconName; tone: PastelName }[] = [
  { icon: 'drop', tone: 'sky' },
  { icon: 'clock', tone: 'butter' },
  { icon: 'alert', tone: 'peach' },
  { icon: 'sun', tone: 'lilac' },
  { icon: 'user', tone: 'mint' },
];

function toggleIn(list: string[] | undefined, value: string, exclusive: string) {
  const cur = list ?? [];
  if (value === exclusive) return cur.includes(value) ? [] : [value];
  const without = cur.filter((v) => v !== exclusive);
  return without.includes(value) ? without.filter((v) => v !== value) : [...without, value];
}

function Options({ options, value, onChange }: { options: string[][]; value?: string; onChange: (v: string | undefined) => void }) {
  return (
    <List>
      {options.map(([title, sub], i) => (
        <View key={title}>
          {i > 0 ? <Divider inset={0} /> : null}
          <Row
            title={title}
            subtitle={sub}
            highlighted={value === title}
            left={<Radio selected={value === title} />}
            onPress={() => onChange(value === title ? undefined : title)}
          />
        </View>
      ))}
    </List>
  );
}

export default function Question() {
  const n = Math.min(5, Math.max(1, Number(useLocalSearchParams<{ n: string }>().n) || 1));
  const { user, updateUser } = useAuth();
  const check = useSkinCheck();
  const a = check.answers;
  const set = (patch: Partial<Answers>) => check.setAnswers(patch);
  // Q5 starts from the profile, as in the design ("Filled in from your profile"); '' = no answer.
  const ageRange = a.ageRange ?? user?.ageRange ?? '';
  const skinTone = a.skinTone ?? user?.skinTone ?? '';

  function go() {
    if (n < 5) router.push(`/check/q/${n + 1}`);
    else {
      set({ ageRange, skinTone });
      updateUser({ ageRange: ageRange || null, skinTone: skinTone || null }); // remembered for the next check
      router.replace('/check/analysing');
    }
  }

  function skip() {
    if (n === 1) set({ skinType: undefined });
    if (n === 2) set({ duration: undefined });
    if (n === 3) set({ symptoms: [], intensity: undefined });
    if (n === 4) set({ changes: [] });
    if (n === 5) {
      set({ ageRange: '', skinTone: '' });
      router.replace('/check/analysing');
      return;
    }
    go();
  }

  const heads: [string, string][] = [
    ['How does your skin usually feel?', 'Think of a normal day, a few hours after washing.'],
    ['How long has it been there?', `For your ${zonesText(check.zones).toLowerCase()}.`],
    ['What do you feel?', 'Choose all that apply.'],
    ['Has anything changed lately?', 'Context helps when the photo alone isn’t clear. Choose all that apply.'],
    ['A bit about you', 'Filled in from your profile. Both are optional.'],
  ];
  const [title, subtitle] = heads[n - 1];
  const meta = META[n - 1];

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.canvas }}>
      <View style={styles.bar}>
        <Pressable accessibilityLabel="Back" onPress={() => router.back()} style={{ width: 40, height: 40, justifyContent: 'center' }}>
          <Icon name="chevron-left" />
        </Pressable>
        <View style={{ flex: 1, flexDirection: 'row', gap: 4 }}>
          {[1, 2, 3, 4, 5].map((i) => (
            <View key={i} style={{ flex: 1, height: 4, borderRadius: 2, backgroundColor: i <= n ? colors.accent : colors.tintStrong }} />
          ))}
        </View>
        <Text style={[type.bodyStrong, { color: colors.accent }]} onPress={skip} suppressHighlighting accessibilityRole="button">
          Skip
        </Text>
      </View>
      <ScrollView style={{ flex: 1 }} showsVerticalScrollIndicator={false}>
        <View style={styles.content}>
          <View style={{ gap: 8 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <IconTile name={meta.icon} tone={meta.tone} size={32} />
              <Text style={[type.label, { color: pastel[meta.tone].ink }]}>Question {n} of 5</Text>
            </View>
            <Text style={type.title}>{title}</Text>
            <Text style={type.bodyL}>{subtitle}</Text>
          </View>

          {n === 1 && <Options options={SKIN_TYPES} value={a.skinType} onChange={(v) => set({ skinType: v })} />}
          {n === 2 && <Options options={DURATIONS} value={a.duration} onChange={(v) => set({ duration: v })} />}
          {n === 3 && (
            <>
              <ChipGroup>
                {SYMPTOMS.map((s) => (
                  <Chip key={s} label={s} selected={!!a.symptoms?.includes(s)} onPress={() => set({ symptoms: toggleIn(a.symptoms, s, 'None of these') })} />
                ))}
              </ChipGroup>
              {a.symptoms?.length && !a.symptoms.includes('None of these') ? (
                <Section title="How strong is it today?">
                  <Segmented
                    options={['Barely', 'Mild', 'Strong'].map((v) => ({ value: v, label: v }))}
                    value={a.intensity ?? ''}
                    onChange={(v) => set({ intensity: v })}
                  />
                </Section>
              ) : null}
            </>
          )}
          {n === 4 && (
            <>
              <ChipGroup>
                {CHANGES.map((s) => (
                  <Chip key={s} label={s} selected={!!a.changes?.includes(s)} onPress={() => set({ changes: toggleIn(a.changes, s, 'Not sure') })} />
                ))}
              </ChipGroup>
              <Text style={type.caption}>Hormonal cycle is optional and only used for this result.</Text>
            </>
          )}
          {n === 5 && (
            <>
              <Section title="Age range">
                <ChipGroup>
                  {AGES.map((s) => (
                    <Chip key={s} label={s} selected={ageRange === s} onPress={() => set({ ageRange: ageRange === s ? '' : s })} />
                  ))}
                </ChipGroup>
              </Section>
              <Section title="Skin tone">
                <SkinToneScale value={skinTone || undefined} onChange={(v) => set({ skinTone: v ?? '' })} />
                <Text style={type.caption}>
                  We use skin tone only to check that the model works equally well for everyone. It never changes how your result is judged.
                </Text>
              </Section>
            </>
          )}
          <Text style={type.caption}>Not sure? Skip it. Your result adapts to the answers you give.</Text>
        </View>
      </ScrollView>
      <View style={styles.footer}>
        <Button label={n === 5 ? 'See my result' : 'Next'} onPress={go} />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  bar: { height: 44, flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 12 },
  content: { paddingHorizontal: 20, paddingTop: 8, paddingBottom: 24, gap: 24 },
  footer: { paddingHorizontal: 20, paddingTop: 12, paddingBottom: 8 },
});
