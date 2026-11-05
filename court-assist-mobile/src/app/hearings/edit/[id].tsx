import { router, useLocalSearchParams } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { ErrorState } from '../../../components/common/ErrorState';
import { LoadingSkeleton } from '../../../components/common/LoadingSkeleton';
import { HearingForm } from '../../../components/hearings/HearingForm';
import { Screen } from '../../../components/layout/Screen';
import { hearingApi } from '../../../services/hearing-api';
import { friendlyError } from '../../../utils/errors';
export default function EditHearing() { const { id } = useLocalSearchParams<{ id: string }>(); const { t } = useTranslation(); const cache = useQueryClient(); const query = useQuery({ queryKey: ['hearing', id], queryFn: () => hearingApi.get(id), enabled: !!id }); return <Screen title={t('hearings.edit')} back>{query.isPending ? <LoadingSkeleton /> : query.isError || !query.data ? <ErrorState message={friendlyError(query.error)} retry={() => { void query.refetch(); }} /> : <HearingForm item={query.data} onSubmit={async (data) => { const updated = await hearingApi.update(id, data); cache.setQueryData(['hearing', id], updated); await Promise.all([cache.invalidateQueries({ queryKey: ['calendar'] }), cache.invalidateQueries({ queryKey: ['dashboard'] })]); router.back(); }} />}</Screen>; }
