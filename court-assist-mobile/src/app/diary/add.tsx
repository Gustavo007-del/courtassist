import { router, useLocalSearchParams } from 'expo-router';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { DiaryEntryForm } from '../../components/diary/DiaryEntryForm';
import { Screen } from '../../components/layout/Screen';
import { diaryApi } from '../../services/diary-api';
export default function AddDiary() { const { caseId, hearingId, date, type } = useLocalSearchParams<{ caseId?: string; hearingId?: string; date?: string; type?: string }>(); const { t } = useTranslation(); const cache = useQueryClient(); return <Screen title={t('diary.add')} subtitle={t('diary.privateLabel')} back><DiaryEntryForm initialCaseId={caseId} initialHearingId={hearingId} initialDate={date} initialType={type} onSubmit={async (data) => { const entry = await diaryApi.create(data); await Promise.all([cache.invalidateQueries({ queryKey: ['diary'] }), cache.invalidateQueries({ queryKey: ['case-diary'] }), cache.invalidateQueries({ queryKey: ['hearing-diary'] }), cache.invalidateQueries({ queryKey: ['case-timeline'] })]); router.replace({ pathname: '/diary/[id]', params: { id: entry.id } }); }} /></Screen>; }
