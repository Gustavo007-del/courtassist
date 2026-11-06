import { Redirect, useLocalSearchParams, router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { Button } from '../../components/common/Button';
import { researchApi } from '../../services/research-api';
import { useState } from 'react';
import { TextField } from '../../components/common/TextField';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { ErrorState } from '../../components/common/ErrorState';
import { EmptyState } from '../../components/common/EmptyState';
export default function Upload() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const { t } = useTranslation();
  const [search, setSearch] = useState('');
  const items = useQuery({
    queryKey: ['research-upload-options', search],
    queryFn: () => researchApi.list({ q: search }),
    enabled: !id,
  });
  if (id) return <Redirect href={{ pathname: '/documents/upload', params: { researchId: id } }} />;
  return (
    <Screen title={t('research.upload')} subtitle={t('research.selectForUpload')} back>
      <TextField label={t('work.search')} value={search} onChangeText={setSearch} />
      {items.isPending ? (
        <LoadingSkeleton />
      ) : items.isError ? (
        <ErrorState message={t('work.error')} retry={() => void items.refetch()} />
      ) : !items.data?.items.length ? (
        <EmptyState title={t('work.empty')} body={t('research.empty')} />
      ) : null}
      {items.data?.items.map((item) => (
        <Button
          key={item.id}
          label={item.title}
          onPress={() => router.replace({ pathname: '/documents/upload', params: { researchId: item.id } })}
        />
      ))}
      <Button label={t('research.add')} onPress={() => router.push('/research/create')} />
    </Screen>
  );
}
