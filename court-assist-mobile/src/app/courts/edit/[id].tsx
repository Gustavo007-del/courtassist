import { router, useLocalSearchParams } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { CourtForm } from '../../../components/courts/CourtForm';
import { ErrorState } from '../../../components/common/ErrorState';
import { LoadingSkeleton } from '../../../components/common/LoadingSkeleton';
import { Screen } from '../../../components/layout/Screen';
import { courtApi } from '../../../services/court-api';
import { friendlyError } from '../../../utils/errors';

export default function EditCourt() { const { id } = useLocalSearchParams<{ id: string }>(); const { t } = useTranslation(); const cache = useQueryClient(); const query = useQuery({ queryKey: ['court', id], queryFn: () => courtApi.get(id), enabled: !!id }); return <Screen title={t('courts.edit')} back>{query.isPending ? <LoadingSkeleton /> : query.isError || !query.data ? <ErrorState message={friendlyError(query.error)} retry={() => { void query.refetch(); }} /> : <CourtForm initial={query.data} submitLabel={t('save')} onSubmit={async (data) => { const court = await courtApi.update(id, data); cache.setQueryData(['court', id], court); await cache.invalidateQueries({ queryKey: ['courts'] }); router.back(); }} />}</Screen>; }
