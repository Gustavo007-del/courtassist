import { useState } from 'react';
import { Alert, Switch, View } from 'react-native';
import { router } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { Card } from '../../components/common/Card';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { Notice } from '../../components/common/Notice';
import { SectionHeader } from '../../components/common/SectionHeader';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { ErrorState } from '../../components/common/ErrorState';
import { TextField } from '../../components/common/TextField';
import { authApi } from '../../features/auth/services/auth-api';
import { useAuthStore } from '../../store/auth-store';
import { useBiometricStore } from '../../store/biometric-store';
import { useTheme } from '../../theme/tokens';
import { friendlyError } from '../../utils/errors';

export default function SecuritySettings() {
  const { t } = useTranslation(); const theme = useTheme(); const client = useQueryClient();
  const enabled = useBiometricStore((state) => state.enabled);
  const user = useAuthStore((state) => state.user);
  const refreshToken = useAuthStore((state) => state.refreshToken);
  const [busy, setBusy] = useState(false); const [toggleError, setToggleError] = useState<string | null>(null);
  const [erasing, setErasing] = useState(false);
  const [password, setPassword] = useState('');
  const { data, isPending, isError, error, refetch } = useQuery({ queryKey: ['sessions', user?.id], queryFn: authApi.sessions, enabled: !!user });
  const devices = useQuery({ queryKey: ['active-sessions', user?.id], queryFn: authApi.activeSessions, enabled: !!user });
  const toggle = async (value: boolean) => {
    setBusy(true); setToggleError(null);
    try { if (value) { const success = await useBiometricStore.getState().enable(); if (!success) setToggleError(t('security.biometricUnavailable')); } else await useBiometricStore.getState().disable(); }
    catch (caught) { setToggleError(friendlyError(caught)); } finally { setBusy(false); }
  };
  const signOut = () => Alert.alert(t('auth.signOut'), t('sync.signOutConfirm'), [
    { text: t('cancel'), style: 'cancel' },
    { text: t('auth.signOut'), style: 'destructive', onPress: async () => { try { if (refreshToken) await authApi.logout(refreshToken).catch(() => {}); } finally { await useAuthStore.getState().clear(); client.clear(); router.replace('/(auth)/login'); } } },
  ]);
  const revoke = (id: string) => Alert.alert(t('security.revokeSession'), t('security.revokeExplanation'), [
    { text: t('cancel'), style: 'cancel' },
    { text: t('security.revokeSession'), style: 'destructive', onPress: () => void authApi.revokeSession(id)
      .then(() => Promise.all([devices.refetch(), refetch()])).catch(caught => setToggleError(friendlyError(caught))) },
  ]);
  const erase = async () => {
    setBusy(true);
    setToggleError(null);
    try {
      const receipt = await authApi.requestErasure(password);
      setPassword('');
      Alert.alert(t('security.erasureRequested'), t('security.erasureReceipt', { id: receipt.id }));
      await useAuthStore.getState().clear();
    } catch (caught) { setToggleError(friendlyError(caught)); }
    finally { setBusy(false); }
  };
  return <Screen title={t('settings2.security')}>
    {toggleError && <Notice message={toggleError} />}
    <Card><View style={{ flexDirection: 'row', gap: 12, alignItems: 'center' }}><View style={{ flex: 1 }}><AppText style={{ fontWeight: '700' }}>{t('security.biometricLock')}</AppText><AppText style={{ color: theme.colors.muted, fontSize: 13 }}>{t('security.biometricDetail')}</AppText></View><Switch value={enabled} disabled={busy} onValueChange={(value) => { void toggle(value); }} trackColor={{ true: theme.colors.accent }} /></View></Card>
    <SectionHeader title={t('security.session')} />
    {isPending ? <LoadingSkeleton rows={1} /> : isError ? <ErrorState message={friendlyError(error)} retry={() => { void refetch(); }} /> : data && <Card><AppText>{t('security.activeSessions')}: {data.active_sessions}</AppText><AppText style={{ color: theme.colors.muted, marginTop: 8 }}>{t('security.lastLogin')}: {data.last_login_at ? new Date(data.last_login_at).toLocaleString() : t('security.unknown')}</AppText></Card>}
    {devices.data?.map(device => <Card key={device.id}>
      <AppText>{device.current ? t('security.currentSession') : t('security.otherSession')}</AppText>
      <AppText>{new Date(device.refreshed_at).toLocaleString()}</AppText>
      {!device.current && <Button label={t('security.revokeSession')} variant="text" onPress={() => revoke(device.id)} />}
    </Card>)}
    <View style={{ gap: 10, marginTop: 24 }}><Button label={t('security.changePassword')} variant="secondary" onPress={() => router.push('/settings/change-password')} /><Button label={t('auth.signOut')} variant="text" onPress={signOut} /></View>
    {!erasing ? <Button label={t('security.eraseAccount')} variant="text" onPress={() => setErasing(true)} /> : <Card>
      <AppText>{t('security.erasureExplanation')}</AppText>
      <TextField label={t('security.currentPassword')} value={password} onChangeText={setPassword} password />
      <Button label={t('security.eraseAccount')} loading={busy} disabled={!password || busy} onPress={() => void erase()} />
      <Button label={t('cancel')} variant="text" onPress={() => { setPassword(''); setErasing(false); }} />
    </Card>}
  </Screen>;
}
