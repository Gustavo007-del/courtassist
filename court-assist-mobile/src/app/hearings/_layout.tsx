import { Redirect, Stack } from 'expo-router';
import { useAuthStore } from '../../store/auth-store';
export default function HearingLayout() { const user = useAuthStore((state) => state.user); if (!user) return <Redirect href="/(auth)/login" />; return <Stack screenOptions={{ headerShown: false }} />; }
