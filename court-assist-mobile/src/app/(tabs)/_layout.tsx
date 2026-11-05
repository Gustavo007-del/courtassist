import { Redirect, Tabs } from 'expo-router';
import { House, BriefcaseBusiness, CalendarDays, ScanLine, UserRound } from 'lucide-react-native';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '../../store/auth-store';
import { useTheme } from '../../theme/tokens';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

export default function TabLayout() {
  const user = useAuthStore((state) => state.user);
  const theme = useTheme(); const { t } = useTranslation();
  const insets = useSafeAreaInsets();
  if (!user) return <Redirect href="/(auth)/login" />;
  return <Tabs screenOptions={{ headerShown: false, tabBarActiveTintColor: theme.colors.navy, tabBarInactiveTintColor: theme.colors.muted, tabBarStyle: { backgroundColor: theme.colors.surface, borderTopColor: theme.colors.border, height: 58 + insets.bottom, paddingTop: 6, paddingBottom: Math.max(8, insets.bottom) }, tabBarLabelStyle: { fontSize: 11, fontWeight: '600' } }}>
    <Tabs.Screen name="index" options={{ title: t('tabs.home'), tabBarIcon: ({ color, size }) => <House color={color} size={size} /> }} />
    <Tabs.Screen name="cases" options={{ title: t('tabs.cases'), tabBarIcon: ({ color, size }) => <BriefcaseBusiness color={color} size={size} /> }} />
    <Tabs.Screen name="calendar" options={{ title: t('tabs.calendar'), tabBarIcon: ({ color, size }) => <CalendarDays color={color} size={size} /> }} />
    <Tabs.Screen name="scanner" options={{ title: t('tabs.scanner'), tabBarIcon: ({ color, size }) => <ScanLine color={color} size={size} /> }} />
    <Tabs.Screen name="profile" options={{ title: t('tabs.profile'), tabBarIcon: ({ color, size }) => <UserRound color={color} size={size} /> }} />
  </Tabs>;
}
