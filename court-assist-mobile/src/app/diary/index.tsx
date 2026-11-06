import { useState } from 'react';
import { View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { ChoiceChips } from '../../components/common/ChoiceChips';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { SectionHeader } from '../../components/common/SectionHeader';
import { TextField } from '../../components/common/TextField';
import { DiaryEntryCard } from '../../components/diary/DiaryEntryCard';
import { Screen } from '../../components/layout/Screen';
import { DIARY_CATEGORIES } from '../../constants/diary';
import { caseApi } from '../../services/case-api';
import { diaryApi } from '../../services/diary-api';
import { friendlyError } from '../../utils/errors';

export default function DiaryList() {
  const { caseId } = useLocalSearchParams<{ caseId?: string }>(); const { t } = useTranslation();
  const [filterCaseId, setFilterCaseId] = useState(caseId ?? ''); const [search, setSearch] = useState(''); const [category, setCategory] = useState(''); const [fromDate, setFromDate] = useState(''); const [toDate, setToDate] = useState(''); const [flag, setFlag] = useState<'all' | 'important' | 'pinned'>('all'); const [order, setOrder] = useState<'newest' | 'oldest'>('newest'); const [offset, setOffset] = useState(0);
  const cases = useQuery({ queryKey: ['diary-case-filter'], queryFn: () => caseApi.list({ limit: 100 }) });
  const filters = { case_id: filterCaseId, q: search, category, from_date: fromDate, to_date: toDate, important: flag === 'important' ? true : undefined, pinned: flag === 'pinned' ? true : undefined, order, limit: 20, offset };
  const query = useQuery({ queryKey: ['diary', filters], queryFn: () => diaryApi.list(filters) });
  const pinned = useQuery({ queryKey: ['diary-pinned', filterCaseId], queryFn: () => diaryApi.list({ case_id: filterCaseId, pinned: true, limit: 5 }), enabled: offset === 0 && flag === 'all' });
  const reset = () => setOffset(0);
  const items = query.data?.items ?? [];
  return <Screen title={t('diary.title')} subtitle={t('diary.privateLabel')} back refreshing={query.isRefetching} onRefresh={() => { void query.refetch(); }}><Button label={t('diary.add')} onPress={() => router.push({ pathname: '/diary/add', params: { caseId: filterCaseId } })} /><View style={{ marginTop: 18 }}><AppText>{t('diary.selectCase')}</AppText><ChoiceChips value={filterCaseId} onChange={(value) => { setFilterCaseId(value); reset(); }} options={[{ value: '', label: t('diary.allCases') }, ...(cases.data?.items ?? []).map((record) => ({ value: record.id, label: `${record.case_title} · ${record.case_number}` }))]} /><TextField label={t('diary.search')} value={search} onChangeText={(value) => { setSearch(value); reset(); }} /><AppText>{t('diary.category')}</AppText><ChoiceChips value={category} onChange={(value) => { setCategory(value); reset(); }} options={[{ value: '', label: t('diary.allCategories') }, ...DIARY_CATEGORIES.map((value) => ({ value, label: t(`diary.categories.${value}`) }))]} /><TextField label={t('diary.fromDate')} value={fromDate} onChangeText={(value) => { setFromDate(value); reset(); }} /><TextField label={t('diary.toDate')} value={toDate} onChangeText={(value) => { setToDate(value); reset(); }} /><ChoiceChips value={flag} onChange={(value) => { setFlag(value); reset(); }} options={(['all', 'important', 'pinned'] as const).map((value) => ({ value, label: t(`diary.filters.${value}`) }))} /><ChoiceChips value={order} onChange={(value) => { setOrder(value); reset(); }} options={(['newest', 'oldest'] as const).map((value) => ({ value, label: t(`diary.filters.${value}`) }))} /></View>{pinned.data?.items.length ? <><SectionHeader title={t('diary.pinnedEntries')} />{pinned.data.items.map((item) => <DiaryEntryCard key={item.id} item={item} onPress={() => router.push({ pathname: '/diary/[id]', params: { id: item.id } })} />)}</> : null}<SectionHeader title={t('diary.history')} />{query.isPending ? <LoadingSkeleton /> : query.isError ? <ErrorState message={friendlyError(query.error)} retry={() => { void query.refetch(); }} /> : !items.length ? <EmptyState title={t('diary.none')} body={t('diary.noneDetail')} /> : <>{items.map((item, index) => <View key={item.id}>{(index === 0 || items[index - 1].entry_date !== item.entry_date) && <SectionHeader title={item.entry_date} />}<DiaryEntryCard item={item} onPress={() => router.push({ pathname: '/diary/[id]', params: { id: item.id } })} /></View>)}<View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}><View style={{ flex: 1 }}><Button label={t('diary.previous')} variant="secondary" onPress={() => setOffset(Math.max(0, offset - 20))} /></View><View style={{ flex: 1 }}><Button label={t('diary.next')} variant="secondary" onPress={() => setOffset(offset + 20)} /></View></View><AppText>{offset + 1}–{Math.min(offset + 20, query.data?.total ?? 0)} / {query.data?.total}</AppText></>}</Screen>;
}
