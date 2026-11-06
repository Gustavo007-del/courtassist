import { Redirect, Stack } from 'expo-router';
import { useAuthStore } from '../../store/auth-store';

export default function AILayout() {
  const user = useAuthStore(state => state.user);
  return user ? <Stack screenOptions={{ headerShown: false }} /> : <Redirect href="/(auth)/login" />;
}

