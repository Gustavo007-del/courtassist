import { Alert, Linking, View } from 'react-native';
import * as Clipboard from 'expo-clipboard';
import { router, useLocalSearchParams } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { SectionHeader } from '../../components/common/SectionHeader';
import { Screen } from '../../components/layout/Screen';
import { ProfileInfoCard } from '../../components/profile/ProfileInfoCard';
import { clientApi } from '../../services/client-api';
import { caseApi } from '../../services/case-api';
import { useAppStore } from '../../store/app-store';
import { useTheme } from '../../theme/tokens';
import { friendlyError } from '../../utils/errors';

export default function ClientDetail() {
  const { id } = useLocalSearchParams<{ id: string }>(); const { t } = useTranslation(); const theme = useTheme(); const cache = useQueryClient();
  const query = useQuery({ queryKey: ['client', id], queryFn: () => clientApi.get(id, true), enabled: !!id }); const client = query.data;
  const cases = useQuery({ queryKey: ['cases', 'client', id], queryFn: () => caseApi.list({ client_id: id, limit: 20 }), enabled: !!id });
  const refresh = async () => { await Promise.all([cache.invalidateQueries({ queryKey: ['client', id] }), cache.invalidateQueries({ queryKey: ['clients'] }), cache.invalidateQueries({ queryKey: ['dashboard'] }), cache.invalidateQueries({ queryKey: ['activities'] })]); };
  const archive = () => Alert.alert(t('clients.archive'), t('clients.archiveConfirm'), [{ text: t('cancel'), style: 'cancel' }, { text: t('clients.archive'), onPress: async () => { await clientApi.archive(id); await refresh(); } }]);
  const remove = () => Alert.alert(t('clients.delete'), t('clients.deleteConfirm'), [{ text: t('cancel'), style: 'cancel' }, { text: t('clients.delete'), style: 'destructive', onPress: async () => { await clientApi.remove(id); await Promise.all([cache.invalidateQueries({ queryKey: ['clients'] }), cache.invalidateQueries({ queryKey: ['dashboard'] }), cache.invalidateQueries({ queryKey: ['activities'] })]); router.replace('/clients'); } }]);
  return <Screen title={client?.full_name ?? t('clients.details')} back refreshing={query.isRefetching} onRefresh={() => { void query.refetch(); }}>
    {query.isPending ? <LoadingSkeleton /> : query.isError || !client ? <ErrorState message={friendlyError(query.error)} retry={() => { void query.refetch(); }} /> : <>
      <Card style={{ gap: 5 }}><AppText style={{ fontSize: 23, fontWeight: '800' }}>{client.full_name}</AppText>{client.organization_name && <AppText style={{ color: theme.colors.muted }}>{client.organization_name}</AppText>}<AppText style={{ color: client.is_archived ? theme.colors.accent : theme.colors.success, fontWeight: '700' }}>{t(client.is_archived ? 'clients.archived' : 'clients.active')}</AppText></Card>
      <View style={{ marginTop: 14, gap: 8 }}><Button label={t('clients.edit')} onPress={() => router.push({ pathname: '/clients/edit/[id]', params: { id } })} /><Button label={t('clients.notes')} variant="secondary" onPress={() => router.push({ pathname: '/clients/[id]/notes', params: { id } })} /><Button label={t('clients.interactions')} variant="secondary" onPress={() => router.push({ pathname: '/clients/[id]/interactions', params: { id } })} /></View>
      <SectionHeader title={t('clients.contact')} /><ProfileInfoCard rows={[{ label: t('profile2.phoneNumber'), value: client.phone_number }, { label: t('clients.alternatePhone'), value: client.alternate_phone }, { label: t('auth.email'), value: client.email }]} />
      <View style={{ marginTop: 10, gap: 8 }}><Button label={t('clients.call')} variant="secondary" onPress={() => { void Linking.openURL(`tel:${client.phone_number}`); }} />{client.email && <Button label={t('clients.email')} variant="secondary" onPress={() => { void Linking.openURL(`mailto:${client.email}`); }} />}<Button label={t('clients.copyPhone')} variant="text" onPress={() => { void Clipboard.setStringAsync(client.phone_number).then(() => useAppStore.getState().showToast(t('clients.copied'))); }} /></View>
      <SectionHeader title={t('clients.address')} /><ProfileInfoCard rows={[{ label: t('profile2.address'), value: client.address }, { label: t('profile2.city'), value: client.city }, { label: t('profile2.district'), value: client.district }, { label: t('profile2.state'), value: client.state }, { label: t('clients.postalCode'), value: client.postal_code }]} />
      <SectionHeader title={t('clients.details')} /><ProfileInfoCard rows={[{ label: t('clients.type'), value: t(`clients.${client.client_type}`) }, { label: t('clients.occupation'), value: client.occupation }]} />
      <SectionHeader title={t('clients.privateNotes')} /><Card><AppText style={{ color: client.notes ? theme.colors.text : theme.colors.muted }}>{client.notes || t('clients.noNotes')}</AppText></Card>
      <SectionHeader title={t('clients.cases')} /><Card><AppText style={{ color: theme.colors.muted }}>{client.associated_case_count} {t('clients.cases')}</AppText>{cases.data?.items.map((item) => <Button key={item.id} label={`${item.case_number} · ${item.case_title}`} variant="text" onPress={() => router.push({ pathname: '/cases/[id]', params: { id: item.id } })} />)}</Card>
      <View style={{ marginTop: 22, gap: 8 }}>{client.is_archived ? <Button label={t('clients.restore')} variant="secondary" onPress={() => { void clientApi.restore(id).then(refresh); }} /> : <Button label={t('clients.archive')} variant="secondary" onPress={archive} />}<Button label={t('clients.delete')} variant="text" onPress={remove} /></View>
    </>}
  </Screen>;
}
