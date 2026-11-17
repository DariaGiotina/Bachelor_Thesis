// 03 · Log in
import { Image } from 'expo-image';
import { router } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, StyleSheet, Text, View } from 'react-native';

import { Icon } from '@/components/icon';
import { Button, Callout, Checkbox, Field, Heading, NavBar, Screen, TextLink } from '@/components/ui';
import { AuthError, isEmail, LOCK_MINUTES, MAX_ATTEMPTS, useAuth } from '@/lib/auth';
import { colors, radius, type } from '@/lib/theme';

export default function LogIn() {
  const { logIn } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [keep, setKeep] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const canSubmit = isEmail(email) && password.length > 0;

  async function submit() {
    if (!canSubmit) {
      setError('Please enter your email and password.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await logIn(email, password, keep);
    } catch (e) {
      setError(e instanceof AuthError ? e.message : 'Something went wrong. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <Screen
        nav={<NavBar />}
        footer={
          <>
            <Button label="Log in" onPress={submit} loading={busy} />
            <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 4 }}>
              <Text style={[type.body, { color: colors.ink2 }]}>New to Lumière?</Text>
              <TextLink onPress={() => router.replace('/sign-up')}>Create an account</TextLink>
            </View>
          </>
        }>
        <View style={{ height: 210 + 32 }}>
          <View style={styles.photoClip}>
            <Image source={require('@/assets/images/photos/applying-serum.jpg')} style={StyleSheet.absoluteFill} contentFit="cover" />
            <Text style={[type.title, styles.overlayTitle]}>Welcome back</Text>
          </View>
          <Pressable accessibilityLabel="Log in" onPress={submit} style={styles.arrow}>
            <Icon name="arrow-right" size={26} color={colors.accentDeep} />
          </Pressable>
        </View>
        <Heading title="Log in" subtitle="Pick up your routine where you left off." />
        <View style={{ gap: 16 }}>
          <Field label="Email" value={email} onChangeText={setEmail} autoCapitalize="none" autoComplete="email" keyboardType="email-address" textContentType="emailAddress" placeholder="name@email.com" />
          <Field label="Password" value={password} onChangeText={setPassword} secureTextEntry autoComplete="current-password" textContentType="password" placeholder="Your password" onSubmitEditing={submit} />
        </View>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
          <Checkbox checked={keep} onChange={setKeep} label="Keep me signed in" />
          <TextLink onPress={() => router.push('/reset-password')}>Forgot password?</TextLink>
        </View>
        {error ? (
          <Callout icon="alert" tone="flag">
            {error}
          </Callout>
        ) : (
          <Callout icon="lock">{`After ${MAX_ATTEMPTS} failed attempts, sign-in pauses for ${LOCK_MINUTES} minutes to protect your account.`}</Callout>
        )}
      </Screen>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  photoClip: { height: 210, borderRadius: radius.xl, overflow: 'hidden', justifyContent: 'flex-end' },
  overlayTitle: { color: colors.white, padding: 16, textShadowColor: 'rgba(42,30,34,0.35)', textShadowRadius: 8 },
  arrow: {
    position: 'absolute',
    right: 22,
    top: 178,
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: colors.roseStrong,
    borderWidth: 6,
    borderColor: colors.canvas,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
