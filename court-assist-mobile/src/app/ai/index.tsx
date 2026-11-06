import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { Screen } from '../../components/layout/Screen';
import { aiApi } from '../../services/ai-api';

export default function AIHome() {
  const { t } = useTranslation();
  const prefs = useQuery({ queryKey: ['ai', 'preferences'], queryFn: aiApi.preferences });
  return <Screen back title={t('ai.title')} subtitle={t('ai.optional')}>
    <Card><AppText>{t('ai.disclaimer')}</AppText></Card>
    <Button label={t('ai.preferences')} variant="secondary" onPress={() => router.push('/ai/preferences')} />
    {prefs.isPending ? <LoadingSkeleton /> : prefs.isError
      ? <ErrorState message={t('work.error')} retry={() => void prefs.refetch()} />
      : !prefs.data.available || !prefs.data.enabled
        ? <AppText>{t(prefs.data.available ? 'ai.disabled' : 'ai.unavailable')}</AppText>
        : (['ask', 'summarize', 'dates', 'metadata', 'chronology', 'draft', 'diary'] as const).map(mode =>
            <Button key={mode} label={t(`ai.kinds.${mode}`)} onPress={() => router.push({ pathname: '/ai/request', params: { mode } })} />)}
    <Button label={t('ai.conversations')} variant="secondary" onPress={() => router.push({ pathname: '/ai/history', params: { mode: 'conversations' } })} />
    <Button label={t('ai.jobs')} variant="secondary" onPress={() => router.push('/ai/history')} />
    <Button label={t('ai.usage')} variant="secondary" onPress={() => router.push({ pathname: '/ai/history', params: { mode: 'usage' } })} />
  </Screen>;
}

