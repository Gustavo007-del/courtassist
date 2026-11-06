import { useState } from 'react';
import { Alert } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Pagination } from '../../components/ai/Controls';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { Screen } from '../../components/layout/Screen';
import { aiApi, isWorking } from '../../services/ai-api';

export default function AIConversation() {
  const { t } = useTranslation();
  const { id } = useLocalSearchParams<{ id: string }>();
  const cache = useQueryClient();
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState(false);
  const query = useQuery({
    queryKey: ['ai', 'conversation', id, offset], queryFn: () => aiApi.conversation(id, offset),
    refetchInterval: query => query.state.data?.items.some(isWorking) ? 4000 : false,
  });
  return <Screen back title={t('ai.conversation')} subtitle={t('ai.disclaimer')}>
    {error && <AppText>{t('work.error')}</AppText>}
    {query.isPending ? <LoadingSkeleton /> : query.isError
      ? <ErrorState message={t('work.error')} retry={() => void query.refetch()} />
      : <>
        <Button label={t('ai.followUp')} onPress={() => router.push({
          pathname: '/ai/request', params: { mode: 'ask', conversationId: id,
            previousJobId: query.data.items[0]?.question ? query.data.items[0].id : '',
            caseId: query.data.items[0]?.case_id ?? '' },
        })} />
        {!query.data.items.length && <AppText>{t('ai.emptyHistory')}</AppText>}
        {query.data.items.map(job => <Card key={job.id}>
          {job.question && <AppText>{job.question}</AppText>}
          <AppText>{t(`ai.status.${job.status}`)}</AppText>
          {job.result?.items?.slice(0, 2).map((item, index) => <AppText key={index}>{item.quote}</AppText>)}
          <Button label={t('ai.openJob')} variant="secondary" onPress={() => router.push({ pathname: '/ai/job', params: { id: job.id } })} />
        </Card>)}
        <Pagination offset={offset} hasMore={offset + 20 < query.data.total} setOffset={setOffset} />
        <Button label={t('ai.deleteConversation')} variant="text" onPress={() => Alert.alert(
          t('ai.deleteConversation'), t('ai.deleteExplanation'), [
            { text: t('cancel'), style: 'cancel' },
            { text: t('ai.delete'), style: 'destructive', onPress: () => {
              void aiApi.removeConversation(id).then(() => {
                cache.removeQueries({ queryKey: ['ai', 'conversation', id] });
                void cache.invalidateQueries({ queryKey: ['ai'] });
                router.back();
              }).catch(() => setError(true));
            } },
          ],
        )} />
      </>}
  </Screen>;
}

