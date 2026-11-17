// 02 · Sign up
import { Image } from 'expo-image';
import { router } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, Text, View } from 'react-native';

import { Button, Callout, Checkbox, Field, Heading, NavBar, Screen, TextLink } from '@/components/ui';
import { AuthError, isEmail, passwordStrength, POLICY_VERSION, useAuth } from '@/lib/auth';
import { colors, type } from '@/lib/theme';

const METER = [colors.flag, colors.caution, colors.good, colors.good];

export default function SignUp() {
  const { register } = useAuth();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [terms, setTerms] = useState(false);
  const [news, setNews] = useState(false);
  const [touched, setTouched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const strength = passwordStrength(password);
  const meterColor = METER[Math.max(0, strength.score - 1)];
  const canSubmit = name.trim() && isEmail(email) && strength.score >= 2 && terms;

  async function submit() {
    setTouched(true);
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      await register(name, email, password);
      // the root layout switches to the app once a user is signed in
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
        contentStyle={{ gap: 20 }}
        footer={
          <>
            <Button label="Create account" onPress={submit} loading={busy} disabled={touched && !canSubmit} />
            <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 4 }}>
              <Text style={[type.body, { color: colors.ink2 }]}>Already have an account?</Text>
              <TextLink onPress={() => router.replace('/log-in')}>Log in</TextLink>
            </View>
          </>
        }>
        <Image source={require('@/assets/images/photos/hero-cream-tan.jpg')} style={{ height: 120, borderRadius: 22 }} contentFit="cover" />
        <Heading title="Create your account" subtitle="Save your skin checks, routines and daily log." />
        <View style={{ gap: 16 }}>
          <Field label="Full name" value={name} onChangeText={setName} autoComplete="name" textContentType="name" placeholder="Your name" error={touched && !name.trim() ? 'Please enter your name.' : null} />
          <Field
            label="Email"
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            autoComplete="email"
            keyboardType="email-address"
            textContentType="emailAddress"
            placeholder="name@email.com"
            error={touched && !isEmail(email) ? 'Please enter a valid email address.' : null}
          />
          <View style={{ gap: 8 }}>
            <Field
              label="Password"
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              autoComplete="new-password"
              textContentType="newPassword"
              placeholder="At least 12 characters"
            />
            <View style={{ flexDirection: 'row', gap: 4 }}>
              {[1, 2, 3, 4].map((i) => (
                <View key={i} style={{ flex: 1, height: 4, borderRadius: 2, backgroundColor: strength.score >= i ? meterColor : colors.line }} />
              ))}
            </View>
            <Text style={[type.caption, { color: password ? meterColor : colors.ink2 }]}>{strength.message}</Text>
          </View>
        </View>
        <View style={{ gap: 14 }}>
          <Checkbox checked={terms} onChange={setTerms} label={`I agree to the Terms of Use and Privacy Policy (v${POLICY_VERSION}).`} />
          {touched && !terms ? <Text style={[type.caption, { color: colors.flag }]}>Please accept the terms to continue.</Text> : null}
          <Checkbox checked={news} onChange={setNews} label="Email me product news. Optional." />
        </View>
        {error ? (
          <Callout icon="alert" tone="flag">
            {error}
          </Callout>
        ) : null}
        <Text style={type.caption}>We ask for photo and skin-data consent separately, the first time you run a skin check.</Text>
      </Screen>
    </KeyboardAvoidingView>
  );
}
