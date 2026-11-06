import { router, useLocalSearchParams } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { ErrorState } from '../../../components/common/ErrorState';
import { LoadingSkeleton } from '../../../components/common/LoadingSkeleton';
import { DiaryEntryForm } from '../../../components/diary/DiaryEntryForm';
import { Screen } from '../../../components/layout/Screen';
import { diaryApi } from '../../../services/diary-api';
import { friendlyError } from '../../../utils/errors';
export default function EditDiary() { const { id } = useLocalSearchParams<{ id: string }>(); const { t } = useTranslation(); const cache = useQueryClient(); const query = useQuery({ queryKey: ['diary-entry', id], queryFn: () => diaryApi.get(id), enabled: !!id }); return <Screen title={t('diary.edit')} back>{query.isPending ? <LoadingSkeleton /> : query.isError || !query.data ? <ErrorState message={friendlyError(query.error)} retry={() => { void query.refetch(); }} /> : <DiaryEntryForm item={query.data} onSubmit={async (data, base) => { const updated = await diaryApi.update(id, data, base); cache.setQueryData(['diary-entry', id], updated); await Promise.all([cache.invalidateQueries({ queryKey: ['diary'] }), cache.invalidateQueries({ queryKey: ['case-diary'] }), cache.invalidateQueries({ queryKey: ['case-timeline'] })]); router.back(); }} />}</Screen>; }
