import { useEffect, useState } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { Stack, router } from 'expo-router';
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
import { SyncLifecycle } from '../components/SyncLifecycle';
import { NotificationLifecycle } from '../components/NotificationLifecycle';

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 60_000, networkMode: 'always' }, mutations: { networkMode: 'always' } } });
const privateRoutes = ['(tabs)', 'settings', 'profile', 'clients', 'courts', 'cases', 'hearings', 'diary',
  'scanner', 'documents', 'tasks', 'appointments', 'notifications', 'ai', 'sync', 'finance', 'drafting', 'research', 'practice-tools'];

export default function RootLayout() {
  const theme = useTheme();
  const hydrate = useAuthStore((state) => state.hydrate);
  const signedIn = useAuthStore(state => !!state.user);
  const [ready, setReady] = useState(false);
  useEffect(() => useAuthStore.subscribe((state, previous) => {
    if (state.user?.id !== previous.user?.id) { void queryClient.cancelQueries(); queryClient.clear(); if (!state.user && previous.user) router.replace('/(auth)/login'); }
  }), []);
  useEffect(() => { Promise.all([hydrate(), loadLanguage(), useThemeStore.getState().hydrate(), useBiometricStore.getState().hydrate()]).finally(() => setReady(true)); }, [hydrate]);
  return <SafeAreaProvider><QueryClientProvider client={queryClient}><StatusBar style={theme === dark ? 'light' : 'dark'} />{ready ? <View style={{ flex: 1 }}>
    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: theme.colors.background } }}>
      <Stack.Screen name="index" />
      <Stack.Screen name="(auth)" />
      <Stack.Screen name="reset-password" />
      <Stack.Protected guard={signedIn}>
        {privateRoutes.map(name => <Stack.Screen key={name} name={name} />)}
      </Stack.Protected>
    </Stack>
    <NotificationLifecycle /><SyncLifecycle /><Toast /><BiometricGate />
  </View> : <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: theme.colors.background }}><ActivityIndicator color={theme.colors.accent} size="large" /></View>}</QueryClientProvider></SafeAreaProvider>;
}
