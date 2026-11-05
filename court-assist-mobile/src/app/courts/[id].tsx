import { Alert, Linking, View } from 'react-native';
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
import { courtApi } from '../../services/court-api';
import { useTheme } from '../../theme/tokens';
import { friendlyError } from '../../utils/errors';

export default function CourtDetail() {
  const { id } = useLocalSearchParams<{ id: string }>(); const { t } = useTranslation(); const theme = useTheme(); const cache = useQueryClient(); const query = useQuery({ queryKey: ['court', id], queryFn: () => courtApi.get(id), enabled: !!id }); const court = query.data;
  const toggleFavorite = async () => { if (!court) return; if (court.is_favorite) await courtApi.unfavorite(id); else await courtApi.favorite(id); await Promise.all([cache.invalidateQueries({ queryKey: ['court', id] }), cache.invalidateQueries({ queryKey: ['courts'] }), cache.invalidateQueries({ queryKey: ['courts-favorites'] })]); };
  const remove = () => Alert.alert(t('courts.delete'), t('courts.deleteConfirm'), [{ text: t('cancel'), style: 'cancel' }, { text: t('courts.delete'), style: 'destructive', onPress: async () => { await courtApi.remove(id); await cache.invalidateQueries({ queryKey: ['courts'] }); router.replace('/courts'); } }]);
  return <Screen title={court?.name ?? t('courts.title')} back refreshing={query.isRefetching} onRefresh={() => { void query.refetch(); }}>{query.isPending ? <LoadingSkeleton /> : query.isError || !court ? <ErrorState message={friendlyError(query.error)} retry={() => { void query.refetch(); }} /> : <>
    <Card><AppText style={{ fontSize: 22, fontWeight: '800' }}>{court.name}</AppText><AppText style={{ color: theme.colors.muted }}>{t(`courts.types.${court.court_type}`, court.court_type)} · {court.district}, {court.state}</AppText><AppText style={{ color: court.record_scope === 'shared' ? theme.colors.success : theme.colors.accent, fontWeight: '700', marginTop: 8 }}>{t(`courts.${court.record_scope}`)}</AppText></Card>
    <View style={{ marginTop: 14, gap: 8 }}><Button label={t(court.is_favorite ? 'courts.unfavorite' : 'courts.favorite')} onPress={() => { void toggleFavorite(); }} />{court.can_edit && <Button label={t('courts.edit')} variant="secondary" onPress={() => router.push({ pathname: '/courts/edit/[id]', params: { id } })} />}</View>
    <SectionHeader title={t('courts.address')} /><ProfileInfoCard rows={[{ label: t('courts.address'), value: court.address }, { label: t('courts.district'), value: court.district }, { label: t('courts.state'), value: court.state }, { label: t('courts.jurisdiction'), value: court.jurisdiction }]} />
    <SectionHeader title={t('clients.contact')} /><ProfileInfoCard rows={[{ label: t('courts.phone'), value: court.phone_number }, { label: t('courts.email'), value: court.email }, { label: t('courts.website'), value: court.official_website }]} />
    <View style={{ marginTop: 10, gap: 8 }}>{court.phone_number && <Button label={t('clients.call')} variant="secondary" onPress={() => { void Linking.openURL(`tel:${court.phone_number}`); }} />}{court.email && <Button label={t('clients.email')} variant="secondary" onPress={() => { void Linking.openURL(`mailto:${court.email}`); }} />}{court.official_website && <Button label={t('courts.website')} variant="secondary" onPress={() => { void Linking.openURL(court.official_website!); }} />}</View>
    {(court.notes || court.source) && <><SectionHeader title={t('courts.notes')} /><ProfileInfoCard rows={[{ label: t('courts.notes'), value: court.notes }, { label: t('courts.source'), value: court.source }]} /></>}
    {court.can_edit && <View style={{ marginTop: 22 }}><Button label={t('courts.delete')} variant="text" onPress={remove} /></View>}
  </>}</Screen>;
}
