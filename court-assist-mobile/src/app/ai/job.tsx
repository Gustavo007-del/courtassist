import { useRef, useState } from 'react';
import { Alert } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { randomUUID } from 'expo-crypto';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { ExternalConsent } from '../../components/ai/Controls';
import { ResultReview } from '../../components/ai/ResultReview';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { Screen } from '../../components/layout/Screen';
import { aiApi, aiErrorKey, isWorking } from '../../services/ai-api';

export default function AIJobDetail() {
  const { t } = useTranslation();
  const { id } = useLocalSearchParams<{ id: string }>();
  const cache = useQueryClient();
  const [external, setExternal] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const retryId = useRef<string | null>(null);
  const query = useQuery({
    queryKey: ['ai', 'job', id], queryFn: () => aiApi.job(id),
    refetchInterval: query => query.state.data && isWorking(query.state.data) ? 3000 : false,
  });
  const job = query.data;
  const preferences = useQuery({ queryKey: ['ai', 'preferences'], queryFn: aiApi.preferences, enabled: !!job?.can_retry });
  const prefs = preferences.data;
  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError('');
    try { await action(); } catch (caught) {
      setError(t(aiErrorKey(caught), { defaultValue: t('work.error') }));
    } finally {
      setBusy(false);
    }
  };
  return <Screen back title={job ? t(`ai.kinds.${job.kind}`) : t('ai.openJob')} subtitle={t('ai.disclaimer')}
    onRefresh={() => void query.refetch()} refreshing={query.isRefetching}>
    {error && <AppText>{error}</AppText>}
    {query.isPending ? <LoadingSkeleton /> : query.isError || !job
      ? <ErrorState message={t('work.error')} retry={() => void query.refetch()} />
      : <>
        <Card>
          {job.question && <AppText>{job.question}</AppText>}
          <AppText>{t(`ai.status.${job.status}`)}</AppText>
          {job.error_code && <AppText>{t(`ai.errors.${job.error_code}`, { defaultValue: t('work.error') })}</AppText>}
          <AppText>{job.provider} · {job.model}</AppText>
          <AppText>{t('ai.tokens', { input: job.input_tokens ?? '—', output: job.output_tokens ?? '—' })}</AppText>
          <AppText>{t('ai.expires', { date: new Date(job.expires_at).toLocaleDateString() })}</AppText>
        </Card>
        {isWorking(job) && <Button label={t('ai.cancelJob')} loading={busy} variant="secondary" onPress={() => void run(async () => {
          await aiApi.cancel(id);
          await query.refetch();
        })} />}
        {job.can_retry && prefs && <>
          <ExternalConsent prefs={prefs} allowed={external} onChange={setExternal} />
          <Button label={t('ai.retryJob')} loading={busy} disabled={!prefs.enabled || !prefs.available || (prefs.external_provider && (!prefs.external || !external))}
            onPress={() => void run(async () => {
              retryId.current ??= randomUUID();
              const retry = await aiApi.retry(id, { request_id: retryId.current,
                external_confirmation: prefs.external_provider && external ? prefs.external_confirmation : undefined });
              router.replace({ pathname: '/ai/job', params: { id: retry.id } });
            })} />
        </>}
        {job.document_id && job.error_code === 'ocr_required' && <Button label={t('ai.openOCR')} variant="secondary" onPress={() =>
          router.push({ pathname: '/documents/ocr', params: { id: job.document_id! } })} />}
        {job.result && <ResultReview key={job.id} job={job} refresh={() => void query.refetch()} />}
        {job.conversation_id && <Button label={t('ai.conversation')} variant="secondary" onPress={() =>
          router.push({ pathname: '/ai/conversation', params: { id: job.conversation_id! } })} />}
        <Button label={t('ai.delete')} variant="text" loading={busy} onPress={() => Alert.alert(
          t('ai.delete'), t('ai.deleteExplanation'), [
            { text: t('cancel'), style: 'cancel' },
            { text: t('ai.delete'), style: 'destructive', onPress: () => void run(async () => {
              await aiApi.remove(id);
              cache.removeQueries({ queryKey: ['ai', 'job', id] });
              void cache.invalidateQueries({ queryKey: ['ai'] });
              router.back();
            }) },
          ],
        )} />
      </>}
  </Screen>;
}

