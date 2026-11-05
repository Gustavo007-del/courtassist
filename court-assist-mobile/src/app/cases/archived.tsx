import { View } from 'react-native';
import { router } from 'expo-router';
import { useInfiniteQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { CaseCard } from '../../components/cases/CaseCard';
import { Button } from '../../components/common/Button';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { Screen } from '../../components/layout/Screen';
import { caseApi } from '../../services/case-api';
import { friendlyError } from '../../utils/errors';
export default function ArchivedCases() { const { t } = useTranslation(); const query = useInfiniteQuery({ queryKey: ['cases', 'archived'], initialPageParam: 0, queryFn: ({ pageParam }) => caseApi.list({ archived: true, limit: 20, offset: pageParam }), getNextPageParam: (last) => last.offset + last.items.length < last.total ? last.offset + last.items.length : undefined }); const items = query.data?.pages.flatMap((page) => page.items) ?? []; return <Screen title={t('cases.archived')} back refreshing={query.isRefetching} onRefresh={() => { void query.refetch(); }}>{query.isPending ? <LoadingSkeleton /> : query.isError ? <ErrorState message={friendlyError(query.error)} retry={() => { void query.refetch(); }} /> : !items.length ? <EmptyState title={t('cases.empty')} body={t('cases.noArchived')} /> : <View style={{ gap: 10 }}>{items.map((item) => <CaseCard key={item.id} item={item} onPress={() => router.push({ pathname: '/cases/[id]', params: { id: item.id } })} />)}{query.hasNextPage && <Button label={t('clients.loadMore')} loading={query.isFetchingNextPage} onPress={() => { void query.fetchNextPage(); }} />}</View>}</Screen>; }
