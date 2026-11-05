import { useState } from 'react';
import { View } from 'react-native';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Notice } from '../../components/common/Notice';
import { authApi } from '../../features/auth/services/auth-api';
import { setLanguage, type Language } from '../../i18n';
import { useAuthStore } from '../../store/auth-store';
import { friendlyError } from '../../utils/errors';
import { useAppStore } from '../../store/app-store';

export default function LanguageSettings() {
  const { t, i18n } = useTranslation(); const client = useQueryClient(); const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null);
  const select = async (language: Language) => { setBusy(true); setError(null); try { const user = await authApi.updateMe({ preferred_language: language }); useAuthStore.setState({ user }); client.setQueryData(['me', user.id], user); await Promise.all([client.invalidateQueries({ queryKey: ['dashboard'] }), client.invalidateQueries({ queryKey: ['activities'] })]); await setLanguage(language); useAppStore.getState().showToast(i18n.t('settings.saved')); } catch (e) { setError(friendlyError(e)); } finally { setBusy(false); } };
  return <Screen title={t('settings.language')} subtitle={t('settings.languageDetail')}>{error && <Notice message={error} />}<Card><View style={{ gap: 12 }}><Button label={`${i18n.language === 'en' ? '✓  ' : ''}${t('settings.english')}`} variant="secondary" onPress={() => select('en')} disabled={busy} /><Button label={`${i18n.language === 'ml' ? '✓  ' : ''}${t('settings.malayalam')}`} variant="secondary" onPress={() => select('ml')} disabled={busy} /></View></Card></Screen>;
}
