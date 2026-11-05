import { router } from 'expo-router';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { ClientForm } from '../../components/clients/ClientForm';
import { Screen } from '../../components/layout/Screen';
import { clientApi } from '../../services/client-api';
import { useAppStore } from '../../store/app-store';

export default function AddClient() { const { t } = useTranslation(); const cache = useQueryClient(); return <Screen title={t('clients.add')} back><ClientForm submitLabel={t('clients.add')} onSubmit={async (data) => { const client = await clientApi.create(data); await Promise.all([cache.invalidateQueries({ queryKey: ['clients'] }), cache.invalidateQueries({ queryKey: ['dashboard'] }), cache.invalidateQueries({ queryKey: ['activities'] })]); useAppStore.getState().showToast(t('clients.created')); router.replace({ pathname: '/clients/[id]', params: { id: client.id } }); }} /></Screen>; }
