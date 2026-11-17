// 12 · Choose area
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import Svg, { Ellipse, Path } from 'react-native-svg';

import { Button, Chip, ChipGroup, Heading, NavBar, Screen, Segmented } from '@/components/ui';
import { useSkinCheck, Zone, ZONE_LABEL } from '@/lib/skin-check';
import { colors, pastel, PastelName, type } from '@/lib/theme';

const ZONES: { zone: Exclude<Zone, 'face'>; tone: PastelName; cx: number; cy: number; rx: number; ry: number }[] = [
  { zone: 'forehead', tone: 'lilac', cx: 120, cy: 72, rx: 46, ry: 20 },
  { zone: 'nose', tone: 'butter', cx: 120, cy: 150, rx: 15, ry: 22 },
  // the face looks at the user, so the person's left cheek is on the right of the drawing
  { zone: 'left_cheek', tone: 'rose', cx: 166, cy: 170, rx: 24, ry: 26 },
  { zone: 'right_cheek', tone: 'rose', cx: 74, cy: 170, rx: 24, ry: 26 },
  { zone: 'chin', tone: 'mint', cx: 120, cy: 228, rx: 24, ry: 14 },
];

function FaceMap({ selected, whole, onToggle }: { selected: Zone[]; whole: boolean; onToggle: (z: Exclude<Zone, 'face'>) => void }) {
  return (
    <View style={{ backgroundColor: colors.surface, borderRadius: 20, paddingVertical: 20, alignItems: 'center' }}>
      <View style={{ width: 240, height: 270 }}>
        <Svg width={240} height={270} viewBox="0 0 240 270">
          <Path
            d="M120 18c48 0 88 36 88 92 0 70-38 142-88 142S32 180 32 110c0-56 40-92 88-92Z"
            fill={whole ? colors.tint : colors.white}
            stroke={whole ? colors.accent : colors.ink3}
            strokeWidth={1.5}
          />
          <Path d="M76 124h88M115 132v33M101 198h38" stroke={colors.ink3} strokeWidth={1.5} fill="none" strokeLinecap="round" />
          {!whole &&
            ZONES.map((z) => {
              const on = selected.includes(z.zone);
              return (
                <Ellipse
                  key={z.zone}
                  cx={z.cx}
                  cy={z.cy}
                  rx={z.rx}
                  ry={z.ry}
                  fill={on ? colors.roseStrong : pastel[z.tone].bg}
                  stroke={on ? colors.accent : pastel[z.tone].ink}
                  strokeWidth={on ? 1.5 : 1}
                  opacity={on ? 1 : 0.8}
                />
              );
            })}
        </Svg>
        {/* touch targets over the zones (SVG press handlers are not supported the same way on web) */}
        {!whole &&
          ZONES.map((z) => (
            <Pressable
              key={z.zone}
              accessibilityRole="checkbox"
              accessibilityLabel={ZONE_LABEL[z.zone]}
              accessibilityState={{ checked: selected.includes(z.zone) }}
              onPress={() => onToggle(z.zone)}
              style={{ position: 'absolute', left: z.cx - z.rx, top: z.cy - z.ry, width: z.rx * 2, height: z.ry * 2, borderRadius: z.rx }}
            />
          ))}
      </View>
    </View>
  );
}

export default function ChooseArea() {
  const check = useSkinCheck();
  const [whole, setWhole] = useState(check.wholeFace);
  const [zones, setZones] = useState<Zone[]>(check.wholeFace ? ['left_cheek', 'right_cheek'] : check.zones);

  const toggle = (z: Exclude<Zone, 'face'>) => setZones((list) => (list.includes(z) ? list.filter((x) => x !== z) : [...list, z]));
  const ordered = ZONES.map((z) => z.zone).filter((z) => zones.includes(z));
  const count = whole ? 1 : ordered.length;

  function next() {
    check.setArea(whole, ordered);
    router.push('/check/capture');
  }

  return (
    <Screen
      nav={<NavBar />}
      contentStyle={{ gap: 24 }}
      footer={
        <Button
          label={whole ? 'Continue with whole face' : `Continue with ${count} zone${count === 1 ? '' : 's'}`}
          disabled={count === 0}
          onPress={next}
        />
      }>
      <Heading title="Where should we look?" />
      <Segmented
        options={[
          { value: 'whole', label: 'Whole face' },
          { value: 'zones', label: 'Specific zones' },
        ]}
        value={whole ? 'whole' : 'zones'}
        onChange={(v) => setWhole(v === 'whole')}
      />
      <FaceMap selected={zones} whole={whole} onToggle={toggle} />
      {whole ? (
        <Text style={type.caption}>One photo of your whole face, straight on, in good light.</Text>
      ) : (
        <View style={{ gap: 10 }}>
          <ChipGroup>
            {ZONES.map((z) => (
              <Chip key={z.zone} label={ZONE_LABEL[z.zone]} selected={zones.includes(z.zone)} onPress={() => toggle(z.zone)} />
            ))}
          </ChipGroup>
          <Text style={type.caption}>Tap where you notice something. You’ll take one close-up per zone.</Text>
        </View>
      )}
    </Screen>
  );
}
