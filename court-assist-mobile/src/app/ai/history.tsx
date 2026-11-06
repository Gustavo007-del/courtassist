import { useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Pagination } from '../../components/ai/Controls';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { Screen } from '../../components/layout/Screen';
import { aiApi, isWorking } from '../../services/ai-api';

export default function AIHistory() {
  const { t } = useTranslation();
  const { mode, documentId } = useLocalSearchParams<{ mode?: 'usage' | 'conversations'; documentId?: string }>();
  const [offset, setOffset] = useState(0);
  const usage = mode === 'usage';
  const conversations = mode === 'conversations';
  const jobs = useQuery({
    queryKey: ['ai', 'history', mode, documentId, offset],
    queryFn: () => usage ? aiApi.usage(offset) : documentId ? aiApi.documentJobs(documentId, offset) : aiApi.jobs(offset),
    enabled: !conversations,
    refetchInterval: query => !usage && query.state.data?.items.some(isWorking) ? 4000 : false,
  });
  const chats = useQuery({
    queryKey: ['ai', 'conversations', offset], queryFn: () => aiApi.conversations(offset), enabled: conversations,
  });
  const totals = useQuery({ queryKey: ['ai', 'usage-summary'], queryFn: aiApi.usageSummary, enabled: usage });
  return <Screen back title={t(conversations ? 'ai.conversations' : usage ? 'ai.usage' : documentId ? 'ai.documentResults' : 'ai.jobs')}>
    {usage && (totals.isPending ? <LoadingSkeleton rows={2} /> : totals.isError
      ? <ErrorState message={t('work.error')} retry={() => void totals.refetch()} />
      : <Card>
        <AppText>{t('ai.dailyRequests', { used: totals.data.requests, limit: totals.data.daily_limit })}</AppText>
        <AppText>{t('ai.tokens', { input: totals.data.input_tokens ?? '—', output: totals.data.output_tokens ?? '—' })}</AppText>
        {totals.data.estimated_cost != null && <AppText>{t('ai.estimatedCost', { cost: totals.data.estimated_cost })}</AppText>}
      </Card>)}
    {conversations ? chats.isPending ? <LoadingSkeleton /> : chats.isError
      ? <ErrorState message={t('work.error')} retry={() => void chats.refetch()} />
      : <>
        {!chats.data.items.length && <AppText>{t('ai.emptyHistory')}</AppText>}
        {chats.data.items.map(chat => <Button key={chat.id} variant="secondary" label={new Date(chat.created_at).toLocaleString()}
          onPress={() => router.push({ pathname: '/ai/conversation', params: { id: chat.id } })} />)}
        <Pagination offset={offset} hasMore={chats.data.items.length === 20} setOffset={setOffset} />
      </>
      : jobs.isPending ? <LoadingSkeleton /> : jobs.isError
        ? <ErrorState message={t('work.error')} retry={() => void jobs.refetch()} />
        : <>
          {!jobs.data.items.length && <AppText>{t('ai.emptyHistory')}</AppText>}
          {jobs.data.items.map(job => <Card key={job.id}>
            <AppText>{t(`ai.kinds.${job.kind}`)} · {t(`ai.status.${job.status}`)}</AppText>
            <AppText>{new Date(job.created_at).toLocaleString()}</AppText>
            {usage ? <AppText>{t('ai.tokens', { input: job.input_tokens ?? '—', output: job.output_tokens ?? '—' })}</AppText>
              : <Button label={t('ai.openJob')} variant="secondary" onPress={() => router.push({ pathname: '/ai/job', params: { id: job.id } })} />}
          </Card>)}
          <Pagination offset={offset} hasMore={offset + 20 < jobs.data.total} setOffset={setOffset} />
        </>}
  </Screen>;
}

