import { View } from 'react-native';
import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { CourtCard } from '../../components/courts/CourtCard';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { Screen } from '../../components/layout/Screen';
import { courtApi } from '../../services/court-api';
import { friendlyError } from '../../utils/errors';

export default function FavoriteCourts() { const { t } = useTranslation(); const query = useQuery({ queryKey: ['courts-favorites'], queryFn: courtApi.favorites }); return <Screen title={t('courts.favorites')} back refreshing={query.isRefetching} onRefresh={() => { void query.refetch(); }}>{query.isPending ? <LoadingSkeleton /> : query.isError ? <ErrorState message={friendlyError(query.error)} retry={() => { void query.refetch(); }} /> : !query.data?.items.length ? <EmptyState title={t('courts.empty')} body={t('courts.emptyDetail')} /> : <View style={{ gap: 10 }}>{query.data.items.map((court) => <CourtCard key={court.id} court={court} onPress={() => router.push({ pathname: '/courts/[id]', params: { id: court.id } })} />)}</View>}</Screen>; }
