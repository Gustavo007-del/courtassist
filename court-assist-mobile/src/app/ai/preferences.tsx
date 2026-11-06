import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { TextField } from '../../components/common/TextField';
import { Toggle } from '../../components/ai/Controls';
import { Screen } from '../../components/layout/Screen';
import { aiApi, aiErrorKey, type Preferences } from '../../services/ai-api';

const flags = ['enabled', 'documents', 'assistant', 'external'] as const;
type Choices = Pick<Preferences, typeof flags[number]>;

export default function AISettings() {
  const { t } = useTranslation();
  const cache = useQueryClient();
  const query = useQuery({ queryKey: ['ai', 'preferences'], queryFn: aiApi.preferences });
  const [changes, setChanges] = useState<Partial<Choices>>({});
  const [retention, setRetention] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const prefs = query.data;
  const save = async () => {
    if (!prefs) return;
    setBusy(true);
    setMessage('');
    try {
      const updated = await aiApi.savePreferences({
        ...changes,
        ...(changes.external ? { external_confirmation: prefs.external_confirmation } : {}),
        ...(retention === undefined ? {} : { retention_days: Number(retention) }),
      });
      cache.setQueryData(['ai', 'preferences'], updated);
      void cache.invalidateQueries({ queryKey: ['ai'] });
      setChanges({});
      setRetention(undefined);
      setMessage(t('ai.saved'));
    } catch (error) {
      setMessage(t(aiErrorKey(error), { defaultValue: t('work.error') }));
    } finally {
      setBusy(false);
    }
  };
  return <Screen back title={t('ai.preferences')} subtitle={t('ai.optional')}>
    {message && <AppText>{message}</AppText>}
    {query.isPending ? <LoadingSkeleton /> : query.isError || !prefs
      ? <ErrorState message={t('work.error')} retry={() => void query.refetch()} />
      : <Card>
        <AppText>{t('ai.disclaimer')}</AppText>
        <AppText>{prefs.available ? `${prefs.provider} · ${prefs.model}` : t('ai.unavailable')}</AppText>
        {flags.filter(key => key !== 'external' || prefs.external_provider || prefs.external).map(key =>
          <Toggle key={key} label={t(`ai.consent.${key}`)} value={changes[key] ?? prefs[key]}
            onChange={value => setChanges(current => ({ ...current, [key]: value }))} />)}
        {prefs.external_provider && <>
          <AppText>{t('ai.externalNotice', { provider: prefs.provider, model: prefs.model })}</AppText>
          <AppText>{prefs.provider_policy}</AppText>
        </>}
        <TextField label={t('ai.retentionDays')} keyboardType="numeric"
          value={retention ?? String(prefs.retention_days)} onChangeText={setRetention} />
        <AppText>{t('ai.retentionExplanation')}</AppText>
        <Button label={t('work.save')} loading={busy} onPress={() => void save()} />
      </Card>}
  </Screen>;
}

