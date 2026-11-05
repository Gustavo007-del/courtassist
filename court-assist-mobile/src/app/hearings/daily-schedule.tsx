import { View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { AppText } from '../../components/common/AppText';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { SectionHeader } from '../../components/common/SectionHeader';
import { Notice } from '../../components/common/Notice';
import { HearingCard } from '../../components/hearings/HearingCard';
import { Screen } from '../../components/layout/Screen';
import { hearingApi } from '../../services/hearing-api';
import { friendlyError } from '../../utils/errors';
export default function DailySchedule() { const { day = new Date().toISOString().slice(0, 10) } = useLocalSearchParams<{ day?: string }>(); const { t } = useTranslation(); const query = useQuery({ queryKey: ['calendar-day', day], queryFn: () => hearingApi.day(day) }); const conflicts = useQuery({ queryKey: ['calendar-day-conflicts', day], queryFn: () => hearingApi.dayConflicts(day) }); const items = query.data?.items ?? []; const groups = Object.groupBy(items, (item) => item.court_name || t('cases.noCourt')); return <Screen title={t('hearings.dailySchedule')} subtitle={day} back>{query.isPending ? <LoadingSkeleton /> : query.isError ? <ErrorState message={friendlyError(query.error)} retry={() => { void query.refetch(); }} /> : !items.length ? <EmptyState title={t('hearings.none')} body={t('hearings.noneDetail')} /> : <><AppText>{t('hearings.total')}: {query.data?.total}</AppText>{conflicts.data?.length ? <Notice message={`${t('hearings.potentialConflicts')}: ${conflicts.data.length}`} /> : null}{Object.entries(groups).map(([court, entries]) => <View key={court}><SectionHeader title={court} />{entries?.filter((item) => item.hearing_time).map((item) => <HearingCard key={item.id} item={item} onPress={() => router.push({ pathname: '/hearings/[id]', params: { id: item.id } })} />)}{entries?.some((item) => !item.hearing_time) && <SectionHeader title={t('hearings.timeUnknown')} />}{entries?.filter((item) => !item.hearing_time).map((item) => <HearingCard key={item.id} item={item} onPress={() => router.push({ pathname: '/hearings/[id]', params: { id: item.id } })} />)}</View>)}</>}</Screen>; }
