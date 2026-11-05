import { router } from 'expo-router';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { CourtForm } from '../../components/courts/CourtForm';
import { Screen } from '../../components/layout/Screen';
import { courtApi } from '../../services/court-api';
import { useAppStore } from '../../store/app-store';

export default function AddCourt() { const { t } = useTranslation(); const cache = useQueryClient(); return <Screen title={t('courts.add')} back><CourtForm submitLabel={t('courts.add')} onSubmit={async (data) => { const court = await courtApi.create(data); await Promise.all([cache.invalidateQueries({ queryKey: ['courts'] }), cache.invalidateQueries({ queryKey: ['dashboard'] }), cache.invalidateQueries({ queryKey: ['activities'] })]); useAppStore.getState().showToast(t('courts.created')); router.replace({ pathname: '/courts/[id]', params: { id: court.id } }); }} /></Screen>; }
