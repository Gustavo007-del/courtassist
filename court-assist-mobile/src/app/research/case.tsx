import { useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { Button } from '../../components/common/Button';
import { TextField } from '../../components/common/TextField';
import { Notice } from '../../components/common/Notice';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { researchApi } from '../../services/research-api';
import { friendlyError } from '../../utils/errors';
export default function CaseResearch() {
  const { caseId } = useLocalSearchParams<{ caseId: string }>();
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');
  const q = useQuery({
    queryKey: ['case-research', caseId, offset],
    queryFn: () => researchApi.caseItems(caseId, offset),
  });
  const existing = useQuery({
    queryKey: ['research-link-options', search],
    queryFn: () => researchApi.list({ q: search }),
    enabled: !!search,
  });
  async function link(id: string) {
    try {
      await researchApi.link(caseId, id);
      void qc.invalidateQueries({ queryKey: ['case-research'] });
      void qc.invalidateQueries({ queryKey: ['research'] });
      setSearch('');
    } catch (e) {
      setError(friendlyError(e));
    }
  }
  return (
    <Screen title={t('research.linkedCases')} back>
      {error && <Notice message={error} />}
      <Button
        label={t('research.add')}
        onPress={() => router.push({ pathname: '/research/create', params: { caseId } })}
      />
      <Button
        label={t('research.notes')}
        variant="secondary"
        onPress={() => router.push({ pathname: '/research/notes', params: { caseId } })}
      />
      <TextField label={t('research.findToLink')} value={search} onChangeText={setSearch} />
      {search &&
        existing.data?.items.map((item) => (
          <Button
            key={item.id}
            label={t('research.linkCase') + ': ' + item.title}
            variant="secondary"
            onPress={() => void link(item.id)}
          />
        ))}
      {q.isPending ? (
        <LoadingSkeleton />
      ) : q.isError ? (
        <ErrorState message={t('work.error')} retry={() => void q.refetch()} />
      ) : q.data.items.length ? (
        q.data.items.map((item) => (
          <Button
            key={item.id}
            label={item.title}
            variant="secondary"
            onPress={() => router.push({ pathname: '/research/[id]', params: { id: item.id } })}
          />
        ))
      ) : (
        <EmptyState title={t('work.empty')} body={t('research.empty')} />
      )}{' '}
      {offset > 0 && <Button label="←" variant="secondary" onPress={() => setOffset(offset - 30)} />}{' '}
      {q.data && offset + 30 < q.data.total && (
        <Button label="→" variant="secondary" onPress={() => setOffset(offset + 30)} />
      )}
    </Screen>
  );
}
