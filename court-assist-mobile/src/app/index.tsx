import { useEffect, useState } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { router } from 'expo-router';
import { Scale } from 'lucide-react-native';
import { useTranslation } from 'react-i18next';
import * as Network from 'expo-network';
import { ensureSession } from '../services/api';
import { AppText } from '../components/common/AppText';
import { useAuthStore } from '../store/auth-store';
import { setLanguage } from '../i18n';
import { useThemeStore } from '../store/theme-store';

export default function Splash() {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  useEffect(() => { let active = true; (async () => {
    const network = await Network.getNetworkStateAsync().catch(() => null);
    return (network?.isConnected !== false && await ensureSession()) || await useAuthStore.getState().restoreOffline();
  })().then(async (valid) => { if (!active) return; const user = useAuthStore.getState().user; if (valid && user) { await setLanguage(user.preferred_language).catch(() => {}); if (user.preferences) await useThemeStore.getState().setMode(user.preferences.theme).catch(() => {}); } router.replace(valid ? '/(tabs)' : '/(auth)/login'); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, []);
  return <View style={{ flex: 1, backgroundColor: '#12263A', justifyContent: 'center', alignItems: 'center', padding: 24 }}><Scale size={52} color="#C7AA76" /><AppText style={{ color: '#FFFFFF', fontWeight: '800', fontSize: 30, marginTop: 24 }}>{t('appName')}</AppText><AppText style={{ color: '#C7AA76', marginTop: 8 }}>{t('tagline')}</AppText>{loading && <ActivityIndicator style={{ marginTop: 48 }} color="#C7AA76" accessibilityLabel={t('loading')} />}</View>;
}
