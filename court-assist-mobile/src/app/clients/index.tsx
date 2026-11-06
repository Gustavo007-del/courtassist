import { useMemo, useState } from 'react';
import { View } from 'react-native';
import { router } from 'expo-router';
import { useInfiniteQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Button } from '../../components/common/Button';
import { ChoiceChips } from '../../components/common/ChoiceChips';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { TextField } from '../../components/common/TextField';
import { ClientCard } from '../../components/clients/ClientCard';
import { ListScreen } from '../../components/layout/Screen';
import { clientApi } from '../../services/client-api';
import { friendlyError } from '../../utils/errors';

type TypeFilter = '' | 'individual' | 'organization';
export default function ClientList() {
  const { t } = useTranslation(); const [search, setSearch] = useState(''); const [type, setType] = useState<TypeFilter>(''); const [archived, setArchived] = useState(false); const [sort, setSort] = useState<'recent' | 'alphabetical'>('recent');
  const query = useInfiniteQuery({ queryKey: ['clients', search, type, archived, sort], initialPageParam: 0, queryFn: ({ pageParam }) => clientApi.list({ q: search.trim(), client_type: type, archived, sort, limit: 20, offset: pageParam }), getNextPageParam: (last) => last.offset + last.items.length < last.total ? last.offset + last.items.length : undefined });
  const clients = useMemo(() => query.data?.pages.flatMap((page) => page.items) ?? [], [query.data]);
  return <ListScreen
    title={t('clients.title')} back
    filters={<View style={{ gap: 10, marginBottom: 18 }}><Button label={t('clients.add')} onPress={() => router.push('/clients/add')} /><TextField label={t('clients.search')} value={search} onChangeText={setSearch} /><ChoiceChips value={type} onChange={setType} options={[{ value: '', label: t('clients.all') }, { value: 'individual', label: t('clients.individual') }, { value: 'organization', label: t('clients.organization') }]} /><ChoiceChips value={archived ? 'archived' : 'active'} onChange={(value) => setArchived(value === 'archived')} options={[{ value: 'active', label: t('clients.active') }, { value: 'archived', label: t('clients.archived') }]} /><ChoiceChips value={sort} onChange={setSort} options={[{ value: 'recent', label: t('clients.recent') }, { value: 'alphabetical', label: t('clients.alphabetical') }]} /></View>}
    data={query.isError ? [] : clients}
    renderItem={({ item: client }) => <ClientCard client={client} onPress={() => router.push({ pathname: '/clients/[id]', params: { id: client.id } })} />}
    refreshing={query.isRefetching && !query.isFetchingNextPage}
    onRefresh={() => void query.refetch()}
    ListEmptyComponent={query.isPending ? <LoadingSkeleton /> : query.isError
      ? <ErrorState message={friendlyError(query.error)} retry={() => void query.refetch()} />
      : <><EmptyState title={t('clients.empty')} body={t('clients.emptyDetail')} /><Button label={t('clients.add')} variant="secondary" onPress={() => router.push('/clients/add')} /></>}
    ListFooterComponent={query.hasNextPage ? <Button label={t('clients.loadMore')} variant="secondary" loading={query.isFetchingNextPage} onPress={() => void query.fetchNextPage()} /> : undefined}
  />;
}
