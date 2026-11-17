// Fitzpatrick skin-tone scale (types I-VI) with a "Prefer not to say" chip.
import { Pressable, Text, View } from 'react-native';

import { colors, type } from '@/lib/theme';
import { Chip } from './ui';

const TONES: [string, string][] = [
  ['I', '#F6E1D3'],
  ['II', '#EBC9AE'],
  ['III', '#D8A985'],
  ['IV', '#B47F57'],
  ['V', '#7E5235'],
  ['VI', '#4A2E20'],
];

export function SkinToneScale({ value, onChange }: { value?: string; onChange: (v: string | undefined) => void }) {
  return (
    <View style={{ gap: 12 }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
        {TONES.map(([label, fill]) => {
          const on = value === label;
          return (
            <Pressable
              key={label}
              accessibilityRole="radio"
              accessibilityLabel={`Skin tone type ${label}`}
              accessibilityState={{ selected: on }}
              onPress={() => onChange(on ? undefined : label)}
              style={{ width: 52, alignItems: 'center', gap: 6 }}>
              <View
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 20,
                  backgroundColor: fill,
                  borderWidth: on ? 2.5 : 0,
                  borderColor: colors.accent,
                }}
              />
              <Text style={on ? [type.bodyStrong, { color: colors.accent }] : type.label}>{label}</Text>
            </Pressable>
          );
        })}
      </View>
      <View style={{ flexDirection: 'row' }}>
        <Chip label="Prefer not to say" selected={value === undefined} onPress={() => onChange(undefined)} />
      </View>
    </View>
  );
}
