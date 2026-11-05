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
import { CourtCard } from '../../components/courts/CourtCard';
import { Screen } from '../../components/layout/Screen';
import { COURT_TYPES, KERALA_DISTRICTS } from '../../constants/courts';
import { courtApi } from '../../services/court-api';
import { friendlyError } from '../../utils/errors';

export default function CourtList() {
  const { t } = useTranslation(); const [search, setSearch] = useState(''); const [type, setType] = useState(''); const [district, setDistrict] = useState(''); const [state, setState] = useState('Kerala');
  const query = useInfiniteQuery({ queryKey: ['courts', search, type, district, state], initialPageParam: 0, queryFn: ({ pageParam }) => courtApi.list({ q: search.trim(), court_type: type, district, state: state.trim(), limit: 20, offset: pageParam }), getNextPageParam: (last) => last.offset + last.items.length < last.total ? last.offset + last.items.length : undefined });
  const courts = useMemo(() => query.data?.pages.flatMap((page) => page.items) ?? [], [query.data]);
  return <Screen title={t('courts.title')} back refreshing={query.isRefetching && !query.isFetchingNextPage} onRefresh={() => { void query.refetch(); }}>
    <View style={{ gap: 10, marginBottom: 18 }}><Button label={t('courts.add')} onPress={() => router.push('/courts/add')} /><Button label={t('courts.favorites')} variant="secondary" onPress={() => router.push('/courts/favorites')} /><TextField label={t('courts.search')} value={search} onChangeText={setSearch} /><TextField label={t('courts.state')} value={state} onChangeText={setState} autoCapitalize="words" /><ChoiceChips value={type} onChange={setType} options={[{ value: '', label: t('courts.allTypes') }, ...COURT_TYPES.map((value) => ({ value, label: t(`courts.types.${value}`) }))]} /><ChoiceChips value={district} onChange={setDistrict} options={[{ value: '', label: t('courts.allDistricts') }, ...KERALA_DISTRICTS.map((value) => ({ value, label: value }))]} /></View>
    {query.isPending ? <LoadingSkeleton /> : query.isError ? <ErrorState message={friendlyError(query.error)} retry={() => { void query.refetch(); }} /> : courts.length === 0 ? <EmptyState title={t('courts.empty')} body={t('courts.emptyDetail')} /> : <View style={{ gap: 10 }}>{courts.map((court) => <CourtCard key={court.id} court={court} onPress={() => router.push({ pathname: '/courts/[id]', params: { id: court.id } })} />)}{query.hasNextPage && <Button label={t('clients.loadMore')} variant="secondary" loading={query.isFetchingNextPage} onPress={() => { void query.fetchNextPage(); }} />}</View>}
  </Screen>;
}
