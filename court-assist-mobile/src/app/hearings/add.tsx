import { router, useLocalSearchParams } from 'expo-router';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { HearingForm } from '../../components/hearings/HearingForm';
import { Screen } from '../../components/layout/Screen';
import { hearingApi } from '../../services/hearing-api';
export default function AddHearing() { const { caseId } = useLocalSearchParams<{ caseId?: string }>(); const { t } = useTranslation(); const cache = useQueryClient(); return <Screen title={t('hearings.schedule')} back><HearingForm initialCaseId={caseId} onSubmit={async (data) => { const item = await hearingApi.create(data); await Promise.all([cache.invalidateQueries({ queryKey: ['calendar'] }), cache.invalidateQueries({ queryKey: ['dashboard'] }), cache.invalidateQueries({ queryKey: ['case-timeline', data.case_id] })]); router.replace({ pathname: '/hearings/[id]', params: { id: item.id } }); }} /></Screen>; }
