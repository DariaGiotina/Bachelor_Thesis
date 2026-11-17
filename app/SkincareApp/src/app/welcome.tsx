// 01 · Welcome
import { Image } from 'expo-image';
import { router } from 'expo-router';
import { StyleSheet, Text, View } from 'react-native';

import { Icon } from '@/components/icon';
import { Button, Logo, Screen } from '@/components/ui';
import { colors, radius, type } from '@/lib/theme';

export default function Welcome() {
  return (
    <Screen
      footer={
        <>
          <Button label="Create an account" onPress={() => router.push('/sign-up')} />
          <Button label="Log in" variant="secondary" onPress={() => router.push('/log-in')} />
          <Text style={[type.caption, { textAlign: 'center' }]}>Informational only. Not a medical device.</Text>
        </>
      }
      contentStyle={{ paddingTop: 12 }}>
      <Logo />
      <View style={styles.hero}>
        <Image source={require('@/assets/images/photos/hero-cream-tan.jpg')} style={styles.photo} contentFit="cover" />
        <Image source={require('@/assets/images/photos/cutout-serum.png')} style={styles.cutout} contentFit="contain" />
        <View style={{ position: 'absolute', left: 24, top: 22 }}>
          <Icon name="bow" size={26} color={colors.white} />
        </View>
        <View style={styles.tag}>
          <Icon name="bow" size={19} color={colors.accent} />
          <Text style={[type.label, { color: colors.ink }]}>Gentle routines for sensitive skin</Text>
        </View>
      </View>
      <View style={{ gap: 12 }}>
        <Text style={type.display}>
          Love your skin,{'\n'}
          <Text style={{ color: colors.accent }}>every day.</Text>
        </Text>
        <Text style={type.bodyL}>
          See what your skin may be showing, learn what’s really in your products and keep a routine that feels like yours.
        </Text>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  hero: { height: 330 },
  photo: { flex: 1, borderRadius: radius.xl },
  cutout: { position: 'absolute', right: -6, bottom: -40, width: 51, height: 150 },
  tag: {
    position: 'absolute',
    left: 16,
    bottom: 16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: colors.white,
    borderRadius: radius.pill,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
});
