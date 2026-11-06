import { useState } from 'react';
import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { Button } from '../../components/common/Button';
import { TextField } from '../../components/common/TextField';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { draftingApi } from '../../services/drafting-api';
export default function Drafting() {
  const { t } = useTranslation();
  const [search, setSearch] = useState('');
  const [archived, setArchived] = useState(false);
  const [offset, setOffset] = useState(0);
  const q = useQuery({
    queryKey: ['drafts', search, archived, offset],
    queryFn: () =>
      draftingApi.list({ q: search, archived: String(archived), offset: String(offset), limit: '30' }),
  });
  return (
    <Screen title={t('work.drafting')} back onRefresh={() => void q.refetch()} refreshing={q.isRefetching}>
      <Button label={t('work.newDraft')} onPress={() => router.push('/drafting/create')} />
      <Button
        label={t('work.templates')}
        variant="secondary"
        onPress={() => router.push({ pathname: '/drafting/library', params: { kind: 'draft-templates' } })}
      />
      <Button
        label={t('work.clauses')}
        variant="secondary"
        onPress={() => router.push({ pathname: '/drafting/library', params: { kind: 'draft-clauses' } })}
      />
      <TextField
        label={t('work.search')}
        value={search}
        onChangeText={(value) => {
          setSearch(value);
          setOffset(0);
        }}
      />
      <Button
        label={archived ? t('work.drafts') : t('work.archived')}
        variant="secondary"
        onPress={() => {
          setArchived(!archived);
          setOffset(0);
        }}
      />
      {q.isPending ? (
        <LoadingSkeleton />
      ) : q.isError ? (
        <ErrorState message={t('work.error')} retry={() => void q.refetch()} />
      ) : q.data.length ? (
        q.data.map((row) => (
          <Button
            key={row.id}
            variant="secondary"
            label={row.title + ' · ' + t(`work.${row.status}`, row.status)}
            onPress={() => router.push({ pathname: '/practice-tools/draft-editor', params: { id: row.id } })}
          />
        ))
      ) : (
        <EmptyState title={t('work.empty')} body={t('work.emptyBody')} />
      )}{' '}
      {offset > 0 && <Button label="←" variant="secondary" onPress={() => setOffset(offset - 30)} />}{' '}
      {q.data?.length === 30 && (
        <Button label="→" variant="secondary" onPress={() => setOffset(offset + 30)} />
      )}
    </Screen>
  );
}
