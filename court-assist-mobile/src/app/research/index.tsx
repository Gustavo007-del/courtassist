import { useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { Button } from '../../components/common/Button';
import { TextField } from '../../components/common/TextField';
import { AppText } from '../../components/common/AppText';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { researchApi } from '../../services/research-api';
export default function Research() {
  const params = useLocalSearchParams<Record<string, string>>();
  const { t } = useTranslation();
  const [q, setQ] = useState(params.q ?? '');
  const [offset, setOffset] = useState(0);
  const [favorite, setFavorite] = useState(false);
  const [archived, setArchived] = useState(false);
  const filters = {
    ...params,
    q,
    offset: String(offset),
    limit: '30',
    favorite: favorite ? 'true' : '',
    archived: String(archived),
  };
  const query = useQuery({ queryKey: ['research', filters], queryFn: () => researchApi.list(filters) });
  return (
    <Screen
      title={t('research.library')}
      subtitle={t('research.disclaimer')}
      back
      onRefresh={() => void query.refetch()}
      refreshing={query.isRefetching}
    >
      <Button label={t('research.add')} onPress={() => router.push('/research/create')} />
      <Button
        label={t('research.notes')}
        variant="secondary"
        onPress={() => router.push('/research/notes')}
      />
      <Button label={t('research.tags')} variant="secondary" onPress={() => router.push('/research/tags')} />
      <Button
        label={t('research.import')}
        variant="secondary"
        onPress={() => router.push('/research/import')}
      />
      <TextField
        label={t('work.search')}
        value={q}
        onChangeText={(value) => {
          setQ(value);
          setOffset(0);
        }}
      />
      <Button
        label={t('research.filters')}
        variant="secondary"
        onPress={() => router.push({ pathname: '/research/filters', params: { ...params, q } })}
      />
      <Button
        label={(favorite ? '★ ' : '☆ ') + t('research.favorites')}
        variant="secondary"
        onPress={() => {
          setFavorite(!favorite);
          setOffset(0);
        }}
      />
      <Button
        label={archived ? t('research.library') : t('work.archived')}
        variant="secondary"
        onPress={() => {
          setArchived(!archived);
          setOffset(0);
        }}
      />
      {query.isPending ? (
        <LoadingSkeleton />
      ) : query.isError ? (
        <ErrorState message={t('work.error')} retry={() => void query.refetch()} />
      ) : query.data.items.length ? (
        <>
          <AppText>{query.data.total}</AppText>
          {query.data.items.map((item) => (
            <Button
              key={item.id}
              variant="secondary"
              label={`${item.favorite ? '★ ' : ''}${item.title}\n${t(`research.types.${item.item_type}`, item.item_type)} · ${item.citation || t('research.noCitation')}`}
              onPress={() => router.push({ pathname: '/research/[id]', params: { id: item.id } })}
            />
          ))}
        </>
      ) : (
        <EmptyState title={t('work.empty')} body={t('research.empty')} />
      )}{' '}
      {offset > 0 && <Button label="←" variant="secondary" onPress={() => setOffset(offset - 30)} />}{' '}
      {query.data && offset + 30 < query.data.total && (
        <Button label="→" variant="secondary" onPress={() => setOffset(offset + 30)} />
      )}
    </Screen>
  );
}
