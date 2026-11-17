// 23 · Photo not usable: the service flagged the photo as unlike the photos the model learned from
// (the out-of-scope detector), so no score is shown and nothing is saved.
import { Image } from 'expo-image';
import { Redirect, router } from 'expo-router';
import { StyleSheet, Text, View } from 'react-native';

import { Button, Callout, Divider, Heading, IconTile, List, NavBar, Row, Screen } from '@/components/ui';
import { useSkinCheck } from '@/lib/skin-check';
import { colors, radius, type } from '@/lib/theme';

export default function Unusual() {
  const check = useSkinCheck();
  const r = check.result;
  if (!r || r.status !== 'unusual_photo') return <Redirect href="/skin" />;

  function retake() {
    check.setResult(null);
    check.setArea(check.wholeFace, check.zones);
    router.replace('/check/capture');
  }

  return (
    <Screen
      nav={<NavBar onBack={() => { check.reset(); router.dismissTo('/skin'); }} backIcon="close" />}
      footer={<Button label="Retake photo" onPress={retake} />}>
      {check.photos[0] ? (
        <View style={styles.preview}>
          <Image source={{ uri: check.photos[0].uri }} style={StyleSheet.absoluteFill} contentFit="cover" blurRadius={12} />
          <View style={[StyleSheet.absoluteFill, { backgroundColor: 'rgba(26,18,20,0.35)' }]} />
        </View>
      ) : null}
      <Heading
        title="This photo is hard to read"
        subtitle="Before looking at your skin, we check that the photo looks like the close-up skin photos Lumière learned from. This one didn’t pass."
      />
      <List>
        <Row title="Fill the frame with skin" subtitle="Move closer so the zone fills the oval. Avoid hair, clothes and background." left={<IconTile name="face" tone="peach" />} />
        <Divider inset={68} />
        <Row title="Use soft daylight" subtitle="Face a window. Avoid flash, filters and strong shadows." left={<IconTile name="sun" tone="butter" />} />
        <Divider inset={68} />
        <Row title="Hold still" subtitle="Tap the screen to focus before taking the photo." left={<IconTile name="camera" tone="mint" />} />
      </List>
      <Callout tone="flag" icon="alert">
        <Text style={type.bodyStrong}>Some changes need a professional</Text>
        <Text style={[type.label, { color: colors.ink }]}>
          Lumière only looks for acne-like breakouts, eczema-like dryness and redness-type irritation. For a spot or mole that is new, growing, changing colour, bleeding or itchy, please see a dermatologist or GP.
        </Text>
      </Callout>
      <Text style={type.caption}>Nothing has been saved. A clear photo gives a more reliable result.</Text>
    </Screen>
  );
}

const styles = StyleSheet.create({
  preview: { height: 170, borderRadius: radius.lg, overflow: 'hidden', backgroundColor: colors.tint },
});
