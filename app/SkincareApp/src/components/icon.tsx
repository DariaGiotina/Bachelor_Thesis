import Svg, { Path } from 'react-native-svg';

import { colors } from '@/lib/theme';
import { ICON_PATHS, IconName } from './icon-paths';

export type { IconName };

export function Icon({ name, size = 24, color = colors.ink }: { name: IconName; size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24">
      <Path d={ICON_PATHS[name]} fill={color} />
    </Svg>
  );
}
