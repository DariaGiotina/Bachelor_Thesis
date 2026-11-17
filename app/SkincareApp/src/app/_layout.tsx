import { HankenGrotesk_400Regular, HankenGrotesk_500Medium, HankenGrotesk_600SemiBold } from '@expo-google-fonts/hanken-grotesk';
import { YoungSerif_400Regular } from '@expo-google-fonts/young-serif';
import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { AuthProvider, useAuth } from '@/lib/auth';
import { SkinCheckProvider } from '@/lib/skin-check';
import { colors } from '@/lib/theme';

SplashScreen.preventAutoHideAsync();

function RootNavigator() {
  const { ready, user } = useAuth();
  const [fontsLoaded] = useFonts({ YoungSerif_400Regular, HankenGrotesk_400Regular, HankenGrotesk_500Medium, HankenGrotesk_600SemiBold });

  useEffect(() => {
    if (ready && fontsLoaded) SplashScreen.hideAsync();
  }, [ready, fontsLoaded]);

  if (!ready || !fontsLoaded) return null;

  return (
    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.canvas } }}>
      <Stack.Screen name="index" />
      <Stack.Protected guard={!!user}>
        <Stack.Screen name="(app)" />
      </Stack.Protected>
      <Stack.Protected guard={!user}>
        <Stack.Screen name="welcome" />
        <Stack.Screen name="sign-up" />
        <Stack.Screen name="log-in" />
        <Stack.Screen name="reset-password" />
      </Stack.Protected>
    </Stack>
  );
}

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <SkinCheckProvider>
          <StatusBar style="dark" />
          <RootNavigator />
        </SkinCheckProvider>
      </AuthProvider>
    </SafeAreaProvider>
  );
}
