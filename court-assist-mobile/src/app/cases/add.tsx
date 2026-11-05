import { router } from 'expo-router';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { CaseForm } from '../../components/cases/CaseForm';
import { Screen } from '../../components/layout/Screen';
import { caseApi } from '../../services/case-api';
import { useAppStore } from '../../store/app-store';
export default function AddCase() { const { t } = useTranslation(); const cache = useQueryClient(); return <Screen title={t('cases.add')} back><CaseForm onSubmit={async (data) => { const item = await caseApi.create(data); await Promise.all([cache.invalidateQueries({ queryKey: ['cases'] }), cache.invalidateQueries({ queryKey: ['clients'] }), cache.invalidateQueries({ queryKey: ['dashboard'] })]); useAppStore.getState().showToast(t('cases.created')); router.replace({ pathname: '/cases/[id]', params: { id: item.id } }); }} /></Screen>; }
