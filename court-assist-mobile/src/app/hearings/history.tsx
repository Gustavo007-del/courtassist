import { useState } from 'react';
import { View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { ChoiceChips } from '../../components/common/ChoiceChips';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { HearingCard } from '../../components/hearings/HearingCard';
import { Screen } from '../../components/layout/Screen';
import { HEARING_STATUSES } from '../../constants/hearings';
import { hearingApi } from '../../services/hearing-api';
import { friendlyError } from '../../utils/errors';
export default function HearingHistory() { const { caseId } = useLocalSearchParams<{ caseId: string }>(); const { t } = useTranslation(); const [status, setStatus] = useState(''); const query = useQuery({ queryKey: ['case-hearings', caseId, status], queryFn: () => hearingApi.caseHistory(caseId, status), enabled: !!caseId }); return <Screen title={t('hearings.history')} back><ChoiceChips value={status} onChange={setStatus} options={[{ value: '', label: t('hearings.allStatuses') }, ...HEARING_STATUSES.map((value) => ({ value, label: t(`hearings.statuses.${value}`) }))]} />{query.isPending ? <LoadingSkeleton /> : query.isError ? <ErrorState message={friendlyError(query.error)} retry={() => { void query.refetch(); }} /> : !query.data?.items.length ? <EmptyState title={t('hearings.none')} body={t('hearings.noneDetail')} /> : <View style={{ gap: 9 }}>{query.data.items.map((item) => <HearingCard key={item.id} item={item} onPress={() => router.push({ pathname: '/hearings/[id]', params: { id: item.id } })} />)}</View>}</Screen>; }
