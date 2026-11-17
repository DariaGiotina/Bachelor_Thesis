// 05 · Reset password
import { router } from 'expo-router';
import { useState } from 'react';
import { Text, View } from 'react-native';

import { Button, Callout, Field, Heading, IconTile, NavBar, Screen, Section, StepNumber } from '@/components/ui';
import { isEmail } from '@/lib/auth';
import { type } from '@/lib/theme';

const STEPS = [
  ['Open the link in your email', 'It works for 30 minutes.'],
  ['Choose a new password', 'At least 12 characters.'],
  ['Sign in again', 'Other devices are signed out, for your safety.'],
];

export default function ResetPassword() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);

  return (
    <Screen
      nav={<NavBar />}
      footer={
        <>
          <Button label="Send reset link" disabled={!isEmail(email)} onPress={() => setSent(true)} />
          <Button label="Back to log in" variant="ghost" onPress={() => router.back()} />
        </>
      }>
      <IconTile name="lock" tone="lilac" size={72} />
      <Heading title="Reset your password" subtitle="Enter the email you signed up with and we’ll send you a reset link." />
      <Field label="Email" value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" autoComplete="email" placeholder="name@email.com" />
      {sent ? (
        <Callout icon="info" tone="caution">
          Reset emails are sent by the Lumière server, which this test version does not use yet. Accounts are kept on this device only.
        </Callout>
      ) : null}
      <Section title="What happens next">
        {STEPS.map(([title, sub], i) => (
          <View key={title} style={{ flexDirection: 'row', gap: 12 }}>
            <StepNumber n={i + 1} />
            <View style={{ flex: 1, gap: 2 }}>
              <Text style={type.bodyStrong}>{title}</Text>
              <Text style={type.label}>{sub}</Text>
            </View>
          </View>
        ))}
      </Section>
    </Screen>
  );
}
