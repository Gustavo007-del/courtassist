import { router, useLocalSearchParams } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { ClientForm } from '../../../components/clients/ClientForm';
import { ErrorState } from '../../../components/common/ErrorState';
import { LoadingSkeleton } from '../../../components/common/LoadingSkeleton';
import { Screen } from '../../../components/layout/Screen';
import { clientApi } from '../../../services/client-api';
import { useAppStore } from '../../../store/app-store';
import { friendlyError } from '../../../utils/errors';

export default function EditClient() { const { id } = useLocalSearchParams<{ id: string }>(); const { t } = useTranslation(); const cache = useQueryClient(); const query = useQuery({ queryKey: ['client', id], queryFn: () => clientApi.get(id, true), enabled: !!id }); return <Screen title={t('clients.edit')} back>{query.isPending ? <LoadingSkeleton /> : query.isError || !query.data ? <ErrorState message={friendlyError(query.error)} retry={() => { void query.refetch(); }} /> : <ClientForm initial={query.data} submitLabel={t('save')} onSubmit={async (data) => { const client = await clientApi.update(id, data); cache.setQueryData(['client', id], client); await Promise.all([cache.invalidateQueries({ queryKey: ['clients'] }), cache.invalidateQueries({ queryKey: ['dashboard'] }), cache.invalidateQueries({ queryKey: ['activities'] })]); useAppStore.getState().showToast(t('clients.updated')); router.back(); }} />}</Screen>; }
