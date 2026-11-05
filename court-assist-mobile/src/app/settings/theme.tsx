import { useState } from 'react';
import { View } from 'react-native';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Notice } from '../../components/common/Notice';
import { preferencesApi } from '../../services/preferences-api';
import { useAuthStore } from '../../store/auth-store';
import { useThemeStore } from '../../store/theme-store';
import { useAppStore } from '../../store/app-store';
import { friendlyError } from '../../utils/errors';
import type { ThemeMode } from '../../features/auth/types';

export default function ThemeSettings() {
  const { t } = useTranslation(); const client = useQueryClient();
  const mode = useThemeStore((state) => state.mode);
  const user = useAuthStore((state) => state.user);
  const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null);
  const select = async (next: ThemeMode) => {
    if (busy || next === mode) return;
    setBusy(true); setError(null);
    try {
      const preferences = await preferencesApi.update({ theme: next });
      if (user) useAuthStore.setState({ user: { ...user, preferences } });
      client.setQueryData(['preferences', user?.id], preferences);
      await useThemeStore.getState().setMode(next);
      useAppStore.getState().showToast(t('settings2.saved'));
    } catch (caught) { setError(friendlyError(caught)); } finally { setBusy(false); }
  };
  return <Screen title={t('settings2.theme')} subtitle={t('settings2.themeDetail')}>{error && <Notice message={error} />}<Card><View style={{ gap: 10 }}>{(['light', 'dark', 'system'] as ThemeMode[]).map((choice) => <Button key={choice} label={`${mode === choice ? '✓  ' : ''}${t(`settings2.${choice}`)}`} variant="secondary" disabled={busy} onPress={() => { void select(choice); }} />)}</View></Card></Screen>;
}
