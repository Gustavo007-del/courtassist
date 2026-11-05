import { useState } from 'react';
import { View } from 'react-native';
import { router } from 'expo-router';
import { useInfiniteQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { CaseCard } from '../../components/cases/CaseCard';
import { Button } from '../../components/common/Button';
import { ChoiceChips } from '../../components/common/ChoiceChips';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { TextField } from '../../components/common/TextField';
import { Screen } from '../../components/layout/Screen';
import { CASE_CATEGORIES } from '../../constants/cases';
import { KERALA_DISTRICTS } from '../../constants/courts';
import { caseApi, type CasePriority } from '../../services/case-api';
import { friendlyError } from '../../utils/errors';

export default function Cases() {
  const { t } = useTranslation(); const [q, setQ] = useState(''); const [category, setCategory] = useState(''); const [status, setStatus] = useState(''); const [district, setDistrict] = useState(''); const [priority, setPriority] = useState<'' | CasePriority>(''); const [sort, setSort] = useState<'updated' | 'filing' | 'alphabetical'>('updated');
  const query = useInfiniteQuery({ queryKey: ['cases', q, category, status, district, priority, sort], initialPageParam: 0, queryFn: ({ pageParam }) => caseApi.list({ q: q.trim(), category, status, district, priority, sort, limit: 20, offset: pageParam }), getNextPageParam: (last) => last.offset + last.items.length < last.total ? last.offset + last.items.length : undefined });
  const items = query.data?.pages.flatMap((page) => page.items) ?? [];
  return <Screen title={t('cases.title')} refreshing={query.isRefetching && !query.isFetchingNextPage} onRefresh={() => { void query.refetch(); }}><View style={{ gap: 8, marginBottom: 16 }}><Button label={t('cases.add')} onPress={() => router.push('/cases/add')} /><Button label={t('cases.archived')} variant="secondary" onPress={() => router.push('/cases/archived')} /><TextField label={t('cases.search')} value={q} onChangeText={setQ} /><ChoiceChips value={status} onChange={setStatus} options={['', 'Active', 'Pending', 'Stayed', 'Disposed'].map((value) => ({ value, label: value ? t(`cases.statuses.${value}`) : t('cases.all') }))} /><ChoiceChips value={category} onChange={setCategory} options={[{ value: '', label: t('cases.allTypes') }, ...CASE_CATEGORIES.map((value) => ({ value, label: t(`cases.categories.${value}`) }))]} /><ChoiceChips value={district} onChange={setDistrict} options={[{ value: '', label: t('courts.allDistricts') }, ...KERALA_DISTRICTS.map((value) => ({ value, label: value }))]} /><ChoiceChips value={priority} onChange={setPriority} options={(['', 'Normal', 'High', 'Urgent'] as const).map((value) => ({ value, label: value ? t(`cases.priorities.${value}`) : t('cases.allPriorities') }))} /><ChoiceChips value={sort} onChange={setSort} options={(['updated', 'filing', 'alphabetical'] as const).map((value) => ({ value, label: t(`cases.sort.${value}`) }))} /></View>
    {query.isPending ? <LoadingSkeleton /> : query.isError ? <ErrorState message={friendlyError(query.error)} retry={() => { void query.refetch(); }} /> : items.length === 0 ? <><EmptyState title={t('cases.empty')} body={t('cases.emptyDetail')} /><Button label={t('cases.add')} variant="secondary" onPress={() => router.push('/cases/add')} /></> : <View style={{ gap: 10 }}>{items.map((item) => <CaseCard key={item.id} item={item} onPress={() => router.push({ pathname: '/cases/[id]', params: { id: item.id } })} />)}{query.hasNextPage && <Button label={t('clients.loadMore')} variant="secondary" loading={query.isFetchingNextPage} onPress={() => { void query.fetchNextPage(); }} />}</View>}
  </Screen>;
}
