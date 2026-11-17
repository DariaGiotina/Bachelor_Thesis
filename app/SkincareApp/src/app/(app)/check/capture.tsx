// 13 · Capture photo: one photo per chosen zone, from the camera or imported from the gallery.
import { CameraType, CameraView, useCameraPermissions } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import { router } from 'expo-router';
import { useRef, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Svg, { Ellipse, Path } from 'react-native-svg';

import { Icon } from '@/components/icon';
import { Button, NavBar } from '@/components/ui';
import { useSkinCheck, ZONE_LABEL } from '@/lib/skin-check';
import { colors, radius, type } from '@/lib/theme';

const TIPS = ['Daylight', 'No filter', 'No make-up'];

export default function Capture() {
  const check = useSkinCheck();
  const [permission, requestPermission] = useCameraPermissions();
  const [facing, setFacing] = useState<CameraType>('front');
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const camera = useRef<CameraView>(null);

  const pending = check.pendingZones();
  const zone = pending[0] ?? check.zones[check.zones.length - 1];
  const index = check.zones.indexOf(zone) + 1;
  const title = zone === 'face' ? 'Whole face' : `${ZONE_LABEL[zone]} · ${index} of ${check.zones.length}`;
  const prompt = zone === 'face' ? 'Fill the oval with your face' : `Fill the oval with your ${ZONE_LABEL[zone].toLowerCase()}`;

  function accept(uri: string) {
    check.addPhoto({ zone, uri });
    if (pending.length <= 1) router.replace('/check/q/1');
  }

  async function shoot() {
    if (!camera.current || !ready || busy) return;
    setBusy(true);
    try {
      const pic = await camera.current.takePictureAsync({ quality: 0.9 });
      if (pic?.uri) accept(pic.uri);
    } catch {
      setCameraError('The photo could not be taken. Try again or import one.');
    } finally {
      setBusy(false);
    }
  }

  async function importPhoto() {
    const res = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 1 });
    if (!res.canceled && res.assets[0]) accept(res.assets[0].uri);
  }

  const granted = permission?.granted;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.night }}>
      <NavBar light title={title} backIcon="close" />
      <View style={styles.content}>
        <View style={styles.viewfinder}>
          {granted ? (
            <CameraView
              ref={camera}
              style={StyleSheet.absoluteFill}
              facing={facing}
              mirror={facing === 'front'}
              onCameraReady={() => setReady(true)}
              onMountError={(e) => setCameraError(e.message)}
            />
          ) : (
            <View style={styles.permission}>
              <Icon name="camera" size={32} color={colors.white} />
              <Text style={[type.body, { color: colors.white, textAlign: 'center' }]}>
                {permission?.canAskAgain === false
                  ? 'Camera access is off for Lumière. Turn it on in Settings, or import a photo instead.'
                  : 'Lumière needs the camera to take the photo. The photo is analysed and then deleted.'}
              </Text>
              {permission?.canAskAgain !== false ? <Button label="Allow camera" compact onPress={requestPermission} /> : null}
            </View>
          )}
          {granted ? (
            <View pointerEvents="none" style={StyleSheet.absoluteFill}>
              <Svg width="100%" height="100%" viewBox="0 0 353 470" preserveAspectRatio="xMidYMid meet">
                <Ellipse cx={177} cy={237} rx={110} ry={145} stroke="rgba(255,255,255,0.7)" strokeWidth={1.5} fill="none" />
                <Path d="M55 140v-26h26M273 114h26v26M299 350v26h-26M81 376H55v-26" stroke="rgba(255,255,255,0.95)" strokeWidth={2.5} fill="none" />
              </Svg>
              <Text style={[type.label, styles.prompt]}>{prompt}</Text>
            </View>
          ) : null}
        </View>
        {cameraError ? <Text style={[type.caption, { color: colors.roseStrong, textAlign: 'center' }]}>{cameraError}</Text> : null}
        <View style={styles.tips}>
          {TIPS.map((t) => (
            <View key={t} style={styles.tip}>
              <Text style={[type.label, { color: colors.white }]}>{t}</Text>
            </View>
          ))}
        </View>
        <View style={styles.controls}>
          <Pressable style={styles.side} onPress={importPhoto} accessibilityRole="button" accessibilityLabel="Import a photo">
            <View style={styles.sideButton}>
              <Icon name="image" color={colors.white} />
            </View>
            <Text style={[type.caption, { color: colors.white }]}>Import</Text>
          </Pressable>
          <Pressable style={styles.shutter} onPress={shoot} disabled={!granted || !ready || busy} accessibilityRole="button" accessibilityLabel="Take photo">
            {busy ? <ActivityIndicator color={colors.night} /> : <View style={[styles.shutterInner, (!granted || !ready) && { opacity: 0.4 }]} />}
          </Pressable>
          <Pressable style={styles.side} onPress={() => setFacing((f) => (f === 'front' ? 'back' : 'front'))} accessibilityRole="button" accessibilityLabel="Flip camera">
            <View style={styles.sideButton}>
              <Icon name="flip" color={colors.white} />
            </View>
            <Text style={[type.caption, { color: colors.white }]}>Flip</Text>
          </Pressable>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  content: { flex: 1, paddingHorizontal: 20, paddingTop: 8, paddingBottom: 12, gap: 20 },
  viewfinder: { flex: 1, borderRadius: radius.xl, overflow: 'hidden', backgroundColor: '#2A1E22' },
  permission: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 16, padding: 24 },
  prompt: { position: 'absolute', bottom: 24, alignSelf: 'center', color: colors.white },
  tips: { flexDirection: 'row', justifyContent: 'center', gap: 8 },
  tip: { backgroundColor: 'rgba(255,255,255,0.12)', borderRadius: radius.pill, paddingHorizontal: 12, paddingVertical: 6 },
  controls: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 12 },
  side: { width: 72, alignItems: 'center', gap: 6 },
  sideButton: { width: 48, height: 48, borderRadius: 24, backgroundColor: 'rgba(255,255,255,0.14)', alignItems: 'center', justifyContent: 'center' },
  shutter: { width: 76, height: 76, borderRadius: 38, borderWidth: 3, borderColor: colors.white, alignItems: 'center', justifyContent: 'center' },
  shutterInner: { width: 62, height: 62, borderRadius: 31, backgroundColor: colors.white },
});
