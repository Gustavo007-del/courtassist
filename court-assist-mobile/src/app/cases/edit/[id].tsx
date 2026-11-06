import { router, useLocalSearchParams } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { CaseForm } from '../../../components/cases/CaseForm';
import { ErrorState } from '../../../components/common/ErrorState';
import { LoadingSkeleton } from '../../../components/common/LoadingSkeleton';
import { Screen } from '../../../components/layout/Screen';
import { caseApi } from '../../../services/case-api';
import { friendlyError } from '../../../utils/errors';
export default function EditCase() { const { id } = useLocalSearchParams<{ id: string }>(); const { t } = useTranslation(); const cache = useQueryClient(); const query = useQuery({ queryKey: ['case', id], queryFn: () => caseApi.get(id, true), enabled: !!id }); return <Screen title={t('cases.edit')} back>{query.isPending ? <LoadingSkeleton /> : query.isError || !query.data ? <ErrorState message={friendlyError(query.error)} retry={() => { void query.refetch(); }} /> : query.data.is_archived ? <ErrorState message={t('cases.archiveConfirm')} retry={() => router.back()} /> : <CaseForm item={query.data} onSubmit={async (data, base) => { const updated = await caseApi.update(id, data, base); cache.setQueryData(['case', id], updated); await Promise.all([cache.invalidateQueries({ queryKey: ['cases'] }), cache.invalidateQueries({ queryKey: ['case-timeline', id] }), cache.invalidateQueries({ queryKey: ['dashboard'] })]); router.back(); }} />}</Screen>; }
