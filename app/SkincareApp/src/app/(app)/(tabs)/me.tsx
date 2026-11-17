// 50 · Me (account part only)
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { Icon } from '@/components/icon';
import { Button, Divider, IconTile, List, Row, Screen, Section } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { mlServiceUrl } from '@/lib/ml-api';
import { loadHistory } from '@/lib/skin-check';
import { colors, type } from '@/lib/theme';

export default function Me() {
  const { user, logOut } = useAuth();
  const [checks, setChecks] = useState(0);

  useFocusEffect(
    useCallback(() => {
      if (user) loadHistory(user.id).then((h) => setChecks(h.length));
    }, [user]),
  );

  if (!user) return null;
  return (
    <Screen inTabs contentStyle={{ paddingTop: 12 }}>
      <Text style={type.display}>Me</Text>
      <View style={styles.card}>
        <View style={styles.avatar}>
          <Text style={[type.title, { color: colors.accentDeep }]}>{user.name.charAt(0).toUpperCase()}</Text>
        </View>
        <View style={{ flex: 1, gap: 2 }}>
          <Text style={type.headline}>{user.name}</Text>
          <Text style={type.label}>{user.email}</Text>
        </View>
      </View>
      <Section title="Skin profile">
        <List>
          <Row title="Age range" right={<Text style={type.bodyStrong}>{user.ageRange ?? 'Not set'}</Text>} />
          <Divider />
          <Row title="Skin tone" right={<Text style={type.bodyStrong}>{user.skinTone ? `Type ${user.skinTone}` : 'Not set'}</Text>} />
        </List>
      </Section>
      <List>
        <Row
          title="Past skin checks"
          left={<IconTile name="clock" tone="rose" />}
          right={
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              <Text style={type.label}>{checks}</Text>
              <Icon name="chevron-right" color={colors.ink3} />
            </View>
          }
          onPress={() => router.push('/history')}
        />
        <Divider inset={68} />
        <Row title="Privacy and data" subtitle={user.consentVersion ? `Consent given · policy v${user.consentVersion}` : 'No consent given yet'} left={<IconTile name="shield" tone="sky" />} />
      </List>
      <Button label="Log out" variant="secondary" icon="logout" onPress={logOut} />
      <Text style={type.caption}>Analysis service: {mlServiceUrl()}</Text>
    </Screen>
  );
}

const styles = StyleSheet.create({
  card: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 16, borderRadius: 20, backgroundColor: colors.tint },
  avatar: { width: 56, height: 56, borderRadius: 28, backgroundColor: colors.white, alignItems: 'center', justifyContent: 'center' },
});
