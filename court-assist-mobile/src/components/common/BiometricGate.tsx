import { useState } from 'react';
import { View } from 'react-native';
import { Fingerprint } from 'lucide-react-native';
import { useTranslation } from 'react-i18next';
import { useBiometricStore } from '../../store/biometric-store';
import { useAuthStore } from '../../store/auth-store';
import { useTheme } from '../../theme/tokens';
import { AppText } from './AppText';
import { Button } from './Button';

export function BiometricGate() {
  const user = useAuthStore((state) => state.user);
  const locked = useBiometricStore((state) => state.locked);
  const theme = useTheme(); const { t } = useTranslation(); const [busy, setBusy] = useState(false);
  if (!user || !locked) return null;
  return <View style={{ position: 'absolute', inset: 0, zIndex: 100, backgroundColor: theme.colors.background, justifyContent: 'center', alignItems: 'center', padding: 32, gap: 16 }}>
    <Fingerprint size={58} color={theme.colors.accent} /><AppText style={{ fontSize: 24, fontWeight: '800', textAlign: 'center' }}>{t('security.lockedTitle')}</AppText>
    <AppText style={{ color: theme.colors.muted, textAlign: 'center' }}>{t('security.lockedDetail')}</AppText>
    <View style={{ alignSelf: 'stretch', marginTop: 16 }}><Button label={t('security.unlock')} loading={busy} onPress={async () => { setBusy(true); try { await useBiometricStore.getState().unlock(); } finally { setBusy(false); } }} /></View>
  </View>;
}
