import { Redirect, Stack } from 'expo-router';
import { useAuthStore } from '../../store/auth-store';

export default function SyncLayout() {
  const owner = useAuthStore(state => state.user?.id);
  return owner ? <Stack screenOptions={{ headerShown: false }} /> : <Redirect href="/(auth)/login" />;
}

