import { useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { Button } from '../../components/common/Button';
import { TextField } from '../../components/common/TextField';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { financeApi, type FinanceKind } from '../../services/finance-api';
export default function Records() {
  const {
    kind = 'payments',
    clientId,
    caseId,
  } = useLocalSearchParams<{ kind: FinanceKind; clientId?: string; caseId?: string }>();
  const { t } = useTranslation();
  const [search, setSearch] = useState('');
  const [offset, setOffset] = useState(0);
  const q = useQuery({
    queryKey: ['finance', kind, search, offset, clientId, caseId],
    queryFn: () =>
      financeApi.list(kind, {
        q: search,
        offset: String(offset),
        limit: '30',
        client_id: clientId ?? '',
        case_id: caseId ?? '',
      }),
  });
  const items = q.data?.filter(
    (row) =>
      (!clientId || row.client_id === clientId) &&
      (!caseId || row.case_id === caseId) &&
      `${row.number ?? ''} ${row.description ?? ''} ${row.status ?? ''} ${row.reference ?? ''}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  return (
    <Screen
      title={t(`work.${kind === 'fee-agreements' ? 'agreements' : kind}`)}
      back
      onRefresh={() => void q.refetch()}
      refreshing={q.isRefetching}
    >
      <Button
        label={t('work.add')}
        onPress={() =>
          router.push({
            pathname: '/finance/form',
            params: { kind, clientId: clientId ?? '', caseId: caseId ?? '' },
          })
        }
      />
      <TextField
        label={t('work.search')}
        value={search}
        onChangeText={(value) => {
          setSearch(value);
          setOffset(0);
        }}
      />
      {q.isPending ? (
        <LoadingSkeleton />
      ) : q.isError ? (
        <ErrorState message={t('work.error')} retry={() => void q.refetch()} />
      ) : items?.length ? (
        items.map((row) => (
          <Button
            key={row.id}
            variant="secondary"
            label={`${row.number || row.description || row.reference || row.id.slice(0, 8)} · ₹${row.amount ?? row.total ?? '0.00'} · ${row.status ?? ''}`}
            onPress={() => router.push({ pathname: '/finance/detail', params: { kind, id: row.id } })}
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
