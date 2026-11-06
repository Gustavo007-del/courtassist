import { useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { TextField } from '../../components/common/TextField';
import { Button } from '../../components/common/Button';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { draftingApi, type LibraryKind } from '../../services/drafting-api';
export default function Library() {
  const { kind = 'draft-templates' } = useLocalSearchParams<{ kind: LibraryKind }>();
  const { t } = useTranslation();
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [offset, setOffset] = useState(0);
  const q = useQuery({
    queryKey: ['draft-library', kind, search, category, offset],
    queryFn: () => draftingApi.library(kind, search, offset, category),
  });
  return (
    <Screen
      title={t(kind === 'draft-templates' ? 'work.templates' : 'work.clauses')}
      back
      onRefresh={() => void q.refetch()}
      refreshing={q.isRefetching}
    >
      <Button
        label={t('work.new')}
        onPress={() => router.push({ pathname: '/drafting/library-editor', params: { kind } })}
      />
      <TextField
        label={t('work.search')}
        value={search}
        onChangeText={(value) => {
          setSearch(value);
          setOffset(0);
        }}
      />
      <TextField
        label={t('work.category')}
        value={category}
        onChangeText={(value) => {
          setCategory(value);
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
            label={`${row.name ?? row.title} · ${row.category} · ${t(row.built_in ? 'work.builtIn' : 'work.private')}`}
            onPress={() =>
              router.push({ pathname: '/drafting/library-editor', params: { kind, id: row.id } })
            }
          />
        ))
      ) : (
        <EmptyState title={t('work.empty')} body={t('work.emptyBody')} />
      )}
      {offset > 0 && <Button label="←" variant="secondary" onPress={() => setOffset(offset - 30)} />}{' '}
      {q.data?.length === 30 && (
        <Button label="→" variant="secondary" onPress={() => setOffset(offset + 30)} />
      )}
    </Screen>
  );
}
