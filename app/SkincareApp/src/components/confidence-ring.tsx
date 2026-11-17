import { Text, View } from 'react-native';
import Svg, { Circle } from 'react-native-svg';

import { colors, type } from '@/lib/theme';

export function ConfidenceRing({ value, size = 76 }: { value: number; size?: number }) {
  const stroke = 8;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  return (
    <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
      <Svg width={size} height={size} style={{ position: 'absolute', transform: [{ rotate: '-90deg' }] }}>
        <Circle cx={size / 2} cy={size / 2} r={r} stroke={colors.tintStrong} strokeWidth={stroke} fill="none" />
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={colors.accent}
          strokeWidth={stroke}
          fill="none"
          strokeDasharray={`${c * value} ${c}`}
          strokeLinecap="round"
        />
      </Svg>
      <Text style={type.bodyStrong}>{Math.round(value * 100)}%</Text>
    </View>
  );
}
