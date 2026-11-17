// Placeholder for tabs whose module is built in a later step (barcode scanner, routines).
import { Text, View } from 'react-native';

import { Heading, IconTile, Screen } from '@/components/ui';
import { PastelName, type } from '@/lib/theme';
import { IconName } from './icon';

export function ComingSoon({ title, text, icon, tone }: { title: string; text: string; icon: IconName; tone: PastelName }) {
  return (
    <Screen inTabs contentStyle={{ paddingTop: 12 }}>
      <Heading large title={title} />
      <View style={{ alignItems: 'flex-start', gap: 16 }}>
        <IconTile name={icon} tone={tone} size={72} />
        <Text style={type.bodyL}>{text}</Text>
      </View>
    </Screen>
  );
}
