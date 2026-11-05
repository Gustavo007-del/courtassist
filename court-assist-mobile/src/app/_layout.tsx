import { useEffect, useState } from 'react';
import { ActivityIndicator, AppState, View } from 'react-native';
import { Stack } from 'expo-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { loadLanguage } from '../i18n';
import { useAuthStore } from '../store/auth-store';
import { dark, useTheme } from '../theme/tokens';
import { Toast } from '../components/common/Toast';
import { BiometricGate } from '../components/common/BiometricGate';
import { useThemeStore } from '../store/theme-store';
import { useBiometricStore } from '../store/biometric-store';

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 60_000 } } });

export default function RootLayout() {
  const theme = useTheme();
  const hydrate = useAuthStore((state) => state.hydrate);
  const [ready, setReady] = useState(false);
  useEffect(() => { Promise.all([hydrate(), loadLanguage(), useThemeStore.getState().hydrate(), useBiometricStore.getState().hydrate()]).finally(() => setReady(true)); }, [hydrate]);
  useEffect(() => { const subscription = AppState.addEventListener('change', (state) => { if (state !== 'active') useBiometricStore.getState().lock(); }); return () => subscription.remove(); }, []);
  return <SafeAreaProvider><QueryClientProvider client={queryClient}><StatusBar style={theme === dark ? 'light' : 'dark'} />{ready ? <View style={{ flex: 1 }}><Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: theme.colors.background } }}><Stack.Screen name="index" /><Stack.Screen name="(auth)" /><Stack.Screen name="(tabs)" /><Stack.Screen name="settings" /><Stack.Screen name="profile" /><Stack.Screen name="clients" /><Stack.Screen name="courts" /><Stack.Screen name="cases" /><Stack.Screen name="hearings" /><Stack.Screen name="reset-password" /></Stack><Toast /><BiometricGate /></View> : <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: theme.colors.background }}><ActivityIndicator color={theme.colors.accent} size="large" /></View>}</QueryClientProvider></SafeAreaProvider>;
}
